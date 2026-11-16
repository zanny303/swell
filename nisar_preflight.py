"""Inspect a real NISAR GUNW granule and export raw phase/coherence for GIS.
Not a scientific displacement inversion; no assumed wavelength, incidence or correction signs.
"""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import h5py
import rasterio as rio
from rasterio.transform import from_origin

def inspect_export(path,out,maturity,coherence_min=.3):
    path=Path(path);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if maturity not in ('beta','provisional','validated','unknown'):raise ValueError('Declare documented collection maturity')
    if not 0<=coherence_min<=1:raise ValueError('Coherence threshold 0–1')
    with h5py.File(path,'r') as f:
        datasets=[];f.visititems(lambda name,obj:datasets.append('/'+name) if isinstance(obj,h5py.Dataset) else None)
        candidates=[k for k in datasets if '/GUNW/grids/frequencyA/unwrappedInterferogram/' in k and k.endswith('/unwrappedPhase') and k.split('/')[-2] in ('HH','VV')]
        if not candidates:raise ValueError('No recognized frequency A HH/VV unwrapped phase; inspect granule via existing swell.ingest inspect')
        if len(candidates)!=1:raise ValueError('Ambiguous phase polarization; choose one unambiguous granule')
        phase=candidates[0];grp=phase.rsplit('/',1)[0];parent=grp.rsplit('/',1)[0];a=f[phase]
        if len(a.shape)!=2 or np.prod(a.shape)>100_000_000:raise ValueError('Unsupported phase shape or size')
        def field(name,shape=None):
            hits=[k for k in (grp+'/'+name,parent+'/'+name) if k in f and (shape is None or f[k].shape==shape)]
            if len(hits)!=1:raise ValueError('Missing/ambiguous coordinate or quality field: '+name)
            return f[hits[0]]
        y=np.asarray(field('yCoordinates',(a.shape[0],)),dtype=float);x=np.asarray(field('xCoordinates',(a.shape[1],)),dtype=float);epsg=int(np.asarray(field('projection')).item())
        if min(len(x),len(y))<2 or not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('Invalid geocoding axes')
        dx,dy=np.diff(x),np.diff(y)
        if not np.allclose(dx,dx[0],rtol=1e-6,atol=1e-7) or not np.allclose(dy,dy[0],rtol=1e-6,atol=1e-7) or dx[0]==0 or dy[0]==0:raise ValueError('Irregular coordinate axes')
        crs=rio.crs.CRS.from_epsg(epsg)
        if not crs.is_projected:raise ValueError('Expected a projected NISAR raster')
        def read(ds):
            b=ds[:].astype('float32');fill=ds.attrs.get('_FillValue');
            if fill is not None:b[b==fill]=np.nan
            return b
        phi=read(a);coh=read(field('coherenceMagnitude',a.shape));cc=read(field('connectedComponents',a.shape));good=np.isfinite(phi)&np.isfinite(coh)&(coh>=coherence_min)&(coh<=1)&np.isfinite(cc)&(cc>0)&(cc<255)
        if not good.any():raise ValueError('No valid coherent connected pixels')
        profile={'driver':'GTiff','height':a.shape[0],'width':a.shape[1],'count':1,'dtype':'float32','nodata':float('nan'),'crs':crs,'transform':from_origin(float(x.min()-abs(dx[0])/2),float(y.max()+abs(dy[0])/2),float(abs(dx[0])),float(abs(dy[0]))),'compress':'deflate'}
        def save(name,v,units):
            if dx[0]<0:v=v[:,::-1]
            if dy[0]>0:v=v[::-1]
            with rio.open(out/name,'w',**profile) as dst:dst.write(v.astype('float32'),1);dst.set_band_unit(1,units)
        save('phase-raw-masked.tif',np.where(good,phi,np.nan),'rad');save('coherence.tif',np.where((coh>=0)&(coh<=1),coh,np.nan),'1');save('components.tif',np.where(good,cc,np.nan),'1')
        def metadata(suffix):
            hits=[k for k in datasets if k.startswith('/science/') and '/identification/' in k and k.endswith('/'+suffix)]
            if len(hits)!=1:return None
            v=f[hits[0]][()];return v.decode(errors='replace') if isinstance(v,bytes) else str(v)
        record={'source_file':path.name,'maturity_user_declared':maturity,'polarization':grp.split('/')[-1],'phase_path':phase,'crs':str(crs),'posting_m':[float(abs(dx[0])),float(abs(dy[0]))],'reference_utc':metadata('referenceZeroDopplerStartTime'),'secondary_utc':metadata('secondaryZeroDopplerStartTime'),'coherence_min':coherence_min,'valid_fraction':float(good.mean()),'corrections_applied':[],'science_approved':False,'warning':'Raw phase with quality mask, NOT vertical displacement. No ionosphere/troposphere/tide correction applied. Connected-component phase references can differ. Beta products are for familiarization; provisional/validated status and calibration must be verified independently.'}
    with path.open('rb') as stream:record['sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
    (out/'preflight.json').write_text(json.dumps(record,indent=2));return record
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--out',default='nisar-preflight');p.add_argument('--maturity',choices=['beta','provisional','validated','unknown'],default='unknown');p.add_argument('--coherence',type=float,default=.3);a=p.parse_args();print(json.dumps(inspect_export(a.file,a.out,a.maturity,a.coherence),indent=2))
