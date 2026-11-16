"""Independent GNSS ENU comparison with explicit, verified viewing vectors and stable reference.
No assumption of zero horizontal motion and no T1 promotion.
"""
import argparse,datetime as dt,json,math,re
from pathlib import Path
import numpy as np
from science_assurance import plain,sha

def parse(raw,station,dates):
    lines=raw.decode().splitlines();header=[x.strip('_') for x in lines[0].split()]
    names=['site','YYMMMDD','e0(m)','east(m)','n0(m)','north(m)','u0(m)','up(m)','sig_e(m)','sig_n(m)','sig_u(m)'];col={x:header.index(x) for x in names};result={}
    for line in lines[1:]:
        row=line.split()
        try:
            day=dt.datetime.strptime(row[col['YYMMMDD']],'%y%b%d').date().isoformat()
            if row[col['site']]!=station or day not in dates:continue
            xyz=[1000*(float(row[col[a]])+float(row[col[b]])) for a,b in [('e0(m)','east(m)'),('n0(m)','north(m)'),('u0(m)','up(m)')]];sig=[1000*float(row[col['sig_'+q+'(m)']]) for q in 'enu']
            if all(math.isfinite(x) for x in xyz+sig) and all(0<x<1000 for x in sig):result[day]={'enu_mm':xyz,'formal_daily_sigma_mm':sig}
        except (IndexError,ValueError):continue
    return result

def compare(station,reference,vector,ref_vector,days):
    # Vector convention is positive towards sensor; user must supply verified source geometry and sign.
    v,w=np.asarray(vector,float),np.asarray(ref_vector,float)
    if v.shape!=(3,) or w.shape!=(3,) or not np.isfinite(v).all() or not np.isfinite(w).all() or abs(np.linalg.norm(v)-1)>.005 or abs(np.linalg.norm(w)-1)>.005:raise ValueError('Verified unit ENU vectors required for both stations')
    if len(days)!=2 or not all(d in station and d in reference for d in days):raise ValueError('Both stations need exact same two dates')
    a,b=days
    d=np.array(station[b]['enu_mm'])-station[a]['enu_mm'];e=np.array(reference[b]['enu_mm'])-reference[a]['enu_mm']
    return {'station_los_change_mm':float(d@v),'reference_los_change_mm':float(e@w),'relative_los_change_mm':float(d@v-e@w),'warning':'No covariance, offsets, monument stability or spatial representativeness validated. Not a calibrated uncertainty or T1 pass.'}

def collect(root):
    import external_evidence as ee
    s,dates,key=ee.active(root);cache=ee.cached_gnss(root,key)
    if not cache:raise ValueError('Retrieve ground stations in the existing SWELL Decision Room first.')
    days=[x.isoformat() for x in dates];rows=[]
    for st in cache['stations']:
        sid=st['station'];assert re.fullmatch('[A-Z0-9]{4}',sid)
        try:
            raw=ee.fetch(ee.TENV+sid+'.tenv3');rows.append({'station':sid,'lat':st['lat'],'lon':st['lon'],'source_url':ee.TENV+sid+'.tenv3','sha256':sha(raw),'daily':parse(raw,sid,days)})
        except Exception as exc:rows.append({'station':sid,'error':str(exc)[:200]})
    out={'site_hash':key,'frame':'IGS20','dates':days,'stations':rows,'citation':ee.CITATION,'warning':'Full ENU daily positions (not relative radar comparison). Daily formal sigmas only; geometry and co-reference required.'};p=root/'out'/f'gnss-enu-{key}.json';p.write_text(plain(out));print(p);return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',default='.');p.add_argument('--geometry',help='Optional JSON containing station, reference, station_vector, reference_vector, dates, geometry_source, sign_convention; human-verified radar metadata required');a=p.parse_args();out=collect(Path(a.project).resolve())
    if a.geometry:
        g=json.loads(Path(a.geometry).read_text());assert g['geometry_source'] and g['sign_convention']=='positive toward sensor' and g['station']!=g['reference']
        rows={x['station']:x['daily'] for x in out['stations'] if 'daily' in x};print(plain(compare(rows[g['station']],rows[g['reference']],g['station_vector'],g['reference_vector'],g['dates'])))
