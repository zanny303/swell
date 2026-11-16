import json,io,zipfile
import numpy as np, pytest, rasterio as rio
from rasterio.io import MemoryFile
import site_twin as st, science_observations as so, science_events as se, science_plans as sp, global_dem as gd
from test_site_twin import fixture

P=dict(lat=32.7767,lon=-96.797,radius=150,dx=30,datum='TEST FIXTURE',meters=True)
def wtr(p,ar):
 d=st.domain(p); n=d['n'];
 with MemoryFile() as mf:
  with mf.open(driver='GTiff',width=n,height=n,count=1,dtype='uint8',crs=d['epsg'],transform=rio.Affine(*d['transform']),nodata=255) as ds:ds.write(ar.astype('uint8'),1)
  return mf.read()
def test_eonet_geometry():
 x=se.normalize({'events':[{'id':'event-1','title':'Fixture storm','categories':[{'title':'Storms'}],'geometry':[{'type':'Point','coordinates':[4,5],'date':'2026-01-01T00:00:00Z'},{'type':'Point','coordinates':[6,7],'date':'2026-01-02T00:00:00Z'},{'type':'Point','coordinates':[500,7],'date':'2026-01-03T00:00:00Z'}]},{'id':'invalid','geometry':[]}]})
 assert len(x['features'])==1 and x['features'][0]['geometry']['coordinates']==[6,7]
def test_global_fallback(tmp_path,monkeypatch):
 p={**P,'lat':48.21,'lon':16.37};raw=fixture(p);calls=[]
 def fetch(url,**kw):calls.append(url);return raw
 monkeypatch.setattr(st,'fetch_bytes',fetch);d=st.acquire(p,tmp_path);assert 'GLO-30' in d['source'] and d['upstream_tiles'][0]['sha256']==st.digest(raw);assert 'N48_00_E016_00' in calls[0];assert st.acquire(p,tmp_path)['cache_status']=='cached'
 assert 'S34_00_W059_00' in gd.tile_url(-34,-59,90)
def test_water_registration_comparison(tmp_path):
 d=st.acquire(P,tmp_path,fixture(P));ar=np.zeros((10,10),dtype='uint8');ar[:,0]=255;ar[:,1]=251;ar[:,2]=3;ar[:,3:6]=1;raw=wtr(P,ar);m=so.register_water(tmp_path,d['id'],raw,'DSWx-S1','2026-01-01T12:00:00Z','OPERA_B01_WTR.tif');assert (tmp_path/m['image'].lstrip('/')).exists();assert so.list_observations(tmp_path,d['id'])[0]['id']==m['id'];assert m['metrics']['open_water_fraction_of_clear_display_pixels']>0
 r=st.run({'id':d['id'],'rain_mm_h':[100],'infiltration':0,'event_start_utc':'2026-01-01T11:00:00Z'},tmp_path);x=so.compare_registered(tmp_path,{'result_id':r['run_id'],'observation_id':m['id'],'hour':1});assert x['clear_pixels']==70;assert x['tp']+x['fp']+x['fn']+x['tn']==70
 with pytest.raises(ValueError):so.register_water(tmp_path,d['id'],raw,'DSWx-S1','2026-01-01T12:00:00Z','fake_BWTR.tif')
def test_plans(tmp_path):
 d=st.acquire(P,tmp_path,fixture(P));r=st.run({'id':d['id'],'rain_mm_h':[100],'infiltration':0},tmp_path);x=sp.plan({'result_id':r['run_id'],'role':'engineer','optimize':True},tmp_path);assert len(x['ranked_scenarios'])==4 and not x['engineering_approved'];assert x['ranked_scenarios'][0]['wet_area_m2']<=x['ranked_scenarios'][-1]['wet_area_m2'];assert max(abs(a['water_balance_error_m3']) for a in x['ranked_scenarios'])<1e-6
 z=zipfile.ZipFile(io.BytesIO(st.pack({'result_id':r['run_id'],'role':'engineer'},tmp_path)));assert any(k.startswith('reviews/plan-') for k in z.namelist())
def test_water_requires_integer(tmp_path):
 d=st.acquire(P,tmp_path,fixture(P));
 with pytest.raises(ValueError):so.register_water(tmp_path,d['id'],fixture(P,water=True),'DSWx-HLS','2026-01-01T12:00:00Z','WTR.tif')

def test_shallow_water_lake_at_rest_and_dam_break():
 from shallow_water import step,simulate
 z=np.tile(np.linspace(0,1,10),(10,1));h=2-z;mx=np.zeros_like(h);my=mx.copy();a,b,c=step(z,h,mx,my,10,.2);assert np.max(abs(a-h))<1e-12 and np.max(abs(b))<1e-12 and np.max(abs(c))<1e-12
 z=np.zeros((10,10));h=np.zeros_like(z);h[:,:5]=.5;a,b,c=step(z,h,mx,my,10,.1);assert a[:,5].min()>0 and a.min()>=0 and a.sum()==pytest.approx(h.sum());assert b[:,4].max()>0
 frames,peak,bud=simulate(z,20,[30],0,0);assert np.allclose(frames[-1],.03) and abs(bud[-1]['balance_error_m3'])<1e-7

def test_momentum_run(tmp_path):
 d=st.acquire(P,tmp_path,fixture(P));r=st.run({'id':d['id'],'rain_mm_h':[30],'infiltration':0,'solver':'momentum'},tmp_path);assert r['model']=='SWE-hydrostatic-Rusanov-1.0';assert r['inputs']['solver']=='momentum';assert abs(r['baseline'][-1]['balance_error_m3'])<1e-5
 from decision_engine import numerical_review
 m=numerical_review({'result_id':r['run_id']},tmp_path);assert m['peak_depth_mae_m']>=0

def test_physics_ai_hard_mass_and_step():
 torch=pytest.importorskip('torch');from physics_ai import make_model,conservative_step
 torch.set_num_threads(1);m=make_model(torch);z=torch.arange(16,dtype=torch.float32).reshape(1,1,4,4)*.1;rate=torch.tensor([20.,40.]);t=torch.tensor([1800.,3600.]);a=m(z,rate,t);assert float(a.detach().min())>=0 and torch.allclose(a.mean((1,2,3)),rate*t/3600000,atol=1e-7)
 b=conservative_step(torch,z,a,rate,20.);assert float(b.detach().min())>=0 and torch.allclose(b.mean((1,2,3)),rate*(t+30)/3600000,atol=1e-7);b.mean().backward();assert all(p.grad is None or torch.isfinite(p.grad).all() for p in m.parameters())
