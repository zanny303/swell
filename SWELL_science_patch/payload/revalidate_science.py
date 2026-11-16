"""Reanalyse a cached real NISAR site without downloading again or touching credentials.
Run from existing project root, with server stopped. Only trusted locally generated NPZs.
"""
import argparse, json, pathlib, shutil, tempfile, os, hashlib, datetime
os.environ.setdefault('OPENBLAS_NUM_THREADS','1'); os.environ.setdefault('OMP_NUM_THREADS','1')
import numpy as np
from swell import validate
ROOT=pathlib.Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--site',required=True,help='Existing trusted out/dallas.npz'); ap.add_argument('--publish',action='store_true',help='Publish verified files after backing up existing outputs; otherwise stage only'); a=ap.parse_args()
    src=pathlib.Path(a.site).resolve()
    if not src.is_file(): raise SystemExit(f'Missing {src}; do not regenerate the synthetic fixture. Find your cached real NPZ in out/.')
    site=validate.load_site(str(src)); source=site['source']
    if 'SYNTH' in source.upper() or 'NISAR' not in source.upper(): raise SystemExit('Refusing non-NISAR or synthetic site.')
    active=ROOT/'site/data/site.json'
    old=json.loads(active.read_text(encoding='utf-8')) if active.exists() else {}
    if old and 'SYNTH' not in str(old.get('source','')).upper():
        if old.get('name')!=site['name'] or old.get('pass_days')!=site['pass_days'].tolist() or not np.allclose(old.get('bbox'),site['bbox']):
            raise SystemExit('Cached NPZ does not match active real study. No files changed.')
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'); stage=ROOT/'out'/'science_revisions'/stamp; stage.mkdir(parents=True)
    (stage/'paper').mkdir(); validate.ROOT=stage
    print('Input:',src,'\nSource:',source,'\nPasses:',len(site['pass_days']),'\nRunning retrospective validation; original files untouched.',flush=True)
    validate.main(['--site',str(src)])
    new=json.loads((stage/'site/data/site.json').read_text(encoding='utf-8'))
    report=json.loads((stage/'out/results.json').read_text(encoding='utf-8'))
    assert new['source']==source and new['pass_days']==site['pass_days'].tolist()
    assert new['params']['alpha']>=0 and 0<=new['params']['b']<=1
    # Keep existing ancillary sensor records for same site, but do not claim they were rerun;
    # these are independent archived observations, not this revision's model validation.
    if old.get('source')==source and old.get('sensors'):
        new['sensors']={k:{**v,'status':'archived','finding':'Prior-revision result; re-run Add the other satellites again. '+str(v.get('finding') or v.get('reason') or '')} for k,v in old['sensors'].items() if isinstance(v,dict)}; new['scientific_validity']['ancillary_note']='Archived ancillary records retained from prior run; model comparisons not rerun and not evidence of forecast skill.'
        (stage/'site/data/site.json').write_text(json.dumps(new,allow_nan=False),encoding='utf-8')
    if old.get('source')==source and old.get('wetness_check'):
        new['wetness_check']=old['wetness_check']  # rainfall/wetness index unchanged
        (stage/'site/data/site.json').write_text(json.dumps(new,allow_nan=False),encoding='utf-8')
    manifest={'input':str(src.relative_to(ROOT)) if src.is_relative_to(ROOT) else src.name,'input_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'source':source,'model_version':new['model_version'],'pass_days':new['pass_days'],'validation':new['scientific_validity'],'published':False}
    (stage/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    if a.publish:
        targets=[p.relative_to(stage) for folder in ('site/data','out','paper') for p in (stage/folder).rglob('*') if p.is_file()]
        backup=stage/'previous'; backup.mkdir()
        for rel in targets:
            dst=ROOT/rel
            if dst.exists(): (backup/rel).parent.mkdir(parents=True,exist_ok=True); shutil.copy2(dst,backup/rel)
        # preserve original real provenance, raw data, .env, other app assets and ledgers;
        # publish site JSON last. Roll back on any error.
        done=[]
        try:
            for rel in sorted(targets,key=lambda x: str(x)=='site/data/site.json'):
                dst=ROOT/rel;dst.parent.mkdir(parents=True,exist_ok=True);tmp=dst.with_name(dst.name+'.science-tmp');shutil.copy2(stage/rel,tmp);os.replace(tmp,dst);done.append(rel)
        except Exception:
            for rel in reversed(done):
                if (backup/rel).exists(): shutil.copy2(backup/rel,ROOT/rel)
                else: (ROOT/rel).unlink(missing_ok=True)
            raise
        manifest['published']=True;(stage/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
        print('Published science results only; previous files:',backup)
    else: print('Staged only. Rerun with --publish to publish after reviewing.')
    print('Report:',stage/'out/results.json'); print(json.dumps(report['scientific_validity'],indent=2,ensure_ascii=False));print('Complete. No new independent validation claimed.')
if __name__=='__main__': main()
