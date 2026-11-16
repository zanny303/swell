"""Guided, provenance-bound decision rehearsal. No structural or operational approval.
Reuses SWELL's actual radar observations, terrain solver and stakeholder exports.
"""
from __future__ import annotations
import hashlib, io, json, math, re, zipfile
from pathlib import Path
import numpy as np
import site_twin as st
import external_evidence as ee
import science_plans

VERSION='decision-mission-1.1'
from radar_investigation import matching_audit, footprint, within, investigation
ROLES={
 'engineer':('Infrastructure engineer','Where should we inspect surface drainage and measure ground conditions?','Inspect the proposed drainage location, survey elevations and collect independent displacement measurements.'),
 'planner':('City planner','Which drainage or infiltration option deserves a feasibility review?','Compare land availability, ownership, maintenance responsibility and downstream effects before design.'),
 'utility':('Water utility','Where should crews investigate drainage or water leakage?','Check actual pipe inventories, leak records and outlet capacity; no pipe connectivity is inferred.'),
 'emergency':('Emergency manager','Which locations merit field reconnaissance after a storm?','Check observed water depths and official warnings; do not infer safe routes from this screening.'),
 'resident':('Resident','What can we learn about water collecting near our neighborhood?','Document ponding from a safe location and share observations with the responsible local authority.')}

def evidence(app):
    s,dates,key=ee.active(app)
    n=int(s['n']); a=np.asarray(s['observed_los'],dtype=float); coh=np.asarray(s['coh'],dtype=float); ref=np.asarray(s['reference'],dtype=bool)
    if not 2<=n<=200 or a.shape!=(len(dates),n,n) or coh.shape!=(n,n) or ref.shape!=(n,n):raise ValueError('Invalid radar grid')
    a[a==-9999]=np.nan
    provenance=json.loads((Path(app)/'out/real_site_provenance.json').read_text())
    quality_basis='Study-level coherence proxy (pair-specific cache not matched)'
    # Prefer the last pair's actual coherence rather than an archive-average mask.
    # Never mix a different NPZ with the current browser study.
    dataset_key=str(provenance.get('site',''))
    if re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',dataset_key):
        path=Path(app)/'out'/f'{dataset_key}.npz'
        try:
            if path.stat().st_size>150_000_000:raise ValueError('Oversized cached study')
            with np.load(path,allow_pickle=False) as z:
                raw=np.asarray(z['los'],float);q=np.asarray(z['coh_pairs'],float)
                if raw.shape==a.shape and q.shape==(len(dates)-1,n,n) and np.array_equal(z['pass_days'],s['pass_days']) and np.allclose(z['bbox'],s['bbox'],atol=1e-6,rtol=0) and np.allclose(raw,a,atol=.051,rtol=0,equal_nan=True):
                    coh=q[-1];a=raw;quality_basis='Last interferometric pair coherence, matched cached NPZ and study timeline'
        except (OSError,ValueError,KeyError,TypeError):pass
    valid=np.isfinite(a[-1])&np.isfinite(a[-2])&np.isfinite(coh)&(coh>=.30)&(~ref)
    delta=np.where(valid,a[-1]-a[-2],np.nan)
    w,south,e,north=map(float,s['bbox']); rows=[]
    for r,c in np.argwhere(valid):
        rows.append({'row':int(r),'col':int(c),'los_mm':float(delta[r,c]),'coherence':float(coh[r,c]),'lat':north-(int(r)+.5)*(north-south)/n,'lon':w+(int(c)+.5)*(e-w)/n})
    audit=matching_audit(app,key,n,[d.isoformat() for d in dates])
    if audit:
        g=audit['geometry']
        for c in rows:
            r,j=c['row'],c['col'];c.update(lat=g['lat'][r][j],lon=g['lon'][r][j],geometry_status='audited block center',footprint=footprint(g,r,j))
    rows.sort(key=lambda x:-abs(x['los_mm']))
    gnss=ee.cached_gnss(app,key)
    prep=Path(app)/'out/provenance.json'; processing=json.loads(prep.read_text()) if prep.exists() else {}
    return {'version':VERSION,'site':s['name'],'source':s['source'],'hash':key,'bbox':s['bbox'],'n':n,'dates':[d.isoformat() for d in dates],'cells':rows,'valid_cells':len(rows),'total_cells':n*n,'gnss':{'station_count':gnss['station_count'],'stations':[{'station':x['station'],'matched_dates':x.get('matched_dates',0),'lat':x['lat'],'lon':x['lon']} for x in gnss['stations']],'warning':gnss['warning']} if gnss else None,'quality_basis':quality_basis,'geometry_status':'audited projected block centers' if audit else 'legacy approximate grid; unlinked scenario','granule_pairs':[{k:x.get(k) for k in ('name','ref','sec','maturity','short_name','track','frame','updated')} for x in provenance.get('steps',{}).get('radar',{}).get('pairs',[])],'processing':{'reference':processing.get('reference'),'surface_filter':processing.get('scene_surface_filter'),'incidence_note':processing.get('incidence_note')},'limitations':'Referenced and processed LOS change, not direct vertical deformation or damage. Coherence threshold 0.30 is a screening rule, not calibrated reliability. If pair-specific coherence cannot be matched, the study-level proxy is visibly identified. The observation footprint is distinct from local terrain; check geometry status before interpreting the link. No causal relation between radar signal and local ponding is established.','roles':ROLES,'clay_status':(s.get('scientific_validity') or {}).get('status','Not independently validated')}

def selection(app,p):
    ev=evidence(app)
    if p.get('site_hash')!=ev['hash']:raise ValueError('Active radar study has changed; restart this decision.')
    row,col=p.get('row'),p.get('col'); matches=[x for x in ev['cells'] if x['row']==row and x['col']==col]
    if not matches:raise ValueError('Choose a cell with eligible real radar evidence.')
    role=p.get('role','engineer')
    if role not in ROLES:raise ValueError('Unknown stakeholder role')
    return ev,matches[0],role

def _run_context(p,app,root):
    ev,c,role=selection(app,p);r=st.load_result(root,p['result_id']);d,z=st.load(root,r['site']['id'])
    if 'test fixture' in (d['source']+' '+d['vertical_datum']).lower() or 'synthetic' in (d['source']+' '+d['vertical_datum']).lower():raise ValueError('Test terrain is not supported in the real-data decision workspace.')
    if not d.get('source_url') or not d.get('source_sha256'):raise ValueError('Use provider terrain with recorded provenance in this guided workflow.')
    # Explicit location binding: a regional selection may motivate a local investigation,
    # but the DEM must be centered on the user-selected coordinates, not a different site.
    lat=st.num(p['lat'],-79,83);lon=st.num(p['lon'],-179.8,179.8)
    w,s,e,n=ev['bbox']
    if not w<=lon<=e or not s<=lat<=n:raise ValueError('Local location must be inside the real radar study bounding box.')
    if abs(lat-d['lat'])>1e-7 or abs(lon-d['lon'])>1e-7:raise ValueError('Saved terrain/run does not match the selected local coordinates.')
    if c.get('footprint') and not within(c['footprint'],d['lat'],d['lon']):raise ValueError('Local terrain center is outside the audited radar block. Select that block again and load terrain. Separate experiments remain available in Site Twin.')
    if r['inputs']['solver']!='diffusive' :raise ValueError('Guided review uses the existing diffusive solver only.')
    if r['inputs'].get('outlet') is not None:raise ValueError('Guided review uses a closed screening domain, not an outlet design.')
    return ev,c,role,r,d,z

def _metrics(b,s,bp,sp,area):
    return {'baseline_storage_m3':float(b[-1]['stored_m3']),'intervention_storage_m3':float(s[-1]['stored_m3']),'storage_reduction_m3':float(b[-1]['stored_m3']-s[-1]['stored_m3']),'baseline_peak_m':float(np.max(bp)),'intervention_peak_m':float(np.max(sp)),'baseline_wet_m2':float((bp>=.05).sum()*area),'intervention_wet_m2':float((sp>=.05).sum()*area),'rain_m3':float(b[-1]['rain_m3']),'baseline_balance_residual_m3':float(max(abs(x['balance_error_m3']) for x in b)),'intervention_balance_residual_m3':float(max(abs(x['balance_error_m3']) for x in s)),'baseline_infiltrated_m3':float(b[-1]['infiltrated_m3']),'intervention_infiltrated_m3':float(s[-1]['infiltrated_m3']),'intervention_captured_m3':float(s[-1]['drained_m3'])}

def paired_review(p,app,root):
    ev,c,role,r,d,z=_run_context(p,app,root);i=r['inputs'];rain=i['rain_mm_h'];area=d['dx']**2
    if z.size*len(rain)>20_000:raise ValueError('Choose a smaller area or shorter storm for this paired sensitivity review.')
    if not i['edits']:raise ValueError('Paint at least one intervention before comparison.')
    # Changing the recipient is not a new physical run. Reuse exact run-bound
    # numerical checks, but create a separate role-bound draft record.
    folder=st.storage(root)/'results'/r['run_id']/'reviews'
    from decision_engine import save_review
    for path in sorted(folder.glob('mission-paired-*.json')):
        try:
            old=json.loads(path.read_text())
            if old['version']==VERSION and old['run_id']==r['run_id'] and old['site_hash']==ev['hash'] and old['radar_selection']==c and old['terrain']['source_sha256']==d['source_sha256']:
                reused={k:v for k,v in old.items() if k not in ('record_id','reviewed_utc','reused_from')}
                reused.update(role=role,verification_required=ROLES[role][2],reused_from=old['record_id'])
                return save_review(root,r,'mission-paired',reused)
        except (OSError,ValueError,TypeError,KeyError):continue
    bp,sp=np.asarray(r['baseline_peak']),np.asarray(r['scenario_peak'])
    base=_metrics(r['baseline'],r['scenario'],bp,sp,area);cases=[{'name':'Original assumptions · 30 s','infiltration_factor':1.,'timestep_s':30.,**base}]
    for name,factor,dt in [('Both alternatives · 15 s',1.,15.),('Lower infiltration · 30 s',.8,30.),('Higher infiltration · 30 s',1.2,30.)]:
        cap=min(100.,i['infiltration']*factor);cc=np.full(z.shape,cap);dr=np.zeros_like(z)
        for x in i['edits']:
            if x['kind']=='drain':dr[x['row'],x['col']]=x['rate']
            else:cc[x['row'],x['col']]=min(100.,x['rate']*factor)
        args=(i['roughness'],i['suction_mm']*i['moisture_deficit']/1000)
        _,bpeak,bmass=st.solve('diffusive',z,d['dx'],rain,cap,0,*args,dt=dt)
        _,speak,smass=st.solve('diffusive',z,d['dx'],rain,cc,dr,*args,dt=dt)
        cases.append({'name':name,'infiltration_factor':factor,'timestep_s':dt,**_metrics(bmass,smass,bpeak,speak,area)})
    delta=[x['storage_reduction_m3'] for x in cases];tol=max(1e-6,base['rain_m3']*1e-9)
    direction='Less stored water in every tested case' if min(delta)>tol else 'More stored water in every tested case' if max(delta)<-tol else 'No consistent reduction beyond numerical tolerance'
    review={'version':VERSION,'run_id':r['run_id'],'site_hash':ev['hash'],'role':role,'radar_selection':c,'geographic_relationship':'terrain center inside audited block' if c.get('footprint') else 'unverified legacy approximate location; separate scenario','local_location':{'lat':d['lat'],'lon':d['lon']},'terrain':{k:d[k] for k in ['source','source_sha256','source_url','dx','n','epsg','vertical_datum']},'storm_mm_h':rain,'model':r['model'],'boundary':r['boundary'],'edits':i['edits'],'assumptions':{'infiltration_mm_h':i['infiltration'],'roughness':i['roughness'],'suction_mm':i['suction_mm'],'moisture_deficit':i['moisture_deficit']},'metrics':base,'cases':cases,'storage_reduction_range_m3':[min(delta),max(delta)],'direction':direction,'timestep_effect_m3':cases[1]['storage_reduction_m3']-base['storage_reduction_m3'],'numerical_mass_balance':all(abs(x[k])<=tol for x in cases for k in ['baseline_balance_residual_m3','intervention_balance_residual_m3']),'warning':'Four deterministic comparisons of the same storm; not a probability interval or validation against observed floods. Timestep and infiltration checks do not establish spatial convergence, sewer capacity, downstream safety or causal linkage to radar. Closed boundaries and idealized sinks. Reported storage reduction is local modeled storage, not proven avoided flooding.','verification_required':ROLES[role][2],'engineering_approved':False}
    from decision_engine import save_review
    return save_review(root,r,'mission-paired',review)

def _get_review(p,app,root):
    ev,c,role,r,d,z=_run_context(p,app,root)
    import re
    key=str(p.get('review_id',''))
    if not re.fullmatch('[a-f0-9]{64}',key):raise ValueError('Run paired review first.')
    review=json.loads((st.storage(root)/'results'/r['run_id']/'reviews'/('mission-paired-'+key+'.json')).read_text())
    if review['record_id']!=key or review['run_id']!=r['run_id'] or review['site_hash']!=ev['hash'] or review['role']!=role or review['radar_selection']!=c:raise ValueError('Review is stale or belongs to another decision. Rerun it.')
    return ev,r,review

def explain(p,app,root):
    import ai_provider as ai
    ev,r,review=_get_review(p,app,root)
    question=str(p.get('question','')).strip()[:700] or 'Explain this comparison and give the next field verification action.'
    site,_,sources,_=ai._evidence(question,{'role':review['role'],'selected_cell':{'row':review['radar_selection']['row'],'col':review['radar_selection']['col']}})
    # Keep context compact and computed server-side; do not send huge raw GNSS series or arrays.
    data={'site':ev['site'],'site_hash':ev['hash'],'dates':ev['dates'][-2:],'radar_selection':review['radar_selection'],'gnss':ev['gnss'],'warning':ev['limitations'],'local_run':{k:review[k] for k in ('run_id','role','storm_mm_h','terrain','metrics','storage_reduction_range_m3','direction','warning','verification_required')}}
    answer=ai._generate(question+' Respond in 100 words or less: observation, conditional model comparison, one key limitation, next field action. Use [LOCAL-RUN] for run-derived claims and do not imply approval.',data,{'role':review['role']},sources[:3])
    provider,_,model,_=ai._config()
    return {'answer':answer,'provider':provider,'model':model,'run_id':r['run_id'],'sources':[{'id':x.get('id'),'title':x.get('title'),'url':x.get('url')} for x in sources[:3]],'warning':'AI explanation only; the numerical results are produced by the saved physical run, not the language model.'}

def package(p,app,root):
    ev,r,review=_get_review(p,app,root);note=str(p.get('note','')).strip()
    if not 5<=len(note)<=2000:raise ValueError('Write a short stakeholder decision or inspection action before export.')
    plan=science_plans.plan({'result_id':r['run_id'],'role':review['role']},root)
    with zipfile.ZipFile(io.BytesIO(st.pack({'result_id':r['run_id'],'role':review['role']},root))) as original:files={x:original.read(x) for x in original.namelist() if x!='manifest.json'}
    evidence_record={k:ev[k] for k in ('site','source','hash','bbox','dates','valid_cells','total_cells','gnss','quality_basis','granule_pairs','processing','limitations','clay_status','geometry_status')}
    files['mission/evidence.json']=json.dumps(evidence_record,indent=2).encode();files['mission/paired-review.json']=json.dumps(review,indent=2).encode();files['mission/role-plan.json']=json.dumps(plan,indent=2).encode()
    files['mission/decision.json']=json.dumps({'status':'DRAFT FIELD INVESTIGATION','role':review['role'],'note':note,'run_id':r['run_id'],'review_id':review['record_id'],'requires_verification':review['verification_required'],'engineering_approved':False},indent=2).encode()
    files['manifest.json']=json.dumps({'version':VERSION,'run_id':r['run_id'],'site_hash':ev['hash'],'engineering_approved':False,'mass_balance_passed':review['numerical_mass_balance'],'sha256':{k:hashlib.sha256(v).hexdigest() for k,v in files.items()}},indent=2).encode()
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as f:
        for k,v in files.items():f.writestr(k,v)
    return out.getvalue()

def http_get(handler,app,root):
    if handler.path.split('?')[0]=='/api/mission/projected-display':
        try:
            from projected_display import active
            return handler._json(200,active(app))
        except Exception:return handler._json(400,{'error':'Projected display unavailable; legacy map remains approximate'})
    if handler.path.split('?')[0]=='/api/mission/investigation':
        try:
            from urllib.parse import urlparse,parse_qs
            q=parse_qs(urlparse(handler.path).query);ev=evidence(app);c=next(x for x in ev['cells'] if x['row']==int(q['row'][0]) and x['col']==int(q['col'][0]));a=matching_audit(app,ev['hash'],ev['n'],ev['dates']);return handler._json(200,{'site_hash':ev['hash'],'selection':c,**investigation(a,c,ev)})
        except Exception:return handler._json(400,{'error':'Matching audited observation unavailable'})
    if not handler.path.split('?')[0]=='/api/mission/evidence':return handler._json(404,{'error':'Unknown mission route'})
    try:return handler._json(200,evidence(app))
    except (ValueError,KeyError,FileNotFoundError,TypeError,IndexError) as exc:return handler._json(400,{'error':'Real study unavailable or provenance incomplete: '+str(exc)[:250]})
    except Exception:return handler._json(502,{'error':'Could not load the real study evidence. Check the source files.'})

def http_post(handler,app,root,local_only,redact):
    if not local_only(handler) or 'application/json' not in (handler.headers.get('Content-Type') or ''):return handler._json(403,{'error':'Decision requests require the local SWELL server.'})
    try:
        n=int(handler.headers.get('Content-Length','0'))
        if not 0<n<=16000:return handler._json(413,{'error':'Invalid decision request size'})
        p=json.loads(handler.rfile.read(n));action=handler.path.split('?')[0].rsplit('/',1)[-1]
        if action=='compare-evidence':
            from independent_comparison import collect
            return handler._json(200,collect(app,p))
        if action=='review':return handler._json(200,paired_review(p,app,root))
        if action=='explain':return handler._json(200,explain(p,app,root))
        if action=='package':
            data=package(p,app,root);handler.send_response(200);handler.send_header('Content-Type','application/zip');handler.send_header('Content-Disposition','attachment; filename="SWELL-stakeholder-decision.zip"');handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data);return
        return handler._json(404,{'error':'Unknown mission action'})
    except (ValueError,KeyError,TypeError,FileNotFoundError) as exc:return handler._json(400,{'error':redact(exc)})
    except Exception as exc:return handler._json(502,{'error':redact(exc)})
