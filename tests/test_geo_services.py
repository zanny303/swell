import json,io,math
from datetime import datetime,timezone,timedelta
import pytest
import geo_services as g

def test_ai_forcing(monkeypatch):
    today=datetime.now(timezone.utc).date();days=[(today+timedelta(days=x)).isoformat() for x in range(15)]
    def get(url,*args):
        assert 'ecmwf_aifs025_single' in url
        return json.dumps({'daily_units':{'precipitation_sum':'mm'},'daily':{'time':days,'precipitation_sum':[1]*14+[None]},'latitude':32.75,'longitude':-96.75}).encode(),'fixture','retrieved'
    monkeypatch.setattr(g,'get',get);d=g.forecast({'lat':['32.8'],'lon':['-96.8']});assert len(d['daily'])==13 and d['daily'][0]['date']==days[1] and d['model_run_utc'] is None

def test_coords():
    for q in ({'lat':['nan'],'lon':['0']},{'lat':['91'],'lon':['1']}):
        with pytest.raises(ValueError):g.coords(q)

def test_usgs(monkeypatch):
    monkeypatch.setattr(g,'get',lambda *a:(b'{"type":"FeatureCollection","features":[]}', 'fixture','retrieved'));assert g.quakes({})['collection']['features']==[]

def test_firms(monkeypatch):
    monkeypatch.setenv('FIRMS_MAP_KEY','fake-test-key');monkeypatch.setattr(g,'get',lambda *a:(b'latitude,longitude,acq_date,acq_time,frp,confidence\n32.8,-96.8,2025-06-01,0300,5,n\n','fixture','retrieved'))
    d=g.fires({'bbox':['-97,32,-96,33']});assert d['collection']['features'][0]['geometry']['coordinates']==[-96.8,32.8];assert 'fake-test-key' not in str(d)

def test_wmts(monkeypatch):
    xml='''<Capabilities xmlns="http://www.opengis.net/wmts/1.0" xmlns:o="http://www.opengis.net/ows/1.1"><Contents><Layer><o:Identifier>TEST</o:Identifier><o:Title>Test</o:Title><Style><o:Identifier>default</o:Identifier></Style><Format>image/png</Format><TileMatrixSetLink><TileMatrixSet>Global</TileMatrixSet></TileMatrixSetLink></Layer><TileMatrixSet><o:Identifier>Global</o:Identifier><TileMatrix><o:Identifier>0</o:Identifier><TileWidth>256</TileWidth><TileHeight>256</TileHeight><MatrixWidth>1</MatrixWidth><MatrixHeight>1</MatrixHeight></TileMatrix></TileMatrixSet></Contents></Capabilities>'''
    monkeypatch.setattr(g,'get',lambda *a:(xml.encode(),'fixture','retrieved'));assert g.wmts({})['layers'][0]['labels']==['0']

def test_native_tile(tmp_path):
    import numpy as np,rasterio,earth_services
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin
    from PIL import Image
    with MemoryFile() as mem:
        with mem.open(driver='GTiff',width=20,height=20,count=1,dtype='float32',crs='EPSG:4326',transform=from_origin(-97,33,.05,.05)) as ds:ds.write(np.arange(400,dtype='float32').reshape(20,20),1)
        raw=mem.read()
    d=earth_services.raster_preview(raw,'test.tif',tmp_path);z=8;x=int((-96.5+180)/360*2**z);y=int((1-math.asinh(math.tan(math.radians(32.5)))/math.pi)/2*2**z)
    img=Image.open(io.BytesIO(g.raster_tile(tmp_path,d['sha256'],z,x,y)));assert img.size==(256,256);a=np.asarray(img);assert a[...,3].max()==255 and a[...,3].min()==0
