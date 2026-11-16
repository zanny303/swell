import numpy as np
from swell import synthetic, fit as F, pinn, science_audit as A

def test_constrained_fit_matches_exact_equations():
    s=synthetic.make(); fr=F.fit_all(s); p=fr['par']; mask=F.masks(s)['clay']; tr=fr['train']; actual=fr['mcorr'][tr][:,mask]; pred=F.predict(s,p)[s['pass_days'][tr]][:,mask]
    assert p['alpha']>=0 and 0<=p['b']<=1
    assert np.isclose(p['sse'],np.nansum((pred-actual)**2))

def test_negative_response_is_not_accepted_as_clay_physics():
    s=synthetic.make(); fr=F.fit_all(s); p=F.fit_clay(s,-F.predict(s,fr['par'])[s['pass_days']],fr['train'])
    assert p['alpha']>=0 and 0<=p['b']<=1

def test_pinn_physics_does_not_use_future_wetness():
    s=synthetic.make(); fr=F.fit_all(s); a=pinn._train(s,fr,20,20,7); altered=dict(s); altered['w']=s['w'].copy(); altered['w'][s['pass_days'][fr['train'][-1]]+1:]=0.99
    b=pinn._train(altered,fr,20,20,7)
    assert a==b

def test_rolling_benchmark_reports_common_support_and_no_approval():
    s=synthetic.make(); fr=F.fit_all(s); a=A.audit(s,fr,[{'name':'T1 GPS','passed':None}]); assert not a['approval_allowed']; assert a['rolling_los']['n']>0; assert a['rolling_los']['physics_rmse_mm']>=0
