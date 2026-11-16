"""Install additive stakeholder workflow; preserve original application, data, and secrets.
Run from the folder containing run_swell.py. Only anchored additions modify existing source.
"""
from pathlib import Path
import argparse,json,hashlib,shutil,datetime,os
HERE=Path(__file__).resolve().parent

def sha(b):return hashlib.sha256(b).hexdigest()
def insert(s,anchor,after,label):
    if after in s:return s
    if s.count(anchor)!=1:raise ValueError('Cannot safely merge '+label+' — unique source anchor missing; nothing overwritten.')
    return s.replace(anchor,after)

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',default='.');p.add_argument('--check',action='store_true');a=p.parse_args();r=Path(a.project).resolve()
    files=['run_swell.py','site/index.html','site_twin.py','external_evidence.py','terrain_routing.py','science_plans.py','ai_provider.py']
    missing=[x for x in files if not (r/x).is_file()]
    if missing:raise SystemExit('Missing prerequisite files (apply the prior Research Integration Patch first): '+', '.join(missing))
    pending={};manifest=json.loads((HERE/'manifest.json').read_text())
    for name,digest in manifest.items():
        b=(HERE/'payload'/name).read_bytes()
        if sha(b)!=digest:raise SystemExit('Corrupt patch file: '+name)
        if (r/name).exists() and (r/name).read_bytes()!=b:raise SystemExit('Different existing new-file content: '+name+'; nothing overwritten.')
        if not (r/name).exists():pending[name]=b
    try:
        s=(r/'run_swell.py').read_text(encoding='utf-8');old=s
        if '/api/external/gnss' not in s or '/api/external/terrain' not in s:raise ValueError('Research Integration routes missing. Install that patch first.')
        for method,body in [('GET','return mission.http_get(self,APP,ROOT)'),('POST','return mission.http_post(self,APP,ROOT,_local_only,_redact_secrets)')]:
            anchor=f'    def do_{method}(self):\n        parsed = urlparse(self.path)\n';change=anchor+"        if parsed.path.startswith('/api/mission/'):\n            import stakeholder_mission as mission\n            "+body+'\n';s=insert(s,anchor,change,'run_swell.py '+method)
        if "self.path='/decision-mission.html' if ready else '/index.html'" not in s:
            anchor="            self.path='/index.html'\n            return super().do_GET()";change="""            # Prefer guided stakeholder workflow when real NISAR provenance is present.
            try:
                active=json.loads((ROOT/'data'/'site.json').read_text(encoding='utf-8'))
                source=str(active.get('source','')).upper()
                ready='NISAR' in source and 'SYNTH' not in source and (APP/'out'/'real_site_provenance.json').is_file()
            except (OSError,ValueError,TypeError):ready=False
            self.path='/decision-mission.html' if ready else '/index.html'
            return super().do_GET()"""
            s=insert(s,anchor,change,'run_swell.py home route')
        compile(s,'run_swell.py','exec')
        if s!=old:pending['run_swell.py']=s.encode()
        s=(r/'site/index.html').read_text(encoding='utf-8');old=s
        anchor='<nav id="steps"></nav>';change='<a id="guidedMission" href="decision-mission.html" style="font-weight:700;color:#94ffea;border:1px solid #348b80;border-radius:7px;padding:6px 9px;white-space:nowrap">Guided decision ↗</a>\n  '+anchor;s=insert(s,anchor,change,'index guided link')
        anchor='<script src="external-evidence.js"></script>';change=anchor+'\n<script src="mission-bridge.js"></script>';s=insert(s,anchor,change,'index bridge script')
        if s!=old:pending['site/index.html']=s.encode()
    except ValueError as e:raise SystemExit(str(e))
    if a.check:print('Compatible guided mission patch; '+str(len(pending))+' files to install/update. No writes made.');return
    if not pending:print('Guided mission already installed.');return
    backup=r/'out'/'mission_patch_backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup.mkdir(parents=True)
    for name in pending:
        if (r/name).is_file():(backup/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(r/name,backup/name)
    done=[]
    try:
        for name,b in pending.items():
            dest=r/name;dest.parent.mkdir(parents=True,exist_ok=True);tmp=dest.with_name(dest.name+'.mission-tmp');tmp.write_bytes(b);os.replace(tmp,dest);done.append(name)
    except Exception:
        for name in reversed(done):
            if (backup/name).exists():shutil.copy2(backup/name,r/name)
            else:(r/name).unlink(missing_ok=True)
        raise
    print('Installed guided stakeholder mission:',len(done),'files. Backups:',backup,'\nExisting NASA data, .env, outputs and original workspaces retained. Restart SWELL.')
if __name__=='__main__':main()
