"""Chromium harness for actual UI and backend using explicitly synthetic test rasters.
Never claim live data. Network-only operations intentionally unavailable in this regression run.
"""
from pathlib import Path
import sys,tempfile,json,io,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import site_twin as st
import decision_engine as de
import science_plans as sp
from test_site_twin import fixture
from PIL import Image
root=Path('site');screen=Path('screenshots');screen.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as tmp,sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage']);page=b.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1,accept_downloads=True);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 html=(root/'site-twin.html').read_text();js=(root/'site-twin.js').read_text();page.set_content(html.replace('<script src="site-twin.js"></script>','<script>'+js+'</script>'))
 page.screenshot(path=str(screen/'site-twin-no-terrain.png'),full_page=True)
 def request(path,payload):
  action=path.split('/')[-1].split('?')[0]
  if action=='terrain':
   q={**payload,'datum':'SYNTHETIC NUMERICAL TEST FIXTURE — NOT DALLAS TERRAIN','meters':True};d=st.acquire(q,Path(tmp),fixture(q));d['source']='SYNTHETIC TEST FIXTURE — NOT A REAL SITE';return {'status':200,'body':d}
  if action=='run':return {'status':200,'body':st.run(payload,Path(tmp))}
  if action=='numerical-review':return {'status':200,'body':de.numerical_review(payload,Path(tmp))}
  if action=='observations':return {'status':200,'body':[]}
  if action=='plan':return {'status':200,'body':sp.plan(payload,Path(tmp))}
  if action=='research':return {'status':200,'body':de.research(payload,Path(tmp))}
  if action=='package':return {'status':200,'zip':list(st.pack(payload,Path(tmp)))}
  return {'status':502,'body':{'error':'Offline harness; no live external data'}}
 page.expose_function('pythonRequest',request);page.evaluate('''()=>{window.fetch=async(path,opts)=>{const p=JSON.parse(opts?.body||'{}');const r=await window.pythonRequest(path,p);return r.zip?new Response(new Uint8Array(r.zip),{status:r.status}):new Response(JSON.stringify(r.body),{status:r.status})}}''')
 page.locator('#radius').fill('100');page.locator('#dx').fill('10');page.locator('#load').click();page.wait_for_function("document.querySelector('#state').textContent.includes('20 × 20')");page.locator('#plus').click();page.locator('#reset').click();page.locator('[data-step="simulate"]').click();page.locator('#rain').fill('40, 20, 0');page.locator('#tool').select_option('drain');page.locator('#rate').fill('60');box=page.locator('#map').bounding_box();page.mouse.move(box['x']+box['width']*.45,box['y']+box['height']*.5);page.mouse.down();page.mouse.move(box['x']+box['width']*.60,box['y']+box['height']*.5,steps=6);page.mouse.up();assert int(page.locator('#editCount').inner_text().split()[0])>0;page.locator('#run').click();page.wait_for_function("!document.querySelector('#export').disabled",timeout=30000);assert 'Completed' in page.locator('#runStatus').inner_text();assert float(page.locator('#scenarioVol').inner_text().split()[0])<float(page.locator('#baseVol').inner_text().split()[0]);page.screenshot(path=str(screen/'site-twin-simulation-fixture.png'),full_page=True)
 page.locator('#meshBtn').click();page.screenshot(path=str(screen/'site-twin-terrain-fixture.png'),full_page=True);page.locator('#meshBtn').click();page.locator('[data-step="verify"]').click();page.locator('#numericalReview').evaluate('(el)=>el.closest("details").open=true');page.locator('#numericalReview').click();page.wait_for_function("document.querySelector('#numericalOut').textContent.includes('peak_depth_mae_m')",timeout=30000);page.locator('#researchQuestion').evaluate('(el)=>el.closest("details").open=true');page.locator('#researchQuestion').fill('SAR flood extent verification');page.locator('#researchReview').click();page.wait_for_function("document.querySelector('#researchOut').textContent.includes('NASA OPERA')");page.screenshot(path=str(screen/'site-twin-verification-fixture.png'),full_page=True);page.locator('[data-step="act"]').click();assert page.locator('#earthResult').get_attribute('href').find('siteOverlay=')>0
 page.wait_for_function("document.querySelector('#planOut').textContent.includes('Review actions')");page.locator('#planOut input[type=checkbox]').first.check();page.locator('#planOptimize').evaluate('(el)=>el.closest("details").open=true');page.locator('#planOptimize').click();page.wait_for_function("document.querySelector('#planOut').textContent.includes('Computed alternatives')",timeout=30000);page.screenshot(path=str(screen/'science-stakeholder-plan-fixture.png'),full_page=True)
 with page.expect_download() as d:page.locator('#export').click()
 path=d.value.path();z=zipfile.ZipFile(path);assert 'review-report.html' in z.namelist();assert any(x.startswith('reviews/numerical') for x in z.namelist());page.screenshot(path=str(screen/'site-twin-export-fixture.png'),full_page=True);page.locator('#lat').fill('33');page.locator('#lat').press('Tab');assert page.locator('#export').is_disabled();assert not errors,errors;b.close();print('PASS: Chromium actual Site Twin markup, coordinate handoff, grid loading, zoom, painting, simulation, 3D surface, verification, export, invalidation; synthetic terrain only.')
