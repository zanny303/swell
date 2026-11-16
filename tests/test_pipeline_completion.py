import numpy as np, h5py, pytest, rasterio
from pyproj import Transformer
from radar_change import change
from forecast_ensemble import evaluate
from test_decision_engine import setup_run

def test_radar(tmp_path):
    a=tmp_path/'NISAR_L2_PR_GCOV_001_001_A_001_4005_DHDH_A_20260101T000000_20260101T000100_ABCDEF_P_C_001.h5'
    b=tmp_path/a.name.replace('20260101','20260113').replace('GCOV_001','GCOV_002')
    for path,power in [(a,1.),(b,.1)]:
        with h5py.File(path,'w') as f:
            g=f.create_group('/science/LSAR/GCOV/grids/frequencyA');g['xCoordinates']=[500005,500015,500025];g['yCoordinates']=[35,25,15];g['projection']=32615;g['HHHH']=np.full((3,3),power);g['mask']=np.array([[0,1,1],[1,1,1],[1,1,255]]);g['numberOfLooks']=np.full((3,3),5.)
    inv=Transformer.from_crs(32615,4326,always_xy=True);w,s=inv.transform(500000,10);e,n=inv.transform(500030,40);bbox=[w,s,e,n]
    r=change(a,b,bbox,tmp_path/'out');assert r['valid_pixels']==7;assert r['median_delta_db']==pytest.approx(-10)
    with rasterio.open(tmp_path/'out/delta-db.tif') as ds:assert np.isnan(ds.read(1)[0,0]);assert ds.crs.to_epsg()==32615
    with pytest.raises(ValueError):change(b,a,bbox,tmp_path/'out2')

def test_ensemble(tmp_path):
    _,r=setup_run(tmp_path);o=evaluate({'result_id':r['run_id']},tmp_path);assert len(o['members'])==9 and not o['engineering_approved'];assert max(abs(m['water_balance_error_m3']) for m in o['members'])<1e-5;assert o['wet_in_any_member_m2']>=o['wet_in_all_members_m2']

def test_external_product(tmp_path):
    import json, hashlib, site_twin as st
    from model_products import register
    _,r=setup_run(tmp_path);d=r['site'];p=tmp_path/'output.tif'
    with rasterio.open(p,'w',driver='GTiff',width=d['n'],height=d['n'],count=1,dtype='float32',crs=d['epsg'],transform=rasterio.Affine(*d['transform'])) as ds:ds.write(np.ones((d['n'],d['n']),dtype='float32'),1)
    m=dict(kind='water_probability',model='test model',version='1',source='test only',input_provenance='fixture',valid_time_utc='2026-01-01T00:00:00Z',units='1',sha256=hashlib.sha256(p.read_bytes()).hexdigest());o=register(tmp_path,d['id'],p,m);assert o['coverage']==1 and not o['engineering_approved']
    with pytest.raises(ValueError):register(tmp_path,d['id'],p,{**m,'sha256':'bad'})

def test_literature(tmp_path):
    import json
    from literature_rag import retrieve,explain
    (tmp_path/'note.txt').write_text('Radar backscatter changes can reflect surface moisture. Water extent verification requires independent evidence.')
    (tmp_path/'corpus.json').write_text(json.dumps([dict(title='test note',url='https://example.org/test',file='note.txt')]))
    x=retrieve('radar moisture',tmp_path/'corpus.json');assert x[0]['id']=='E1' and 'moisture' in x[0]['text'];assert not retrieve('zzzzzzz',tmp_path/'corpus.json');assert explain('q',x,None)['status'].startswith('retrieval only')
