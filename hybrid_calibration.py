"""Small reproducible ML residual calibration for one instrument/site and one target.
Chronological train/validation/test, conservative abstention. No fabricated training data.
This estimates a point depth, not a mass-conserving replacement for the spatial model.
"""
import csv,io,json,hashlib,datetime
import numpy as np

def train(raw):
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))));cols=['physics_depth_m','rain_mm','antecedent_moisture','observed_depth_m']
    if not 100<=len(rows)<=50000:raise ValueError('Need 100–50,000 chronologically ordered observations from one site and forecast horizon')
    ts=[datetime.datetime.fromisoformat(r['target_utc']) for r in rows];issued=[datetime.datetime.fromisoformat(r['issue_utc']) for r in rows]
    if any(t.tzinfo is None for t in ts+issued) or any(a>=b for a,b in zip(ts,ts[1:])) or any(a>=b for a,b in zip(issued,ts)) or len({b-a for a,b in zip(issued,ts)})!=1:raise ValueError('Use increasing timezone-aware target times and one fixed forecast lead; inputs must have been available at issue time')
    data=np.array([[float(r[c]) for c in cols] for r in rows]);
    if not np.isfinite(data).all() or (data<0).any() or (data[:,2]>1).any():raise ValueError('Invalid measurement values')
    x,y=data[:,:3],data[:,3];n=len(x);i,j=int(.6*n),int(.8*n);train_idx=np.array([k for k in range(i) if ts[k]<issued[i]],dtype=int);val_idx=np.array([k for k in range(i,j) if ts[k]<issued[j]],dtype=int);
    if len(train_idx)<40 or len(val_idx)<10:raise ValueError('Insufficient nonoverlapping observations for chronological holdout')
    mean=x[train_idx].mean(0);sd=x[train_idx].std(0);sd[sd<1e-9]=1;X=np.c_[np.ones(n),(x-mean)/sd];r=y-x[:,0];
    # validation selects among a small, declared grid; test used once, untouched
    def rmse(a,b):return float(np.sqrt(np.mean((a-b)**2)))
    choices=[]
    for lam in (.01,.1,1,10,100):
        reg=np.diag([0,lam,lam,lam]);beta=np.linalg.solve(X[train_idx].T@X[train_idx]+reg,X[train_idx].T@r[train_idx]);pred=np.maximum(0,x[:,0]+X@beta);choices.append((rmse(y[val_idx],pred[val_idx]),lam,beta,pred))
    val,lam,beta,pred=min(choices,key=lambda a:a[0]);base=rmse(y[j:],x[j:,0]);test=rmse(y[j:],pred[j:]);val_base=rmse(y[val_idx],x[val_idx,0]);
    return {'algorithm':'ridge residual learning; physics baseline retained','sha256':hashlib.sha256(raw).hexdigest(),'splits':[len(train_idx),len(val_idx),n-j],'purged_rows':n-len(train_idx)-len(val_idx)-(n-j),'train_end':ts[i-1].isoformat(),'validation_end':ts[j-1].isoformat(),'test_end':ts[-1].isoformat(),'forecast_lead_seconds':(ts[0]-issued[0]).total_seconds(),'lambda':lam,'mean':mean.tolist(),'scale':sd.tolist(),'coefficients':beta.tolist(),'min':x[train_idx].min(0).tolist(),'max':x[train_idx].max(0).tolist(),'validation_baseline_rmse_m':val_base,'validation_hybrid_rmse_m':val,'test_baseline_rmse_m':base,'test_hybrid_rmse_m':test,'eligible_for_review':bool(val<val_base and test<base),'warning':'User-supplied history, issue-time leakage and sensor provenance must be independently reviewed. Test improvement does not certify a forecast. Point residual only; not applied to spatial mass balance or design automatically.'}

def predict(m,x):
    x=np.array(x,dtype=float)
    if x.shape!=(3,) or not np.isfinite(x).all() or not m['eligible_for_review'] or np.any(x<m['min']) or np.any(x>m['max']):return {'status':'abstain','reason':'Skill gate failed or outside training envelope'}
    v=max(0,float(x[0]+np.r_[1,(x-np.array(m['mean']))/m['scale']]@m['coefficients']))
    return {'status':'candidate prediction; unapproved','physics_depth_m':float(x[0]),'hybrid_depth_m':v,'warning':m['warning']}
if __name__=='__main__':
    import argparse,pathlib
    ap=argparse.ArgumentParser();ap.add_argument('history',nargs='?');ap.add_argument('--out',default='hybrid-model.json');ap.add_argument('--predict',nargs=3,type=float,metavar=('PHYSICS_DEPTH_M','RAIN_MM','MOISTURE'));ap.add_argument('--model',default='hybrid-model.json');a=ap.parse_args();
    if a.predict is not None:print(json.dumps(predict(json.loads(pathlib.Path(a.model).read_text()),a.predict),indent=2))
    else:
        if not a.history:ap.error('Provide observation CSV or --predict')
        m=train(pathlib.Path(a.history).read_bytes());pathlib.Path(a.out).write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
