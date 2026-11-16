"""Location-scoped evidence, screening and review exports. Never substitute demo data."""
import csv, io, json, math, zipfile, hashlib
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from earth_services import get
from geo_services import coords, forecast

VERSION='location-screening-1.0'
def now(): return datetime.now(timezone.utc).isoformat()
def fetch(url, ttl=300):
    raw, stamp, status=get(url, ttl)
    return json.loads(raw),stamp,status

def envelope(source,url,d,stamp,status):
    return dict(source=source,url=url,data=d,retrieved_utc=stamp,status=status)

def alerts(lat,lon):
    url='https://api.weather.gov/alerts/active?'+urlencode({'point':f'{lat:.4f},{lon:.4f}'})
    d,t,s=fetch(url,60)
    if d.get('type')!='FeatureCollection': raise ValueError('Invalid NWS alert reply')
    rows=[]
    for f in d['features']:
        p=f['properties']; rows.append({k:p.get(k) for k in ('event','headline','severity','urgency','sent','effective','expires','instruction','description','id')})
    return envelope('US National Weather Service active alerts',url,rows,t,s)

def gauges(lat,lon):
    # Nearby points are not necessarily the same catchment. No inference of flooding at GPS point.
    r=.25; b=[max(-180,lon-r),max(-90,lat-r),min(180,lon+r),min(90,lat+r)]
    base='https://api.waterdata.usgs.gov/ogcapi/v0/collections/'
    location_url=base+'monitoring-locations/items?'+urlencode({'bbox':','.join(map(str,b)), 'limit':100,'f':'json'})
    d,t,s=fetch(location_url,3600)
    if d.get('type')!='FeatureCollection':raise ValueError('Invalid USGS location response')
    stations={}
    for f in d['features']:
        p=f['properties'];g=f.get('geometry') or {};c=g.get('coordinates');sid=p.get('id') or f.get('id')
        if g.get('type')!='Point' or not c or not isinstance(sid,str) or not sid.startswith('USGS-'):continue
        stations[sid]=c
    # Limit request to the nearest 20 candidate monitoring locations; not necessarily river gages.
    ids=sorted(stations,key=lambda i:(stations[i][1]-lat)**2+(stations[i][0]-lon)**2*math.cos(math.radians(lat))**2)[:20]
    if not ids:return envelope('USGS monitoring locations (no candidates)',location_url,[],t,s)
    url=base+'latest-continuous/items?'+urlencode({'monitoring_location_id':','.join(ids),'parameter_code':'00065','limit':100,'f':'json'})
    d,t,s=fetch(url,120)
    if d.get('type')!='FeatureCollection':raise ValueError('Invalid USGS response')
    rows=[]
    for f in d['features']:
        p=f['properties'];sid=p.get('monitoring_location_id');c=stations.get(sid)
        if not c:continue
        rows.append(dict(id=sid,lat=c[1],lon=c[0],time=p.get('time'),value=p.get('value'),unit=p.get('unit_of_measure'),approval=p.get('approval_status')))
    result=envelope('USGS latest gage height (local gage datum; nearest 20 candidate stations)',url,rows,t,s);result['station_query']=location_url;return result

def river(lat,lon):
    url='https://flood-api.open-meteo.com/v1/flood?'+urlencode({'latitude':lat,'longitude':lon,'daily':'river_discharge','models':'glofas_v4_forecast','forecast_days':7,'past_days':0})
    d,t,s=fetch(url,900); a=d['daily']; units=d['daily_units']['river_discharge']
    if units not in ('m³/s','m3/s') or len(a['time'])!=len(a['river_discharge']):raise ValueError('Unexpected discharge units or shape')
    rows=[dict(date=x,discharge_m3s=y) for x,y in zip(a['time'],a['river_discharge']) if isinstance(y,(float,int)) and math.isfinite(y) and y>=0]
    if not rows: raise ValueError('No discharge output')
    return envelope('GloFAS v4 forecast via Open-Meteo (5 km; nearest modeled river, not a parcel forecast)',url,{'grid_lat':d.get('latitude'),'grid_lon':d.get('longitude'),'daily':rows},t,s)

def moisture(lat,lon):
    url='https://api.open-meteo.com/v1/forecast?'+urlencode({'latitude':lat,'longitude':lon,'current':'soil_moisture_0_to_1cm,soil_moisture_9_to_27cm','timezone':'GMT','forecast_days':1})
    d,t,s=fetch(url,900); a=d['current']; u=d['current_units']; out={'time':a['time'],'grid_lat':d.get('latitude'),'grid_lon':d.get('longitude')}
    for k in ('soil_moisture_0_to_1cm','soil_moisture_9_to_27cm'):
        v=a.get(k)
        if u.get(k) not in ('m³/m³','m3/m3') or not isinstance(v,(int,float)) or not 0<=v<=1:raise ValueError('Missing or invalid moisture output')
        out[k]=v
    return envelope('Open-Meteo weather-model soil moisture (not an in-situ or satellite measurement)',url,out,t,s)

def soils(lat,lon):
    url='https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest'
    # Only validated numerical parameters can enter this fixed query.
    sql=f"SELECT TOP 12 m.mukey,m.muname,c.compname,c.comppct_r,c.hydgrp FROM mupolygon p JOIN mapunit m ON p.mukey=m.mukey JOIN component c ON c.mukey=m.mukey WHERE p.mupolygongeo.STIntersects(geometry::STGeomFromText('POINT({lon:.7f} {lat:.7f})',4326))=1 ORDER BY c.comppct_r DESC"
    req=Request(url,data=urlencode({'query':sql,'format':'JSON'}).encode(),headers={'User-Agent':'SWELL research local client/3.0','Content-Type':'application/x-www-form-urlencoded'})
    with urlopen(req,timeout=15) as r: d=json.loads(r.read(2_000_000))
    if 'Table' not in d: raise ValueError('No soil survey rows returned')
    rows=[dict(zip(('mukey','mapunit','component','percent','hydrologic_group'),x)) for x in d['Table'] if len(x)==5]
    return envelope('USDA NRCS SSURGO soil map (survey interpretation; not borehole data)',url,rows,now(),'retrieved')

def snapshot(q):
    lat,lon=coords(q)
    jobs={'alerts':alerts,'gauges':gauges,'river':river,'moisture':moisture,'soils':soils,'ai_rain':lambda a,b:forecast({'lat':[str(a)],'lon':[str(b)]})}
    def call(item):
        name,fn=item
        try:return name,fn(lat,lon)
        except Exception:return name,{'status':'unavailable','data':None,'error':'Source unavailable, outside coverage, or invalid response. No replacement values.'}
    with ThreadPoolExecutor(max_workers=6) as ex: result=dict(ex.map(call,jobs.items()))
    return {'lat':lat,'lon':lon,'crs':'EPSG:4326','created_utc':now(),'sources':result,'structural_status':'UNKNOWN — requires surveyed structure, foundation, material and condition inputs; no safety rating inferred.'}

def number(v,lo,hi,label):
    if isinstance(v,bool):raise ValueError(label)
    try:x=float(v)
    except (ValueError,TypeError):raise ValueError(label)
    if not math.isfinite(x) or not lo<=x<=hi:raise ValueError(label)
    return x

def runoff(p,cn):
    s=25400/cn-254; ia=.2*s
    return 0. if p<=ia else (p-ia)**2/(p+.8*s)

def screen(payload):
    lat,lon=coords({'lat':[payload.get('lat')],'lon':[payload.get('lon')]}); rain=payload.get('rain_mm')
    if not isinstance(rain,list) or not 1<=len(rain)<=15:raise ValueError('Supply 1–15 daily rainfall totals')
    rain=[number(x,0,2000,'Invalid rain mm') for x in rain]
    cn=number(payload.get('cn'),40,98,'Curve number 40–98 required'); proposed=number(payload.get('proposed_cn'),40,98,'Proposed curve number 40–98 required')
    area=number(payload.get('area_m2'),1,1e8,'Area must be 1–100,000,000 m²'); extra=number(payload.get('extra_rain_mm',0),0,1000,'Extra rain must be 0–1000 mm'); retain=number(payload.get('retention_m3',0),0,1e9,'Retention volume invalid')
    # Treat forecast window as one continuous event. No daily resetting of abstraction.
    rows=[]; total=0; prev_b=prev_s=0
    for i,r in enumerate(rain):
        total+=r; p=total+extra; b=runoff(total,cn)*area/1000; s=max(0,runoff(p,proposed)*area/1000-retain)
        rows.append({'day':i+1,'rain_mm':r,'cumulative_rain_mm':total,'baseline_runoff_m3':b,'scenario_runoff_m3':s,'baseline_increment_m3':b-prev_b,'scenario_increment_m3':s-prev_s});prev_b,prev_s=b,s
    depth=payload.get('water_depth_m'); exposure=None
    if depth is not None:
        depth=number(depth,0,30,'Water depth must be 0–30 m'); exposure={'assumed_water_depth_m':depth,'base_pressure_kpa':1000*9.80665*depth/1000,'resultant_kn_per_m_width':.5*1000*9.80665*depth**2/1000,'warning':'Static freshwater on one side of a vertical wall; not a structural capacity, velocity, impact, buoyancy or stability check.'}
    return {'model':VERSION,'lat':lat,'lon':lon,'structural_exposure_screen':exposure,'inputs':{'rain_mm':rain,'cn':cn,'proposed_cn':proposed,'area_m2':area,'extra_rain_mm':extra,'retention_m3':retain},'daily':rows,'sensitivity_baseline_final_m3':[runoff(total,max(40,cn-10))*area/1000,runoff(total,min(98,cn+10))*area/1000],'forcing_reference_user_supplied':payload.get('forcing_reference'),'warning':'NRCS event runoff volume screening, continuous storm assumption; curve numbers/area/retention are user assumptions. Not flood extent, flood depth, hydraulic routing, structural rating or certified design. Sensitivity is not a confidence interval.'}

ROLES={'engineer':['Obtain survey elevations, geotechnical borings, foundation and drainage plans.','Validate catchment, design storm and hydraulic model before design.'], 'planner':['Review land cover assumptions and official floodplain layers.','Compare scenario runoff volumes; do not use as zoning determination.'], 'utility':['Obtain utility asset elevations and as-built data.','Review gauge observations and inspect vulnerable assets through approved procedures.'], 'emergency':['Use official warnings and agency evacuation instructions.','Do not infer safe roads from this screening model.'], 'resident':['Read official weather alerts; avoid flooded roads.','Request professional inspection if structural damage is suspected.']}

def export(payload):
    import ezdxf
    from pyproj import CRS, Transformer, Geod
    result=screen(payload); lat,lon=result['lat'],result['lon']; role=payload.get('role')
    if role not in ROLES:raise ValueError('Select a known role')
    # Explicitly a review area, not parcel/catchment. Use locally centred metric azimuthal projection.
    radius=number(payload.get('review_radius_m',100),5,10000,'Review radius 5–10000 m')
    crs=CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs'); tr=Transformer.from_crs('EPSG:4326',crs,always_xy=True); inv=Transformer.from_crs(crs,'EPSG:4326',always_xy=True)
    x,y=tr.transform(lon,lat); lon2,lat2=inv.transform(x,y)
    if abs(lat2-lat)>1e-7 or abs((lon2-lon+180)%360-180)>1e-7:raise ValueError('Coordinate round-trip failed')
    doc=ezdxf.new('R2010');doc.units=6; doc.layers.new('REVIEW_AREA');doc.layers.new('SELECTED_GPS');m=doc.modelspace();m.add_circle((x,y),radius,dxfattribs={'layer':'REVIEW_AREA'});m.add_point((x,y),dxfattribs={'layer':'SELECTED_GPS'});m.add_text('DRAFT REVIEW AREA - NOT SURVEYED OR APPROVED',dxfattribs={'height':max(1,radius/30),'insert':(x-radius,y+radius*1.1)})
    f=io.StringIO();doc.write(f);dxf=f.getvalue(); reread=ezdxf.read(io.StringIO(dxf));audit=reread.audit()
    if audit.errors or audit.fixes:raise ValueError('DXF audit failed')
    geo=Geod(ellps='WGS84'); ring=[list(geo.fwd(lon,lat,i*5,radius)[:2]) for i in range(72)];ring.append(ring[0]);
    if abs(lat)>89.8 or any(abs(a[0]-b[0])>180 for a,b in zip(ring,ring[1:])):raise ValueError('Review polygon crosses antimeridian or pole; choose smaller radius')
    features={'type':'FeatureCollection','features':[{'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':{'kind':'selected coordinate'}},{'type':'Feature','geometry':{'type':'Polygon','coordinates':[ring]},'properties':{'kind':'assumed review area','radius_m':radius}}]}
    csvfile=io.StringIO();w=csv.DictWriter(csvfile,fieldnames=list(result['daily'][0]));w.writeheader();w.writerows(result['daily'])
    files={'review-area.dxf':dxf,'review-area.geojson':json.dumps(features,indent=2),'projection.wkt':crs.to_wkt(),'runoff.csv':csvfile.getvalue(),'scenario.json':json.dumps(result,indent=2),'evidence-client-snapshot.json':json.dumps({'warning':'Client-supplied snapshot; integrity hashes are not provider authentication','snapshot':payload.get('evidence_snapshot')},indent=2),'review.txt':'DRAFT — NOT CERTIFIED\n'+role+'\n'+'\n'.join(ROLES[role])+'\n'+result['warning']+'\nNo CNC toolpath: requires approved geometry, stock, material, machine, tool, workholding and independent CAM collision verification.'}
    manifest={'generated_utc':now(),'role':role,'checks':{'dxf_reopened_audited':True,'coordinate_roundtrip':True,'units':'metres','engineering_approved':False,'machine_execution_approved':False},'sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in files.items()}}
    files['manifest.json']=json.dumps(manifest,indent=2); buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for k,v in files.items():z.writestr(k,v)
    return buf.getvalue()
