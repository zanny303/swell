"""Build self-contained, credential-free, read-only replay from a verified export.
No arbitrary notes, prompts, tokens, imagery or private environment files copied.
"""
from pathlib import Path
import argparse,json,zipfile,hashlib,html,re
from science_assurance import summary,plain

def verify(path):
    with zipfile.ZipFile(path) as z:
        if len(z.namelist())!=len(set(z.namelist())) or sum(x.file_size for x in z.infolist())>100_000_000:raise ValueError('Invalid or oversized archive')
        m=json.loads(z.read('manifest.json'));expected=m['sha256'];actual=set(z.namelist())-{'manifest.json'}
        if actual!=set(expected) or not all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in expected.items()):raise ValueError('Archive integrity check failed')
        r,e,v=[json.loads(z.read(x)) for x in ('scenario.json','mission/evidence.json','mission/paired-review.json')]
        if r['run_id']!=m['run_id'] or v['run_id']!=m['run_id'] or e['hash']!=m['site_hash'] or v['site_hash']!=e['hash'] or m['engineering_approved'] is not False:raise ValueError('Run/evidence identifiers or approval state mismatch')
        return m,r,e,v

def build(path,dest,project=None):
    m,r,e,v=verify(path);s=r['site'];i=r['inputs'];site={k:s[k] for k in ('lat','lon','dx','n','epsg','source','vertical_datum','source_sha256')};obs={k:e[k] for k in ('site','source','dates','quality_basis','valid_cells','total_cells','granule_pairs','limitations','clay_status')};obs['gnss']=e.get('gnss');obs['selection']=v['radar_selection'];data={'site':site,'evidence':obs,'run_id':m['run_id'],'rain':i['rain_mm_h'],'infiltration':i['infiltration'],'roughness':i['roughness'],'boundary':r['boundary'],'edits':i['edits'],'baseline_peak':r['baseline_peak'],'scenario_peak':r['scenario_peak'],'baseline_frames':r['baseline_frames'],'scenario_frames':r['scenario_frames'],'summary':summary(r),'cases':[{k:c[k] for k in ('name','baseline_storage_m3','intervention_storage_m3','baseline_peak_m','intervention_peak_m','baseline_wet_m2','intervention_wet_m2')} for c in v['cases']],'role':v['role'],'action':v['verification_required'],'warning':r['warning'],'radar':None}
    # Optional exact active study match. Never publishes arbitrary JSON objects or API configuration.
    if project is not None:
        import external_evidence as ee, numpy as np
        root=Path(project);active,dates,key=ee.active(root)
        if key!=e['hash']:raise ValueError('Active site differs from exported one')
        a=np.asarray(active['observed_los'],float);a[(a==-9999)|(~np.isfinite(a))]=np.nan
        data['radar']={'n':active['n'],'los':np.where(np.isfinite(a),a,None).tolist(),'dates':[d.isoformat() for d in dates],'geo':'Legacy grid indices; not building-level positions.'}
    payload=plain(data).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=Path(__file__).with_name('public_replay_template.html').read_text(encoding='utf-8');out=Path(dest);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(template.replace('/*__PAYLOAD__*/',payload),encoding='utf-8');return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--output',default='public_replay/index.html');p.add_argument('--include-active-radar',action='store_true',help='Explicitly allow published real active radar grid in replay');p.add_argument('--project',default='.');a=p.parse_args();print(build(a.package,a.output,a.project if a.include_active_radar else None))
