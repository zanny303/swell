"""Apply science-only files, preserving existing data and credentials. Run from project root."""
import argparse, pathlib, json, hashlib, shutil, datetime, os
HERE=pathlib.Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    a=argparse.ArgumentParser();a.add_argument('--project',default='.');a.add_argument('--check',action='store_true');args=a.parse_args()
    root=pathlib.Path(args.project).resolve(); files=json.loads((HERE/'manifest.json').read_text())
    if not (root/'run_swell.py').is_file() or not (root/'swell/fit.py').is_file():raise SystemExit('Run in SWELL root (the folder containing run_swell.py).')
    mismatches=[]; work=[]
    for row in files:
        rel=pathlib.Path(row['path']);p=root/rel;new=HERE/'payload'/row.get('payload_path',row['path'])
        if sha(new)!=row['new_sha256']:raise SystemExit('Corrupt patch: '+str(rel))
        if p.exists() and sha(p)==row['new_sha256']:continue
        if (row['old_sha256'] is None and p.exists()) or (row['old_sha256'] is not None and (not p.is_file() or sha(p)!=row['old_sha256'])):
            mismatches.append(str(rel))
        else:work.append((rel,new))
    if mismatches:
        print('Different local source files detected. Nothing was overwritten; preserve your Claude changes.\n'+ '\n'.join(mismatches));raise SystemExit(2)
    if args.check:print('Compatible patch:',len(work),'files to update. Existing data untouched.');return
    if not work:print('Patch already applied.');return
    backup=root/'out'/'recovery_patch_backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup.mkdir(parents=True)
    for rel,new in work:
        p=root/rel
        if p.exists():(backup/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,backup/rel)
    done=[]
    try:
        for rel,new in work:
            p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.patch-tmp');shutil.copy2(new,tmp);os.replace(tmp,p);done.append(rel)
    except Exception:
        for rel in reversed(done):
            if (backup/rel).exists():shutil.copy2(backup/rel,root/rel)
            else:(root/rel).unlink(missing_ok=True)
        raise
    print('Applied',len(done),'recovery/demo files. Prior code:',backup,'\nNo .env, cached data, provenance, or site.json replaced. Next: python run_swell.py (no revalidation needed for this patch)')
if __name__=='__main__':main()
