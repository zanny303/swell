import io,json
from urllib.parse import urlparse,parse_qs
import pytest,numpy as np
import planetary_products as p

def test_targeted_query_and_filter():
    rows=[{'id':'urn:nasa:pds:context:service:generate_tool','title':'Generate Tool'}, {'id':'urn:nasa:pds:abc:1','product_class':'Product_Observational','target_name':['Mars']}, {'id':'urn:nasa:pds:lro:lola:1','product_class':'Product_Observational','target_name':['Moon'],'title':'LOLA observation'}, {'id':'urn:nasa:pds:lro:doc:1','product_class':'Product_Document','target_name':'Moon'}]
    def open_(req,timeout):
        assert '/classes/Product_Observational' in req.full_url
        q=parse_qs(urlparse(req.full_url).query)
        assert q['q']==['target_name eq "Moon"'] and q['keywords']==['LOLA']
        return io.BytesIO(json.dumps({'data':rows}).encode())
    d=p.search('moon','LOLA',opener=open_)
    assert [x['title'] for x in d['results']]==['LOLA observation']
    assert d['results'][0]['url'].startswith('https://pds.nasa.gov/api/search/1/products/')
    with pytest.raises(ValueError):p.search('moon" or true')

def test_planetary_dem_gradient(tmp_path):
    rasterio=pytest.importorskip('rasterio');from rasterio.transform import from_origin
    dem=tmp_path/'test.tif';z=np.tile(np.arange(100,dtype='float32')*10,(100,1));z[50,50]=-9999
    with rasterio.open(dem,'w',driver='GTiff',height=100,width=100,count=1,dtype='float32',crs='+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +R=3396190 +units=m +no_defs',transform=from_origin(-50000,50000,1000,1000),nodata=-9999) as d:d.write(z,1)
    q=p.dem_window('mars',0,0,local_path=dem);assert q['valid_cells']==65*65-1
    assert q['slope_stats']['median']==pytest.approx(np.degrees(np.arctan(.01)),rel=.01)
    assert q['elevation_m'][32][32] is None and q['slope_deg'][32][32] is None
    assert q['source'].startswith('User supplied')
    with pytest.raises(ValueError,match='radius'):p.dem_window('moon',0,0,local_path=dem)

def test_pds_empty_no_fallback():
    d=p.search('mars','Mars',opener=lambda *a,**kw:io.BytesIO(b'{"data":[]}'))
    assert d['results']==[]
