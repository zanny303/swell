import io,json,zipfile,hashlib,subprocess,sys
from pathlib import Path
import numpy as np
import pytest
import science_assurance as a
import radar_assurance as ra
import gnss_assurance as ga
import site_twin as st
import stakeholder_mission as m
from test_stakeholder_mission import setup

def test_projected_geometry_and_shift():
    from pyproj import Transformer
    x=500000+np.arange(7)*80;y=3600000-np.arange(5)*80;g=ra.geometry(x,y,2,32614);assert g['trimmed_native_cols']==1 and g['trimmed_native_rows']==1
    lon,lat=Transformer.from_crs(32614,4326,always_xy=True).transform(x[:3].mean(),y[:2].mean());assert g['lat'][0][0]==pytest.approx(lat) and g['lon'][0][0]==pytest.approx(lon)
    with pytest.raises(ValueError,match='alignment'):ra.assert_aligned((32614,x,y),(32614,x+80,y))
    with pytest.raises(ValueError):ra.assert_aligned((32614,x,y),(32615,x,y))

def test_components_and_common_support():
    p=np.ones((4,4));q=np.ones_like(p);c=np.ones_like(p);c[0,0]=2;q[2,2]=.1;p[2,2]=100
    phase,coh,comp,support,mixed=ra.aggregate(p,q,c,2);assert mixed==1 and np.isnan(phase[0,0]) and phase[1,1]==1 and support[1,1]==.75
    c=np.ones((4,4),int);c[:,3]=2;p=np.arange(16).reshape(4,4).astype(float);ref=np.ones_like(c,dtype=bool);result,counts=ra.anchored(p,c,ref);assert np.isnan(result[:,3]).all() and np.median(result[:,:3])==0

def test_full_enu_and_projection():
    raw=b'site YYMMMDD _e0(m) __east(m) ____n0(m) _north(m) u0(m) ____up(m) sig_e(m) sig_n(m) sig_u(m)\nABCD 26JUL05 10 .99 20 .1 30 .2 .001 .002 .003\nABCD 26JUL17 11 .01 20 .12 30 .22 .001 .002 .003\n';days=['2026-07-05','2026-07-17'];x=ga.parse(raw,'ABCD',days);r={k:{'enu_mm':[0,0,0]} for k in days};res=ga.compare(x,r,[1,0,0],[1,0,0],days);assert res['relative_los_change_mm']==pytest.approx(20)
    with pytest.raises(ValueError):ga.compare(x,r,[1,1,1],[1,0,0],days)

def test_analytic_benchmarks():assert all(x['passed'] for x in a.benchmarks()['cases'])

def test_convergence_and_reproduction(tmp_path,monkeypatch):
    app,root,p,e,r=setup(tmp_path,monkeypatch);d,z=st.load(root,r['site']['id']);report=a.run_review(p,app,root);assert [x['timestep_s'] for x in report['cases']]==[30,15,10,5];assert report['cases'][0]['saved_peak_max_abs_error_m']==0;assert len(report['alternatives'])==1;assert len(report['alternatives'][0]['edits'])==len(r['inputs']['edits'])
    for k,v in a.reproduce_files(r,d,z).items():dest=tmp_path/k;dest.parent.mkdir(exist_ok=True);dest.write_bytes(v)
    result=subprocess.run([sys.executable,str(tmp_path/'reproduce/reproduce.py')],capture_output=True,text=True);assert result.returncode==0,result.stderr

def test_enriched_export_and_replay(tmp_path,monkeypatch):
    from build_public_replay import build
    app,root,p,e,r=setup(tmp_path,monkeypatch);review=m.paired_review(p,app,root);monkeypatch.setattr(m.science_plans,'research',lambda q,root:{'sources':[]});data=a.package({**p,'review_id':review['record_id'],'note':'Inspect actual drainage capacity.'},app,root);f=tmp_path/'export.zip';f.write_bytes(data)
    with zipfile.ZipFile(f) as z:
        man=json.loads(z.read('manifest.json'));assert all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in man['sha256'].items());assert 'reproduce/elevation.npy' in z.namelist();assert 'reproduce/elevation.tif' in z.namelist();assert not any(k.startswith('reviews/') for k in z.namelist())
    out=build(f,tmp_path/'index.html',app);assert 'Inspect actual drainage capacity.' not in out.read_text();assert 'CONTROLLED TEST ONLY' in out.read_text()

def test_claim_checker_rejects_wrong_number_unit_or_source():
    facts={'storage':{'value':10.,'unit':'m3','source_id':'LOCAL-RUN','tolerance':.1}};base={'metric':'storage','value':10.,'unit':'m3','source_id':'LOCAL-RUN'}
    assert a.check_claims([base],facts,{'LOCAL-RUN'})['all_passed']
    for k,v in [('value',100),('unit','mm'),('source_id','E99')]:assert not a.check_claims([{**base,k:v}],facts,{'LOCAL-RUN'})['all_passed']

def test_momentum_analytic_reference():
    b=a.momentum_benchmark();assert b['refinement_improves'];assert max(abs(x['mass_error_m3']) for x in b['cases'])<1e-6

def test_checked_ai_fails_closed(tmp_path,monkeypatch):
    import ai_provider as ai
    app,root,p,e,r=setup(tmp_path,monkeypatch);review=m.paired_review(p,app,root);p={**p,'review_id':review['record_id']}
    monkeypatch.setattr(ai,'_config',lambda:('mock','https://example.org','test','not-used'))
    monkeypatch.setattr(ai,'_generate',lambda *args:'not JSON');assert not a.checked_ai(p,app,root)['passed']
    f=a.facts(r,review['radar_selection']);claims=[{'metric':k,'value':v['value'],'unit':v['unit'],'source_id':v['source_id']} for k,v in f.items()]
    monkeypatch.setattr(ai,'_generate',lambda *args:json.dumps({'claims':claims}));assert a.checked_ai(p,app,root)['passed']
    claims[0]['value']+=1;assert not a.checked_ai(p,app,root)['passed']
