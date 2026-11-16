"""Fixed-host Earth observation and AI weather forcing adapters. No fabricated or stale-as-live data."""
import csv,io,json,math,os,re
from datetime import datetime,timezone,timedelta
from urllib.parse import urlencode
from earth_services import get,bbox_value

def coords(q):
    lat=float(q.get('lat',[''])[0]);lon=float(q.get('lon',[''])[0])
    if not math.isfinite(lat) or not math.isfinite(lon) or not(-90<=lat<=90 and -180<=lon<=180):raise ValueError('Invalid WGS84 coordinates')
    return lat,lon

def forecast(q):
    lat,lon=coords(q); start=datetime.now(timezone.utc).date()+timedelta(days=1)
    url='https://api.open-meteo.com/v1/forecast?'+urlencode({'latitude':lat,'longitude':lon,'models':'ecmwf_aifs025_single','daily':'precipitation_sum','timezone':'GMT','forecast_days':15,'precipitation_unit':'mm'})
    raw,stamp,status=get(url,900);d=json.loads(raw)
    if d.get('error'):raise ValueError('Forecast provider rejected this request')
    daily=d['daily']; unit=d['daily_units']['precipitation_sum']; times=daily['time']; values=daily['precipitation_sum']
    if unit!='mm' or len(times)!=len(values):raise ValueError('Invalid forecast units or shape')
    rows=[]
    for date,v in zip(times,values):
        expected=(start+timedelta(days=len(rows))).isoformat()
        if date<start.isoformat():continue
        if date!=expected or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:break
        rows.append({'date':date,'rain_mm':v})
    if not rows:raise ValueError('No continuous complete future daily precipitation available')
    return {'source':'ECMWF AIFS Single via Open-Meteo','model':'ecmwf_aifs025_single','native_grid_degrees':0.25,'requested_lat':lat,'requested_lon':lon,'provider_lat':d.get('latitude'),'provider_lon':d.get('longitude'),'retrieved_utc':stamp,'status':status,'model_run_utc':None,'daily':rows,'units':'mm/day','warning':'Daily forecast derived from coarse AI weather output; forecast issue time not supplied by this endpoint. Not ground-motion AI. Open-Meteo public endpoint is noncommercial; ECMWF data CC BY 4.0.'}

def quakes(q):
    url='https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson';raw,stamp,status=get(url,60);d=json.loads(raw)
    if d.get('type')!='FeatureCollection' or not isinstance(d.get('features'),list):raise ValueError('Invalid USGS response')
    return {'source':'USGS ComCat M2.5+ past day','retrieved_utc':stamp,'status':status,'collection':d}

def fires(q):
    key=os.environ.get('FIRMS_MAP_KEY','');
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',key):raise ValueError('Set FIRMS_MAP_KEY on the local server first')
    b=bbox_value(q.get('bbox',[''])[0]);w,s,e,n=map(float,b.split(','))
    if (e-w)*(n-s)>400:raise ValueError('Zoom in to a regional area before requesting fire points')
    try:raw,stamp,status=get('https://firms.modaps.eosdis.nasa.gov/api/area/csv/'+key+'/VIIRS_NOAA20_NRT/'+b+'/1',300)
    except Exception:raise RuntimeError('FIRMS source unavailable or key rejected') from None
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if not {'latitude','longitude','acq_date','acq_time'}.issubset(reader.fieldnames or []):raise ValueError('Invalid FIRMS response; check key and quota')
    features=[]
    for row in reader:
        try:lat=float(row['latitude']);lon=float(row['longitude']);when=datetime.strptime(row['acq_date']+' '+row['acq_time'].zfill(4),'%Y-%m-%d %H%M').replace(tzinfo=timezone.utc).isoformat()
        except (ValueError,KeyError):continue
        if not(-90<=lat<=90 and -180<=lon<=180):continue
        features.append({'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':{'observed_utc':when,'confidence':row.get('confidence'),'frp_mw':row.get('frp'),'source':'VIIRS NOAA-20 NRT'}})
    return {'source':'NASA FIRMS VIIRS NOAA-20 NRT','retrieved_utc':stamp,'status':status,'collection':{'type':'FeatureCollection','features':features}}

def wmts(q):
    """Read authoritative matrix definitions, not guessed product identifiers."""
    import xml.etree.ElementTree as E
    url='https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/wmts.cgi?SERVICE=WMTS&REQUEST=GetCapabilities&VERSION=1.0.0'
    raw,stamp,status=get(url,3600);root=E.fromstring(raw);ns={'w':'http://www.opengis.net/wmts/1.0','o':'http://www.opengis.net/ows/1.1'};contents=root.find('w:Contents',ns)
    if contents is None:raise ValueError('No WMTS Contents')
    matrices={}
    for x in contents.findall('w:TileMatrixSet',ns):
        ident=x.findtext('o:Identifier',namespaces=ns);m=x.findall('w:TileMatrix',ns)
        if not ident or not m:continue
        try:
            labels=[y.findtext('o:Identifier',namespaces=ns) for y in m];widths=[int(y.findtext('w:MatrixWidth',namespaces=ns)) for y in m];heights=[int(y.findtext('w:MatrixHeight',namespaces=ns)) for y in m];sizes=[(int(y.findtext('w:TileWidth',namespaces=ns)),int(y.findtext('w:TileHeight',namespaces=ns))) for y in m]
            if any(w!=2**i or h!=2**i for i,(w,h) in enumerate(zip(widths,heights))) or len(set(sizes))!=1:continue
            matrices[ident]={'labels':labels,'tile_width':sizes[0][0],'tile_height':sizes[0][1]}
        except (ValueError,TypeError):continue
    layers=[]
    for x in contents.findall('w:Layer',ns):
        ident=x.findtext('o:Identifier',namespaces=ns);fmt=x.findtext('w:Format',namespaces=ns);links=[y.findtext('w:TileMatrixSet',namespaces=ns) for y in x.findall('w:TileMatrixSetLink',ns)];link=next((y for y in links if y in matrices),None)
        if not ident or not link or fmt not in ('image/png','image/jpeg'):continue
        dims=x.findall('w:Dimension',ns);timed=next((d for d in dims if (d.findtext('o:Identifier',namespaces=ns) or '').lower()=='time'),None);style=x.find('w:Style',ns)
        layers.append({'id':ident,'title':x.findtext('o:Title',namespaces=ns) or ident,'format':fmt,'style':style.findtext('o:Identifier',namespaces=ns) if style is not None else 'default','matrix':link,**matrices[link],'time_default':timed.findtext('w:Default',namespaces=ns) if timed is not None else None,'timed':timed is not None})
    return {'source':'NASA GIBS WMTS EPSG:3857 capabilities','retrieved_utc':stamp,'status':status,'layers':layers}

def raster_tile(root,digest,z,x,y):
    """Native source GeoTIFF -> Web Mercator display tile, not a scientific measurement."""
    import numpy as np
    import rasterio
    from rasterio.vrt import WarpedVRT
    from rasterio.enums import Resampling,ColorInterp
    from rasterio.transform import from_bounds
    from PIL import Image
    if not re.fullmatch(r'[0-9a-f]{64}',digest) or not(0<=z<=22 and 0<=x<2**z and 0<=y<2**z):raise ValueError('Invalid raster tile address')
    p=root/'uploads'/'earth'/digest
    meta=json.loads((p/'metadata.json').read_text());span=20037508.342789244;size=2*span/(2**z);left=-span+x*size;top=span-y*size;transform=from_bounds(left,top-size,left+size,top,256,256)
    with rasterio.open(p/'source.tif') as src:
        with WarpedVRT(src,crs='EPSG:3857',transform=transform,width=256,height=256,resampling=Resampling.nearest,add_alpha=not (ColorInterp.alpha in src.colorinterp)) as vrt:
            valid=(vrt.read(vrt.colorinterp.index(ColorInterp.alpha)+1)>0) if ColorInterp.alpha in vrt.colorinterp else vrt.dataset_mask()>0
            colors=src.colorinterp
            if all(c in colors for c in (ColorInterp.red,ColorInterp.green,ColorInterp.blue)) and all(t=='uint8' for t in src.dtypes):
                rgb=vrt.read([colors.index(c)+1 for c in (ColorInterp.red,ColorInterp.green,ColorInterp.blue)]).transpose(1,2,0)
            else:
                a=vrt.read(1).astype(float);valid &= np.isfinite(a);lo,hi=meta['preview_range'];v=np.clip((np.nan_to_num(a,nan=lo)-lo)/max(hi-lo,1e-12),0,1);rgb=np.stack([255*v,255*(1-abs(2*v-1)),255*(1-v)],axis=-1).astype('uint8')
            rgba=np.concatenate([rgb,(255*valid[...,None]).astype('uint8')],axis=2)
    out=io.BytesIO();Image.fromarray(rgba).save(out,format='PNG');return out.getvalue()
