"""Compare the existing adaptive momentum solver on a saved experiment; never overwrite it."""
import argparse, hashlib, io, json, zipfile
from pathlib import Path
import numpy as np
import shallow_water as sw
from science_assurance import arrays, spatial, budget_alternative

def evaluate(r,z):
    i=r['inputs'];dx=r['site']['dx'];area=dx**2
    if i.get('outlet') is not None or i['suction_mm']*i['moisture_deficit']!=0:raise ValueError('Closed boundary and constant infiltration required')
    cases=[];prev=None
    for dt in (5.,2.,1.):
        cap,dr=arrays(i,z)
        def run(c,d):return sw.simulate(z,dx,i['rain_mm_h'],c,d,i['roughness'],dt=dt)
        _,bp,bm=run(i['infiltration'],0);_,sp,sm=run(cap,dr)
        m=spatial(bp,sp,area);m.update(max_dt_s=dt,storage_reduction_m3=bm[-1]['stored_m3']-sm[-1]['stored_m3'],minimum_dt_s=[bm[-1]['adaptive_min_dt_s'],sm[-1]['adaptive_min_dt_s']],steps=[bm[-1]['steps'],sm[-1]['steps']],max_balance_residual_m3=max(abs(x['balance_error_m3']) for x in bm+sm))
        if prev is not None:m['successive']={'baseline':spatial(prev[0],bp,area),'intervention':spatial(prev[1],sp,area)}
        prev=(bp,sp);cases.append(m)
        print('Adaptive cap',dt,'peak',m['peak_m'],'storage reduction',m['storage_reduction_m3'],flush=True)
    gate=all(c['max_balance_residual_m3']<=max(1e-5,z.size*area*sum(i['rain_mm_h'])/1000*1e-8) for c in cases) and all(v['peak_change_pct']<=5 and v['wet_iou']>=.9 and v['depth_rmse_m']<=.025 for c in cases[1:] for v in c['successive'].values())
    alt=budget_alternative(r,z);options=[]
    if alt and all(e['kind']=='drain' for e in i['edits']):
        for name,ed in [('relocated drainage',alt),('extra infiltration on original footprint',[{**e,'kind':'infiltration','rate':i['infiltration']+e['rate']} for e in i['edits']])]:
            if any(e['rate']>100 for e in ed):continue
            c,d=arrays(i,z,ed);_,p,m=sw.simulate(z,dx,i['rain_mm_h'],c,d,i['roughness'],dt=1.)
            options.append({'name':name,'edits':ed,'storage_reduction_m3':bm[-1]['stored_m3']-m[-1]['stored_m3'],**spatial(bp,p,area)})
    return {'run_id':r['run_id'],'cases':cases,'screen_passed':gate,'screen_thresholds':{'peak_change_pct':5,'wet_iou_min':.9,'depth_rmse_m':.025},'alternatives':options,'warning':'Closed domain; no grid refinement, field validation, sewer model or cost equivalence. Maximum timestep cap sensitivity only. Geographic relationship must be checked separately.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('archive',nargs='?',help='Reproducible ZIP; defaults to newest stakeholder export');p.add_argument('--output',default='momentum-review.json');a=p.parse_args()
    from build_public_replay import verify
    if not a.archive:
        candidates=sorted(Path('.').glob('demo_stakeholder_*/SWELL-reproducible-decision.zip'),key=lambda x:x.stat().st_mtime,reverse=True)
        if not candidates:raise SystemExit('No stakeholder reproducible ZIP found. Record with --assurance first.')
        a.archive=str(candidates[0])
    print('Evaluating',a.archive,flush=True)
    verify(a.archive)
    with zipfile.ZipFile(a.archive) as z:
        r=json.loads(z.read('reproduce/scenario.json'));dem=np.load(io.BytesIO(z.read('reproduce/elevation.npy')),allow_pickle=False)
    report=evaluate(r,dem);report['archive_sha256']=hashlib.sha256(Path(a.archive).read_bytes()).hexdigest();Path(a.output).write_text(json.dumps(report,indent=2,allow_nan=False));print('Saved',a.output)
if __name__=='__main__':main()
