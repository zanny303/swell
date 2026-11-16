"""Install pinned upstream engines locally; no API tokens needed. Requires npm + internet."""
from pathlib import Path
import subprocess, tempfile, shutil, os
root=Path(__file__).resolve().parent/'site'/'vendor'
with tempfile.TemporaryDirectory() as tmp:
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    if not npm:raise RuntimeError('Install Node.js LTS and reopen PowerShell first.')
    subprocess.run([npm,'install','--prefix',tmp,'--no-audit','--no-fund','--ignore-scripts','cesium@1.119.0','three@0.128.0'],check=True)
    modules=Path(tmp)/'node_modules'; root.mkdir(exist_ok=True)
    for src,dst in [(modules/'cesium'/'Build'/'Cesium',root/'cesium'),(modules/'three'/'build',root/'three'),(modules/'three'/'examples'/'js'/'controls',root/'three-controls')]:
        shutil.copytree(src,dst,dirs_exist_ok=True)
    for pkg in ('cesium','three'):
        for lic in (modules/pkg).glob('LICENSE*'):shutil.copyfile(lic,root/(pkg+'-'+lic.name))
print('Local renderers installed. Run python run_swell.py.')
# Only change references after successful installation; existing engine versions preserved.
page=root.parent/'index.html'
text=page.read_text()
for old,new in [('https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/','vendor/cesium/'),('https://cdn.jsdelivr.net/npm/three@0.128.0/build/','vendor/three/'),('https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/','vendor/three-controls/')]:text=text.replace(old,new)
page.write_text(text)
