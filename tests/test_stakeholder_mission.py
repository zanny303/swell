import hashlib,io,json,zipfile
import numpy as np
import pytest
import stakeholder_mission as m
import site_twin as st
from test_site_twin import fixture

def setup(tmp_path,monkeypatch):
    # Test-only synthetic arrays used to exercise the real-provider contract; never shipped as a study.
    app=tmp_path;root=app/'site';(root/'data').mkdir(parents=True);(app/'out').mkdir()
    lat,lon=32.7767,-96.797
    s={'name':'CONTROLLED TEST ONLY','source':'NASA NISAR GUNW provider mock','bbox':[lon-.03,lat-.03,lon+.03,lat+.03],'n':2,'pass_days':[0,12],'observed_los':[[[0,0],[0,0]],[[10,-9999],[3,7]]],'coh':[[.9,.8],[.1,.8]],'reference':[[0,0],[0,0]],'scientific_validity':{'status':'unvalidated'}}
    (root/'data/site.json').write_text(json.dumps(s));(app/'out/real_site_provenance.json').write_text(json.dumps({'bbox':s['bbox'],'steps':{'radar':{'pairs':[{'ref':'2026-07-05','sec':'2026-07-17'}]}}}));monkeypatch.setattr(st,'fetch_bytes',lambda url:fixture({'lat':lat,'lon':lon,'radius':100,'dx':20}))
    d=st.acquire({'lat':lat,'lon':lon,'radius':100,'dx':20},root);r=st.run({'id':d['id'],'rain_mm_h':[30,10],'infiltration':5,'edits':[{'row':5,'col':5,'kind':'drain','rate':25}]},root)
    ev=m.evidence(app);p={'site_hash':ev['hash'],'row':0,'col':0,'lat':lat,'lon':lon,'role':'engineer','result_id':r['run_id']}
    return app,root,p,ev,r

def test_mission_evidence_mask_and_provenance(tmp_path,monkeypatch):
    app,root,p,e,r=setup(tmp_path,monkeypatch)
    assert e['valid_cells']==2 and e['dates']==['2026-07-05','2026-07-17'] and e['cells'][0]['los_mm']==10
    assert e['gnss'] is None
    with pytest.raises(ValueError,match='eligible'):m.selection(app,{**p,'row':0,'col':1})
    with pytest.raises(ValueError,match='changed'):m.selection(app,{**p,'site_hash':'0'*64})
    s=json.loads((root/'data/site.json').read_text());s['source']='SYNTHETIC';(root/'data/site.json').write_text(json.dumps(s))
    with pytest.raises(ValueError,match='real NISAR'):m.evidence(app)

def test_paired_review_and_package(tmp_path,monkeypatch):
    app,root,p,e,r=setup(tmp_path,monkeypatch)
    res=m.paired_review(p,app,root);assert res['numerical_mass_balance'] and len(res['cases'])==4 and not res['engineering_approved'];assert res['storage_reduction_range_m3'][0]>=0
    assert res['metrics']['baseline_storage_m3']==pytest.approx(r['baseline'][-1]['stored_m3'])
    # The test repository has a local literature corpus. Mock the independent retrieval only.
    monkeypatch.setattr(m.science_plans,'research',lambda q,root:{'sources':[]})
    px={**p,'review_id':res['record_id'],'note':'Inspect actual drainage capacity before field design.'}
    with zipfile.ZipFile(io.BytesIO(m.package(px,app,root))) as f:
        manifest=json.loads(f.read('manifest.json'));assert not manifest['engineering_approved'];assert all(hashlib.sha256(f.read(k)).hexdigest()==v for k,v in manifest['sha256'].items());assert 'mission/role-plan.json' in f.namelist();assert 'baseline-peak-depth.tif' in f.namelist();assert json.loads(f.read('mission/decision.json'))['status']=='DRAFT FIELD INVESTIGATION'
    with pytest.raises(ValueError,match='stale'):m.package({**px,'role':'resident'},app,root)
    with pytest.raises(ValueError,match='does not match'):m.paired_review({**p,'lat':p['lat']+.001},app,root)

def test_explain_uses_saved_run(tmp_path,monkeypatch):
    app,root,p,e,r=setup(tmp_path,monkeypatch);res=m.paired_review(p,app,root)
    import ai_provider as ai
    monkeypatch.setattr(ai,'_evidence',lambda q,c:({}, {}, [{'id':'E1','title':'Test','url':'https://example.org'}],False))
    monkeypatch.setattr(ai,'_config',lambda:('meta','https://example.org','test','not-used'))
    def generate(q,site,context,sources):
        assert site['local_run']['metrics']==res['metrics'] and site['site_hash']==e['hash'];assert len(sources)==1
        return 'Check field evidence [LOCAL-RUN].'
    monkeypatch.setattr(ai,'_generate',generate)
    a=m.explain({**p,'review_id':res['record_id'],'question':'Explain'},app,root)
    assert a['provider']=='meta' and a['run_id']==r['run_id'] and a['answer']


def test_pair_coherence_cache_must_match(tmp_path,monkeypatch):
    app,root,p,e,r=setup(tmp_path,monkeypatch)
    f=app/'out/real_site_provenance.json';d=json.loads(f.read_text());d['site']='dallas';f.write_text(json.dumps(d));s=json.loads((root/'data/site.json').read_text());raw=np.array(s['observed_los'],float);raw[raw==-9999]=np.nan
    dest=app/'out/dallas.npz';np.savez(dest,los=raw,pass_days=s['pass_days'],bbox=s['bbox'],coh_pairs=np.array([[[.1,.9],[.9,.8]]]))
    updated=m.evidence(app);assert updated['quality_basis'].startswith('Last interferometric pair');assert [(x['row'],x['col']) for x in updated['cells']]==[(1,1),(1,0)]
    raw[-1,0,0]=999;np.savez(dest,los=raw,pass_days=s['pass_days'],bbox=s['bbox'],coh_pairs=np.ones((1,2,2)))
    assert m.evidence(app)['quality_basis'].startswith('Study-level')

def test_real_home_route_guided(tmp_path,monkeypatch):
    import run_swell,threading,urllib.request,os
    from http.server import ThreadingHTTPServer
    app,root,p,e,r=setup(tmp_path,monkeypatch)
    (root/'decision-mission.html').write_text('guided decision room');(root/'index.html').write_text('original Earth studio')
    monkeypatch.setattr(run_swell,'ROOT',root);monkeypatch.setattr(run_swell,'APP',app);monkeypatch.chdir(root)
    server=ThreadingHTTPServer(('127.0.0.1',0),run_swell.SWELLHandler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        host=f'http://127.0.0.1:{server.server_port}'
        assert urllib.request.urlopen(host+'/',timeout=5).read()==b'guided decision room'
        assert urllib.request.urlopen(host+'/earth',timeout=5).read()==b'original Earth studio'
        assert urllib.request.urlopen(host+'/api/mission/evidence',timeout=5).status==200
    finally:server.shutdown();server.server_close();thread.join(timeout=2)
