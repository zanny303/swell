"""Run-bound stakeholder decision cards and constrained scenario screening.
Actual simulations, no fabricated assets/costs or approved recommendations.
"""
import numpy as np
import site_twin as st
from decision_engine import save_review,research
from location_services import ROLES

def plan(p,root):
    r=st.load_result(root,p['result_id']);d,z=st.load(root,r['site']['id']);i=r['inputs'];role=p.get('role','engineer')
    if role not in ROLES:raise ValueError('Invalid role')
    peak=np.asarray(r['scenario_peak']);base=np.asarray(r['baseline_peak']);area=d['dx']**2
    metrics={'baseline_wet_area_m2':float((base>=.05).sum()*area),'scenario_wet_area_m2':float((peak>=.05).sum()*area),'baseline_peak_m':float(base.max()),'scenario_peak_m':float(peak.max()),'final_baseline_storage_m3':r['baseline'][-1]['stored_m3'],'final_scenario_storage_m3':r['scenario'][-1]['stored_m3']}
    tasks=[{'id':'source','action':'Check terrain source, datum and acquisition date','reason':d['source'],'requires':'Survey confirmation before engineering use'}, {'id':'rain','action':'Confirm forcing and boundary assumptions','reason':r['boundary'],'requires':'Local rain/gauge data and boundary conditions'}, {'id':'validate','action':'Compare with time-matched observed surface water','reason':'Numerical predictions do not establish flood extent','requires':'OPERA WTR or independently observed depths'}]
    for k,a in enumerate(ROLES[role]):tasks.append({'id':f'role-{k}','action':a,'reason':f'{role.capitalize()} review requirement','requires':'Human review'})
    options=[]
    if p.get('optimize'):
        if z.size*len(i['rain_mm_h'])>30000:raise ValueError('Optimization budget: use smaller domain or shorter event')
        count=int(st.num(p.get('max_cells',3),1,8));cap=st.num(p.get('extra_infiltration_mm_h',10),0,100);drain=st.num(p.get('drain_mm_h',25),0,250)
        # Candidate locations are wet model cells only: not actual permissible construction sites.
        selected=[tuple(map(int,np.unravel_index(j,z.shape))) for j in np.argsort(-peak.ravel(),kind='stable') if peak.ravel()[j]>=.05][:count]
        c=np.full(z.shape,i['infiltration']);dr=np.zeros_like(z)
        for e in i['edits']:(dr if e['kind']=='drain' else c)[e['row'],e['col']]=e['rate']
        for name,cc,dd in [('Saved intervention',c.copy(),dr.copy()),('Additional infiltration',c.copy(),dr.copy()),('Additional drainage',c.copy(),dr.copy()),('Combined',c.copy(),dr.copy())]:
            if name in ('Additional infiltration','Combined'):
                for row,col in selected:cc[row,col]=min(100,cc[row,col]+cap)
            if name in ('Additional drainage','Combined'):
                for row,col in selected:dd[row,col]=min(250,dd[row,col]+drain)
            _,v,budget=st.solve(i.get('solver','diffusive'),z,d['dx'],i['rain_mm_h'],cc,dd,i['roughness'],i['suction_mm']*i['moisture_deficit']/1000,outlet=i.get('outlet'))
            candidates=[{'row':row,'col':col,'infiltration_mm_h':float(cc[row,col]),'drain_mm_h':float(dd[row,col])} for row,col in selected] if name!='Saved intervention' else []
            options.append({'name':name,'candidate_cells':candidates,'wet_area_m2':float((v>=.05).sum()*area),'peak_depth_m':float(v.max()),'final_stored_m3':budget[-1]['stored_m3'],'water_balance_error_m3':budget[-1]['balance_error_m3']})
        options.sort(key=lambda x:(x['wet_area_m2'],x['peak_depth_m'],x['final_stored_m3']))
    # Include only comparisons and records actually attached to the run.
    import json
    f=st.storage(root)/'results'/r['run_id'];comparisons=[json.loads(x.read_text()) for x in (f/'comparisons').glob('*.json')]
    sources=research({'question':'OPERA flood water validation terrain drainage hydraulic '+role},root)['sources']
    return save_review(root,r,'plan',{'run_id':r['run_id'],'role':role,'metrics':metrics,'tasks':tasks,'ranked_scenarios':options,'sources':sources,'comparisons':comparisons,'warning':'Draft model screening, not engineering design. Candidate edits are ranked by modeled wet area then peak depth then final storage; land ownership, costs, soil feasibility, pipe capacity, and structural constraints are unknown. No safe route or approved construction recommendation.','engineering_approved':False})
