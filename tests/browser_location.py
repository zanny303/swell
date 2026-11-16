"""Offline Chromium UI harness: real computation/export, unavailable upstream sources. Not a live map test."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
import location_services as loc
root=Path('site');screen=Path('screenshots');screen.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 page=b.new_page(viewport={'width':1500,'height':1100},device_scale_factor=1);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 html=(root/'location.html').read_text();js=(root/'location.js').read_text();page.set_content(html.replace('<script src="location.js"></script>','<script>'+js+'</script>'))
 # Offline harness routes calls directly to actual local model and exporter.
 page.evaluate('''() => {window.fetch=async(path,opts)=>{let p=JSON.parse(opts?.body||'{}');if(path.includes('snapshot'))return new Response(JSON.stringify({lat:32.7767,lon:-96.797,created_utc:'Offline test',sources:Object.fromEntries(['alerts','gauges','river','moisture','soils','ai_rain'].map(k=>[k,{status:'unavailable',data:null}]))}),{status:200});return new Promise(resolve=>window.pythonRequest(path,p).then(v=>resolve(v.zip?new Response(new Uint8Array(v.zip),{status:200}):new Response(JSON.stringify(v),{status:200}))));}}''')
 page.expose_function('pythonRequest',lambda path,p: {'zip':list(loc.export(p))} if path.endswith('package') else loc.screen(p))
 page.locator('#refresh').click();page.wait_for_function("document.querySelector('#locStatus').textContent.includes('0/6')");page.locator('#rain').fill('20, 30, 50');page.locator('#run').click();page.wait_for_function("!document.querySelector('#export').disabled");assert page.locator('#base').inner_text()=='505.4';page.screenshot(path=str(screen/'location-offline-screening.png'),full_page=True)
 page.locator('#retention_m3').fill('100');assert page.locator('#export').is_disabled();page.locator('#run').click();page.wait_for_function("!document.querySelector('#export').disabled");print('PASS: location UI, unavailable sources, actual model computation, input invalidation and rerun');assert not errors,errors;b.close()
