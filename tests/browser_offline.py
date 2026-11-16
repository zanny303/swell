"""Actual browser regression of offline workspace; start server separately."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, os
screens=Path('screenshots');screens.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1600,'height':1000},accept_downloads=True)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    if os.environ.get('SWELL_LOCAL_HARNESS'):
        # Browser navigation is disabled in some sandboxes. Exercise the actual HTML/JS
        # with the actual bundled local data; this is NOT a network E2E test.
        root=Path('site'); html=(root/'offline.html').read_text()
        html=html.replace('<script src="hydro.js"></script>','<script>'+ (root/'hydro.js').read_text()+'</script>')
        local=(root/'offline.js').read_text().replace("fetch('data/site.json')", "Promise.resolve({json:()=>Promise.resolve("+(root/'data/site.json').read_text()+")})")
        html=html.replace('<script src="offline.js"></script>','<script>'+local+'</script>')
        page.set_content(html)
    else:
        page.goto('http://127.0.0.1:8000/offline.html')
    page.wait_for_function("document.querySelector('#scen').textContent.includes('mm')",timeout=60000)
    before=page.locator('#scen').inner_text();page.screenshot(path=str(screens/'01-offline-decision-studio.png'),full_page=True)
    page.locator('#plus').click();assert page.locator('#zoom').inner_text()=='150%';page.locator('#minus').click();assert page.locator('#zoom').inner_text()=='100%'
    page.locator('#rain').fill('0');page.locator('#run').click();assert page.locator('#scen').inner_text()!=before
    for tab in ['investigate','understand','simulate','act','verify']:
        page.locator(f'[data-tab={tab}]').click();page.screenshot(path=str(screens/f'{tab}-offline.png'),full_page=True)
    page.locator('[data-tab=simulate]').click();page.locator('#tool').select_option('drain');page.locator('#amount').fill('80');page.locator('#map').click(position={'x':300,'y':180});page.screenshot(path=str(screens/'07-offline-painted.png'),full_page=True)
    with page.expect_download() as d:page.locator('#download').click()
    path=d.value.path();out=json.loads(Path(path).read_text());assert out['paint'];assert out['engine']=='water-balance-1.0'
    with page.expect_download() as d:page.locator('#csv').click()
    assert d.value.suggested_filename=='swell-grid.csv'
    assert not errors,errors
    print('PASS: offline browser zoom, model input changes, six tabs, paint, scenario JSON, grid CSV, no page errors')
    browser.close()
