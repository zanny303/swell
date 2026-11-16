"""Independent DEM-derived flow analysis via Deltares PyFlwDir (MIT)."""
import importlib.metadata, hashlib
import numpy as np
from affine import Affine

def analyze(root,site_id):
    import site_twin
    try:import pyflwdir
    except ImportError:raise ValueError('Optional engine missing. In your active venv run: python -m pip install pyflwdir') from None
    meta,z=site_twin.load(root,site_id)
    z=np.asarray(z,dtype=np.float64)
    if z.ndim!=2 or not np.isfinite(z).all() or z.size>300000:raise ValueError('Expected complete bounded metric DEM')
    tr=Affine(*meta['transform'][:6]);
    if tr.a<=0 or tr.e>=0 or tr.b!=0 or tr.d!=0:raise ValueError('Expected north-up metric DEM')
    flw=pyflwdir.from_dem(z,nodata=-9999.,transform=tr,latlon=False,outlets='edge')
    area=np.asarray(flw.upstream_area(unit='m2'),float); basins=np.asarray(flw.basins())
    if area.shape!=z.shape or basins.shape!=z.shape or not np.isfinite(area).all() or (area<=0).any():raise ValueError('Routing engine returned invalid coverage')
    r,c=np.unravel_index(np.argmax(area),area.shape)
    return {'site_id':site_id,'source':meta['source'],'dem_sha256':meta['source_sha256'],'engine':'Deltares PyFlwDir '+importlib.metadata.version('pyflwdir'),'repository':'https://github.com/Deltares/pyflwdir','upstream_area_m2':area.round(2).tolist(),'basin_ids':basins.tolist(),'largest_upstream_m2':float(area[r,c]),'largest_cell':[int(r),int(c)],'basin_count':int(len(set(basins.ravel())-{0})),'warning':'D8 terrain routing with depression filling and edge outlets. Area only within the selected DEM; not flood depth, measured drainage, pipe connectivity or validated design. Do not use filled DEM as surveyed elevation.'}
