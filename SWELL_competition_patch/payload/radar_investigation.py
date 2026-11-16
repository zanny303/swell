"""Bind audited projected geometry to the exact active dataset; expose evidence, not causal scores."""
from pathlib import Path
import json, math
import numpy as np
from pyproj import Transformer
from functools import lru_cache
@lru_cache(maxsize=16)
def transformer(frm,to):return Transformer.from_crs(frm,to,always_xy=True)

def matching_audit(root, site_hash, n, dates):
    p=Path(root)/'out'/f'radar-assurance-{site_hash}.json'
    if not p.is_file():return None
    a=json.loads(p.read_text());g=a['geometry'];t=list(map(float,g['transform']))
    if a['site_hash']!=site_hash or g['n']!=n or t[0]<=0 or t[4]>=0 or t[1]!=0 or t[3]!=0 or not all(map(math.isfinite,t)):raise ValueError('Invalid cached radar geometry')
    if [x['pair'] for x in a['granules']]!=[list(x) for x in zip(dates[:-1],dates[1:])]:raise ValueError('Cached audit timeline mismatch')
    lat,lon=np.asarray(g['lat']),np.asarray(g['lon']);rr,cc=np.indices((n,n));x=t[2]+(cc+.5)*t[0];y=t[5]+(rr+.5)*t[4]
    ll,aa=transformer(g['epsg'],4326).transform(x,y)
    if lat.shape!=(n,n) or lon.shape!=(n,n) or not np.allclose(lat,aa,atol=1e-7,rtol=0) or not np.allclose(lon,ll,atol=1e-7,rtol=0):raise ValueError('Audit centers disagree with projected transform')
    return a

def footprint(g,row,col):
    dx,_,left,_,dy,top=g['transform'];x=left+col*dx;y=top+row*dy
    corners=[(x,y),(x+dx,y),(x+dx,y+dy),(x,y+dy),(x,y)]
    tr=transformer(g['epsg'],4326);ll,aa=tr.transform(*zip(*corners))
    return {'epsg':g['epsg'],'projected_bounds':[x,y+dy,x+dx,y],'polygon_lonlat':[[float(lo),float(la)] for lo,la in zip(ll,aa)],'spacing_m':[dx,-dy]}

def within(f,lat,lon):
    x,y=transformer(4326,f['epsg']).transform(lon,lat);w,s,e,n=f['projected_bounds'];return w<=x<=e and s<=y<=n

def investigation(a,c,ev):
    if a is None:return {'status':'No matching raw radar audit. Do not attribute a physical cause.','hypotheses':[]}
    r,j=c['row'],c['col'];p=a['latest_pair'];last=a['granules'][-1];raw=p['component_referenced_raw_phase_rad'][r][j];q=p['common_support_coherence'][r][j];support=p['valid_support_fraction'][r][j]
    hypotheses=[{'name':'Physical ground motion / shrink-swell','status':'Unresolved','evidence':'Radar phase is observed; clay mechanism is not independently calibrated.','next':'Co-referenced GNSS projected to verified radar LOS, survey and soil tests.'},{'name':'Moisture-related scattering or phase','status':'Unresolved','evidence':'Low coherence may indicate decorrelation; it is not diagnostic of moisture.','next':'Time-matched GCOV backscatter, soil moisture and precipitation; test correspondence.'},{'name':'Atmospheric / ionospheric phase','status':'Unresolved','evidence':f"Latest pair ionosphere sensitivity RMS: {last.get('iono_legacy_sign_sensitivity_rad_rms')} rad (legacy sign sensitivity only).",'next':'Verify correction units/sign and apply validated atmosphere and ionosphere processing.'},{'name':'Unwrapping / reference effects','status':'Unresolved','evidence':f"Raw component-referenced phase at selected block: {raw} rad; valid common support {support:.1%}. {a['phase_closure']}.",'next':'Inspect component membership and alternate references; acquire redundant interferograms for closure.'}]
    return {'status':'Investigation only: competing explanations remain unresolved.','raw_phase_rad':raw,'audit_coherence':q,'valid_support_fraction':support,'strict_count':last['threshold_0_5_valid_blocks'],'strict_counts':[{'pair':x['pair'],'blocks':x['threshold_0_5_valid_blocks']} for x in a['granules']],'hypotheses':hypotheses}
