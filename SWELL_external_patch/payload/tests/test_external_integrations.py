import datetime as dt,json,sys,types
from pathlib import Path
import numpy as np
import external_evidence as ev
import terrain_routing as tr

def date(x):return dt.date.fromisoformat(x)

def test_station_catalog_spatial_temporal_filter():
    rows=b'Sta Lat Long Hgt X Y Z Dtbeg Dtend Dtmod NumSol\nABCD 32.8 -96.8 100 1 2 3 2020-01-01 2026-10-31 2026-11-01 900\nOLD1 32.8 -96.8 100 1 2 3 2020-01-01 2023-01-01 2023-01-01 800\nFAR1 35 -100 100 1 2 3 2020-01-01 2026-10-31 2026-11-01 900\n'
    found=ev.stations(rows,[-97,32.6,-96.5,33],[date('2026-07-05'),date('2026-10-21')])
    assert [x['station'] for x in found]==['ABCD'] and found[0]['covers_full_window']

def test_daily_positions_include_integer_offset_and_no_interpolation():
    raw=b'site YYMMMDD u0(m) ____up(m) sig_u(m)\nABCD 26JUL05 100 .995 .002\nABCD 26JUL29 101 .005 .003\n'
    out=ev.series(raw,'ABCD',[date('2026-07-05'),date('2026-07-17'),date('2026-07-29')]);assert [x['vertical_change_mm'] for x in out]==[0,None,10]

def test_paper_search_and_cached_retrieval(tmp_path,monkeypatch):
    data={'results':[{'id':'https://openalex.org/W123','title':'Radar moisture deformation','abstract_inverted_index':{'Radar':[0],'moisture':[1],'deformation':[2]},'is_retracted':False,'type':'article'},{'id':'https://openalex.org/W456','title':'Retracted','is_retracted':True}]}
    monkeypatch.setattr(ev,'fetch',lambda *a:json.dumps(data).encode());r=ev.search(tmp_path,'radar moisture deformation');assert len(r['sources'])==1
    assert ev.research_for_question(tmp_path,'radar moisture deformation')[0]['id']=='OA-W123';assert not ev.research_for_question(tmp_path,'cooking pasta')

def test_dem_routing_adapter_calls_external_engine(tmp_path,monkeypatch):
    import site_twin
    monkeypatch.setattr(site_twin,'load',lambda *a:({'source':'test DEM fixture','source_sha256':'abc','transform':[10,0,0,0,-10,20]},np.array([[4.,3.],[2.,1.]])))
    calls={}
    def from_dem(data,**kw):
        calls.update(kw);return types.SimpleNamespace(upstream_area=lambda unit:np.array([[100,100],[100,400]]),basins=lambda:np.ones((2,2),int))
    monkeypatch.setitem(sys.modules,'pyflwdir',types.SimpleNamespace(from_dem=from_dem));monkeypatch.setattr(tr.importlib.metadata,'version',lambda _: 'fixture')
    d=tr.analyze(tmp_path,'id');assert calls['latlon'] is False and d['largest_upstream_m2']==400 and d['largest_cell']==[1,1]

def test_gnss_cache_bound_to_site(tmp_path):
    key='a'*64;ev._save(tmp_path/'out/external_evidence'/f'gnss-{key}.json',{'site_sha256':key});assert ev.cached_gnss(tmp_path,key)['site_sha256']==key;assert ev.cached_gnss(tmp_path,'b'*64) is None;assert ev.cached_gnss(tmp_path,'../bad') is None
