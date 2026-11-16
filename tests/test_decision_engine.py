import io,zipfile
import pytest
import site_twin as st
import decision_engine as de
from test_site_twin import fixture

def setup_run(root):
    p=dict(lat=32.7767,lon=-96.797,radius=100,dx=20,datum='TEST ONLY',meters=True)
    d=st.acquire(p,root,fixture(p));r=st.run({'id':d['id'],'rain_mm_h':[100],'infiltration':0},root);return p,r

def test_review_and_export(tmp_path):
    p,r=setup_run(tmp_path);q={'result_id':r['run_id']};v=de.numerical_review(q,tmp_path);assert v['peak_depth_mae_m']>=0 and not v['engineering_approved'];assert abs(v['fine_water_budget_residual_m3'])<1e-6
    pkg=zipfile.ZipFile(io.BytesIO(st.pack(q,tmp_path)));assert any(x.startswith('reviews/numerical') for x in pkg.namelist())

def test_soil_measurements(tmp_path):
    p,r=setup_run(tmp_path);q={'result_id':r['run_id'],'lat':p['lat'],'lon':p['lon'],'csv':'top_m,bottom_m,material,theta_initial,theta_scenario,porosity,vertical_strain_per_theta,source\n0,2,clay,0.2,0.25,0.4,0.1,test lab fixture\n'};v=de.soil_review(q,tmp_path);assert v['estimated_vertical_change_mm']==pytest.approx(10)
    with pytest.raises(ValueError):de.soil_review({**q,'csv':q['csv'].replace('0.25','0.8')},tmp_path)

def test_asset_datum_and_exposure(tmp_path):
    p,r=setup_run(tmp_path);q={'result_id':r['run_id'],'datum':'TEST ONLY','csv':f'asset_id,lat,lon,entry_elevation_m,source\nA,{p["lat"]},{p["lon"]},100,test survey fixture\n'};a=de.asset_review(q,tmp_path);assert a['assets'][0]['intervention_depth_above_entry_m']>0
    with pytest.raises(ValueError):de.asset_review({**q,'datum':'wrong'},tmp_path)

def test_retrieval(tmp_path):
    a=de.research({'question':'SAR water extent verification'},tmp_path);assert a['sources'][0]['title']=='NASA OPERA';assert not de.research({'question':'zzzzzzz'},tmp_path)['sources']

def test_one_way_boundary():
    import numpy as np
    z=np.tile(np.linspace(3,0,10),(10,1));_,_,closed=st.simulate(z,20,[100,0],0,0);_,_,opened=st.simulate(z,20,[100,0],0,0,outlet={'row':5,'col':9,'stage_m':0});assert opened[-1]['boundary_outflow_m3']>0 and opened[-1]['stored_m3']<closed[-1]['stored_m3'];assert abs(opened[-1]['balance_error_m3'])<1e-7
    with pytest.raises(ValueError):st.simulate(z,20,[10],0,0,outlet={'row':5,'col':5,'stage_m':0})

def test_site_evidence_saved(tmp_path,monkeypatch):
    import location_services as loc
    p,r=setup_run(tmp_path);monkeypatch.setattr(loc,'snapshot',lambda q:{'lat':float(q['lat'][0]),'lon':float(q['lon'][0]),'sources':{'alerts':{'status':'unavailable'}}});e=de.local_evidence({'id':r['site']['id']},tmp_path);run=st.run({'id':r['site']['id'],'rain_mm_h':[20],'evidence_id':e['snapshot_id']},tmp_path);z=zipfile.ZipFile(io.BytesIO(st.pack({'result_id':run['run_id']},tmp_path)));assert 'location-evidence.json' in z.namelist()

def test_registered_point_forecast(tmp_path):
    import datetime,csv
    p,r=setup_run(tmp_path);f=io.StringIO();w=csv.writer(f);w.writerow(['issue_utc','target_utc','physics_depth_m','rain_mm','antecedent_moisture','observed_depth_m']);start=datetime.datetime(2020,1,1,tzinfo=datetime.timezone.utc)
    for i in range(150):
        t=start+datetime.timedelta(days=i);x=(i%10+1)/10;w.writerow([(t-datetime.timedelta(hours=1)).isoformat(),t.isoformat(),x,10+i%10*10,.3,x+.1])
    m=de.train_point({'id':r['site']['id'],'lat':p['lat'],'lon':p['lon'],'source':'test fixture sensor','csv':f.getvalue()},tmp_path);assert m['eligible_for_review'];q={'result_id':r['run_id'],'model_id':m['model_id'],'hour':1,'moisture':.3,'moisture_source':'fixture'};a=de.predict_point(q,tmp_path);assert a['run_id']==r['run_id'] and a['status'] in ('abstain','candidate prediction; unapproved');assert de.predict_point({**q,'moisture':.8},tmp_path)['status']=='abstain'
