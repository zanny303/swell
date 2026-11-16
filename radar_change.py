"""NISAR GCOV location-window change screening, not flood classification.
Reads native L2 gamma0 power, excludes invalid mask/looks, refuses mismatched grids.
"""
import argparse, datetime, hashlib, json, re
from pathlib import Path
import h5py
import numpy as np
import rasterio as rio
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

def sha(p):
    with open(p,'rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def identity(p):
    a=Path(p).stem.split('_')
    if len(a)<15 or a[0]!='NISAR' or a[1]!='L2' or a[3]!='GCOV': raise ValueError('Expected official NISAR L2 GCOV filename')
    t=datetime.datetime.strptime(a[11],'%Y%m%dT%H%M%S').replace(tzinfo=datetime.timezone.utc)
    return tuple(a[i] for i in (1,3,5,6,7,8,9,10,13,14)),t

def subset(path,bbox,frequency,pol,min_looks):
    with h5py.File(path,'r') as f:
        g=f[f'/science/LSAR/GCOV/grids/frequency{frequency}'];ds=g[pol]
        x=np.asarray(g['xCoordinates'],float); y=np.asarray(g['yCoordinates'],float); epsg=int(g['projection'][()]); crs=rio.crs.CRS.from_epsg(epsg)
        if len(x)<2 or len(y)<2 or not crs.is_projected or ds.shape!=(len(y),len(x)) or not np.issubdtype(ds.dtype,np.floating):raise ValueError('Unsupported grid or intensity data')
        if not (np.isfinite(x).all() and np.isfinite(y).all()):raise ValueError('Invalid axes')
        dx=np.diff(x);dy=np.diff(y)
        if dx[0]<=0 or dy[0]>=0 or not np.allclose(dx,dx[0],rtol=1e-7) or not np.allclose(dy,dy[0],rtol=1e-7):raise ValueError('Expected regular eastward / southward axes')
        w,s,e,n=transform_bounds(4326,crs,*bbox,densify_pts=21)
        cols=np.flatnonzero((x>=w)&(x<=e));rows=np.flatnonzero((y>=s)&(y<=n))
        if not len(cols) or not len(rows) or len(cols)*len(rows)>4_000_000:raise ValueError('Empty or oversized AOI')
        sl=(slice(rows[0],rows[-1]+1),slice(cols[0],cols[-1]+1))
        def read(name):
            d=g[name];a=np.asarray(d[sl],float);fill=d.attrs.get('_FillValue');
            if fill is not None:a[a==fill]=np.nan
            return a
        v=read(pol);mask=read('mask');looks=read('numberOfLooks');good=np.isfinite(v)&(v>0)&np.isfinite(mask)&(mask>0)&(mask<255)&np.isfinite(looks)&(looks>=min_looks)
        return x[cols],y[rows],epsg,float(dx[0]),float(-dy[0]),np.where(good,v,np.nan)

def change(before,after,bbox,out,frequency='A',pol='HHHH',min_looks=3,maturity='unknown'):
    if frequency not in ('A','B') or pol not in ('HHHH','HVHV','VVVV','VHVH','RHRH','RVRV') or not 1<=min_looks<=100 or maturity not in ('beta','provisional','validated','unknown'):raise ValueError('Invalid radar options')
    w,s,e,n=bbox
    if not -180<=w<e<=180 or not -90<=s<n<=90:raise ValueError('Invalid AOI')
    a,t0=identity(before);b,t1=identity(after)
    if a!=b or t1<=t0:raise ValueError('Pair must share track, direction, frame, mode, polarization, source, processing release and orbit fidelity; chronological order required')
    x,y,crs,dx,dy,p=subset(before,bbox,frequency,pol,min_looks);X,Y,C,DX,DY,q=subset(after,bbox,frequency,pol,min_looks)
    if crs!=C or (dx,dy)!=(DX,DY) or x.shape!=X.shape or y.shape!=Y.shape or not np.allclose(x,X,rtol=0,atol=dx*1e-5) or not np.allclose(y,Y,rtol=0,atol=dy*1e-5):raise ValueError('Native grids differ; require explicit registration before comparison')
    good=np.isfinite(p)&np.isfinite(q)
    if not good.any():raise ValueError('No jointly valid pixels')
    delta=np.full(p.shape,np.nan);delta[good]=10*(np.log10(q[good])-np.log10(p[good]));out=Path(out);out.mkdir(parents=True,exist_ok=True)
    profile=dict(driver='GTiff',height=len(y),width=len(x),count=1,dtype='float32',nodata=float('nan'),crs=f'EPSG:{crs}',transform=from_origin(x[0]-dx/2,y[0]+dy/2,dx,dy),compress='deflate')
    for name,v in [('before-gamma0-db',10*np.log10(p)),('after-gamma0-db',10*np.log10(q)),('delta-db',delta)]:
        with rio.open(out/(name+'.tif'),'w',**profile) as ds:ds.write(v.astype('float32'),1);ds.set_band_unit(1,'dB')
    record={'method':'paired native-grid log power ratio','before':Path(before).name,'after':Path(after).name,'before_utc':t0.isoformat(),'after_utc':t1.isoformat(),'source_hashes':[sha(before),sha(after)],'bbox':bbox,'frequency':frequency,'polarization':pol,'maturity_declared':maturity,'crs':crs,'posting_m':[dx,dy],'valid_pixels':int(good.sum()),'valid_fraction':float(good.mean()),'median_delta_db':float(np.nanmedian(delta)),'outputs':{p.name:sha(p) for p in out.glob('*-db.tif')},'warning':'Candidate backscatter change only; not a flood mask or displacement. Filename compatibility is necessary not sufficient: independently check local incidence, processing version, noise, layover/shadow, calibration and ground evidence. Maturity declaration is not verified.'}
    (out/'radar-change.json').write_text(json.dumps(record,indent=2));return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('before');p.add_argument('after');p.add_argument('--bbox',nargs=4,type=float,required=True);p.add_argument('--out',required=True);p.add_argument('--frequency',default='A');p.add_argument('--pol',default='HHHH');p.add_argument('--min-looks',type=float,default=3);p.add_argument('--maturity',default='unknown');a=p.parse_args();print(json.dumps(change(a.before,a.after,a.bbox,a.out,a.frequency,a.pol,a.min_looks,a.maturity),indent=2))
