"""Nearest-sample display lookup for geographically registered radar grids.
No interpolation across withheld cells; source scientific values unchanged.
"""
import base64
import numpy as np
from pyproj import Transformer
from radar_investigation import matching_audit

def lookup(g,size=480):
    n=int(g['n']);dx,_,w,_,dy,north=g['transform'];e=w+dx*n;s=north+dy*n
    fwd=Transformer.from_crs(g['epsg'],4326,always_xy=True);inv=Transformer.from_crs(4326,g['epsg'],always_xy=True)
    bounds=list(fwd.transform_bounds(w,s,e,north,densify_pts=21))
    if not -180<=bounds[0]<bounds[2]<=180 or not -90<=bounds[1]<bounds[3]<=90:raise ValueError('Antimeridian/spanning radar grid not supported')
    xx,yy=np.meshgrid(np.linspace(bounds[0],bounds[2],size,endpoint=False)+(bounds[2]-bounds[0])/(2*size),np.linspace(bounds[3],bounds[1],size,endpoint=False)-(bounds[3]-bounds[1])/(2*size))
    x,y=inv.transform(xx,yy);col=(x-w)/dx;row=(y-north)/dy;valid=(col>=0)&(col<n)&(row>=0)&(row<n)
    # index into the original 480-square painted display, retain brush edges
    lut=np.full((size,size),-1,dtype='<i4');lut[valid]=np.minimum(size-1,np.floor(row[valid]*size/n).astype(int))*size+np.minimum(size-1,np.floor(col[valid]*size/n).astype(int))
    # Pixel lookup is for display; exact point location is calculated server-side for selected centers/polygons.
    r,c=np.indices((n+1,n+1));lo,la=fwd.transform(w+c*dx,north+r*dy)
    perimeter=np.vstack([np.column_stack([lo[0],la[0]]),np.column_stack([lo[1:,-1],la[1:,-1]]),np.column_stack([lo[-1,-2::-1],la[-1,-2::-1]]),np.column_stack([lo[-2::-1,0],la[-2::-1,0]])])
    return {'bbox':bounds,'size':size,'n':n,'lookup_i32':base64.b64encode(lut.tobytes()).decode(),'lat':g['lat'],'lon':g['lon'],'corner_lat':la.tolist(),'corner_lon':lo.tolist(),'outline':perimeter.tolist(),'epsg':g['epsg'],'transform':g['transform'],'scope':'Nearest-sampled projected raster display, exact cell center and corners. No new scientific measurements.'}

def active(app):
    import external_evidence as ee
    s,dates,key=ee.active(app);a=matching_audit(app,key,int(s['n']),[d.isoformat() for d in dates]);return {'available':False,'warning':'No matching geometry audit; approximate legacy display.'} if a is None else {'available':True,'site_hash':key,**lookup(a['geometry'])}
