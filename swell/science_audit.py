"""Versioned retrospective audit; no validation threshold is changed."""
import numpy as np
from . import fit as F, physics as ph, twin as TW

VERSION = 'swell-science-0.2'

def rolling_los(site, fr):
    """Fixed training fit; roll origin to previous pass; no realized future rain in predictions.
    Target is referenced LOS, not physical displacement truth. Archive-wide preprocessing
    and coherence masks are inherited; hence this is not an independent operational test.
    """
    pd = site['pass_days']; rows=[]; errors=[]; baseline=[]
    for k in fr['test']:
        k=int(k); origin=int(pd[k-1]); target=int(pd[k]); rain=np.array(site['rain'][:target+1],float)
        rain[origin+1:]=0.0  # declared dry assumption; never use future realized rainfall
        w=ph.wetness(rain); mu=TW.run(site,fr,upto_pass=k-1,w=w)['mean'][target]
        predicted=F.cosi(site)*mu+fr['beta']*(1-site['paved'])*(w[target]-w[pd[0]])
        obs=site['los'][k]; persist=site['los'][k-1]
        valid=F.masks(site)['clay'] & np.isfinite(predicted) & np.isfinite(obs) & np.isfinite(persist)
        if not valid.any(): continue
        e=(predicted[valid]-obs[valid])**2; b=(persist[valid]-obs[valid])**2
        errors.extend(e); baseline.extend(b)
        rows.append(dict(origin_day=origin,target_day=target,n=int(valid.sum()),physics_rmse_mm=float(np.sqrt(e.mean())),persistence_rmse_mm=float(np.sqrt(b.mean()))))
    a=float(np.sqrt(np.mean(errors))) if errors else None; b=float(np.sqrt(np.mean(baseline))) if baseline else None
    return dict(method='Rolling referenced LOS hindcast; fixed training parameters; zero future rainfall assumption; common finite pixels',physics_rmse_mm=a,persistence_rmse_mm=b,n=len(errors),per_pass=rows,best_retrospective_baseline=('persistence' if b is not None and a is not None and b<=a else 'physics_candidate' if a is not None else 'unavailable'),limitations='Archive-wide masks and detrending inherited; no independent physical truth or archived weather forecasts. Not prospective validation.')

def audit(site, fr, tests):
    failed=[t['name'] for t in tests if t.get('passed') is False]; missing=[t['name'] for t in tests if t.get('passed') is not True]; p=fr['par']
    return dict(version=VERSION, status='EXPERIMENTAL — INSPECTION PLANNING ONLY',failed=failed,not_passed=missing,alpha_at_boundary=bool(p['alpha']<=1e-8),n_passes=len(site['pass_days']),approval_allowed=False,reason='Post-result model revision: requires a new independent acquisition and field/reference checks. Zero clay gain is a non-identification result, not evidence of zero ground movement.',rolling_los=rolling_los(site,fr),target='Referenced line-of-sight change; vertical interpretation assumes negligible horizontal movement.',soil='Clay content may be a proxy, not directly measured linear extensibility.',interval='Nominal model spread, not calibrated predictive confidence.')
