"""Bounded public evidence retrieval. Discovery is not observation-level validation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date,datetime,timezone
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import json,math
from pathlib import Path
CMR='https://cmr.earthdata.nasa.gov/search/'
USGS='https://api.waterdata.usgs.gov/ogcapi/v1/collections/daily/items'
FAMILIES={'NISAR GCOV':'NISAR_L2_GCOV*','OPERA DISP-S1':'OPERA_L3_DISP-S1*','OPERA DSWx':'OPERA_L3_DSWX*','SMAP soil moisture':'SPL3SMP*'}
def fetch(url,opener=urlopen):
    with opener(Request(url,headers={'Accept':'application/json, application/geo+json','User-Agent':'SWELL observation comparison/1.0'}),timeout=18) as f:
        b=f.read(4_000_001)
    if len(b)>4_000_000:raise ValueError('Provider response exceeds bounded size')
    return json.loads(b)
def query(base,params):return base+'?'+urlencode(params,doseq=True)
def discover(family,pattern,box,start,end,opener=urlopen):
    u=query(CMR+'collections.json',{'short_name':pattern,'options[short_name][pattern]':'true','page_size':12})
    entries=fetch(u,opener).get('feed',{}).get('entry',[])
    collections=[]
    for x in entries:
        cid=x.get('id'); name=x.get('short_name') or ''
        if not isinstance(cid,str) or not cid.startswith('C') or not name.upper().startswith(pattern[:-1].upper()):continue
        if 'STATIC' in name.upper():continue
        collections.append({'id':cid,'short_name':name,'version':x.get('version_id'),'title':x.get('dataset_id') or x.get('title')})
    # Limit provider requests, preserve collection IDs and time bounds. Never claim exhaustive.
    results=[];errors=[]
    for c in collections[:3]:
        gu=query(CMR+'granules.json',{'collection_concept_id':c['id'],'bounding_box':','.join(map(str,box)),'temporal':start+'T00:00:00Z,'+end+'T23:59:59Z','page_size':5})
        try:
            for g in fetch(gu,opener).get('feed',{}).get('entry',[]):
                if g.get('collection_concept_id') not in (None,c['id']):continue
                if not g.get('id'):continue
                results.append({'id':g['id'],'collection':c,'title':g.get('producer_granule_id') or g.get('title'),'start':g.get('time_start'),'end':g.get('time_end'),'metadata_url':CMR+'granules.json?'+urlencode({'concept_id':g['id']})})
        except Exception as e:errors.append(type(e).__name__+': '+str(e)[:160])
    return {'family':family,'status':'partial provider failures' if errors else ('catalog candidates' if results else 'no candidates in bounded query'),'collections':collections,'records':results,'errors':errors,'query_url':u,'scope':'Catalog metadata only; overlap and date filters do not prove usable observations, matched acquisition times, comparable geometry, or validation.'}
def gauges(box,start,end,opener=urlopen):
    # Local gauge context within 0.25 degrees padded neighborhood; not terrain-cell water depth.
    w,s,e,n=box; region=[max(-180,w-.25),max(-90,s-.25),min(180,e+.25),min(90,n+.25)]
    u=query(USGS,{'bbox':','.join(map(str,region)),'datetime':start+'/'+end,'parameter_code':'00060','statistic_id':'00003','limit':100,'f':'json'})
    raw=fetch(u,opener);rows=[]
    for f in raw.get('features',[]):
        p=f.get('properties') or {};g=f.get('geometry') or {};xy=g.get('coordinates')
        if p.get('parameter_code')!='00060' or p.get('statistic_id')!='00003':continue
        try:v=float(p['value'])
        except (ValueError,TypeError,KeyError):continue
        t=str(p.get('time',''))
        if not math.isfinite(v) or v<0 or not start<=t[:10]<=end:continue
        if not isinstance(xy,list) or len(xy)<2 or not all(isinstance(a,(int,float)) and math.isfinite(a) for a in xy[:2]):continue
        if not region[0]<=xy[0]<=region[2] or not region[1]<=xy[1]<=region[3]:continue
        rows.append({'station':p.get('monitoring_location_id'),'time':t,'value':v,'unit':p.get('unit_of_measure'),'approval':p.get('approval_status',p.get('approvals_status')),'qualifier':p.get('qualifier'),'lon':xy[0],'lat':xy[1]})
    return {'family':'USGS observed daily stream discharge','status':'observations retrieved' if rows else 'no matching observations','records':rows,'query_url':u,'truncated':any(x.get('rel')=='next' for x in raw.get('links',[])),'scope':'Daily stream discharge at monitoring points, not local surface depth or proof of flood-model skill. Nearby sites may be on unrelated catchments.'}
def collect(app,p):
    from stakeholder_mission import selection
    import external_evidence as ee
    ev,c,role=selection(app,p)
    if not c.get('footprint'):raise ValueError('Matched projected radar footprint required')
    poly=c['footprint']['polygon_lonlat'];lon,lat=zip(*poly);box=[min(lon),min(lat),max(lon),max(lat)];start,end=ev['dates'][-2:];date.fromisoformat(start);date.fromisoformat(end)
    def safe(fn,name,*args):
        try:return fn(*args)
        except Exception as e:return {'family':name,'status':'provider unavailable','records':[],'error':type(e).__name__+': '+str(e)[:200]}
    with ThreadPoolExecutor(max_workers=5) as ex:
        fs=[ex.submit(safe,discover,name,name,pattern,box,start,end) for name,pattern in FAMILIES.items()];fs.append(ex.submit(safe,gauges,'USGS daily discharge',box,start,end));sources=[f.result() for f in fs]
    out={'site_hash':ev['hash'],'selection':c,'interval':[start,end],'bbox_wsen':box,'retrieved_utc':datetime.now(timezone.utc).isoformat(),'sources':sources,'warning':'Independent evidence inventory only. No causal attribution, no cross-sensor displacement comparison or field validation has been established.'}
    path=cache_path(app,ev['hash'],c);ee._save(path,out);return out

def cache_path(app,site_hash,c):return Path(app)/'out'/f'comparison-{site_hash}-{int(c["row"])}-{int(c["col"])}.json'
