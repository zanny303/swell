"""Exchange contract for outputs from independent models (Prithvi, SWMM, hydraulic solvers).
Registers an externally produced raster; does not execute or certify external models.
"""
import argparse,json,hashlib,datetime,math
from pathlib import Path
import numpy as np
import rasterio as rio
from rasterio.warp import reproject,Resampling
import site_twin as st

KINDS={'water_class':('1',Resampling.nearest),'water_probability':('1',Resampling.average),'depth':('m',Resampling.bilinear),'los_displacement':('mm',Resampling.bilinear)}
def register(root,site_id,path,manifest):
    d,z=st.load(root,site_id);p=Path(path);m=json.loads(Path(manifest).read_text()) if not isinstance(manifest,dict) else manifest
    kind=m['kind'];unit,resampling=KINDS[kind]
    for k in ('model','version','source','input_provenance','valid_time_utc','units'):
        if not isinstance(m.get(k),str) or not m[k].strip():raise ValueError('Missing '+k)
    if m['units']!=unit:raise ValueError('Unexpected units')
    t=datetime.datetime.fromisoformat(m['valid_time_utc']);
    if t.tzinfo is None:raise ValueError('Timestamp needs UTC offset')
    if kind=='depth' and m.get('vertical_datum')!=d['vertical_datum']:raise ValueError('Depth exchange requires matching declared datum')
    if kind=='los_displacement' and not m.get('los_convention'):raise ValueError('Declare LOS sign and reference')
    with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    if sha!=m.get('sha256'):raise ValueError('Source raster checksum mismatch')
    with rio.open(p) as src:
        if not src.crs or not src.crs.is_projected or src.crs.linear_units.lower() not in ('metre','meter','metres','meters') or src.count!=1 or src.width*src.height>100_000_000:raise ValueError('Bounded metric projected single-band raster required')
        if max(src.res)>d['dx']*1.01:raise ValueError('Site grid finer than supplied output; reload at coarser resolution')
        a=src.read(1,masked=True).filled(np.nan) if np.issubdtype(src.dtypes[0],np.floating) else src.read(1,masked=True).astype(float).filled(np.nan)
        vals=a[np.isfinite(a)]
        if not len(vals) or (kind=='water_class' and not np.isin(vals,[0,1]).all()) or (kind=='water_probability' and (vals.min()<0 or vals.max()>1)) or (kind=='depth' and vals.min()<0):raise ValueError('Invalid values for declared product type')
        dest=np.full(z.shape,np.nan,dtype=np.float32);reproject(a,dest,src_transform=src.transform,src_crs=src.crs,src_nodata=np.nan,dst_transform=rio.Affine(*d['transform']),dst_crs=d['epsg'],dst_nodata=np.nan,resampling=resampling)
        native={'crs':str(src.crs),'pixel_spacing':list(src.res)}
    valid=np.isfinite(dest)
    if not valid.any():raise ValueError('No site overlap')
    record={'site_id':site_id,'source_metadata':m,'native_grid':native,'coverage':float(valid.mean()),'status':'external model output; unvalidated','engineering_approved':False,'note':'Registration and integrity checks only; no model skill or scientific approval inferred.'}
    key=st.digest(json.dumps(record,sort_keys=True).encode());out=st.storage(root)/site_id/'external'/key;out.mkdir(parents=True,exist_ok=True)
    with rio.open(out/'aligned.tif','w',driver='GTiff',count=1,width=d['n'],height=d['n'],dtype='float32',nodata=float('nan'),crs=d['epsg'],transform=rio.Affine(*d['transform']),compress='deflate') as ds:ds.write(dest,1);ds.set_band_unit(1,unit)
    record['output_sha256']=st.digest((out/'aligned.tif').read_bytes());record['output_path']=str(out/'aligned.tif');(out/'manifest.json').write_text(json.dumps(record,indent=2));return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('site_id');p.add_argument('raster');p.add_argument('manifest');p.add_argument('--root',default='site');a=p.parse_args();print(json.dumps(register(a.root,a.site_id,a.raster,a.manifest),indent=2))
