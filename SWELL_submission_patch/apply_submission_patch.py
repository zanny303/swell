"""Hash-checked SWELL competition update. Preflight all sources, backup, atomic replacements, rollback on error."""
import argparse,datetime,hashlib,json,os,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda x:hashlib.sha256(x).hexdigest()
norm=lambda x:x.replace(b'\r\n',b'\n')
def plan(root):
    if not (root/'stakeholder_mission.py').is_file():raise ValueError('Install the Stakeholder Mission, Scientific Assurance and Polish/Worlds updates first.')
    result=[]; conflicts=[]
    for rel,m in json.loads((HERE/'manifest.json').read_text()).items():
        f=root/rel; payload=(HERE/'payload'/rel).read_bytes(); old=f.read_bytes() if f.exists() else None
        if sha(norm(payload))!=m['new']:raise ValueError('Corrupt payload '+rel)
        if old is not None and sha(norm(old))==m['new']:continue
        if old is not None and 'old_block' in m:
            s=norm(old);a=m['old_block'].encode();b=m['new_block'].encode()
            if s.count(b)==1:continue
            if s.count(a)==1:payload=s.replace(a,b,1)
            else:conflicts.append(rel);continue
        elif (sha(norm(old)) if old is not None else None) not in [m['old'],*m.get('also_old',[])]:
            conflicts.append(rel);continue
        if old and b'\r\n' in old:payload=norm(payload).replace(b'\n',b'\r\n')
        result.append((rel,old,payload))
    if conflicts:raise ValueError('Local source differs. No files written. Preserve local changes and report:\n'+'\n'.join(conflicts))
    return result

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.swell-competition-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',default='.');p.add_argument('--check',action='store_true');a=p.parse_args();root=Path(a.project).resolve()
    try:
        changes=plan(root)
        if a.check:print(f'Compatible submission patch: {len(changes)} file(s) to install/update. No writes made.');return
        if not changes:print('Submission patch already installed.');return
        backup=root/'out'/'submission_patch_backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup.mkdir(parents=True)
        for rel,old,_ in changes:
            if old is not None:atomic(backup/rel,old)
        (backup/'manifest.json').write_text(json.dumps([{'path':r,'existed':o is not None,'old_sha256':sha(o) if o is not None else None,'new_sha256':sha(n)} for r,o,n in changes],indent=2))
        done=[]
        try:
            for rel,old,new in changes:
                cur=(root/rel).read_bytes() if (root/rel).exists() else None
                if cur!=old:raise RuntimeError('File changed during installation: '+rel)
                atomic(root/rel,new);done.append((rel,old))
        except BaseException:
            for rel,old in reversed(done):
                if old is None:(root/rel).unlink(missing_ok=True)
                else:atomic(root/rel,old)
            raise
        print(f'Installed {len(changes)} submission files. Backup: {backup}')
        print('Existing .env, datasets, solver, prior output and decision exports unchanged. Restart SWELL.')
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
if __name__=='__main__':main()
