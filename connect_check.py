"""Connected-machine smoke test of actual providers. No credentials printed."""
import argparse,json,tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import site_twin as st
import earth_services as earth
import decision_engine as de

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lat',type=float,default=32.7767);ap.add_argument('--lon',type=float,default=-96.797);ap.add_argument('--out',default='connection-check.json');a=ap.parse_args();p={'lat':a.lat,'lon':a.lon,'radius':100,'dx':20}
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        def terrain():
            d=st.acquire(p,root);result={'terrain':{'n':d['n'],'epsg':d['epsg'],'source':d['source'],'datum':d['vertical_datum']}}
            try:result['aerial_image']={'bytes':len(st.imagery(root,d['id'])),'status':'retrieved and extent checked'}
            except Exception as e:result['aerial_image']={'status':'failed','error':type(e).__name__}
            return result
        def nasa():
            d=st.evidence(p);return {k:{'status':v['status'],'granules':len(v['granules'])} for k,v in d.items()}
        jobs={'terrain_and_imagery':terrain,'NASA_GIBS':lambda:{'layers':len(earth.capabilities()['layers'])},'NASA_CMR':nasa,'AIFS':lambda:{'hours':len(st.hourly_forecast(p)['rows'])}}
        def attempt(kv):
            k,f=kv
            try:return k,{'status':'response received','result':f()}
            except Exception as e:return k,{'status':'failed','error_type':type(e).__name__,'error':str(e)[:300]}
        with ThreadPoolExecutor(max_workers=4) as ex:results=dict(ex.map(attempt,jobs.items()))
        out={'checked_utc':st.stamp(),'coordinates':[a.lat,a.lon],'results':results,'warning':'Successful retrieval is not scientific validation. No provider substituted.'};Path(a.out).write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':main()
