"""Chromium test of the real bundled historical imagery. Inline harness avoids sandbox navigation restrictions."""
from pathlib import Path
import base64,os
from playwright.sync_api import sync_playwright
root=Path('site');screens=Path('screenshots');screens.mkdir(exist_ok=True)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage']);page=b.new_page(viewport={'width':1600,'height':1000},device_scale_factor=1);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    if os.environ.get('SWELL_LOCAL_HARNESS'):
        html=(root/'earth-preview.html').read_text();js=(root/'earth-preview.js').read_text().replace("assets/blue-marble.jpg",'data:image/jpeg;base64,'+base64.b64encode((root/'assets/blue-marble.jpg').read_bytes()).decode());page.set_content(html.replace('<script src="earth-preview.js"></script>','<script>'+js+'</script>'))
    else:page.goto('http://127.0.0.1:8000/earth-preview.html')
    page.wait_for_function("document.querySelector('#read').textContent.includes('100%')",timeout=30000)
    page.screenshot(path=str(screens/'earth-real-historical-globe.png'));page.locator('#plus').click();page.wait_for_function("document.querySelector('#read').textContent.includes('135%')");page.locator('#earth').click(position={'x':450,'y':420});assert 'Latitude' in page.locator('#info').inner_text();page.locator('#lat').fill('32.7767');page.locator('#lon').fill('-96.797');page.locator('#search button').click();page.wait_for_function("document.querySelector('#read').textContent.includes('32.78')");page.screenshot(path=str(screens/'earth-real-historical-dallas-coordinate.png'));page.locator('#minus').click();page.wait_for_function("document.querySelector('#read').textContent.includes('100%')");assert not errors,errors;print('PASS: actual historical NASA texture rendered, zoom, coordinate picking and coordinate navigation in Chromium');b.close()
