"""Read cached NISAR granules; never replace the published study. Strict registration and component-aware raw-phase audit."""
import argparse, hashlib, json, re
from pathlib import Path
import numpy as np
from pyproj import Transformer
from science_assurance import plain, finite, sha

def geometry(x,y,n,epsg):
    x,y=np.asarray(x,float),np.asarray(y,float)
    if min(len(x),len(y))<n or not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('Insufficient valid projected axes')
    dx,dy=float(np.diff(x)[0]),float(np.diff(y)[0])
    if dx<=0 or dy>=0 or not np.allclose(np.diff(x),dx,atol=1e-6,rtol=0) or not np.allclose(np.diff(y),dy,atol=1e-6,rtol=0):raise ValueError('Axes must be regularly spaced west-east and north-south')
    h,w=len(y)//n,len(x)//n;bx,by=dx*w,dy*h;left=x[0]-dx/2;top=y[0]-dy/2
    rr,cc=np.indices((n,n));tx=left+(cc+.5)*bx;ty=top+(rr+.5)*by;inv=Transformer.from_crs(epsg,4326,always_xy=True);lon,lat=inv.transform(tx,ty)
    return {'epsg':int(epsg),'transform':[bx,0,float(left),0,by,float(top)],'lat':lat.tolist(),'lon':lon.tolist(),'trimmed_native_rows':len(y)-n*h,'trimmed_native_cols':len(x)-n*w,'native_spacing_m':[dx,abs(dy)],'analysis_spacing_m':[bx,abs(by)],'source_shape':[len(y),len(x)],'n':n}

def assert_aligned(a,b):
    if a[0]!=b[0] or any(x.shape!=y.shape or not np.allclose(x,y,atol=1e-6,rtol=0) for x,y in zip(a[1:],b[1:])):raise ValueError('Projected axes or CRS differ; same array shape is not alignment. No audit output written.')

def aggregate(phase,coh,cc,n,min_coh=.30):
    """Retain single-component blocks with common valid support. No mixing across positive component IDs."""
    H,W=phase.shape;h,w=H//n,W//n
    if min(h,w)<1:raise ValueError('Grid too small')
    p=np.full((n,n),np.nan);q=p.copy();comp=np.zeros((n,n),np.int64);support=np.zeros((n,n));mixed=0
    for r in range(n):
        for c in range(n):
            sl=np.s_[r*h:(r+1)*h,c*w:(c+1)*w];a,b,d=phase[sl],coh[sl],cc[sl];valid=np.isfinite(a)&np.isfinite(b)&(b>=min_coh)&(b<=1)&np.isfinite(d)&(d>0)&(d<65535)&(d==np.floor(d));ids=np.unique(d[valid]);support[r,c]=valid.mean()
            if len(ids)>1:mixed+=1;continue
            if len(ids)==1 and support[r,c]>=.30:p[r,c]=a[valid].mean();q[r,c]=b[valid].mean();comp[r,c]=int(ids[0])
    return p,q,comp,support,mixed

def anchored(phase,comp,ref):
    # Only reference connected components with at least 5 reference cells. No mixing of component offsets.
    result=np.full(phase.shape,np.nan);counts={}
    for k in np.unique(comp):
        if k<=0:continue
        hit=(comp==k)&ref&np.isfinite(phase);counts[int(k)]=int(hit.sum())
        if hit.sum()>=5:result[comp==k]=phase[comp==k]-np.median(phase[hit])
    return result,counts

def read_granule(path,box,layout):
    import h5py
    from swell import ingest
    with h5py.File(path,'r') as f:
        x=np.asarray(f[layout['x']][:],float);y=np.asarray(f[layout['y']][:],float);epsg=int(np.asarray(f[layout['epsg']]))
        # Reproduce legacy crop exactly, to audit coordinates of existing cells.
        tr=Transformer.from_crs(4326,epsg,always_xy=True);(x0,x1),(y0,y1)=tr.transform([box[0],box[2]],[box[1],box[3]])
        j=np.where((x>=min(x0,x1))&(x<=max(x0,x1)))[0];i=np.where((y>=min(y0,y1))&(y<=max(y0,y1)))[0]
        if min(len(i),len(j))<8:raise ValueError('No matching crop')
        sl=np.s_[i.min():i.max()+1,j.min():j.max()+1];x=x[sl[1]];y=y[sl[0]]
        p,q,c=(np.asarray(f[layout[k]][sl],float) for k in ('phase','coh','cc'))
        for key,arr in [('phase',p),('coh',q),('cc',c)]:
            ds=f[layout[key]];fill=ds.attrs.get('_FillValue')
            if fill is None and key=='cc' and np.issubdtype(ds.dtype,np.unsignedinteger):fill=np.iinfo(ds.dtype).max
            if fill is not None:arr[arr==float(np.asarray(fill).reshape(-1)[0])]=np.nan
        corrections=[];iono=None
        for k in ingest._all_datasets(f):
            low=k.lower()
            if any(v in low for v in ('phasescreen','solidearthtide','losunitvector','incidenceangle','centerfrequency')):
                d=f[k];units=d.attrs.get('units','not retained');corrections.append({'path':k,'shape':list(d.shape),'units':str(units)})
        if layout.get('iono') in f and f[layout['iono']].shape==f[layout['phase']].shape:
            iono=np.asarray(f[layout['iono']][sl],float)
        dates=[]
        for key in ('referenceZeroDopplerStartTime','secondaryZeroDopplerStartTime'):
            k='/science/LSAR/identification/'+key;v=f[k][()] if k in f else None;dates.append(v.decode()[:10] if isinstance(v,bytes) else str(v)[:10] if v is not None else None)
        if y[0]<y[-1]:y=y[::-1];p,q,c=p[::-1],q[::-1],c[::-1];iono=iono[::-1] if iono is not None else None
        if x[0]>x[-1]:x=x[::-1];p,q,c=p[:,::-1],q[:,::-1],c[:,::-1];iono=iono[:,::-1] if iono is not None else None
        return (epsg,x,y),p,q,c,iono,corrections,dates

def audit(root,gunw_dir=None):
    import external_evidence as ee
    from real_site import detect_layout
    s,dates,key=ee.active(root);prov=json.loads((root/'out/real_site_provenance.json').read_text());proc=json.loads((root/'out/provenance.json').read_text());site=prov['site'];n=int(s['n']);records=prov['steps']['radar']['pairs'];folder=Path(gunw_dir) if gunw_dir else root/'data'/site/'gunw';names=[x['name'] for x in records]
    if any(Path(k).name!=k for k in names):raise ValueError('Unsafe granule name')
    files=[folder/k for k in names];ref=np.asarray(s['reference'],bool);first=None;results=[];previous=None
    if [x.get('granule') for x in proc.get('correction_budget',[])]!=names:raise ValueError('Legacy processing granule names/order do not match active manifest; no coordinate binding.')
    with np.load(root/'out'/f'{site}.npz',allow_pickle=False) as z:
        old=np.asarray(s['observed_los'],float);old[old==-9999]=np.nan
        if not np.array_equal(z['pass_days'],s['pass_days']) or not np.allclose(z['bbox'],s['bbox'],atol=1e-6,rtol=0) or not np.allclose(z['los'],old,atol=.051,rtol=0,equal_nan=True) or not np.array_equal(z['ref'],ref):raise ValueError('Cached NPZ does not match published study; no coordinate binding.')
    # Use the actual original named files, check recorded date metadata where retained.
    if not all(p.is_file() for p in files):raise ValueError('Missing named cached granules; preserve active study. '+str(folder))
    for f,rec in zip(files,records):
        layout=detect_layout(f);axes,p,q,c,iono,corr,actual=read_granule(f,proc['requested_bbox'],layout)
        if any(v is not None and v!=rec[k] for v,k in zip(actual,('ref','sec'))):raise ValueError('Granule metadata date mismatch')
        if first is None:first=axes
        else:assert_aligned(first,axes)
        g=geometry(axes[1],axes[2],n,axes[0]);raw,coh,comp,support,mixed=aggregate(p,q,c,n);baseline,counts=anchored(raw,comp,ref)
        # Separate raw phase from legacy-sign ionosphere sensitivity; not claim physically verified sign/units.
        if iono is not None:
            # common support for paired comparison so change cannot arise from missing pixels
            common=np.isfinite(iono);pr,_,cr,_,_=aggregate(np.where(common,p,np.nan),q,c,n);ir,_,ic,_,_=aggregate(p-iono,q,c,n);a,_=anchored(pr,cr,ref);b,_=anchored(ir,ic,ref);valid=np.isfinite(a)&np.isfinite(b);iono_rms=float(np.sqrt(np.mean((a[valid]-b[valid])**2))) if valid.any() else None
        else:iono_rms=None
        with f.open('rb') as stream:
            h=hashlib.sha256()
            for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
        high,_=anchored(raw,comp,ref&(coh>=.5));common=np.isfinite(baseline)&np.isfinite(high);ref_rms=float(np.sqrt(np.mean((baseline[common]-high[common])**2))) if common.any() else None
        strict,_,strict_comp,_,_=aggregate(p,q,c,n,.5);strict_ref,_=anchored(strict,strict_comp,ref)
        results.append({'reference_subset_sensitivity_rad_rms':ref_rms,'reference_sensitivity_common_cells':int(common.sum()),'threshold_0_5_valid_blocks':int(np.isfinite(strict_ref).sum()),'granule':f.name,'sha256':h.hexdigest(),'pair':[rec['ref'],rec['sec']],'metadata_dates':actual,'mixed_blocks_withheld':mixed,'component_reference_counts':counts,'valid_component_referenced_blocks':int(np.isfinite(baseline).sum()),'available_correction_geometry_layers':corr,'iono_legacy_sign_sensitivity_rad_rms':iono_rms})
        previous=(baseline,coh,comp,support,raw)
    # Legacy bounding box cross-check, not assuming all provenance is authentic.
    epsg,x,y=first;inv=Transformer.from_crs(epsg,4326,always_xy=True);lo,la=inv.transform([x.min(),x.max(),x.min(),x.max()],[y.min(),y.min(),y.max(),y.max()]);bbox=[min(lo),min(la),max(lo),max(la)]
    if not np.allclose(bbox,s['bbox'],atol=1e-6,rtol=0):raise ValueError('Legacy dataset bounds mismatch; cannot bind geometry to active grid')
    a,b,c,d,e=previous
    output={'version':'radar-assurance-1.0','site_hash':key,'site':s['name'],'geometry':g,'granules':results,'latest_pair':{'component_referenced_raw_phase_rad':finite(a),'common_support_coherence':finite(b),'component_id':c.tolist(),'valid_support_fraction':d.tolist(),'raw_phase_rad':finite(e)},'phase_closure':'Not tested: selected nearest-neighbor chain has no redundant cycles','limitations':'Raw phase in radians, not displacement. Component median reference assumes reference stability; no deramp or full correction geometry validation. Existing published LOS not overwritten. Granule names and cached subset hashes are not original provider signatures.'}
    dest=root/'out'/f'radar-assurance-{key}.json';tmp=dest.with_suffix('.tmp');tmp.write_text(plain(output),encoding='utf-8');tmp.replace(dest);print('Saved',dest);return output

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',default='.');p.add_argument('--gunw-dir');a=p.parse_args();audit(Path(a.project).resolve(),a.gunw_dir)
