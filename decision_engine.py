"""Evidence-bound site analysis. Never labels screening as design approval."""
import csv, io, json, math, hashlib, datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from pyproj import Transformer
import site_twin as st

VERSION='decision-evidence-1.0'

def numerical_review(payload, root):
    """Replay exact input fields at two timesteps; test boundary assumption independently."""
    r=st.load_result(root,payload['result_id']);d,z=st.load(root,r['site']['id']);i=r['inputs'];rain=i['rain_mm_h']; c=np.full(z.shape,i['infiltration']);dr=np.zeros_like(z)
    for e in i['edits']:
        (dr if e['kind']=='drain' else c)[e['row'],e['col']]=e['rate']
    if z.size*len(rain)>80_000:raise ValueError('Review budget exceeded; use smaller area or event')
    A=i['suction_mm']*i['moisture_deficit']/1000
    frames,peak,mass=st.solve(i.get('solver','diffusive'),z,d['dx'],rain,c,dr,i['roughness'],A,dt=15.,outlet=i.get('outlet'))
    old=np.asarray(r['scenario_peak']);err=np.abs(peak-old);wet=old>=.05;wet2=peak>=.05;union=np.count_nonzero(wet|wet2)
    out={'run_id':r['run_id'],'method':'30 s vs 15 s timestep sensitivity; no spatial convergence or field validation','peak_depth_mae_m':float(err.mean()),'peak_depth_max_difference_m':float(err.max()),'wet_extent_iou':float(np.count_nonzero(wet&wet2)/union) if union else None,'fine_water_budget_residual_m3':mass[-1]['balance_error_m3'],'fine_limiter_fraction':mass[-1]['limited_face_fraction'],'status':'numerical sensitivity only','engineering_approved':False}
    return save_review(root,r,'numerical',out)

def save_review(root,r,kind,out):
    folder=st.storage(root)/'results'/r['run_id']/'reviews';folder.mkdir(exist_ok=True); out['reviewed_utc']=st.stamp();out['record_id']=st.digest(json.dumps(out,sort_keys=True).encode());(folder/(kind+'-'+out['record_id']+'.json')).write_text(json.dumps(out,indent=2));return out

def cell(d,lon,lat):
    x,y=Transformer.from_crs(4326,d['epsg'],always_xy=True).transform(lon,lat)
    col=math.floor((x-d['transform'][2])/d['dx']);row=math.floor((d['transform'][5]-y)/d['dx'])
    if not (0<=row<d['n'] and 0<=col<d['n']):raise ValueError('Point outside saved site')
    return row,col

def asset_review(p,root):
    """Sample modeled water-surface elevations at actual surveyed points. No structural rating."""
    r=st.load_result(root,p['result_id']);d,z=st.load(root,r['site']['id']);rows=list(csv.DictReader(io.StringIO(p['csv'])))
    if not 1<=len(rows)<=500:raise ValueError('1–500 asset points required')
    datum=p.get('datum','').strip()
    if not datum or datum!=d['vertical_datum'] or 'not independently verified' in datum:raise ValueError('Asset survey and DEM must have matching, declared vertical datum')
    results=[];ids=set()
    for a in rows:
        aid=a['asset_id'].strip();lat=st.num(a['lat'],-90,90);lon=st.num(a['lon'],-180,180);threshold=st.num(a['entry_elevation_m'],-1000,10000)
        if not aid or aid in ids or not a['source'].strip():raise ValueError('Unique asset identifier and source required')
        ids.add(aid);row,col=cell(d,lon,lat);ground=float(z[row,col]);b=float(r['baseline_peak'][row][col]);s=float(r['scenario_peak'][row][col]);db=max(0,ground+b-threshold) if b>0 else 0;ds=max(0,ground+s-threshold) if s>0 else 0
        results.append({'asset_id':aid,'lat':lat,'lon':lon,'source':a['source'],'entry_elevation_m':threshold,'dem_elevation_m':ground,'baseline_depth_above_entry_m':db,'intervention_depth_above_entry_m':ds,'intervention_static_pressure_kpa':9.80665*ds,'status':'modeled exposure; not capacity or damage assessment'})
    return save_review(root,r,'assets',{'run_id':r['run_id'],'survey_sha256':st.digest(p['csv'].encode()),'vertical_datum':datum,'assets':results,'warning':'Point sampling at DEM resolution; no surveyed building geometry, velocity, structural resistance or certification.'})

def soil_review(p,root):
    """One measured 1-D layered profile; constrained strain screening, not coupled FE."""
    r=st.load_result(root,p['result_id']);d,z=st.load(root,r['site']['id']);lat=st.num(p['lat'],-90,90);lon=st.num(p['lon'],-180,180);cell(d,lon,lat)
    rows=list(csv.DictReader(io.StringIO(p['csv'])));out=[];last=0.;total=0.
    if not 1<=len(rows)<=50:raise ValueError('1–50 continuous layers required')
    for a in rows:
        top=st.num(a['top_m'],0,100);bottom=st.num(a['bottom_m'],0,100);theta0=st.num(a['theta_initial'],0,1);theta1=st.num(a['theta_scenario'],0,1);por=st.num(a['porosity'],.01,.9);coef=st.num(a['vertical_strain_per_theta'],0,2)
        if abs(top-last)>1e-6 or bottom<=top or max(theta0,theta1)>por or not a['source'].strip():raise ValueError('Layers must be continuous, sourced and within porosity')
        strain=coef*(theta1-theta0);movement=1000*(bottom-top)*strain;total+=movement;last=bottom;out.append({'top_m':top,'bottom_m':bottom,'material':a['material'],'source':a['source'],'theta_initial':theta0,'theta_scenario':theta1,'porosity':por,'vertical_strain_per_theta':coef,'estimated_movement_mm':movement})
    return save_review(root,r,'soil',{'run_id':r['run_id'],'lat':lat,'lon':lon,'profile_sha256':st.digest(p['csv'].encode()),'layers':out,'estimated_vertical_change_mm':total,'warning':'User-declared lab/field strain coefficient and scenario moisture per layer. One-dimensional free strain approximation; not computed from flood water depth, no stress, pore pressure or foundation constraints, no site-wide extrapolation.'})

SOURCES=[('NASA OPERA','https://www.jpl.nasa.gov/go/opera/products/dswx-product-suite/','Surface water optical SAR flood extent verification, 30 m posting; DSWx observations describe water presence, not water depth or structural damage. Match acquisition time and grid; exclude ambiguous classes.'),('USGS 3DEP','https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer','Elevation terrain DEM bare earth, multiple source resolutions. Confirm vertical datum and native resolution before comparing assets.'),('Landlab OverlandFlow','https://landlab.csdms.io/user_guide/overland_flow_user_guide.html','Hydraulics flood routing requires appropriate boundary conditions; outlet permits outflow, closed edges do not. Test timestep and spatial resolution.'),('NOAA National Water Model','https://water.noaa.gov/about/nwm','River discharge hydrology forecasting needs catchment connectivity and river routing. Rain-only ponding cannot substitute for river inundation.'),('EPA SWMM','https://github.com/USEPA/Stormwater-Management-Model','Stormwater drains pipes sewer hydraulics require actual network geometry and capacity; idealized sink is not a drainage design.'),('NISAR GUNW','https://nisar-docs.asf.alaska.edu/gunw/','Radar phase coherence deformation line of sight, reference frame, orbit and viewing geometry. Do not infer vertical displacement or structural condition from raw phase.'),('NeuralHydrology','https://github.com/neuralhydrology/neuralhydrology','Hydrologic machine learning needs archived forcing, observations and independent chronological holdout evaluation. Abstain outside training domain.')]

def research(p,root):
    """Local extractive retrieval: TF-IDF cosine over curated notes, not generated citations."""
    import re,collections
    query=str(p.get('question','')).strip()[:1000];
    if not query:raise ValueError('Enter a question')
    def tokens(s):return re.findall(r'[a-z0-9]+',s.lower())
    docs=[collections.Counter(tokens(n+' '+v)) for n,u,v in SOURCES];q=collections.Counter(tokens(query));idf={w:math.log((len(docs)+1)/(1+sum(w in d for d in docs)))+1 for w in set(q)|set().union(*docs)}
    def score(d):
        a=sum(q[w]*d[w]*idf[w]**2 for w in q); b=math.sqrt(sum((v*idf[w])**2 for w,v in q.items())*sum((v*idf[w])**2 for w,v in d.items()));return a/b if b else 0
    chosen=sorted(range(len(docs)),key=lambda i:score(docs[i]),reverse=True)[:3];hits=[{'title':SOURCES[i][0],'url':SOURCES[i][1],'curated_note':SOURCES[i][2],'score':score(docs[i])} for i in chosen if score(docs[i])>.06]
    evidence=None
    if p.get('result_id'):
        r=st.load_result(root,p['result_id']);evidence={'run_id':r['run_id'],'coordinates':[r['site']['lat'],r['site']['lon']],'final_baseline':r['baseline'][-1],'final_intervention':r['scenario'][-1],'warning':r['warning']}
    return {'method':'TF-IDF retrieval over curated source notes; not generative LLM or full-text paper retrieval','sources':hits,'saved_run_evidence':evidence,'status':'retrieved evidence' if hits else 'abstain: no relevant indexed sources','engineering_approved':False}


def local_evidence(p,root):
    """Server-side evidence snapshot tied to registered site, retained for reproducibility."""
    import location_services as loc
    d,_=st.load(root,p['id']);record=loc.snapshot({'lat':[str(d['lat'])],'lon':[str(d['lon'])]});record['site_id']=p['id'];record['snapshot_id']=st.digest(json.dumps(record,sort_keys=True).encode());folder=st.storage(root)/p['id']/'evidence';folder.mkdir(exist_ok=True);(folder/(record['snapshot_id']+'.json')).write_text(json.dumps(record,indent=2));return record

def train_point(p,root):
    import hybrid_calibration as hy
    d,_=st.load(root,p['id']);lat=st.num(p['lat'],-90,90);lon=st.num(p['lon'],-180,180);row,col=cell(d,lon,lat);source=str(p.get('source','')).strip()
    if not source:raise ValueError('Declare observation sensor and archived forecast provenance')
    m=hy.train(p['csv'].encode());m.update({'site_id':p['id'],'lat':lat,'lon':lon,'row':row,'col':col,'source':source,'feature_contract':'depth at fixed lead, cumulative rainfall mm through lead, volumetric antecedent moisture fraction; user-declared history contract'})
    m['model_id']=st.digest(json.dumps(m,sort_keys=True).encode());folder=st.storage(root)/p['id']/'models';folder.mkdir(exist_ok=True);(folder/(m['model_id']+'.json')).write_text(json.dumps(m,indent=2));return m

def predict_point(p,root):
    import re,hybrid_calibration as hy
    r=st.load_result(root,p['result_id']);key=p['model_id']
    if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key):raise ValueError('Invalid model identifier')
    m=json.loads((st.storage(root)/r['site']['id']/'models'/(key+'.json')).read_text());hour=st.num(p['hour'],1,len(r['baseline_frames']))
    if not hour.is_integer() or abs(m['forecast_lead_seconds']-hour*3600)>1:raise ValueError('Selected forecast hour does not match model training lead')
    hour=int(hour);moisture=st.num(p['moisture'],0,1);source=str(p.get('moisture_source','')).strip()
    if not source:raise ValueError('Declare antecedent moisture source')
    depth=r['baseline_frames'][hour-1][m['row']][m['col']];rain=sum(r['inputs']['rain_mm_h'][:hour]);answer=hy.predict(m,[depth,rain,moisture]);answer.update({'run_id':r['run_id'],'model_id':key,'model_card':m,'hour':hour,'lat':m['lat'],'lon':m['lon'],'moisture_source':source,'features':[depth,rain,moisture],'classification':'point forecast candidate only; baseline, not intervention; no spatial mass-balance adjustment'})
    return save_review(root,r,'ai-point',answer)
