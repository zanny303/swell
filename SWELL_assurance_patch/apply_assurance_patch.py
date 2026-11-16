"""Targeted, transactional SWELL assurance update. No data or credentials written."""
import argparse,hashlib,json,datetime,os,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def inject(s,old,new):
    if new in s:return s
    if s.count(old)!=1:raise ValueError('Source anchor mismatch: '+old[:120])
    return s.replace(old,new,1)

def plan(root):
    if not (root/'stakeholder_mission.py').is_file() or not (root/'site/decision-mission.js').is_file():raise ValueError('Install the working Stakeholder Mission patch first.')
    changes={}
    for p in (HERE/'payload').rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(HERE/'payload');dest=root/rel;data=p.read_bytes()
        if dest.exists() and dest.read_bytes()!=data:raise ValueError('Refusing to replace different local add-on: '+str(rel))
        if not dest.exists():changes[rel]=data
    def edit(rel,fun):
        target=root/rel;raw=target.read_bytes();s=raw.decode('utf-8-sig');s2=fun(s.replace('\r\n','\n'))
        if s2!=s.replace('\r\n','\n'):
            changes[Path(rel)]=s2.replace('\n','\r\n' if b'\r\n' in raw else '\n').encode('utf-8')
    def server(s):
        for method,args in [('GET','self,APP,ROOT'),('POST','self,APP,ROOT,_local_only,_redact_secrets')]:
            old=f'    def do_{method}(self):\n        parsed = urlparse(self.path)\n';new=old+f"        if parsed.path.startswith('/api/assurance/'):\n            import science_assurance as assurance\n            return assurance.http_{method.lower()}({args})\n"
            s=inject(s,old,new)
        return s
    edit('run_swell.py',server)
    def js(s):
        inc=(HERE/'assurance_ui.inc.js').read_text(encoding='utf-8').strip()
        s=inject(s,'start();})();',inc+'\nstart();})();')
        s=inject(s,'function invalidate(terrain=false){epoch++;','function invalidate(terrain=false){assuranceClear();epoch++;')
        s=inject(s,'function resetReview(){epoch++;','function resetReview(){assuranceClear();epoch++;')
        s=inject(s,"message('runState','Completed both alternatives. Check sensitivity before export.');","assuranceLocal();message('runState','Completed both alternatives. Check sensitivity before export.');")
        return s
    edit('site/decision-mission.js',js)
    edit('site/decision-mission.html',lambda s:inject(s,'<a href="live.html">Observatory</a>','<a href="live.html">Observatory</a><a href="science-observatory.html">Radar research</a>'))
    # Hard fail fast for future misregistered datasets. Existing real data / LOS results unchanged.
    def ingest(s):
        old='        elif ph_.shape != grid["shape"]:'
        new='        elif (ph_.shape != grid["shape"] or epsg != grid["epsg"] or x.shape != grid["x"].shape or y.shape != grid["y"].shape or not np.allclose(x, grid["x"], atol=1e-6, rtol=0) or not np.allclose(y, grid["y"], atol=1e-6, rtol=0)):'
        return inject(s,old,new)
    edit('swell/ingest.py',ingest)
    def recorder(s):
        s=inject(s,"ap.add_argument('--with-worlds',action='store_true');", "ap.add_argument('--with-worlds',action='store_true');ap.add_argument('--assurance',action='store_true',help='Also record optional scientific assurance and export a reproducible ZIP');")
        s=inject(s,'package_ok=False','package_ok=False;assurance_ok=False')
        old='            if a.with_worlds:\n'
        new='''            if a.assurance:
                def assurance():
                    nonlocal assurance_ok
                    page.locator('#assurancePanel summary').click();page.click('#assuranceRun');wait_text('#assuranceStatus','Screening convergence checks met|Water accounting only|Unavailable:',270000)
                    if 'Unavailable:' in text('#assuranceStatus'):raise RuntimeError(text('#assuranceStatus'))
                    note('Advanced assurance: '+text('#assuranceStatus'));note(text('#assuranceTable'));shot('supplementary_spatial_assurance','#assurancePanel')
                    with page.expect_download(timeout=270000) as event:page.click('#assuranceExport')
                    target=out/'SWELL-reproducible-decision.zip';event.value.save_as(str(target))
                    with zipfile.ZipFile(target) as archive:
                        manifest=json.loads(archive.read('manifest.json'));assert manifest['run_id']==m['run_id'] and manifest['site_hash']==ev['hash'];assert all(hashlib.sha256(archive.read(k)).hexdigest()==v for k,v in manifest['sha256'].items());assert 'reproduce/elevation.npy' in archive.namelist() and 'assurance/spatial-review.json' in archive.namelist()
                    from build_public_replay import build
                    build(target,out/'public-replay.html',ROOT);assurance_ok=True;note('VERIFIED reproducible export and credential-free interactive replay')
                optional('advanced assurance',assurance)
            if a.with_worlds:
'''
        s=inject(s,old,new)
        s=inject(s,"return 0 if core_ok and package_ok and not errors else 1","return 0 if core_ok and package_ok and not errors and (not a.assurance or assurance_ok) else 1")
        return s
    edit('record_stakeholder_demo.py',recorder)
    return changes

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);fd,name=tempfile.mkstemp(dir=path.parent,prefix='.assurance-');os.close(fd)
    try:Path(name).write_bytes(data);os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',default='.');p.add_argument('--check',action='store_true');a=p.parse_args();root=Path(a.project).resolve()
    try:changes=plan(root)
    except Exception as e:raise SystemExit('STOP — no writes made. '+str(e))
    print('Compatible assurance patch:',len(changes),'files to add/update.')
    if a.check or not changes:return
    backup=root/'out'/'assurance_patch_backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup.mkdir(parents=True);records={};before={k:(root/k).read_bytes() if (root/k).exists() else None for k in changes}
    for k,raw in before.items():
        if raw is not None:atomic(backup/k,raw)
        records[k.as_posix()]={'original_sha256':hashlib.sha256(raw).hexdigest() if raw is not None else None,'installed_sha256':hashlib.sha256(changes[k]).hexdigest()}
    atomic(backup/'manifest.json',json.dumps(records,indent=2).encode());written=[]
    try:
        for k,data in changes.items():atomic(root/k,data);written.append(k)
    except Exception:
        for k in reversed(written):
            if before[k] is None:(root/k).unlink(missing_ok=True)
            else:atomic(root/k,before[k])
        raise
    print('Installed. Backups:',backup,'\nNo NASA datasets, credentials, existing saved decisions or core solver files were changed. Restart the server.')
if __name__=='__main__':main()
