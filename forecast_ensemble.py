"""Bounded, deterministic sensitivity ensemble; no probabilistic calibration claims."""
import numpy as np
import site_twin as st
from decision_engine import save_review

def evaluate(payload,root):
    r=st.load_result(root,payload['result_id']);d,z=st.load(root,r['site']['id']);i=r['inputs'];rain=np.asarray(i['rain_mm_h']);
    if z.size*len(rain)>24000:raise ValueError('Ensemble budget exceeded; smaller site or event required')
    c=np.full(z.shape,i['infiltration']);dr=np.zeros_like(z)
    for e in i['edits']:(dr if e['kind']=='drain' else c)[e['row'],e['col']]=e['rate']
    A=i['suction_mm']*i['moisture_deficit']/1000;members=[];peaks=[]
    for rf in (.8,1.,1.2):
        for kf in (.5,1.,1.5):
            _,peak,mass=st.solve(i.get('solver','diffusive'),z,d['dx'],rain*rf,c*kf,dr,i['roughness'],A,outlet=i.get('outlet'))
            members.append({'rain_multiplier':rf,'infiltration_multiplier':kf,'peak_depth_m':float(peak.max()),'wet_area_m2':float((peak>=.05).sum()*d['dx']**2),'water_balance_error_m3':mass[-1]['balance_error_m3']});peaks.append(peak)
    a=np.stack(peaks);low=a.min(axis=0);high=a.max(axis=0);agreement=(a>=.05).sum(axis=0)
    return save_review(root,r,'ensemble',{'run_id':r['run_id'],'method':'nine deterministic rainfall/infiltration perturbations; not calibrated probability or confidence','members':members,'peak_depth_range_m':[float(low.max()),float(high.max())],'wet_in_all_members_m2':float((agreement==9).sum()*d['dx']**2),'wet_in_any_member_m2':float((agreement>0).sum()*d['dx']**2),'cell_min_peak_m':low.tolist(),'cell_max_peak_m':high.tolist(),'wet_member_count':agreement.tolist(),'engineering_approved':False})
