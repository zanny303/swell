"""Offline browser regression for the new evidence copilot and scenario shelf.
Uses mocked workspace outputs; it does not claim a live model or NASA connection."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1280,'height':900},accept_downloads=True)
    errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content('''<!doctype html><html><body><header><div class="right"><button id="askSwell">Ask SWELL</button></div></header>
      <div id="bottomTabs"><button data-bottom-tab="scenario">Scenario</button><button data-bottom-tab="findings">Findings</button></div>
      <div id="bottom"><section class="card" data-bottom-panel="scenario">scenario</section><section class="card" data-bottom-panel="findings" hidden>findings</section></div></body></html>''')
    page.evaluate('''
      window.__applied=false; window.__restored=false; window.__counter=0;
      window.__ctx={site:'Demo site',source:'SYNTHETIC TEST FIXTURE',synthetic:true,can_simulate:true,role:'Engineer',active_state:'inferred',horizon_days:30,selected_cell:null,focus:'test cells',scenario:{changed_cells:2,engine:'legacy'},metrics:{baseline_mm:2.1,scenario_mm:1.8,delta_mm:-.3},uncertainty:{note:'Training RMSE is not a calibrated interval.'}};
      window.SWELL_WORKSPACE={getContext:()=>window.__ctx,getSite:()=>({name:'Demo site',source:'SYNTHETIC TEST FIXTURE'}),previewScenario:(q)=>({ignored:false,eligible:true,settings:{rainMm:80,rainDays:3,dryDays:0,reduction:.4,pavedDelta:0,horizon:30},understood:['80 mm of rain','40% less wetting']}),applyScenario:(s,u)=>{window.__applied=true;return {context:window.__ctx}},captureScenario:(name,note)=>({id:'scenario-'+(++window.__counter),name,note,site:'Demo site',source:'SYNTHETIC TEST FIXTURE',synthetic:true,engine:'legacy',horizon_days:30,role:'Engineer',inputs:{},changed_cells:2,metrics:{baseline_mm:2.1,scenario_mm:1.8,delta_mm:-.3,focus:'test cells'},arrays:{water:[0],drain:[0],pave:[0]}}),restoreScenario:()=>{window.__restored=true;return window.__ctx}};
      window.SwellModel={parseRequest:()=>({ignored:false,settings:{rainMm:80,rainDays:3,dryDays:0,reduction:.4,pavedDelta:0,horizon:30},understood:['80 mm rain','40% less wetting']})};
      window.SwellResearch={answer:()=>({body:'Local structured evidence: test result is present.',limitations:['Synthetic fixture only.']})};
      window.fetch=async (url)=>({ok:true,json:async()=>url.includes('/research')?{method:'TF-IDF retrieval',sources:[{title:'NASA OPERA',url:'https://example.org/opera',curated_note:'Official product documentation'}]}:{status:'retrieval only; optional local generation not configured',sources:[]}});
    ''')
    page.add_script_tag(path=str(ROOT/'site/scenario-shelf.js'))
    page.add_script_tag(path=str(ROOT/'site/ai-copilot.js'))
    page.locator('#askSwell').click()
    page.locator('#scInput').fill('What if 80 mm rain over 3 days with 40% drainage reduction?')
    page.locator('#scForm button[type=submit]').click()
    page.wait_for_function("document.querySelector('#scMessages').innerText.includes('SCENARIO PROPOSAL')")
    page.get_by_role('button',name='Apply to active twin').click()
    page.wait_for_function('window.__applied===true')
    page.locator('#scInput').fill('What is the strongest evidence at this site?')
    page.locator('#scForm button[type=submit]').click()
    page.wait_for_function("document.querySelector('#scMessages').innerText.includes('EVIDENCE REVIEW')")
    assert page.locator('#scMessages a[href="https://example.org/opera"]').count()==1
    page.locator('#scClose').click()
    page.locator('[data-bottom-tab="shelf"]').click()
    page.locator('#ssName').fill('Drainage alternative')
    page.locator('#ssSave').click()
    page.wait_for_function("document.querySelector('#ssList').innerText.includes('Drainage alternative')")
    page.locator('#ssName').fill('Paving alternative')
    page.locator('#ssSave').click()
    page.wait_for_function("document.querySelector('#ssList').innerText.includes('Paving alternative')")
    assert page.locator('#ssCompare tbody tr').count()==2
    page.locator('[data-load="scenario-1"]').click()
    page.wait_for_function('window.__restored===true')
    assert not errors,errors
    print('PASS: evidence copilot, explicit scenario proposal/apply, cited source display, scenario save/compare/load. Synthetic mocked workspace only.')
    browser.close()
