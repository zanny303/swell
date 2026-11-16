"""Location-conditioned flood screening. Original implementation; no fabricated terrain.
Finite-volume, donor-limited diffusive Manning flux, closed outer boundary.
Not a full shallow-water solver or a certified engineering model.
"""
import io,json,hashlib,math,zipfile,datetime,re,os,time,urllib.error
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import numpy as np
import rasterio as rio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin,array_bounds
from rasterio.warp import reproject,Resampling,transform_bounds
from pyproj import CRS,Transformer
from PIL import Image

VERSION='site-diffusive-screen-1.2'
TERRAIN_CACHE_TTL_SECONDS=30*86400
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def num(x,lo,hi):
    if isinstance(x,bool):raise ValueError('Numeric value required')
    x=float(x)
    if not math.isfinite(x) or not lo<=x<=hi:raise ValueError('Value outside allowed bounds')
    return x

def domain(p):
    lat=num(p['lat'],-79,83);lon=num(p['lon'],-179.8,179.8);radius=num(p.get('radius',500),100,2500);dx=num(p.get('dx',20),5,100)
    n=max(3,math.ceil(2*radius/dx));
    if n>128:raise ValueError('Maximum 128 cells per side; increase cell size')
    # metric local UTM; reject cross-dateline/polar requests
    epsg=(32600 if lat>=0 else 32700)+min(60,int((lon+180)//6)+1)
    x,y=Transformer.from_crs(4326,epsg,always_xy=True).transform(lon,lat)
    t=from_origin(x-n*dx/2,y+n*dx/2,dx,dx)
    bbox=array_bounds(n,n,t); wgs=transform_bounds(epsg,4326,*bbox,densify_pts=21)
    return dict(lat=lat,lon=lon,radius=radius,dx=dx,n=n,epsg=epsg,transform=list(t)[:6],bbox=list(bbox),wgs84=list(wgs))

def digest(b):return hashlib.sha256(b).hexdigest()
def storage(root):
    p=Path(root)/'uploads'/'site-twin';p.mkdir(parents=True,exist_ok=True);return p

def fetch_bytes(url,max_bytes=25_000_000,attempts=3,timeout=15):
    """Bounded remote fetch with retries and provider error-body decoding."""
    last=None
    for attempt in range(max(1,int(attempts))):
        try:
            req=Request(url,headers={'User-Agent':'SWELL site twin research/1.2','Accept':'image/tiff, image/*, application/octet-stream, application/json'})
            with urlopen(req,timeout=timeout) as r:
                b=r.read(max_bytes+1);ctype=(r.headers.get('Content-Type') or '').lower()
                if len(b)>max_bytes:raise ValueError('Provider response exceeds size limit')
                if 'json' in ctype or b.lstrip().startswith((b'{',b'[')):
                    try: payload=json.loads(b.decode('utf-8','replace'))
                    except Exception: payload={}
                    if isinstance(payload,dict) and ('error' in payload or 'status' in payload):
                        err=payload.get('error',payload);raise RuntimeError('Elevation provider returned an error: '+str(err)[:700])
                if not b:raise RuntimeError('Elevation provider returned an empty response')
                return b
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,OSError,RuntimeError) as exc:
            last=exc
            if isinstance(exc,urllib.error.HTTPError) and 400<=exc.code<500 and exc.code not in (408,429):
                try: detail=exc.read(700).decode('utf-8','replace')
                except Exception: detail=''
                raise RuntimeError(f'Provider HTTP {exc.code}: {detail or exc.reason}') from None
            if attempt+1<attempts:time.sleep(.5*(2**attempt))
        except ValueError:
            raise
    raise RuntimeError(f'Provider request failed after {attempts} attempts: {last}') from None

def _site_response(meta,a,key,cache_status=None):
    d={k:meta[k] for k in ('lat','lon','radius','dx','n','epsg','transform','bbox','wgs84')}
    rows,cols=np.indices(a.shape);xx=d['transform'][2]+(cols+.5)*d['dx'];yy=d['transform'][5]-(rows+.5)*d['dx'];ll,lt=Transformer.from_crs(d['epsg'],4326,always_xy=True).transform(xx,yy)
    return {**meta,'id':key,'cache_status':cache_status,'elevation':a.round(3).tolist(),'cell_coordinates':np.stack([lt,ll],axis=-1).round(7).tolist()}

def acquire(p,root,raw=None):
    d=domain(p);source='User-supplied DEM; provenance and datum declared by user';url=None
    request_key=digest(json.dumps(d,sort_keys=True).encode())
    index_path=storage(root)/'request-index.json'
    if raw is None and not p.get('refresh'):
        try:
            index=json.loads(index_path.read_text()) if index_path.exists() else {};record=index.get(request_key,{})
            cached_id=record.get('id');cached_at=datetime.datetime.fromisoformat(record.get('cached_utc',''))
            age=(datetime.datetime.now(datetime.timezone.utc)-cached_at).total_seconds()
            if cached_id and 0<=age<TERRAIN_CACHE_TTL_SECONDS:
                meta,a=load(root,cached_id)
                if (storage(root)/cached_id/'original.tif').is_file():return _site_response(meta,a,cached_id,'cached')
        except (ValueError,KeyError,OSError,TypeError):pass
    upstream=None
    if raw is None:
        usgs_error=None
        if 18<=d['lat']<=72 and -180<d['lon']<-60:
            url='https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage?'+urlencode({'bbox':','.join(map(str,d['bbox'])),'bboxSR':d['epsg'],'imageSR':d['epsg'],'size':f"{d['n']},{d['n']}",'format':'tiff','pixelType':'F32','interpolation':'RSP_BilinearInterpolation','adjustAspectRatio':'false','f':'image'})
            try:
                raw=fetch_bytes(url)
                with MemoryFile(raw) as mf,mf.open() as src:
                    if not src.crs or src.count!=1:raise ValueError('Invalid 3DEP raster')
                    probe=np.full((d['n'],d['n']),np.nan,dtype='float64');reproject(rio.band(src,1),probe,src_transform=src.transform,src_crs=src.crs,src_nodata=src.nodata,dst_transform=rio.Affine(*d['transform']),dst_crs=d['epsg'],dst_nodata=np.nan,resampling=Resampling.bilinear)
                    if not np.isfinite(probe).all():raise ValueError('Incomplete 3DEP coverage')
                source='USGS 3DEP elevation service; resampled analysis grid, not native resolution';datum='USGS 3DEP mosaic; vertical datum varies by source and is not independently verified for this export'
            except Exception as exc:usgs_error=str(exc);raw=None
        if raw is None:
            from global_dem import acquire as global_acquire
            try:raw,res,upstream=global_acquire(d,fetch_bytes)
            except Exception as exc:raise RuntimeError(f'No usable real elevation: USGS {usgs_error or "outside coverage"}; Copernicus {exc}. Upload a georeferenced local DEM.') from None
            url=upstream[0]['url'];source=f'Copernicus GLO-{res} DSM (nominal {res} m; buildings and vegetation included). Resampled, not bare-earth terrain; limited flood-screening suitability.';datum='Copernicus EGM2008 geoid; not independently verified for this export'
    else:
        datum=str(p.get('datum','')).strip()
        if not datum or not p.get('meters'):raise ValueError('Declare DEM vertical datum and confirm elevations in metres')
    try:
        with MemoryFile(raw) as mf, mf.open() as src:
            if not src.crs or src.count!=1 or src.width*src.height>100_000_000:raise ValueError('Expected bounded single-band georeferenced DEM')
            if src.units[0] and src.units[0].lower() not in ('m','meter','metre','meters','metres'):raise ValueError('DEM units are not metres')
            a=np.full((d['n'],d['n']),np.nan,dtype='float64')
            reproject(rio.band(src,1),a,src_transform=src.transform,src_crs=src.crs,src_nodata=src.nodata,dst_transform=rio.Affine(*d['transform']),dst_crs=d['epsg'],dst_nodata=np.nan,resampling=Resampling.bilinear)
            native={'crs':str(src.crs),'pixel_size':list(src.res),'units':str(src.units[0] or 'not tagged'),'bounds':list(src.bounds),'nodata':src.nodata}
    except Exception as exc:
        raise ValueError('The elevation service did not return a readable georeferenced GeoTIFF. Try again or upload a local DEM. Details: '+str(exc)) from None
    valid=np.isfinite(a)
    if not valid.all():raise ValueError(f'DEM coverage is only {valid.mean():.1%} of the requested grid. The provider may not cover this location; no synthetic cells were filled.')
    if np.min(a)<-1000 or np.max(a)>10000:raise ValueError('DEM contains invalid elevations; no filling or invented terrain')
    meta={**d,'source':source,'source_url':url,'source_sha256':digest(raw),'retrieved_utc':stamp(),'vertical_datum':datum,'native_response':native,'classification':'OBSERVED TERRAIN / user declaration unverified' if url is None else 'PROVIDER TERRAIN / native resolution and datum not verified'}
    if upstream:meta['upstream_tiles']=upstream;meta['native_response']['nominal_posting_m']=res
    key=digest(json.dumps([d,digest(raw),datum],sort_keys=True).encode());folder=storage(root)/key;folder.mkdir(exist_ok=True)
    (folder/'original.tif').write_bytes(raw);np.save(folder/'elevation.npy',a);(folder/'meta.json').write_text(json.dumps(meta,indent=2))
    if url is not None:
        try:
            index=json.loads(index_path.read_text()) if index_path.exists() else {};index[request_key]={'id':key,'cached_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};tmp=index_path.with_suffix('.tmp');tmp.write_text(json.dumps(index,indent=2));tmp.replace(index_path)
        except OSError:pass
    return _site_response(meta,a,key,'downloaded' if url else 'uploaded')

def load(root,key):
    if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key):raise ValueError('Invalid site ID')
    f=storage(root)/key;return json.loads((f/'meta.json').read_text()),np.load(f/'elevation.npy',allow_pickle=False)

def imagery(root,key):
    from urllib.parse import urlparse
    d,z=load(root,key);url='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export?'+urlencode({'bbox':','.join(map(str,d['bbox'])),'bboxSR':d['epsg'],'imageSR':d['epsg'],'size':'1024,1024','format':'jpg','f':'json'})
    meta=json.loads(fetch_bytes(url,2_000_000));extent=meta['extent'];sr=extent.get('spatialReference',{});returned=[extent[k] for k in ('xmin','ymin','xmax','ymax')]
    if d['epsg'] not in (sr.get('wkid'),sr.get('latestWkid')) or any(abs(x-y)>d['dx']/4 for x,y in zip(returned,d['bbox'])) or (meta.get('width'),meta.get('height'))!=(1024,1024):raise ValueError('Aerial imagery registration mismatch')
    image_url=meta['href'];parsed=urlparse(image_url)
    if parsed.scheme!='https' or not parsed.hostname or not (parsed.hostname=='arcgisonline.com' or parsed.hostname.endswith('.arcgisonline.com')):raise ValueError('Unexpected aerial image host')
    b=fetch_bytes(image_url);im=Image.open(io.BytesIO(b));im.load()
    if im.size!=(1024,1024):raise ValueError('Unexpected image dimensions')
    buf=io.BytesIO();im.convert('RGB').save(buf,'JPEG',quality=94);return buf.getvalue()

def simulate(z,dx,rain,capacity,drain,roughness=.04,suction_deficit_m=0.,dt=30.,outlet=None):
    """Depth-based diffusive routing: positive downhill flux in head, Manning friction.
    Outgoing volumes limited jointly to donor storage. Closed boundaries. Sources/sinks explicit.
    No momentum, rivers, sewer network, or subsurface pressure. Timesteps capped at 30 s.
    """
    z=np.asarray(z,dtype=float);h=np.zeros_like(z);cap=np.broadcast_to(capacity,z.shape);dr=np.broadcast_to(drain,z.shape);area=dx*dx
    if not np.isfinite(z).all() or min(dx,roughness)<=0 or not np.isfinite(cap).all() or not np.isfinite(dr).all() or np.any(cap<0) or np.any(dr<0):raise ValueError('Invalid solver inputs')
    if dt not in (30.,15.,10.,5.):raise ValueError('Unsupported timestep')
    if outlet is not None:
        row,col=int(outlet['row']),int(outlet['col']);stage=float(outlet['stage_m'])
        if not (0<=row<z.shape[0] and 0<=col<z.shape[1] and (row in (0,z.shape[0]-1) or col in (0,z.shape[1]-1))) or not math.isfinite(stage):raise ValueError('Outlet must be a boundary cell with finite external water elevation')
    total=inf=removed=outflow=0.;peak=h.copy();frames=[];mass=[];steps=int(3600/dt);F=np.zeros_like(h);limited=faces=0
    for r in rain:
        for _ in range(steps):
            add=r/1000/steps;h+=add;total+=add*h.size*area
            if suction_deficit_m>0:
                # Sharp wetting-front Green-Ampt integral with nonnegative available water.
                # For a continuous event, solve the ponded capacity and cap by available water.
                A=suction_deficit_m;target=cap/1000/steps;low=np.zeros_like(h);high=h.copy();
                possible=(h-A*np.log1p(h/(F+A)))<=target
                for _bisect in range(14):
                    mid=(low+high)*.5; ok=(mid-A*np.log1p(mid/(F+A)))<=target
                    low=np.where(ok,mid,low);high=np.where(ok,high,mid)
                take=np.where(cap<=0,0,np.where(possible,h,low))
            else:take=np.minimum(h,cap/1000/steps)
            h-=take;F+=take;inf+=take.sum()*area
            take=np.minimum(h,dr/1000/steps);h-=take;removed+=take.sum()*area
            head=z+h
            # square-grid face flux, from higher water surface, only above higher bed crest.
            def flow(a,b,za,zb):
                diff=a-b; depth=np.maximum(0,np.maximum(a,b)-np.maximum(za,zb));raw=depth**(5/3)*np.sqrt(np.abs(diff)/dx)/roughness*dx*dt/area
                # Limit head equalization per face to 1/8 difference (up to four neighbours).
                nonlocal limited,faces
                faces+=int(np.count_nonzero(raw));limited+=int(np.count_nonzero(raw>np.abs(diff)/8+1e-12));return np.sign(diff)*np.minimum(raw,np.abs(diff)/8)
            qx=flow(head[:,:-1],head[:,1:],z[:,:-1],z[:,1:]);qy=flow(head[:-1,:],head[1:,:],z[:-1,:],z[1:,:]);out=np.zeros_like(h)
            out[:,:-1]+=np.maximum(qx,0);out[:,1:]+=np.maximum(-qx,0);out[:-1,:]+=np.maximum(qy,0);out[1:,:]+=np.maximum(-qy,0)
            # additionally limit transfer to avoid overshoot in a single step (screening discretization)
            scale=np.minimum(1,np.divide(h*.25,out,out=np.ones_like(h),where=out>0));qx*=np.where(qx>=0,scale[:,:-1],scale[:,1:]);qy*=np.where(qy>=0,scale[:-1,:],scale[1:,:]);h[:,:-1]-=qx;h[:,1:]+=qx;h[:-1,:]-=qy;h[1:,:]+=qy
            if np.min(h)<-1e-10:raise ArithmeticError('Negative depth')
            if outlet is not None:
                # One-way outlet to specified downstream stage; no river inflow. Face width = dx.
                head_here=z[row,col]+h[row,col];delta=max(0,head_here-stage);wet=max(0,head_here-max(z[row,col],stage));q=wet**(5/3)*math.sqrt(delta/(dx/2))/roughness*dt/dx
                take=min(h[row,col],q,delta/4);h[row,col]-=take;outflow+=take*area
            peak=np.maximum(peak,h)
        stored=float(h.sum()*area);err=total-inf-removed-outflow-stored
        if abs(err)>max(1e-6,total*1e-9):raise ArithmeticError('Water budget failed')
        frames.append(h.copy());mass.append({'rain_m3':total,'infiltrated_m3':float(inf),'drained_m3':float(removed),'boundary_outflow_m3':float(outflow),'stored_m3':stored,'balance_error_m3':float(err),'max_depth_m':float(h.max()),'wet_area_m2':float(np.count_nonzero(h>=.05)*area),'limited_face_fraction':limited/max(1,faces)})
    return np.array(frames),peak,mass

def solve(model,z,dx,rain,capacity,drain,roughness=.04,suction_deficit_m=0.,dt=30.,outlet=None):
    if model=='momentum':
        from shallow_water import simulate as momentum
        return momentum(z,dx,rain,capacity,drain,roughness,suction_deficit_m,dt,outlet)
    if model!='diffusive':raise ValueError('Unknown physics solver')
    return simulate(z,dx,rain,capacity,drain,roughness,suction_deficit_m,dt,outlet)

def run(p,root):
    d,z=load(root,p['id']);rain=p['rain_mm_h'];
    if not isinstance(rain,list) or not 1<=len(rain)<=72:raise ValueError('Supply 1–72 hourly rainfall values')
    rain=[num(x,0,250) for x in rain];base=num(p.get('infiltration',5),0,100);rough=num(p.get('roughness',.04),.01,.3)
    suction=num(p.get('suction_mm',0),0,1000);deficit=num(p.get('moisture_deficit',0),0,.8);A=suction*deficit/1000
    c=np.full(z.shape,base);dr=np.zeros_like(z);edits=p.get('edits',[])
    if not isinstance(edits,list) or len(edits)>z.size*2:raise ValueError('Too many edits')
    for e in edits:
        row,col=int(e['row']),int(e['col']);
        if not (0<=row<z.shape[0] and 0<=col<z.shape[1]):raise ValueError('Edit outside domain')
        if e['kind']=='drain':dr[row,col]=num(e['rate'],0,250)
        elif e['kind']=='infiltration':c[row,col]=num(e['rate'],0,100)
        else:raise ValueError('Unknown edit')
    forcing=None;start=p.get('event_start_utc') or None
    if p.get('forecast_id'):
        fid=p['forecast_id']
        if not isinstance(fid,str) or not re.fullmatch('[0-9a-f]{64}',fid):raise ValueError('Invalid forecast ID')
        forcing=json.loads((storage(root)/'forecasts'/f'{fid}.json').read_text())
        if abs(forcing['lat']-d['lat'])>1e-7 or abs(forcing['lon']-d['lon'])>1e-7 or [r['rain_mm'] for r in forcing['rows']]!=rain:raise ValueError('Forecast does not match site/rainfall; switch to manual forcing')
        start=(datetime.datetime.fromisoformat(forcing['rows'][0]['utc'])-datetime.timedelta(hours=1)).isoformat()
    if start:
        t=datetime.datetime.fromisoformat(start)
        if t.tzinfo is None:raise ValueError('Event start must include timezone offset')
        start=t.astimezone(datetime.timezone.utc).isoformat()
    outlet=p.get('outlet')
    if outlet is not None:
        if not isinstance(outlet,dict) or not d['vertical_datum'] or d['vertical_datum']!=outlet.get('datum') or 'not independently verified' in d['vertical_datum']:raise ValueError('Outlet stage must share declared, checked DEM datum')
        outlet={'row':int(outlet['row']),'col':int(outlet['col']),'stage_m':num(outlet['stage_m'],-1000,10000),'datum':outlet['datum']}
    evidence=None
    if p.get('evidence_id'):
        eid=p['evidence_id']
        if not isinstance(eid,str) or not re.fullmatch('[0-9a-f]{64}',eid):raise ValueError('Invalid evidence snapshot ID')
        evidence=json.loads((storage(root)/p['id']/'evidence'/(eid+'.json')).read_text())
        if evidence.get('site_id')!=p['id'] or evidence.get('snapshot_id')!=eid:raise ValueError('Evidence snapshot does not match site')
    solver=p.get('solver','diffusive')
    inputs={'solver':solver,'local_evidence':evidence,'outlet':outlet,'rain_mm_h':rain,'infiltration':base,'roughness':rough,'suction_mm':suction,'moisture_deficit':deficit,'edits':edits,'forcing':forcing,'event_start_utc':start}
    run_key=digest(json.dumps([VERSION,p['id'],inputs],sort_keys=True).encode())
    b,bp,bm=solve(solver,z,d['dx'],rain,base,0,rough,A,outlet=outlet);s,sp,sm=solve(solver,z,d['dx'],rain,c,dr,rough,A,outlet=outlet)
    overlay=publish_depth(root,d,s[-1],p['id'],len(rain),run_key)
    result={'earth_overlay':overlay,'run_id':run_key,'model':VERSION if solver=='diffusive' else 'SWE-hydrostatic-Rusanov-1.0','site':{**d,'id':p['id']},'inputs':inputs,'baseline':bm,'scenario':sm,'baseline_frames':b.round(5).tolist(),'scenario_frames':s.round(5).tolist(),'baseline_peak':bp.tolist(),'scenario_peak':sp.tolist(),'boundary':('one-way specified-stage outlet; no external inflow' if outlet else 'closed — rainfall ponding screening, not river flood prediction'),'warning':'Uncalibrated spatial screening. Constant or continuous-event Green-Ampt infiltration and idealized drain sinks; no momentum, pipe capacity, external river inflow, groundwater or structural condition inference. Verify resolution, datum, roughness, convergence and observations before use.'}
    if solver=='momentum':result['warning']='Experimental 2D shallow-water finite-volume momentum solver; hydrostatic reconstruction, reflective boundaries, constant infiltration and idealized sink. No field validation, river inflow, sewer capacity or certified engineering. Use grid and timestep sensitivity and observations.'
    (storage(root)/'results'/run_key/'result.json').write_text(json.dumps(result));return result

def load_result(root,key):
    if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key):raise ValueError('Invalid saved run ID')
    r=json.loads((storage(root)/'results'/key/'result.json').read_text())
    if r.get('run_id')!=key:raise ValueError('Saved run ID mismatch')
    return r

def pack(p,root):
    result=load_result(root,p['result_id']) if p.get('result_id') else run(p,root);d=result['site'];profile=dict(driver='GTiff',height=d['n'],width=d['n'],count=1,dtype='float32',crs=d['epsg'],transform=rio.Affine(*d['transform']),compress='deflate');files={}
    for name,k in [('baseline-peak-depth.tif','baseline_peak'),('intervention-peak-depth.tif','scenario_peak')]:
        with MemoryFile() as mem:
            with mem.open(**profile) as dst:dst.write(np.array(result[k],dtype='float32'),1);dst.set_band_unit(1,'m')
            files[name]=mem.read()
    # Actual projected modeled wet cells, not fabricated surveyed geometry.
    import ezdxf
    from rasterio.features import shapes
    a=(np.asarray(result['scenario_peak'])>=.05).astype('uint8');doc=ezdxf.new('R2010');doc.units=6;doc.layers.new('MODEL_WET_5CM');m=doc.modelspace();features=[];inv=Transformer.from_crs(d['epsg'],4326,always_xy=True)
    for geom,val in shapes(a,mask=a.astype(bool),transform=rio.Affine(*d['transform'])):
        for ring in geom['coordinates']:m.add_lwpolyline(ring,close=True,dxfattribs={'layer':'MODEL_WET_5CM'})
        features.append({'type':'Feature','geometry':{'type':'Polygon','coordinates':[[list(inv.transform(x,y)) for x,y in ring] for ring in geom['coordinates']]},'properties':{'threshold_m':.05,'status':'UNCALIBRATED MODEL'}})
    m.add_text('DRAFT MODEL WET EXTENT - NOT SURVEYED OR APPROVED',dxfattribs={'height':d['dx'],'insert':(d['bbox'][0],d['bbox'][3])});f=io.StringIO();doc.write(f);txt=f.getvalue();audit=ezdxf.read(io.StringIO(txt)).audit()
    if audit.errors or audit.fixes:raise ValueError('DXF validation failed')
    files['modeled-wet-extent.dxf']=txt.encode();files['modeled-wet-extent.geojson']=json.dumps({'type':'FeatureCollection','features':features}).encode();files['projection.wkt']=CRS.from_epsg(d['epsg']).to_wkt().encode()
    role=p.get('role','engineer');from location_services import ROLES
    if role not in ROLES:raise ValueError('Invalid role')
    files['review.txt']=(f'DRAFT {role}\n{result["warning"]}\n'+ '\n'.join(ROLES[role])+'\nNo approved design or G-code.').encode();files['scenario.json']=json.dumps(result).encode()
    import csv,html
    f=io.StringIO();w=csv.writer(f);w.writerow(['hour','rain_mm','baseline_stored_m3','scenario_stored_m3','baseline_peak_at_hour_m','scenario_peak_at_hour_m','scenario_balance_error_m3','baseline_boundary_outflow_m3','scenario_boundary_outflow_m3']);w.writerows([[i+1,result['inputs']['rain_mm_h'][i],b['stored_m3'],s['stored_m3'],b['max_depth_m'],s['max_depth_m'],s['balance_error_m3'],b.get('boundary_outflow_m3',0),s.get('boundary_outflow_m3',0)] for i,(b,s) in enumerate(zip(result['baseline'],result['scenario']))]);files['hourly-budget.csv']=f.getvalue().encode()
    b=result['baseline'][-1];s=result['scenario'][-1];esc=html.escape
    files['review-report.html']=(f'<!doctype html><meta charset="utf-8"><title>SWELL review</title><style>body{{font:16px/1.6 system-ui;max-width:850px;margin:40px auto;padding:20px}}h1{{color:#087e78}}p{{max-width:80ch}}</style><h1>SWELL | Site review</h1><h2>DRAFT — NOT APPROVED · {esc(role)}</h2><p>GPS {d["lat"]}, {d["lon"]}; EPSG:{d["epsg"]}; grid {d["n"]} × {d["n"]}, {d["dx"]} m. Terrain source: {esc(d["source"])}. Vertical datum: {esc(d["vertical_datum"])}.</p><h2>Final hour water budget</h2><p>Baseline stored {b["stored_m3"]:.2f} m³; intervention stored {s["stored_m3"]:.2f} m³; infiltrated {s["infiltrated_m3"]:.2f} m³; drained {s["drained_m3"]:.2f} m³; residual {s["balance_error_m3"]:.3g} m³.</p><h2>Review requirements</h2><ul>'+''.join('<li>'+esc(x)+'</li>' for x in ROLES[role])+'</ul><p>'+esc(result['warning'])+'</p><p>Technical audit is not approval. Use official warnings. No construction or CNC instructions.</p>').encode()
    # Include comparison records actually generated by the server for this run.
    comparisons=storage(root)/'results'/result['run_id']/'comparisons'
    if comparisons.exists():
        for f in sorted(comparisons.glob('*.json')):files['comparisons/'+f.name]=f.read_bytes()
    reviews=storage(root)/'results'/result['run_id']/'reviews'
    if reviews.exists():
        for f in sorted(reviews.glob('*.json')):files['reviews/'+f.name]=f.read_bytes()
    if result['inputs'].get('local_evidence'):files['location-evidence.json']=json.dumps(result['inputs']['local_evidence']).encode()
    files['manifest.json']=json.dumps({'model':result['model'],'run_id':result['run_id'],'dxf_audit_passed':True,'mass_balance_passed':True,'engineering_approved':False,'sha256':{k:digest(v) for k,v in files.items()}}).encode();buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as f:
        for k,v in files.items():f.writestr(k,v)
    return buf.getvalue()

def hourly_forecast(p,root=None):
    from earth_services import get
    lat=num(p['lat'],-90,90);lon=num(p['lon'],-180,180)
    url='https://api.open-meteo.com/v1/forecast?'+urlencode({'latitude':lat,'longitude':lon,'models':'ecmwf_aifs025_single','hourly':'precipitation','forecast_days':4,'timezone':'GMT','precipitation_unit':'mm'})
    raw,t,status=get(url,600);d=json.loads(raw);a=d['hourly'];unit=d['hourly_units']['precipitation']
    if unit!='mm' or len(a['time'])!=len(a['precipitation']):raise ValueError('Invalid forecast response')
    now=datetime.datetime.now(datetime.timezone.utc);rows=[]
    for ts,r in zip(a['time'],a['precipitation']):
        when=datetime.datetime.fromisoformat(ts).replace(tzinfo=datetime.timezone.utc)
        if when<=now:continue
        if rows and when!=datetime.datetime.fromisoformat(rows[-1]['utc'])+datetime.timedelta(hours=1):break
        if r is None:break
        rows.append({'utc':when.isoformat(),'rain_mm':num(r,0,250)})
        if len(rows)==72:break
    if not rows:raise ValueError('No continuous hourly AIFS precipitation')
    result={'source':'ECMWF AIFS via Open-Meteo, coarse weather grid; hourly interpolated by provider if applicable','retrieved_utc':t,'status':status,'grid':[d.get('latitude'),d.get('longitude')],'issue_time':None,'lat':lat,'lon':lon,'rows':rows,'warning':'Conditional weather forcing; forecast issue time unavailable. Not local rainfall measurement.'}
    if root is not None:
        result['forecast_id']=digest(json.dumps(result,sort_keys=True).encode());folder=storage(root)/'forecasts';folder.mkdir(exist_ok=True);(folder/(result['forecast_id']+'.json')).write_text(json.dumps(result))
    return result

def evidence(p):
    from earth_services import get,CMR
    d=domain(p);b=','.join(map(str,d['wgs84']));families={'water':'OPERA_L3_DSWX-S1_V1','optical_water':'OPERA_L3_DSWX-HLS_V1','displacement':'OPERA_L3_DISP-S1_V1','nisar':'NISAR_L2_GCOV_V1','nisar_gunw':'NISAR_L2_GUNW_V1'};out={}
    for k,v in families.items():
        try:
            params={'page_size':8,'has_granules':'true'};params['short_name']=v
            url=CMR+'collections.json?'+urlencode(params);raw,t,status=get(url,3600);cols=json.loads(raw)['feed']['entry'];rows=[]
            for c in cols[:3]:
                g=CMR+'granules.json?'+urlencode({'collection_concept_id':c['id'],'bounding_box':b,'page_size':3,'sort_key[]':'-start_date'});raw,ts,st=get(g);rows.extend({'id':x.get('id'),'title':x.get('title'),'collection':c['id'],'start':x.get('time_start'),'end':x.get('time_end'),'links':[l['href'] for l in x.get('links',[]) if str(l.get('href','')).startswith('https://')][:8]} for x in json.loads(raw)['feed']['entry'])
            out[k]={'status':'catalog only','retrieved_utc':t,'granules':rows,'collection_query':url}
        except Exception:out[k]={'status':'unavailable','granules':[]}
    return out

def compare_water(p,root,raw):
    """Compare coincident modeled depth to a classified OPERA B01/WTR surface-water image.
    Clear classes only; no converting SAR intensity to depth; no automatic flood attribution.
    Deliberately evaluated at the coarser of source and simulation grid spacing.
    """
    r=load_result(root,p['result_id']);d=r['site'];_,z=load(root,d['id']);product=p['product'];observed=datetime.datetime.fromisoformat(p['observed_utc']);start=r['inputs']['event_start_utc'];hour=int(p['hour']);
    if not start or not 1<=hour<=len(r['baseline_frames']):raise ValueError('Saved run needs a dated event and valid forecast hour')
    modeled=datetime.datetime.fromisoformat(start)+datetime.timedelta(hours=hour)
    if observed.tzinfo is None or modeled.tzinfo is None or abs((observed-modeled).total_seconds())>3600:raise ValueError('Declare acquisition and modeled times with offsets; within 1 hour required')
    classes={'DSWx-S1':(0,1,3),'DSWx-HLS':(0,1,2),'binary':(0,1)}
    if product not in classes:raise ValueError('Unknown water product')
    with MemoryFile(raw) as mem,mem.open() as src:
        if not src.crs or src.count!=1 or src.width*src.height>100_000_000:raise ValueError('Expected single-band georeferenced water-class raster')
        # compare on model grid only when no finer than native observation resolution (for projected metric data)
        if not src.crs.is_projected or src.crs.linear_units not in ('metre','meter','Meter','Metre'):raise ValueError('Provide projected metre-based water raster for comparison')
        if max(src.res)>d['dx']*1.01:raise ValueError('Model grid is finer than observation; reload terrain at coarser spacing before comparison')
        a=np.full(z.shape,255,dtype='float32');reproject(rio.band(src,1),a,src_crs=src.crs,src_transform=src.transform,src_nodata=src.nodata,dst_crs=d['epsg'],dst_transform=rio.Affine(*d['transform']),dst_nodata=255,resampling=Resampling.nearest)
    valid=np.isin(a,classes[product]);water=(a==1); # exclude ambiguous / partial or vegetation in strict comparison
    valid &= np.isin(a,[0,1]);
    if valid.sum()<10:raise ValueError('Insufficient clear overlapping pixels')
    depth=np.asarray(r['baseline_frames'][hour-1],dtype=float)
    if depth.shape!=z.shape or not np.isfinite(depth).all() or np.any(depth<0):raise ValueError('Invalid modeled depth grid')
    pred=depth>=num(p.get('threshold_m',.05),.001,2);tp=int((valid&water&pred).sum());fp=int((valid&~water&pred).sum());fn=int((valid&water&~pred).sum());tn=int((valid&~water&~pred).sum())
    report={'run_id':r['run_id'],'hour':hour,'product':product,'source_sha256':digest(raw),'observed_utc':observed.isoformat(),'modeled_utc':modeled.isoformat(),'clear_pixels':int(valid.sum()),'domain_coverage':float(valid.mean()),'tp':tp,'fp':fp,'fn':fn,'tn':tn,'iou':tp/(tp+fp+fn) if tp+fp+fn else None,'warning':'Raster product/date user-declared; baseline from a saved server run; not independent source authentication. Open water only, ambiguous/vegetation/cloud/nodata excluded. Existing permanent water is not distinguished from flood water. Not a validation certificate.'}
    folder=storage(root)/'results'/r['run_id']/'comparisons';folder.mkdir(exist_ok=True);key=digest(json.dumps(report,sort_keys=True).encode());(folder/(key+'.json')).write_text(json.dumps(report));return report


def publish_depth(root,d,depth,site_id,hour,key):
    """Reproject the computed depth raster; write transparent WGS84 map layer with bounds."""
    from rasterio.transform import from_bounds
    n= min(512,max(128,d['n']*2));arr=np.full((n,n),np.nan,dtype='float32');reproject(np.asarray(depth,dtype='float32'),arr,src_transform=rio.Affine(*d['transform']),src_crs=d['epsg'],dst_transform=from_bounds(*d['wgs84'],n,n),dst_crs=4326,dst_nodata=np.nan,resampling=Resampling.nearest)
    valid=np.isfinite(arr)&(arr>=.001);v=np.nan_to_num(arr,nan=0);rgba=np.zeros((n,n,4),dtype='uint8');rgba[...,0]=28;rgba[...,1]=np.clip(180-100*v,40,180).astype('uint8');rgba[...,2]=245;rgba[...,3]=np.where(valid,np.minimum(230,60+v*400),0).astype('uint8')
    folder=storage(root)/'results'/key;folder.mkdir(parents=True,exist_ok=True);Image.fromarray(rgba).save(folder/'depth.png');meta={'id':key,'site_id':site_id,'wgs84':d['wgs84'],'lat':d['lat'],'lon':d['lon'],'hour':hour,'image':'/uploads/site-twin/results/'+key+'/depth.png','warning':'UNCALIBRATED modeled depth, final hour, not observed water. Blue opacity increases with depth.'};(folder/'metadata.json').write_text(json.dumps(meta));return meta

def register_photo(root,key,raw,acquired):
    d,z=load(root,key);acquired=str(acquired or 'unknown')[:120]
    with MemoryFile(raw) as mem,mem.open() as src:
        from rasterio.enums import ColorInterp
        if not src.crs or src.width*src.height>100_000_000 or not all(c in src.colorinterp for c in (ColorInterp.red,ColorInterp.green,ColorInterp.blue)) or any(t!='uint8' for t in src.dtypes):raise ValueError('Expected georeferenced uint8 RGB GeoTIFF')
        size=1024;from rasterio.transform import from_bounds
        tr=from_bounds(*d['bbox'],size,size);rgb=np.zeros((3,size,size),dtype='uint8');valid=np.zeros((size,size),dtype='uint8');reproject(src.dataset_mask(),valid,src_transform=src.transform,src_crs=src.crs,dst_transform=tr,dst_crs=d['epsg'],dst_nodata=0,resampling=Resampling.nearest)
        if np.mean(valid>0)<.99:raise ValueError('Imagery must cover at least 99% of the registered site')
        for i,c in enumerate((ColorInterp.red,ColorInterp.green,ColorInterp.blue)):reproject(rio.band(src,src.colorinterp.index(c)+1),rgb[i],src_transform=src.transform,src_crs=src.crs,src_nodata=src.nodata,dst_transform=tr,dst_crs=d['epsg'],resampling=Resampling.bilinear)
        native={'crs':str(src.crs),'pixel_size':list(src.res)}
    folder=storage(root)/key/'imagery';folder.mkdir(exist_ok=True);sha=digest(raw);Image.fromarray(np.moveaxis(rgb,0,-1)).save(folder/(sha+'.png'));(folder/(sha+'.tif')).write_bytes(raw);meta={'source':'User-provided imagery; source and acquisition date not independently authenticated','acquisition_declared':acquired,'sha256':sha,'native':native,'image':'/uploads/site-twin/'+key+'/imagery/'+sha+'.png'};(folder/(sha+'.json')).write_text(json.dumps(meta));return meta
