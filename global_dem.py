"""Bounded public Copernicus DSM fallback. Never fills missing land or ocean cells."""
import math, numpy as np, rasterio as rio
from rasterio.io import MemoryFile
from rasterio.warp import reproject, Resampling

def tile_url(lat,lon,res):
    if res not in (30,90) or not -90<=lat<90 or not -180<=lon<180:raise ValueError('Invalid tile')
    name=f'Copernicus_DSM_COG_{10 if res==30 else 30}_{"N" if lat>=0 else "S"}{abs(lat):02d}_00_{"E" if lon>=0 else "W"}{abs(lon):03d}_00_DEM'
    return f'https://copernicus-dem-{res}m.s3.amazonaws.com/{name}/{name}.tif'

def acquire(d,fetch):
    w,s,e,n=d['wgs84'];tiles=[(y,x) for y in range(math.floor(s),math.floor(n)+1) for x in range(math.floor(w),math.floor(e)+1)]
    if len(tiles)>4:raise ValueError('Too many global DEM tiles')
    errors=[]
    for res in (30,90):
        out=np.full((d['n'],d['n']),np.nan,dtype='float32');sources=[]
        try:
            import hashlib
            for y,x in tiles:
                url=tile_url(y,x,res);raw=fetch(url,max_bytes=65_000_000,attempts=1,timeout=18)
                with MemoryFile(raw) as mf,mf.open() as src:
                    if not src.crs or src.count!=1 or src.width*src.height>30_000_000:raise ValueError('Invalid DSM tile')
                    part=np.full_like(out,np.nan);reproject(rio.band(src,1),part,src_transform=src.transform,src_crs=src.crs,src_nodata=src.nodata,dst_transform=rio.Affine(*d['transform']),dst_crs=d['epsg'],dst_nodata=np.nan,resampling=Resampling.bilinear)
                    sel=np.isfinite(part)&~np.isfinite(out);out[sel]=part[sel]
                    sources.append({'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'native_pixel_size':list(src.res),'native_crs':str(src.crs)})
            if not np.isfinite(out).all():raise ValueError('Incomplete DSM coverage')
            with MemoryFile() as mf:
                with mf.open(driver='GTiff',height=d['n'],width=d['n'],count=1,dtype='float32',crs=d['epsg'],transform=rio.Affine(*d['transform'])) as dst:dst.write(out,1);dst.set_band_unit(1,'m')
                return mf.read(),res,sources
        except Exception as exc:errors.append(f'GLO-{res}: {exc}')
    raise RuntimeError('; '.join(errors))
