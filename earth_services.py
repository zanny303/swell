"""Allowlisted public Earth data services; no fabricated results or arbitrary URL proxy."""
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pathlib import Path
import json, math, time, xml.etree.ElementTree as ET, re, hashlib, io

GIBS='https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi'
CMR='https://cmr.earthdata.nasa.gov/search/'
CACHE={}
def utc(): return datetime.now(timezone.utc).isoformat()
def get(url, ttl=300):
    if url in CACHE and time.monotonic()-CACHE[url][0]<ttl: return CACHE[url][1], CACHE[url][2], 'cached'
    req=Request(url,headers={'User-Agent':'SWELL research local client/2.0','Accept':'*/*'})
    with urlopen(req,timeout=15) as res:
        raw=res.read(32*1024*1024+1)
        if len(raw)>32*1024*1024: raise ValueError('Provider response too large')
        fetched=utc()
    if len(CACHE)>100: CACHE.clear()
    CACHE[url]=(time.monotonic(),raw,fetched)
    return raw,fetched,'retrieved'
def bbox_value(text):
    b=list(map(float,text.split(',')))
    if len(b)!=4 or not all(math.isfinite(x) for x in b) or not (-180<=b[0]<b[2]<=180 and -90<=b[1]<b[3]<=90): raise ValueError('Expected west,south,east,north bounds')
    return ','.join(map(str,b))
def catalog(q):
    kind=q.get('kind',['nisar'])[0]; b=bbox_value(q.get('bbox',['-97.05,32.6,-96.55,33'])[0])
    # Discover collection IDs from CMR rather than assuming a maturity or version.
    keywords={'nisar_gcov':('short_name','NISAR_L2_GCOV_V1'),'nisar':('keyword','NISAR GUNW'),'opera':('short_name','OPERA_L3_DISP-S1_V1'),'opera_dswx_s1':('short_name','OPERA_L3_DSWX-S1_V1'),'opera_dswx_hls':('short_name','OPERA_L3_DSWX-HLS_V1'),'gpm':('keyword','GPM IMERG'),'smap':('keyword','SMAP Soil Moisture'),'dem':('keyword','NASADEM'),'optical':('keyword','Harmonized Landsat Sentinel')}
    if kind not in keywords: raise ValueError('Unknown collection family')
    field,value=keywords[kind];params={field:value,'page_size':30,'has_granules':'true'}
    url=CMR+'collections.json?'+urlencode(params); raw,stamp,status=get(url,3600)
    cols=json.loads(raw)['feed']['entry']; result=[]
    for c in cols:
        result.append({'id':c.get('id'),'title':c.get('title'),'short_name':c.get('short_name'),'version':c.get('version_id'),'provider':c.get('data_center')})
    return {'source':'NASA CMR collections','fetched_utc':stamp,'status':status,'bbox':b,'collections':result,'query_url':url}
def granules(q):
    cid=q.get('id',[''])[0]
    if not re.fullmatch(r'C\d+-[A-Za-z0-9_]+',cid): raise ValueError('Invalid CMR collection ID')
    b=bbox_value(q.get('bbox',['-97.05,32.6,-96.55,33'])[0]); params={'collection_concept_id':cid,'bounding_box':b,'page_size':20,'sort_key[]':'-start_date'}
    url=CMR+'granules.json?'+urlencode(params); raw,stamp,status=get(url)
    rows=json.loads(raw)['feed']['entry']; results=[]
    for r in rows:
        results.append({'id':r.get('id'),'title':r.get('title'),'start':r.get('time_start'),'end':r.get('time_end'),'updated':r.get('updated'),'links':[{'url':l['href'],'title':l.get('title',l.get('rel','source'))} for l in r.get('links',[]) if str(l.get('href','')).startswith('https://')][:12]})
    return {'source':'NASA CMR granules (metadata only)','fetched_utc':stamp,'status':status,'results':results,'query_url':url}
def capabilities():
    url=GIBS+'?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.1.1'; raw,stamp,status=get(url,3600)
    root=ET.fromstring(raw); rows=[]
    for layer in root.iter():
        if layer.tag.split('}')[-1]!='Layer':continue
        child={c.tag.split('}')[-1]:c for c in layer}
        if 'Name' not in child:continue
        dims=[{'name':c.get('name'),'default':c.get('default'),'extent':(c.text or '')[:2000]} for c in layer if c.tag.split('}')[-1] in ('Dimension','Extent')]
        rows.append({'id':child['Name'].text,'title':child['Title'].text if 'Title'in child else child['Name'].text,'dimensions':dims})
    return {'source':'NASA GIBS WMS capabilities','fetched_utc':stamp,'status':status,'layers':rows}
def raster_preview(raw, name, root):
    """Single-band georeferenced raster quicklook. Numeric source retained, never use RGB as measurements."""
    import numpy as np
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.warp import calculate_default_transform,reproject,Resampling,transform_bounds
    from PIL import Image
    digest=hashlib.sha256(raw).hexdigest(); folder=root/'uploads'/'earth'/digest;folder.mkdir(parents=True,exist_ok=True)
    with MemoryFile(raw) as mem, mem.open() as src:
        if not src.crs:raise ValueError('Raster must have an explicit CRS')
        if src.width*src.height>100_000_000:raise ValueError('Raster too large for local preview')
        b=transform_bounds(src.crs,'EPSG:4326',*src.bounds,densify_pts=21)
        if not(-180<=b[0]<b[2]<=180 and -90<=b[1]<b[3]<=90):raise ValueError('Unsupported extent/antimeridian')
        from rasterio.transform import from_bounds
        w,h=min(src.width,1024),min(src.height,1024);transform=from_bounds(*b,w,h)
        a=np.full((h,w),np.nan,dtype='float32'); reproject(source=rasterio.band(src,1),destination=a,src_transform=src.transform,src_crs=src.crs,src_nodata=src.nodata,dst_transform=transform,dst_crs='EPSG:4326',dst_nodata=np.nan,resampling=Resampling.nearest)
        valid=np.isfinite(a)
        if not valid.any():raise ValueError('No finite pixels')
        lo,hi=np.percentile(a[valid],[2,98]); v=np.clip((np.nan_to_num(a,nan=lo)-lo)/max(hi-lo,1e-12),0,1)
        rgb=np.stack([255*v,255*(1-np.abs(2*v-1)),255*(1-v),valid*210],axis=-1).astype('uint8')
        Image.fromarray(rgb).save(folder/'preview.png'); (folder/'source.tif').write_bytes(raw)
        merc,_,_=calculate_default_transform(src.crs,'EPSG:3857',src.width,src.height,*src.bounds); native_m=max(abs(merc.a),abs(merc.e)); max_zoom=max(0,min(22,math.ceil(math.log2(156543.033928/max(native_m,1e-9)))))
        meta={'max_zoom':max_zoom,'source':'user-uploaded raster','name':name,'sha256':digest,'bbox':b,'crs':str(src.crs),'native_shape':[src.height,src.width],'native_resolution':src.res,'band':1,'unit':src.units[0] if src.units else None,'preview_range':[float(lo),float(hi)],'preview':'/uploads/earth/'+digest+'/preview.png','retrieved_utc':utc(),'warning':'Display only, not assimilated. Colors 2–98 percentile; no inferred physical units.'}
        (folder/'metadata.json').write_text(json.dumps(meta,indent=2));return meta
