"""Publish real classified water and processed SAR rasters with immutable provenance.
No inferred depth, change causality, or invented missing pixels.
"""
import argparse, datetime, io, json, re, shutil
from pathlib import Path
import numpy as np, rasterio as rio
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling
from PIL import Image
import site_twin as st

PRODUCTS={'DSWx-S1':(0,1,3,250,251,255),'DSWx-HLS':(0,1,2,252,253,254,255)}

def folder(root,site_id):
    st.load(root,site_id);p=st.storage(root)/site_id/'observations';p.mkdir(exist_ok=True);return p

def _date(value):
    t=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.tzinfo is None:raise ValueError('Acquisition time must include timezone (UTC or offset)')
    return t.astimezone(datetime.timezone.utc).isoformat()

def _render(raw,bbox,kind,product=None):
    with MemoryFile(raw) as mf,mf.open() as src:
        if src.count!=1 or not src.crs or src.width*src.height>100_000_000:raise ValueError('Expected bounded single-band georeferenced raster')
        if kind=='water' and (not np.issubdtype(np.dtype(src.dtypes[0]),np.integer)):raise ValueError('Expected integer OPERA WTR classification, not a reflectance/backscatter image')
        arr=np.full((512,512),np.nan,dtype='float32');reproject(rio.band(src,1),arr,src_transform=src.transform,src_crs=src.crs,src_nodata=src.nodata,dst_transform=from_bounds(*bbox,512,512),dst_crs=4326,dst_nodata=np.nan,resampling=Resampling.nearest)
        native={'crs':str(src.crs),'pixel_size':list(src.res)}
    rgba=np.zeros((512,512,4),dtype='uint8');good=np.isfinite(arr)
    if kind=='water':
        allowed=PRODUCTS[product];good &= np.isin(arr,allowed);clear=good&np.isin(arr,[0,1]);wet=clear&(arr==1)
        if not clear.any():raise ValueError('No clear water/not-water pixels overlap the selected site')
        rgba[wet]=[33,173,255,210];partial=good&(arr==(3 if product=='DSWx-S1' else 2));rgba[partial]=[94,230,209,180]
        rgba[good&~np.isin(arr,[0,1,2,3,255])]=[148,148,148,110]
        metrics={'clear_display_fraction':float(clear.mean()),'open_water_fraction_of_clear_display_pixels':float(wet.sum()/clear.sum()),'note':'Display-pixel fractions only; not native-area estimates.'}
    else:
        if not good.any():raise ValueError('No overlapping valid radar pixels')
        if kind=='radar-change':
            v=np.nan_to_num(arr);strength=np.clip(abs(v)/6,0,1);rgba[...,0]=np.where(v>0,240,35);rgba[...,1]=np.where(v>0,120,170);rgba[...,2]=np.where(v>0,40,245);rgba[...,3]=np.where(good,np.clip(40+strength*190,0,230),0)
        else:
            v=np.clip((np.nan_to_num(arr,nan=-30)+30)/35,0,1);rgba[...,:3]=(v*255).astype('uint8')[...,None];rgba[...,3]=np.where(good,255,0)
        metrics={'valid_display_fraction':float(good.mean()),'display_range_db':[-6,6] if kind=='radar-change' else [-30,5]}
    buf=io.BytesIO();Image.fromarray(rgba).save(buf,format='PNG');return buf.getvalue(),native,metrics

def register_water(root,site_id,raw,product,observed_utc,filename,origin=None):
    if product not in PRODUCTS:raise ValueError('Select OPERA DSWx-S1 or DSWx-HLS WTR product')
    if len(raw)>50_000_000:raise ValueError('Maximum 50 MB classified raster')
    if not re.search(r'(?:^|[_-])(?:WTR|B01_WTR)(?:[_\-.]|$)',filename,re.I) or 'BWTR' in filename.upper():raise ValueError('Select the original WTR water-classification GeoTIFF (not BWTR or browse image)')
    d,_=st.load(root,site_id);when=_date(observed_utc);png,native,metrics=_render(raw,d['wgs84'],'water',product);key=st.digest(json.dumps([site_id,st.digest(raw),product,when,origin],sort_keys=True).encode());p=folder(root,site_id)/key;p.mkdir(exist_ok=True)
    (p/'original.tif').write_bytes(raw);(p/'water.png').write_bytes(png)
    m={'id':key,'site_id':site_id,'kind':'water','product':product,'filename':Path(filename).name,'observed_utc':when,'registered_utc':st.stamp(),'source_sha256':st.digest(raw),'native':native,'metrics':metrics,'wgs84':d['wgs84'],'image':f'/uploads/site-twin/{site_id}/observations/{key}/water.png','source':origin or 'User-supplied OPERA WTR; product and acquisition time declared, not independently authenticated','warning':'Observed surface water class, not depth or flood attribution. Blue = open water; teal = partial/inundated vegetation; gray = masked, transparent = dry/no data. Permanent water not removed.'};(p/'meta.json').write_text(json.dumps(m));return m

def register_radar(root,site_id,before,after,frequency='A',pol='HHHH',maturity='unknown'):
    import radar_change
    d,_=st.load(root,site_id);base=folder(root,site_id);import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        rec=radar_change.change(before,after,d['wgs84'],tmp,frequency,pol,maturity);key=st.digest(json.dumps([site_id,rec],sort_keys=True).encode());p=base/key;p.mkdir(exist_ok=True);views={}
        for name,kind in [('before-gamma0-db','radar-backscatter'),('after-gamma0-db','radar-backscatter'),('delta-db','radar-change')]:
            raw=(Path(tmp)/(name+'.tif')).read_bytes();png,native,metrics=_render(raw,d['wgs84'],kind);(p/(name+'.tif')).write_bytes(raw);(p/(name+'.png')).write_bytes(png);views[name]={'image':f'/uploads/site-twin/{site_id}/observations/{key}/{name}.png','native':native,'metrics':metrics}
        m={'id':key,'site_id':site_id,'kind':'radar','product':'NISAR GCOV','wgs84':d['wgs84'],'registered_utc':st.stamp(),'radar':rec,'views':views,'warning':rec['warning']+' Orange = increased backscatter; blue = decreased; display clipped at ±6 dB.'};(p/'meta.json').write_text(json.dumps(m));return m

def list_observations(root,site_id):
    return [json.loads(f.read_text()) for f in sorted(folder(root,site_id).glob('*/meta.json'))]

def compare_registered(root,p):
    r=st.load_result(root,p['result_id']);key=p['observation_id'];site_id=r['site']['id']
    if not re.fullmatch('[0-9a-f]{64}',key):raise ValueError('Invalid observation ID')
    f=folder(root,site_id)/key;m=json.loads((f/'meta.json').read_text());raw=(f/'original.tif').read_bytes()
    if m['kind']!='water' or st.digest(raw)!=m['source_sha256']:raise ValueError('Observation is not an intact water raster')
    return st.compare_water({'result_id':r['run_id'],'hour':p['hour'],'product':m['product'],'observed_utc':m['observed_utc']},root,raw)

def download_water(root,site_id,product,granule_id):
    """Selected CMR granule only, bounded authenticated WTR file; no arbitrary URL input."""
    from earth_services import get,CMR
    from urllib.parse import urlencode,urlparse,unquote
    if product not in PRODUCTS or not re.fullmatch(r'G\d+-[A-Za-z0-9_]+',granule_id):raise ValueError('Invalid product/granule ID')
    d,_=st.load(root,site_id);short='OPERA_L3_DSWX-'+('S1' if product=='DSWx-S1' else 'HLS')+'_V1';raw,_,_=get(CMR+'granules.json?'+urlencode({'concept_id':granule_id,'short_name':short,'bounding_box':','.join(map(str,d['wgs84'])),'page_size':1}));rows=json.loads(raw)['feed']['entry']
    if len(rows)!=1 or rows[0].get('id')!=granule_id:raise ValueError('Granule not found in selected product and site')
    row=rows[0];links=[]
    for l in row.get('links',[]):
        u=l.get('href','');v=urlparse(u);name=Path(unquote(v.path)).name
        if v.scheme=='https' and v.hostname and (v.hostname.endswith('.earthdatacloud.nasa.gov') or v.hostname.endswith('.earthdata.nasa.gov') or v.hostname=='podaac.jpl.nasa.gov') and re.search(r'_WTR\.tiff?$',name,re.I) and not l.get('inherited'):links.append((u,name))
    if not links:raise ValueError('No supported WTR download link in CMR; download WTR via Earthdata Search and import it instead')
    import earthaccess
    auth=earthaccess.login(strategy='netrc');session=earthaccess.get_requests_https_session();u,name=links[0]
    with session.get(u,stream=True,timeout=(10,30)) as response:
        response.raise_for_status();buf=bytearray()
        for chunk in response.iter_content(128*1024):
            buf.extend(chunk)
            if len(buf)>50_000_000:raise ValueError('WTR exceeds 50 MB limit')
    return register_water(root,site_id,bytes(buf),product,row['time_start'],name,{'provider':'NASA CMR / Earthdata','granule_id':granule_id,'download_url':u,'collection_short_name':short})

def local_radar_files(root):
    import radar_change
    base=Path(root).resolve().parent/'nasa-downloads';base.mkdir(exist_ok=True);records=[]
    for p in sorted(base.glob('NISAR_L2_*_GCOV_*.h5'))[:300]:
        if not p.is_file() or p.is_symlink():continue
        try:group,t=radar_change.identity(p);records.append({'name':p.name,'acquired_utc':t.isoformat(),'compatibility':list(group)})
        except Exception:continue
    return records

def register_local_pair(root,p):
    base=Path(root).resolve().parent/'nasa-downloads';allowed={x['name'] for x in local_radar_files(root)}
    if p['before'] not in allowed or p['after'] not in allowed:raise ValueError('Select two matching local GCOV H5 files in nasa-downloads')
    return register_radar(root,p['id'],base/p['before'],base/p['after'],p.get('frequency','A'),p.get('pol','HHHH'),p.get('maturity','unknown'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default=str(Path(__file__).parent/'site'));p.add_argument('--site',required=True);sub=p.add_subparsers(dest='action',required=True);r=sub.add_parser('radar');r.add_argument('before');r.add_argument('after');r.add_argument('--frequency',default='A');r.add_argument('--pol',default='HHHH');r.add_argument('--maturity',default='unknown');w=sub.add_parser('water');w.add_argument('file');w.add_argument('--product',required=True);w.add_argument('--observed-utc',required=True);a=p.parse_args();out=register_radar(a.root,a.site,a.before,a.after,a.frequency,a.pol,a.maturity) if a.action=='radar' else register_water(a.root,a.site,Path(a.file).read_bytes(),a.product,a.observed_utc,Path(a.file).name);print(json.dumps(out,indent=2))
