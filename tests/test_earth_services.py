import json
from pathlib import Path
import pytest
import earth_services as e

def test_bbox():
    assert e.bbox_value('-97,32,-96,33')=='-97.0,32.0,-96.0,33.0'
    for x in ['nan,0,1,2','1,0,-1,2','0,0,1,100']:
        with pytest.raises(ValueError):e.bbox_value(x)

def test_catalog(monkeypatch):
    def get(url,*a):
        assert 'NISAR+GUNW' in url
        return json.dumps({'feed':{'entry':[{'id':'C123-ASF','title':'Fixture','short_name':'FIXTURE'}]}}).encode(),'test','retrieved'
    monkeypatch.setattr(e,'get',get)
    assert e.catalog({})['collections'][0]['id']=='C123-ASF'

def test_granules(monkeypatch):
    def get(url,*a):
        assert 'collection_concept_id=C123-ASF' in url and 'bounding_box=' in url
        return json.dumps({'feed':{'entry':[{'id':'G123-ASF','links':[{'href':'https://example.org/data'},{'href':'javascript:bad'}]}]}}).encode(),'test','retrieved'
    monkeypatch.setattr(e,'get',get)
    assert len(e.granules({'id':['C123-ASF']})['results'][0]['links'])==1

def test_gibs(monkeypatch):
    monkeypatch.setattr(e,'get',lambda *a:(b'<WMS><Layer><Layer><Name>X</Name><Title>Example</Title><Dimension name="time" default="2024-01-01">2024-01-01</Dimension></Layer></Layer></WMS>','test','retrieved'))
    assert e.capabilities()['layers'][0]['id']=='X'

def test_raster(tmp_path):
    np=pytest.importorskip('numpy');r=pytest.importorskip('rasterio')
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin
    with MemoryFile() as mem:
        with mem.open(driver='GTiff',width=4,height=4,count=1,dtype='float32',crs='EPSG:4326',transform=from_origin(-97,33,.1,.1)) as ds:ds.write(np.arange(16,dtype='float32').reshape(4,4),1)
        raw=mem.read()
    d=e.raster_preview(raw,'fixture.tif',tmp_path)
    assert (tmp_path/d['preview'].lstrip('/')).exists();assert d['bbox'][0]==-97;assert d['native_shape']==[4,4]
