from pathlib import Path
import base64
from playwright.sync_api import sync_playwright
root=Path('site');screen=Path('screenshots');screen.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage']);page=b.new_page(viewport={'width':1440,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 # Actual page and local image, explicitly blocked upstream event and renderer. No fabricated event markers.
 page.route('**/*',lambda route:route.abort());html=(root/'live.html').read_text().replace('<link rel="stylesheet" href="live.css">','<style>'+(root/'live.css').read_text()+'</style>').replace('src="assets/blue-marble.jpg"','src="data:image/jpeg;base64,'+base64.b64encode((root/'assets/blue-marble.jpg').read_bytes()).decode()+'"').replace('<script src="live.js"></script>','<script>'+ (root/'live.js').read_text()+'</script>');page.set_content(html);page.wait_for_function("document.querySelector('#imageryStatus').textContent.includes('unavailable')");page.wait_for_function("!!document.querySelector('#earth canvas')");page.locator('#lat').fill('32.7767');page.locator('#lon').fill('-96.7970');page.locator('#fly').click();assert '32.77670' in page.locator('#gpsReadout').inner_text();page.locator('#settings').click();assert page.locator('#connectionDialog').is_visible();page.locator('button[aria-label="Close connections"]').click();page.locator('#home').click();page.wait_for_timeout(250);page.screenshot(path=str(screen/'science-earth-offline.png'));assert not errors,errors;b.close()
print('PASS: actual new Earth UI, historical image, offline provider status, GPS controls, settings dialog. No live Cesium or external events.')
