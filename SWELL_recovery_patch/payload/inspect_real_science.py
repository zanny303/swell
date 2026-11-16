"""Read-only audit of an authenticated, local NISAR site; does not change any output.
The previous holdout informed model development. Treat further comparisons as exploratory.
"""
import argparse, json, hashlib
from pathlib import Path
import numpy as np
from swell import fit as F, physics as ph, twin as TW
from swell.validate import load_site

def main():
    p=argparse.ArgumentParser();p.add_argument('--site',required=True);a=p.parse_args()
    path=Path(a.site);site=load_site(str(path))
    if 'SYNTH' in str(site.get('source','')).upper():raise SystemExit('Real-site audit refuses synthetic inputs.')
    fr=F.fit_all(site);mk=F.masks(site);pd=site['pass_days'];tr=fr['train'];res=[]
    for label,coef in [('uncorrected',0.),('fitted artifact',fr['beta'])]:
        m=F.to_vertical(site,F.corrected_los(site,coef));par=F.fit_clay(site,m,tr)
        res.append(dict(assumption=label,alpha=par['alpha'],b=par['b'],T=par['T'],tau=par['tau'],training_rmse_mm=par['rmse_train']))
    report=dict(source=site['source'],site=site['name'],input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pass_days=pd.tolist(),n_grid=int(site['n']),finite_per_pass=[int(np.isfinite(x).sum()) for x in site['los']],reference_cells=int(mk['ref'].sum()),control_cells=int(mk['control'].sum()),clay_cells=int(mk['clay'].sum()),control_beta=fr['beta'],control_observation_count=fr['n_control_obs'],fits=res,independent_gps_count=len(site.get('gps',{})),note='Training-only sensitivity to the assumed moisture correction. No model selected on the held-out record; no scientific thresholds changed. Check acquisition sign, reference motion and external correction layers against product metadata and independent GNSS.')
    print(json.dumps(report,indent=2,default=float))
if __name__=='__main__':main()
