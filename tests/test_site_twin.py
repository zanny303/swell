import io,json,zipfile,hashlib,datetime,csv
import numpy as np
import rasterio as rio
from rasterio.io import MemoryFile
import site_twin as st
import hybrid_calibration as hy
import pytest

def fixture(p,water=False,nodata=False):
    d=st.domain(p);n=d['n'];r,c=np.indices((n,n));a=(100+0.1*((r-n/2)**2+(c-n/2)**2)).astype('float32') if not water else ((r+c)%2).astype('float32');
    if nodata:a[0,0]=-9999
    with MemoryFile() as m:
        with m.open(driver='GTiff',width=n,height=n,count=1,dtype='float32',crs=d['epsg'],transform=rio.Affine(*d['transform']),nodata=-9999) as f:f.write(a,1)
        return m.read()

def test_grid_and_coverage(tmp_path):
    p=dict(lat=32.7767,lon=-96.797,radius=100,dx=20,datum='TEST ONLY',meters=True)
    d=st.acquire(p,tmp_path,fixture(p));assert d['n']==10 and d['epsg']==32614;assert abs(d['cell_coordinates'][5][5][0]-p['lat'])<.001
    with pytest.raises(ValueError):st.acquire(p,tmp_path,fixture(p,nodata=True))
    with pytest.raises(ValueError):st.acquire({**p,'meters':False},tmp_path,fixture(p))

def test_slope_and_conservation():
    z=np.tile(np.linspace(4,0,10),(10,1));a,p,b=st.simulate(z,20,[30,0],0,0);assert (a>=0).all();assert abs(b[-1]['balance_error_m3'])<1e-7;assert a[-1,:,-1].mean()>a[-1,:,0].mean()
    c,_,m=st.simulate(z,20,[30,0],0,10);assert m[-1]['stored_m3']<b[-1]['stored_m3'];assert abs(m[-1]['balance_error_m3'])<1e-7

def test_uniform_and_dry():
    z=np.zeros((6,6));a,p,b=st.simulate(z,20,[10],0,0);assert np.allclose(a,.01);a,p,b=st.simulate(z,20,[0],0,0);assert np.max(a)==0

def test_green_ampt():
    z=np.zeros((6,6));a,p,b=st.simulate(z,20,[30],2,0);a,p,c=st.simulate(z,20,[30],2,0,suction_deficit_m=.04);assert c[-1]['infiltrated_m3']>b[-1]['infiltrated_m3'];assert abs(c[-1]['balance_error_m3'])<1e-7

def test_real_file_format_and_package(tmp_path):
    p=dict(lat=32.7767,lon=-96.797,radius=100,dx=20,datum='TEST ONLY',meters=True);d=st.acquire(p,tmp_path,fixture(p));q={'id':d['id'],'rain_mm_h':[30,0],'edits':[{'row':5,'col':5,'kind':'drain','rate':20}],'role':'engineer'};r=st.run(q,tmp_path);assert r['scenario'][-1]['stored_m3']<r['baseline'][-1]['stored_m3'];assert (tmp_path/r['earth_overlay']['image'].lstrip('/')).is_file();z=zipfile.ZipFile(io.BytesIO(st.pack(q,tmp_path)));m=json.loads(z.read('manifest.json'));assert not m['engineering_approved'];assert all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in m['sha256'].items());
    with MemoryFile(z.read('intervention-peak-depth.tif')) as mem,mem.open() as f:assert f.crs.to_epsg()==32614 and f.units[0]=='m'

def test_observed_water_masks(tmp_path):
    p=dict(lat=32.7767,lon=-96.797,radius=100,dx=20,datum='TEST ONLY',meters=True);d=st.acquire(p,tmp_path,fixture(p));r=st.run({'id':d['id'],'rain_mm_h':[100],'infiltration':0,'event_start_utc':'2026-01-01T11:00:00Z'},tmp_path);q=dict(result_id=r['run_id'],hour=1,product='binary',observed_utc='2026-01-01T12:00:00Z');a=st.compare_water(q,tmp_path,fixture(p,water=True));assert a['clear_pixels']==100 and a['tp']+a['fp']+a['fn']+a['tn']==100
    with pytest.raises(ValueError):st.compare_water({**q,'observed_utc':'2026-01-02T12:00:00Z'},tmp_path,fixture(p,water=True))
    z=zipfile.ZipFile(io.BytesIO(st.pack({'result_id':r['run_id'],'role':'planner'},tmp_path)));assert any(x.startswith('comparisons/') for x in z.namelist())

def test_hybrid_holdout_abstention():
    f=io.StringIO();w=csv.writer(f);w.writerow(['issue_utc','target_utc','physics_depth_m','rain_mm','antecedent_moisture','observed_depth_m']);start=datetime.datetime(2020,1,1,tzinfo=datetime.timezone.utc)
    for i in range(150):
        t=start+datetime.timedelta(days=i);x=(i%10+1)/10;w.writerow([(t-datetime.timedelta(hours=1)).isoformat(),t.isoformat(),x,x*10,.3,x+.1])
    m=hy.train(f.getvalue().encode());assert m['eligible_for_review'];assert hy.predict(m,[.5,5,.3])['hybrid_depth_m']==pytest.approx(.6,abs=.001);assert hy.predict(m,[9,5,.3])['status']=='abstain'

def test_nisar_raw_phase_preflight(tmp_path):
    import h5py
    import nisar_preflight as n
    p=tmp_path/'test_only.h5';parent='/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram';g=parent+'/HH'
    with h5py.File(p,'w') as f:
        f[g+'/unwrappedPhase']=np.ones((3,4),dtype='float32');f[g+'/coherenceMagnitude']=np.full((3,4),.8);f[g+'/connectedComponents']=np.ones((3,4));f[parent+'/xCoordinates']=np.arange(4)*80+700000;f[parent+'/yCoordinates']=np.arange(3)*80+3600000;f[parent+'/projection']=32614
    m=n.inspect_export(p,tmp_path/'out','beta');assert m['valid_fraction']==1 and not m['science_approved'] and m['posting_m']==[80.,80.]
    with rio.open(tmp_path/'out'/'phase-raw-masked.tif') as f:assert f.crs.to_epsg()==32614 and f.units[0]=='rad' and f.transform.e==-80

def test_registered_rgb_upload(tmp_path):
    p=dict(lat=32.7767,lon=-96.797,radius=100,dx=20,datum='TEST ONLY',meters=True);d=st.acquire(p,tmp_path,fixture(p));n=d['n']
    with MemoryFile() as m:
        with m.open(driver='GTiff',width=n,height=n,count=3,dtype='uint8',crs=d['epsg'],transform=rio.Affine(*d['transform']),photometric='RGB') as f:f.write(np.full((3,n,n),120,dtype='uint8'))
        raw=m.read()
    meta=st.register_photo(tmp_path,d['id'],raw,'TEST NUMERICAL FIXTURE');assert (tmp_path/meta['image'].lstrip('/')).is_file()
    with pytest.raises(ValueError):st.register_photo(tmp_path,d['id'],fixture(p),'test')

def test_forecast_snapshot_mismatch(tmp_path):
    p=dict(lat=32.7767,lon=-96.797,radius=100,dx=20,datum='TEST ONLY',meters=True);d=st.acquire(p,tmp_path,fixture(p));folder=st.storage(tmp_path)/'forecasts';folder.mkdir();fid='a'*64;(folder/(fid+'.json')).write_text(json.dumps({'lat':p['lat'],'lon':p['lon'],'rows':[{'rain_mm':2,'utc':'2026-01-01T12:00:00Z'}]}))
    with pytest.raises(ValueError):st.run({'id':d['id'],'rain_mm_h':[5],'forecast_id':fid},tmp_path)
    r=st.run({'id':d['id'],'rain_mm_h':[2],'forecast_id':fid},tmp_path);assert r['inputs']['event_start_utc']=='2026-01-01T11:00:00+00:00';assert r['inputs']['forcing']['rows'][0]['rain_mm']==2


def test_usgs_terrain_cache_and_refresh(tmp_path, monkeypatch):
    p=dict(lat=32.7767,lon=-96.797,radius=100,dx=20)
    calls=[]
    raw=fixture(p)
    def fake_fetch(url):
        calls.append(url)
        return raw
    monkeypatch.setattr(st,'fetch_bytes',fake_fetch)
    first=st.acquire(p,tmp_path)
    assert first['cache_status']=='downloaded'
    assert len(calls)==1
    # Same request should be served from the local DEM cache without a provider call.
    monkeypatch.setattr(st,'fetch_bytes',lambda url: (_ for _ in ()).throw(AssertionError('cache miss')))
    second=st.acquire(p,tmp_path)
    assert second['cache_status']=='cached'
    assert second['id']==first['id']
    assert np.allclose(second['elevation'],first['elevation'])
    # Explicit refresh bypasses the cache and replaces the request index.
    monkeypatch.setattr(st,'fetch_bytes',fake_fetch)
    fresh=st.acquire({**p,'refresh':True},tmp_path)
    assert fresh['cache_status']=='downloaded'
    assert len(calls)==2


def test_provider_fetch_retries_transient_network_errors(monkeypatch):
    calls=[]
    def offline(*args,**kwargs):
        calls.append(1)
        raise st.urllib.error.URLError('temporary network failure')
    monkeypatch.setattr(st,'urlopen',offline)
    monkeypatch.setattr(st.time,'sleep',lambda _:None)
    with pytest.raises(RuntimeError,match='3 attempts'):
        st.fetch_bytes('https://example.invalid/dem.tif')
    assert len(calls)==3


def test_provider_json_error_is_not_treated_as_a_raster(monkeypatch):
    class Headers:
        def get(self,key,default=None): return 'application/json'
    class Response:
        headers=Headers()
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self,n): return b'{"error":{"message":"No raster data for this extent"}}'
    monkeypatch.setattr(st,'urlopen',lambda *args,**kwargs:Response())
    with pytest.raises(RuntimeError,match='No raster data for this extent'):
        st.fetch_bytes('https://example.invalid/exportImage')
