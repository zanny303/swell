import base64,io,json,urllib.error
import numpy as np
import pytest
from urllib.parse import parse_qs,urlparse
import independent_comparison as ic
import planetary_products as pp
from projected_display import lookup

def test_projected_grid_lookup():
    from pyproj import Transformer
    n=3;x,y=np.meshgrid(np.arange(n)*720+700360, 3600000-np.arange(n)*720-360)
    lon,lat=Transformer.from_crs(32614,4326,always_xy=True).transform(x,y)
    g={'n':n,'epsg':32614,'transform':[720,0,700000,0,-720,3600000],'lat':lat.tolist(),'lon':lon.tolist()}
    d=lookup(g);a=np.frombuffer(base64.b64decode(d['lookup_i32']),dtype='<i4').reshape(480,480)
    assert a.max()<480**2 and a.min()==-1
    for i in range(n):
        for j in range(n):
            w,s,e,nn=d['bbox'];r=int((nn-lat[i,j])/(nn-s)*480);c=int((lon[i,j]-w)/(e-w)*480);k=int(a[r,c]);assert k>=0
            assert int((k//480+.5)*n/480)==i and int((k%480+.5)*n/480)==j
    assert len(d['outline'])==4*n+1

def test_pds_fallback_strict():
    def get(req,timeout):
        if '/classes/' in req.full_url:raise urllib.error.HTTPError(req.full_url,404,'Not Found',{},None)
        assert '/products?' in req.full_url and 'product_class' in parse_qs(urlparse(req.full_url).query)['q'][0]
        return io.BytesIO(json.dumps({'data':[{'id':'urn:nasa:pds:something:1'}, {'id':'urn:nasa:pds:abc:1','product_class':'Product_Observational','target_name':'Mars'}, {'id':'urn:nasa:pds:lro:lola:1','product_class':'Product_Observational','target_name':['Moon'],'title':'LOLA observation'}]}).encode())
    result=pp.search('moon',opener=get);assert len(result['results'])==1 and result['results'][0]['title']=='LOLA observation'

def test_catalog_bound_and_metadata():
    def get(req,timeout):
        q=parse_qs(urlparse(req.full_url).query)
        if 'collections.json' in req.full_url:
            return io.BytesIO(json.dumps({'feed':{'entry':[{'id':'C1-TEST','short_name':'OPERA_L3_DISP-S1_V1'},{'id':'C2-TEST','short_name':'OPERA_L3_DISP-S1_STATIC'},{'id':'C3-TEST','short_name':'OTHER'}]}}).encode())
        assert q['collection_concept_id']==['C1-TEST'] and q['temporal']==['2026-10-04T00:00:00Z,2026-10-16T23:59:59Z'] and q['bounding_box']==['-97,32,-96,33']
        return io.BytesIO(json.dumps({'feed':{'entry':[{'id':'G1-TEST','title':'record','collection_concept_id':'C1-TEST'},{'id':'G2-TEST','collection_concept_id':'C3-TEST'}]}}).encode())
    out=ic.discover('OPERA DISP-S1','OPERA_L3_DISP-S1*',[-97,32,-96,33],'2026-10-04','2026-10-16',get);assert len(out['records'])==1 and 'metadata only' in out['scope']

def test_gauge_scope_and_filters():
    def f(value,time,coords,parameter='00060'):
        return {'properties':{'value':value,'time':time,'parameter_code':parameter,'statistic_id':'00003','unit_of_measure':'ft^3/s','monitoring_location_id':'USGS-1','approval_status':'Provisional'},'geometry':{'coordinates':coords}}
    data={'features':[f('12.5','2026-10-04',[-96.5,32.5]),f('NaN','2026-10-04',[-96.5,32.5]),f('12','2026-01-01',[-96.5,32.5]),f('12','2026-10-04',[0,0]),f('4','2026-10-04',[-96.5,32.5],'00065')], 'links':[{'rel':'next'}]}
    out=ic.gauges([-97,32,-96,33],'2026-10-04','2026-10-16',lambda *a,**kw:io.BytesIO(json.dumps(data).encode()));assert len(out['records'])==1 and out['truncated'] and out['records'][0]['value']==12.5 and out['records'][0]['approval']=='Provisional'
