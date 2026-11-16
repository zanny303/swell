"""Opt-in science review. Existing SWELL solver, data and decision files are never modified."""
from __future__ import annotations
import argparse, hashlib, io, json, math, re, zipfile, ast, sys, threading
from pathlib import Path
import numpy as np

VERSION='assurance-1.0'
THRESHOLD=.05
_REVIEW_LOCK=threading.Lock()

def sha(b):return hashlib.sha256(b).hexdigest()
def plain(x):return json.dumps(x,allow_nan=False,indent=2)
def finite(a):return np.where(np.isfinite(a),a,None).tolist()
def arrays(i,z,edits=None):
    cap=np.full(z.shape,float(i['infiltration']));dr=np.zeros_like(z)
    for e in i['edits'] if edits is None else edits:
        (dr if e['kind']=='drain' else cap)[int(e['row']),int(e['col'])]=float(e['rate'])
    return cap,dr

def spatial(b,s,area):
    b,s=np.asarray(b),np.asarray(s);mask=b>=THRESHOLD;other=s>=THRESHOLD;union=(mask|other).sum();delta=b-s
    return dict(peak_m=float(b.max()),other_peak_m=float(s.max()),peak_change_pct=float(abs(b.max()-s.max())/max(.001,b.max())*100),wet_m2=float(mask.sum()*area),other_wet_m2=float(other.sum()*area),wet_iou=float((mask&other).sum()/union) if union else 1.,depth_rmse_m=float(np.sqrt(np.mean(delta**2))),max_reduction_m=float(delta.max()),max_increase_m=float(-delta.min()),reduced_gt_1cm_m2=float((delta>.01).sum()*area),increased_gt_1cm_m2=float((delta<-.01).sum()*area))

def summary(r):
    i=r['inputs'];a=r['site']['dx']**2;b,s=r['baseline'][-1],r['scenario'][-1];d=b['stored_m3']-s['stored_m3'];ed={(e['row'],e['col']):e['rate'] for e in i['edits'] if e['kind']=='drain'};ceil=sum(ed.values())/1000*a*len(i['rain_mm_h']);capture=s['drained_m3']
    return dict(storage_reduction_m3=d,storage_reduction_pct=d/b['stored_m3']*100 if b['stored_m3'] else None,drain_capacity_ceiling_m3=ceil,captured_m3=capture,capacity_utilization_pct=capture/ceil*100 if ceil else None,**spatial(r['baseline_peak'],r['scenario_peak'],a))

def trial(r,z,dt,edits=None,rough=None):
    import site_twin as st
    i=r['inputs'];c,d=arrays(i,z,edits);args=(i['roughness'] if rough is None else rough,i['suction_mm']*i['moisture_deficit']/1000)
    b,bp,bm=st.solve('diffusive',z,r['site']['dx'],i['rain_mm_h'],i['infiltration'],0,*args,dt=dt,outlet=i.get('outlet'))
    s,sp,sm=st.solve('diffusive',z,r['site']['dx'],i['rain_mm_h'],c,d,*args,dt=dt,outlet=i.get('outlet'))
    return dict(b=b,bp=bp,bm=bm,s=s,sp=sp,sm=sm)

def budget_alternative(r,z):
    # Deterministic control: translate all edits together, preserving exact rates, kind and count.
    edits=r['inputs']['edits'];shape=z.shape;occupied={(e['row'],e['col']) for e in edits}
    if not edits:return None
    shifts=[(dy,dx) for dy in range(-shape[0]+1,shape[0]) for dx in range(-shape[1]+1,shape[1]) if dy or dx]
    shifts.sort(key=lambda p:(-(p[0]**2+p[1]**2),p))
    for dy,dx in shifts:
        q=[{**e,'row':e['row']+dy,'col':e['col']+dx} for e in edits];coords={(e['row'],e['col']) for e in q}
        if not coords&occupied and all(0<=a<shape[0] and 0<=b<shape[1] for a,b in coords):return q
    return None

def convergence(r,z):
    if r['inputs']['solver']!='diffusive' or z.size*len(r['inputs']['rain_mm_h'])>20000:raise ValueError('Use the diffusive solver and at most 20,000 cell-hours.')
    area=r['site']['dx']**2;prev=None;cases=[];last=None
    for dt in [30,15,10,5]:
        t=trial(r,z,float(dt));m=spatial(t['bp'],t['sp'],area);m.update(timestep_s=dt,storage_reduction_m3=t['bm'][-1]['stored_m3']-t['sm'][-1]['stored_m3'],baseline_limiter=t['bm'][-1]['limited_face_fraction'],intervention_limiter=t['sm'][-1]['limited_face_fraction'],max_balance_error_m3=max(abs(x['balance_error_m3']) for x in t['bm']+t['sm']))
        if prev is not None:m['successive']={k:spatial(prev[k],t[k],area) for k in ('bp','sp')}
        if dt==30:
            m['saved_peak_max_abs_error_m']=max(float(np.max(np.abs(t['bp']-r['baseline_peak']))),float(np.max(np.abs(t['sp']-r['scenario_peak']))))
            if m['saved_peak_max_abs_error_m']>1e-8:raise ValueError('Saved run differs from current solver; do not mix results.')
        cases.append(m); prev=t;last=t
    # predeclared screening gates, not field validation. Both 15->10 and 10->5 must pass.
    gate=all(x['peak_change_pct']<=5 and x['wet_iou']>=.90 and x['depth_rmse_m']<=.025 for c in cases[-2:] for x in c['successive'].values())
    alt=budget_alternative(r,z);alternatives=[]
    if alt:
        a=trial(r,z,5.,alt);alternatives.append({'name':'Deterministic translated footprint control (not optimized)','edits':alt,'storage_reduction_m3':a['bm'][-1]['stored_m3']-a['sm'][-1]['stored_m3'],**spatial(a['bp'],a['sp'],area)})
    # actual saved original and finer-grid outputs are separate; no replacement of saved data.
    return {'version':VERSION,'run_id':r['run_id'],'summary':summary(r),'cases':cases,'spatial_screen_passed':gate,'tolerances':{'peak_change_pct':5,'wet_iou_min':.90,'depth_rmse_m':.025,'successive_pairs':['15→10','10→5']},'status':'Screening convergence checks met; not field validation' if gate else 'Water accounting only: spatial timestep checks not met','alternatives':alternatives,'fine_peak_difference_m':(last['bp']-last['sp']).tolist(),'warning':'Closed domain and idealized capacity. Same footprint control is not a cost-equivalent design or optimized location. No observed event or grid refinement validation.'}

def momentum_benchmark():
    """Independent exact Ritter dry-bed dam-break solution (no friction/source, flux core only)."""
    import shallow_water as sw
    reports=[];end=8.;c0=math.sqrt(sw.G)
    for dx in (2.,1.):
        x=(np.arange(int(200/dx))+.5)*dx;z=np.zeros((3,len(x)));h=np.broadcast_to((x<100).astype(float),z.shape).copy();mx=np.zeros_like(h);my=mx.copy();initial=float(h.sum()*dx*dx);t=0.
        while t<end-1e-12:
            speed=float(np.max(np.abs(sw.velocity(mx,h))+2*np.sqrt(sw.G*np.maximum(h,0))));dt=min(end-t,.3*dx/max(speed,.01));h,mx,my=sw.step(z,h,mx,my,dx,dt)
            if h.min()<-1e-8:raise ArithmeticError('Dam-break negative depths')
            h=np.maximum(h,0);t+=dt
        # Analytical cell-centre comparison; boundary walls outside wave domain for this time.
        xi=(x-100)/end;exact=np.where(xi<=-c0,1,np.where(xi>=2*c0,0,(2*c0-xi)**2/(9*sw.G)))
        reports.append({'dx_m':dx,'time_s':end,'mean_abs_depth_error_m':float(np.mean(np.abs(h[1]-exact))),'mass_error_m3':float(h.sum()*dx*dx-initial)})
    return {'cases':reports,'refinement_improves':reports[-1]['mean_abs_depth_error_m']<reports[0]['mean_abs_depth_error_m'],'scope':'Ritter analytical dry dam break, flux core of existing momentum solver only. Not a complete hydraulic benchmark suite.'}

def cross_solver(r,z):
    import site_twin as st
    i=r['inputs'];d=r['site'];c,dr=arrays(i,z)
    if i['solver']!='diffusive' or i['suction_mm']*i['moisture_deficit']!=0 or i.get('outlet') is not None or z.size*len(i['rain_mm_h'])>15000:raise ValueError('Cross-solver comparison requires closed domain, constant infiltration and at most 15,000 cell-hours.')
    b,bp,bm=st.solve('momentum',z,d['dx'],i['rain_mm_h'],i['infiltration'],0,i['roughness']);f,fp,fm=st.solve('momentum',z,d['dx'],i['rain_mm_h'],c,dr,i['roughness']);area=d['dx']**2
    return {'run_id':r['run_id'],'momentum_storage_reduction_m3':bm[-1]['stored_m3']-fm[-1]['stored_m3'],'momentum_comparison':spatial(bp,fp,area),'baseline_between_solvers':spatial(r['baseline_peak'],bp,area),'intervention_between_solvers':spatial(r['scenario_peak'],fp,area),'adaptive_min_dt_s':[bm[-1]['adaptive_min_dt_s'],fm[-1]['adaptive_min_dt_s']],'warning':'Separate experimental existing momentum engine, not independent external validation. Both use same terrain, idealized sinks and closed boundaries. Disagreement must be investigated, not averaged.'}

def benchmarks():
    import site_twin as st
    z=np.zeros((12,12));out=[]
    for dt in (30.,15.,10.,5.):
        f,p,m=st.simulate(z,10,[20,35,15],5,0,dt=dt);expected=.055
        out.append({'case':'Uniform flat domain, exact 55 mm depth','dt_s':dt,'max_error_m':float(np.max(np.abs(f[-1]-expected))),'passed':bool(np.allclose(f[-1],expected,atol=1e-10,rtol=0))})
        f,p,m=st.simulate(np.arange(144).reshape(12,12).astype(float),10,[0],0,0,dt=dt)
        out.append({'case':'Dry sloped domain, zero forcing','dt_s':dt,'max_error_m':float(np.max(abs(f))),'passed':bool(np.all(f==0))})
    return {'cases':out,'scope':'Analytic limiting cases only. Not independent 2D hydraulic benchmark or field validation.','momentum_dam_break':momentum_benchmark()}

def run_review(p,app,root):
    import stakeholder_mission as m
    ev,c,role,r,d,z=m._run_context(p,app,root)
    report=convergence(r,z);report.update(site_hash=ev['hash'],selection=c,role=role)
    import external_evidence as ee
    target=staging_path(root,r['run_id'],ev['hash'],role,c);ee._save(target,report)
    return report

def staging_path(root,run_id,site_hash,role,c):
    import site_twin as st
    key=sha(plain([run_id,site_hash,role,c]).encode());return st.storage(root)/'results'/run_id/'assurance'/f'{key}.json'

def reproduce_files(r,d,z):
    import site_twin as st
    src=Path(st.__file__).read_text(encoding='utf-8');node=next(x for x in ast.parse(src).body if isinstance(x,ast.FunctionDef) and x.name=='simulate');solver=ast.get_source_segment(src,node)
    bio=io.BytesIO();np.save(bio,z,allow_pickle=False)
    # Only self-contained code for the exact diffusive simulation; no server, network or keys.
    script='import math, json, numpy as np\nfrom pathlib import Path\n'+solver+'\n'+'''if __name__ == '__main__':
    root=Path(__file__).resolve().parent
    r=json.loads((root/'scenario.json').read_text()); z=np.load(root/'elevation.npy',allow_pickle=False); i=r['inputs']; cap=np.full(z.shape,i['infiltration']); drain=np.zeros_like(z)
    for e in i['edits']:
        (drain if e['kind']=='drain' else cap)[e['row'],e['col']]=e['rate']
    args=(i['roughness'],i['suction_mm']*i['moisture_deficit']/1000)
    for label,c,d,key in [('baseline',i['infiltration'],0,'baseline'),('intervention',cap,drain,'scenario')]:
        f,p,m=simulate(z,r['site']['dx'],i['rain_mm_h'],c,d,*args,outlet=i.get('outlet'))
        error=float(np.max(np.abs(p-np.array(r[key+'_peak'])))); frame_error=float(np.max(np.abs(f-np.array(r[key+'_frames'])))); budget_error=abs(m[-1]['stored_m3']-r[key][-1]['stored_m3']); print(label,'peak max abs error m',error,'frame max abs error m',frame_error,'final storage error m3',budget_error)
        assert error<1e-8 and frame_error<=5.01e-6 and budget_error<1e-6,'Reproduction mismatch'
    print('Reproduced saved model, not field validation.')
'''
    return {'reproduce/elevation.npy':bio.getvalue(),'reproduce/scenario.json':plain(r).encode(),'reproduce/reproduce.py':script.encode(),'reproduce/terrain.json':plain(d).encode(),'reproduce/environment.json':plain({'python':sys.version,'numpy':np.__version__,'solver_source_sha256':sha(solver.encode())}).encode(),'reproduce/README.txt':b'Install numpy, then run python reproduce.py in this directory. Exact processed elevation and original saved results included. Numerical reproduction is not field validation. Do not redistribute restricted source imagery.\n'}

def package(p,app,root):
    import stakeholder_mission as m, external_evidence as ee
    ev,c,role,r,d,z=m._run_context(p,app,root)
    # Preserve original package and export behavior; opt-in enriched package keeps just current role records.
    old=m.package(p,app,root)
    with zipfile.ZipFile(io.BytesIO(old)) as f:files={k:f.read(k) for k in f.namelist() if k!='manifest.json' and not k.startswith(('reviews/','comparisons/'))}; manifest=json.loads(f.read('manifest.json'))
    files.update(reproduce_files(r,d,z));
    import rasterio as rio
    with rio.io.MemoryFile() as mem:
        with mem.open(driver='GTiff',height=z.shape[0],width=z.shape[1],count=1,dtype='float64',crs=d['epsg'],transform=rio.Affine(*d['transform']),compress='deflate') as ds:ds.write(z,1);ds.set_band_unit(1,'m')
        files['reproduce/elevation.tif']=mem.read()
    files['assurance/summary.json']=plain(summary(r)).encode();gnss=ee.cached_gnss(app,ev['hash'])
    if gnss:files['assurance/gnss.json']=plain(gnss).encode()
    files['assurance/evidence.json']=plain(ev).encode()
    for name,prefix in [('radar-audit','radar-assurance-'),('gnss-enu','gnss-enu-')]:
        path=Path(app)/'out'/f'{prefix}{ev["hash"]}.json'
        if path.exists():
            record=json.loads(path.read_text())
            if record.get('site_hash')==ev['hash']:files[f'assurance/{name}.json']=plain(record).encode()
    from independent_comparison import cache_path
    cp=cache_path(app,ev['hash'],c)
    if cp.exists():
        record=json.loads(cp.read_text())
        if record.get('site_hash')==ev['hash'] and record.get('selection')==c:files['assurance/independent-comparison.json']=plain(record).encode()
    files['assurance/benchmarks.json']=plain(benchmarks()).encode()
    saved=staging_path(root,r['run_id'],ev['hash'],role,c)
    if saved.exists():files['assurance/spatial-review.json']=saved.read_bytes()
    for suffix,name in [('.momentum.json','cross-solver'),('.ai.json','checked-ai')]:
        pth=saved.with_suffix(suffix)
        if pth.exists():files[f'assurance/{name}.json']=pth.read_bytes()
    manifest.update(version=VERSION,sha256={k:sha(v) for k,v in files.items()});files['manifest.json']=plain(manifest).encode()
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as f:
        for k,v in files.items():f.writestr(k,v)
    return out.getvalue()

def http_post(handler,app,root,local_only,redact):
    if not local_only(handler) or 'application/json' not in (handler.headers.get('Content-Type') or ''):return handler._json(403,{'error':'Local-only request'})
    try:
        n=int(handler.headers.get('Content-Length','0')); action=handler.path.split('?')[0].rsplit('/',1)[-1]
        if not 0<n<=16000:return handler._json(413,{'error':'Invalid request size'})
        p=json.loads(handler.rfile.read(n))
        if action=='review':
            if not _REVIEW_LOCK.acquire(blocking=False):return handler._json(429,{'error':'Another assurance review is running'})
            try:return handler._json(200,run_review(p,app,root))
            finally:_REVIEW_LOCK.release()
        if action=='cross-solver':
            import stakeholder_mission as m
            ev,c,role,r,d,z=m._run_context(p,app,root)
            if not _REVIEW_LOCK.acquire(blocking=False):return handler._json(429,{'error':'Another assurance review is running'})
            try:
                out=cross_solver(r,z);out.update(site_hash=ev['hash'],role=role,selection=c);import external_evidence as ee;ee._save(staging_path(root,r['run_id'],ev['hash'],role,c).with_suffix('.momentum.json'),out);return handler._json(200,out)
            finally:_REVIEW_LOCK.release()
        if action=='checked-ai':
            return handler._json(200,checked_ai(p,app,root))
        if action=='facts':
            import stakeholder_mission as m
            ev,c,role,r,d,z=m._run_context(p,app,root);f=facts(r,c)
            return handler._json(200,check_claims(p['claims'],f,{'LOCAL-RUN','RADAR'}) if 'claims' in p else {'facts':f,'scope':'Server-calculated numeric facts; prose remains unverified.'})
        if action=='package':
            b=package(p,app,root);handler.send_response(200);handler.send_header('Content-Type','application/zip');handler.send_header('Content-Disposition','attachment; filename="SWELL-reproducible-decision.zip"');handler.send_header('Content-Length',str(len(b)));handler.end_headers();handler.wfile.write(b);return
        return handler._json(404,{'error':'Unknown assurance action'})
    except Exception as exc:return handler._json(400,{'error':redact(exc)})

# Structured claims only: deliberately do not certify arbitrary free-form AI text.
def check_claims(claims,facts,source_ids):
    if not isinstance(claims,list) or not 1<=len(claims)<=20:raise ValueError('Supply 1–20 typed claims')
    result=[]
    for c in claims:
        name=c.get('metric');value=c.get('value');unit=c.get('unit');expected=facts.get(name);src=c.get('source_id')
        ok=bool(expected and isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and unit==expected['unit'] and src in source_ids and src==expected['source_id'] and abs(value-expected['value'])<=expected['tolerance'])
        result.append({'claim':c,'passed':ok,'expected':expected})
    return {'claims':result,'all_passed':all(x['passed'] for x in result),'scope':'Checks typed numeric claims against run-bound facts only; not semantic validation of prose or engineering advice.'}

def facts(r,c):
    s=summary(r);return {k:{'value':v,'unit':u,'source_id':src,'tolerance':tol} for k,v,u,src,tol in [('storage_reduction',s['storage_reduction_m3'],'m3','LOCAL-RUN',.1),('baseline_peak',s['peak_m'],'m','LOCAL-RUN',.001),('intervention_peak',s['other_peak_m'],'m','LOCAL-RUN',.001),('selected_los',c['los_mm'],'mm','RADAR',.05),('selected_coherence',c['coherence'],'1','RADAR',.01)]}

def http_get(handler,app,root):
    if handler.path.split('?')[0]!='/api/assurance/geometry':return handler._json(404,{'error':'Unknown assurance route'})
    try:
        import external_evidence as ee
        _,_,key=ee.active(app);path=Path(app)/'out'/f'radar-assurance-{key}.json'
        if not path.exists():return handler._json(200,{'available':False,'warning':'Run python radar_assurance.py locally to check cached granules. Legacy cell locations remain approximate.'})
        v=json.loads(path.read_text());g=v['geometry']
        if v['site_hash']!=key:raise ValueError('Radar geometry belongs to another study')
        return handler._json(200,{'available':True,'geometry':g,'site_hash':key,'granules':v['granules'],'limitations':v['limitations'],'latest_pair':v['latest_pair']})
    except Exception:return handler._json(400,{'error':'Matching radar audit unavailable; no coordinate inference.'})


def checked_ai(p,app,root):
    import stakeholder_mission as m, ai_provider as ai
    ev,r,review=m._get_review(p,app,root);c=review['radar_selection'];f=facts(r,c)
    requested=['storage_reduction','baseline_peak','intervention_peak','selected_los','selected_coherence']
    question='Return ONLY a JSON object {"claims": [{"metric": "...", "value": 0, "unit": "...", "source_id": "..."}]}; include each of the five exact metrics once. Copy values, units and source IDs from the supplied facts. No prose, design approval, citations or additional fields.'
    provider,_,model,_=ai._config();answer=ai._generate(question,{'available':True,'facts':f,'run_id':r['run_id']},{'role':review['role']},[])
    cleaned=answer.strip();cleaned=re.sub(r'^```(?:json)?\s*|\s*```$','',cleaned,flags=re.I)
    try:
        a=json.loads(cleaned);claims=a['claims'];result=check_claims(claims,f,{'LOCAL-RUN','RADAR'});unique=sorted(x['metric'] for x in claims)==sorted(requested)
        passed=bool(unique and result['all_passed'])
    except (ValueError,KeyError,TypeError,AttributeError):passed=False;result={'claims':[],'all_passed':False,'scope':'Invalid structured output; no substitute generated'}
    # Do not present unverified numeric claims as accepted facts; rejected raw answer is not displayed.
    out={'run_id':r['run_id'],'provider':provider,'model':model,'passed':passed,'claims':result['claims'] if passed else [],'warning':'Typed numeric extraction verified only; no semantic/causal or field validation.' if passed else 'Provider response did not match the required run-bound evidence. No checked claims displayed.'}
    import external_evidence as ee
    ee._save(staging_path(root,r['run_id'],ev['hash'],review['role'],c).with_suffix('.ai.json'),out)
    return out

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--benchmarks',action='store_true');a.add_argument('--run-id');a.add_argument('--project',default='.')
    p=a.parse_args();root=Path(p.project).resolve()/'site'
    if p.benchmarks:print(plain(benchmarks()))
    elif p.run_id:
        import site_twin as st
        r=st.load_result(root,p.run_id);d,z=st.load(root,r['site']['id']);rep=convergence(r,z);out=root.parent/'out'/('assurance-'+p.run_id+'.json');out.write_text(plain(rep));print(out)
    else:a.error('Choose --benchmarks or --run-id')

