"""Target-filtered PDS observational metadata and small native MOLA/LOLA DEM windows.
No proxy URLs supplied by clients, no Earth CRS or synthetic fallback.
"""
import json, math, re, urllib.request
from urllib.parse import urlencode, quote
from pathlib import Path
import numpy as np

TARGETS = {x.lower():x for x in ('Mars','Moon','Earth','Venus','Europa','Titan')}
PDS = 'https://pds.nasa.gov/api/search/1'
DEM = {
 'mars': {'title':'MGS MOLA DEM 463 m', 'url':'https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif','page':'https://astrogeology.usgs.gov/search/map/mars_mgs_mola_dem_463m','radius':3396190,'datum':'MOLA areoid, Mars 2000; see USGS source'},
 'moon': {'title':'LRO LOLA DEM 118 m','url':'https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif','page':'https://astrogeology.usgs.gov/search/map/moon_lro_lola_dem_118m','radius':1737400,'datum':'Lunar reference radius; see USGS source'},
}

def _value(x, keys):
    for k in keys:
        for obj in (x,x.get('properties',{})):
            if not isinstance(obj,dict):continue
            v=obj.get(k)
            if isinstance(v,list):v=v[0] if v else None
            if isinstance(v,(str,int,float)) and str(v).strip():return str(v)
    return ''

def normalize(raw,target,limit):
    rows=raw.get('data') or raw.get('results') or raw.get('products') or []
    if isinstance(rows,dict):rows=rows.get('results') or rows.get('items') or []
    if not isinstance(rows,list):raise ValueError('Unknown PDS response structure')
    result=[]
    for x in rows:
        if not isinstance(x,dict):continue
        lid=_value(x,('id','lidvid','lid','product_lid','pds:Identification_Area.pds:logical_identifier'))
        klass=_value(x,('product_class','productClass','pds:Identification_Area.pds:product_class')); generic_type=_value(x,('type','@type'))
        if not klass and generic_type.startswith('Product_'):klass=generic_type
        if not lid.startswith('urn:nasa:pds:') or lid.startswith('urn:nasa:pds:context') or (klass and 'observational' not in klass.lower()):continue
        # The target is enforced by the registry query; explicit contradictory metadata is rejected.
        props=x.get('properties') or {};props=props if isinstance(props,dict) else {}
        values=x.get('target_name') or props.get('target_name') or props.get('pds:Target_Identification.pds:name')
        if values and target.casefold() not in [str(v).casefold() for v in (values if isinstance(values,list) else [values])]:continue
        result.append({'id':lid,'title':_value(x,('title','name','pds:Identification_Area.pds:title')) or lid,'target_name':target,'start_date_time':_value(x,('start_date_time','pds:Time_Coordinates.pds:start_date_time')),'description':_value(x,('description','pds:Observation_Area.pds:comment'))[:500], 'url':PDS+'/products/'+quote(lid,safe=':'),'product_class':'Product_Observational (registry endpoint)'})
        if len(result)>=limit:break
    return result

def search(body, keywords='', limit=12, opener=urllib.request.urlopen):
    target=TARGETS.get(body.lower())
    if not target:raise ValueError('Choose a supported planetary target')
    limit=max(1,min(25,int(limit)));keywords=keywords.strip()[:180]
    params={'q':f'target_name eq "{target}"','limit':limit}
    if keywords and keywords.casefold()!=target.casefold():params['keywords']=keywords
    url=PDS+'/classes/Product_Observational?'+urlencode(params)
    with opener(urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'SWELL planetary evidence'}),timeout=25) as response:
        raw=json.loads(response.read(5_000_001))
    records=normalize(raw,target,limit);summary=raw.get('summary') or {}
    return {'source':'NASA PDS Search API','target':target,'query':keywords,'results':records,'total':summary.get('total') if isinstance(summary,dict) else None,'scope':'Target-filtered observational products only; not an exhaustive inventory','request_url':url}

def dem_window(body,lat,lon,local_path=None):
    import rasterio
    from rasterio.windows import Window
    from pyproj import CRS, Transformer, Geod
    from rasterio.env import Env
    meta=DEM.get(body)
    if not meta:raise ValueError('Native DEM adapter currently supports Mars and Moon only')
    lat,lon=float(lat),float(lon)
    if not math.isfinite(lat+lon) or not -89.5<=lat<=89.5 or not -180<=lon<=180:raise ValueError('Use east-positive longitude [-180,180] and latitude within ±89.5°')
    if local_path is None:
        req=urllib.request.Request(meta['url'],headers={'Range':'bytes=0-0','Accept-Encoding':'identity'})
        with urllib.request.urlopen(req,timeout=12) as r:
            if r.status!=206 or not (r.headers.get('Content-Range') or '').startswith('bytes 0-0/'):raise ValueError('Provider does not support bounded range reads; no full global DEM download attempted')
        path='/vsicurl/'+meta['url']
    else:path=str(Path(local_path))
    with Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_HTTP_TIMEOUT='20',GDAL_HTTP_MAX_RETRY='0',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif'):
        with rasterio.open(path) as d:
            if d.count!=1 or not d.crs:raise ValueError('Native single-band DEM with planetary CRS required')
            crs=CRS.from_user_input(d.crs);geo=crs.geodetic_crs
            if not geo or abs(geo.ellipsoid.semi_major_metre-meta['radius'])>20000:raise ValueError('DEM planetary radius does not match selected body')
            if abs(d.transform.b)>1e-9 or abs(d.transform.d)>1e-9:raise ValueError('Rotated grid unsupported')
            fwd=Transformer.from_crs(geo,crs,always_xy=True);inv=Transformer.from_crs(crs,geo,always_xy=True)
            x,y=fwd.transform(lon,lat);row,col=d.index(x,y)
            if not 0<=row<d.height or not 0<=col<d.width:raise ValueError('Location not contained in native DEM')
            r0,c0=max(0,row-32),max(0,col-32);h=min(65,d.height-r0);w=min(65,d.width-c0)
            win=Window(c0,r0,w,h);z=d.read(1,window=win,masked=True).astype('float64').filled(np.nan)
            z=z*float(d.scales[0])+float(d.offsets[0]);units=d.units[0]
            if units and units.lower() not in ('m','meter','meters','metre','metres'):raise ValueError('DEM vertical units are not metres')
            # Product pages establish metre units for these allowlisted rasters. A local override is for tests/user-supplied source only.
            a=d.window_transform(win);rr,cc=np.indices(z.shape);xx=a.c+(cc+.5)*a.a;yy=a.f+(rr+.5)*a.e;ll,bb=inv.transform(xx,yy)
            gd=Geod(a=geo.ellipsoid.semi_major_metre,b=geo.ellipsoid.semi_minor_metre)
            _,_,dx=gd.inv(ll[1:-1,:-2],bb[1:-1,:-2],ll[1:-1,2:],bb[1:-1,2:]);_,_,dy=gd.inv(ll[:-2,1:-1],bb[:-2,1:-1],ll[2:,1:-1],bb[2:,1:-1]);s=np.full(z.shape,np.nan)
            with np.errstate(divide='ignore',invalid='ignore'):
                inner=np.degrees(np.arctan(np.hypot((z[1:-1,2:]-z[1:-1,:-2])/dx,(z[2:,1:-1]-z[:-2,1:-1])/dy)))
            inner[(dx<=0)|(dy<=0)|~np.isfinite(z[1:-1,1:-1])]=np.nan;s[1:-1,1:-1]=inner
            if not np.isfinite(z).any():raise ValueError('No valid elevation samples')
            clean=lambda a:np.where(np.isfinite(a),a,None).tolist()
            stats=lambda a: {'min':float(np.nanmin(a)), 'max':float(np.nanmax(a)), 'median':float(np.nanmedian(a))} if np.isfinite(a).any() else None
            return {'body':body,'source':meta['title'] if local_path is None else 'User supplied / test DEM, provenance not verified','source_url':meta['page'],'data_url':meta['url'] if local_path is None else None,'datum':meta['datum'] if local_path is None else 'User supplied, datum unverified','lat':lat,'lon':lon,'native_crs':crs.to_string(),'native_window':[r0,c0,h,w],'elevation_m':clean(z),'slope_deg':clean(s),'elevation_stats':stats(z),'slope_stats':stats(s),'valid_cells':int(np.isfinite(z).sum()),'warning':'Native samples; slope is a centered terrain gradient using body-specific geodesic spacing. Not landing safety, illumination, temperature or resource estimates. No interpolation across missing pixels.'}
