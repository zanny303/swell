"""Record a completed stakeholder workflow from the real running SWELL app.
Raw video is supplemental; the seven screenshots are for the official slide deck.
No generated images, fixture substitution or benchmark concealment. Logs missing steps.
"""
from __future__ import annotations
import argparse, json, hashlib, pathlib, re, time, zipfile, sys
from urllib.request import urlopen
ROOT=pathlib.Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--url',default='http://127.0.0.1:8000');ap.add_argument('--role',choices=['engineer','planner','utility','emergency','resident'],default='planner');ap.add_argument('--row',type=int);ap.add_argument('--col',type=int);ap.add_argument('--lat',type=float);ap.add_argument('--lon',type=float);ap.add_argument('--skip-ai',action='store_true');ap.add_argument('--headless',action='store_true');ap.add_argument('--no-imagery',action='store_true');ap.add_argument('--with-worlds',action='store_true');ap.add_argument('--assurance',action='store_true',help='Also record optional scientific assurance and export a reproducible ZIP');ap.add_argument('--browser-executable',help=argparse.SUPPRESS);a=ap.parse_args()
    if (a.row is None)!=(a.col is None) or (a.lat is None)!=(a.lon is None):ap.error('Give both row and col, or both lat and lon.')
    try:
        with urlopen(a.url+'/api/mission/evidence',timeout=25) as f: ev=json.load(f)
        if not ev['valid_cells']:raise ValueError('No eligible real radar cells.')
    except Exception as e:print('STOP: real NISAR evidence unavailable. Start SWELL, check the real study and provenance. '+str(e));return 2
    try:from playwright.sync_api import sync_playwright
    except ImportError:print('Run python -m pip install playwright, then python -m playwright install chromium');return 2
    out=ROOT/('demo_stakeholder_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir();report=[];errors=[];shots=[];core_ok=False;package_ok=False;assurance_ok=False
    def note(t):report.append(str(t));print(t,flush=True)
    note('REAL DATA: '+ev['site']+' | '+ev['source']+' | '+str(ev['dates'])+' | '+ev['quality_basis'])
    note('Science boundary: observed LOS, not vertical motion. Local forecast is conditional screening, not design.')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=a.headless,**({'executable_path':a.browser_executable} if a.browser_executable else {}));ctx=browser.new_context(viewport={'width':1600,'height':1000},record_video_dir=str(out),record_video_size={'width':1600,'height':1000},accept_downloads=True);page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:300]));video=page.video
        def text(sel):return page.locator(sel).inner_text(timeout=10000)
        def wait_enabled(sel,timeout=270000):page.locator(sel).wait_for(state='visible',timeout=timeout);page.wait_for_function('(s)=>!document.querySelector(s).disabled',arg=sel,timeout=timeout)
        def wait_text(sel,regex,timeout=270000):page.wait_for_function('([s,r])=>new RegExp(r,"i").test(document.querySelector(s)?.textContent||"")',arg=[sel,regex],timeout=timeout)
        def shot(name,sel=None):
            if sel:page.locator(sel).scroll_into_view_if_needed()
            else:page.evaluate('window.scrollTo(0,0)')
            page.wait_for_timeout(450);f=out/f'{len(shots)+1:02d}_{name}.png';page.screenshot(path=str(f));shots.append(f.name);note('Scene: '+name)
        def optional(name,fn):
            try:fn()
            except Exception as e:note('OPTIONAL UNAVAILABLE '+name+': '+str(e)[:240])
        try:
            page.goto(a.url+'/decision-mission.html',wait_until='domcontentloaded');wait_text('#sourceState','REAL NISAR STUDY',45000);page.select_option('#missionRole',a.role)
            choices=ev['cells']; strong=[x for x in choices if x['coherence']>=.5]; chosen=next((x for x in choices if x['row']==a.row and x['col']==a.col),None) if a.row is not None else (strong or choices)[0]
            if chosen is not None and chosen['coherence']<.5:page.select_option('#qualityScreen','0.30');note('Explicit legacy coherence screen: 0.30; not high-confidence motion.')
            note('Geometry: '+ev.get('geometry_status','legacy approximate'))
            if chosen is None:raise ValueError('Requested radar cell is not eligible.')
            # All cells are clickable; the menu exposes the highest-change 30. For an explicit cell bypassing the menu use its actual canvas position.
            value=f"{chosen['row']},{chosen['col']}"
            if page.locator('#candidate option').evaluate_all('(a,v)=>a.some(x=>x.value===v)',arg=value):page.select_option('#candidate',value)
            else:
                box=page.locator('#radar').bounding_box();page.locator('#radar').click(position={'x':(chosen['col']+.5)*box['width']/ev['n'],'y':(chosen['row']+.5)*box['height']/ev['n']})
            if a.lat is not None:
                page.fill('#locLat',str(a.lat));page.locator('#locLat').press('Tab');page.fill('#locLon',str(a.lon));page.locator('#locLon').press('Tab')
            note('Selected observation: '+text('#selection'));shot('01_radar_and_role')

            page.click('#loadTerrain');wait_text('#terrainInfo',r'analysis cells|Unavailable:');
            if 'Unavailable:' in text('#terrainInfo'):raise RuntimeError(text('#terrainInfo'))
            note('Terrain: '+text('#terrainInfo'))
            def gnss():
                if ev.get('gnss'):note('Cached independent GNSS: '+text('#gnssInfo'));return
                page.click('#gnss');wait_text('#gnssInfo','stations in matching region|Unavailable:');note('GNSS: '+text('#gnssInfo'))
            optional('GNSS',gnss)
            def imagery():
                page.click('#photo');wait_text('#terrainRead','Esri World Imagery|Unavailable:');note(text('#terrainRead'))
            if not a.no_imagery:optional('aerial imagery',imagery)
            shot('02_local_terrain')
            page.click('#route');wait_text('#terrainRead','local basins|Unavailable:');note('Routing: '+text('#terrainRead'))
            if not page.locator('#candidateDrain').is_disabled():page.click('#candidateDrain')
            else:
                note('OPTIONAL UNAVAILABLE: routing; painting explicitly chosen central terrain cell instead.')
                page.locator('#terrain').click()
            wait_text('#editCount','^[1-9]');note('Edits: '+text('#editCount'));shot('03_intervention_footprint')
            page.click('#runMission');wait_text('#runState','Completed both|Unavailable:');
            if 'Unavailable:' in text('#runState'):raise RuntimeError(text('#runState'))
            note('Comparison: '+text('#baseWater')+' -> '+text('#altWater')+' | '+text('#deltaWater'));shot('04_same_storm_comparison','.result')
            page.click('#review');wait_text('#reviewOut','across the tested|all four cases|Unavailable:');
            if 'Unavailable:' in text('#reviewOut'):raise RuntimeError(text('#reviewOut'))
            note('Numerical review: '+text('#reviewOut'));shot('05_numerical_review','#reviewOut')
            page.click('#suggestAction');wait_enabled('#exportMission')
            note('Stakeholder action: '+page.locator('#decisionNote').input_value());shot('06_stakeholder_action','.decision')
            with page.expect_download(timeout=270000) as event:page.click('#exportMission')
            downloaded=event.value;target=out/'SWELL-stakeholder-decision.zip';downloaded.save_as(str(target))
            with zipfile.ZipFile(target) as z:
                m=json.loads(z.read('manifest.json'));d=json.loads(z.read('mission/decision.json'))
                assert m['engineering_approved'] is False and m['mass_balance_passed'] and m['site_hash']==ev['hash'] and d['run_id']==m['run_id'] and d['role']==a.role
                assert all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in m['sha256'].items())
            package_ok=True;core_ok=True;note('VERIFIED exported ZIP, matching run and observation hash, draft role decision and all member hashes.')
            if not a.skip_ai:
                def ai():
                    if page.locator('#askMission').is_disabled():raise RuntimeError('No configured provider; core workflow complete.')
                    page.click('#askMission');wait_text('#aiState','Live provider response received',270000)
                    note('AI: '+text('#aiState'));shot('07_decision_and_live_ai','.decision')
                optional('AI',ai)
            if len(shots)<7:shot('07_exported_decision','.decision')
            if a.assurance:
                def assurance():
                    nonlocal assurance_ok
                    page.locator('#hypotheses summary').click();page.wait_for_timeout(700);note('Hypothesis investigation: '+text('#hypothesisOutput'));shot('radar_hypotheses','#hypotheses');page.locator('#hypotheses summary').click();page.locator('#assurancePanel summary').click();page.click('#assuranceRun');wait_text('#assuranceStatus','Screening convergence checks met|Water accounting only|Unavailable:',270000)
                    if 'Unavailable:' in text('#assuranceStatus'):raise RuntimeError(text('#assuranceStatus'))
                    note('Advanced assurance: '+text('#assuranceStatus'));note(text('#assuranceTable'));shot('supplementary_spatial_assurance','#assurancePanel')
                    with page.expect_download(timeout=270000) as event:page.click('#assuranceExport')
                    target=out/'SWELL-reproducible-decision.zip';event.value.save_as(str(target))
                    with zipfile.ZipFile(target) as archive:
                        manifest=json.loads(archive.read('manifest.json'));assert manifest['run_id']==m['run_id'] and manifest['site_hash']==ev['hash'];assert all(hashlib.sha256(archive.read(k)).hexdigest()==v for k,v in manifest['sha256'].items());assert 'reproduce/elevation.npy' in archive.namelist() and 'assurance/spatial-review.json' in archive.namelist()
                    from build_public_replay import build
                    build(target,out/'public-replay.html',ROOT);assurance_ok=True;note('VERIFIED reproducible export and credential-free interactive replay')
                    try:
                        from competition_replay import enhance
                        enhance(target,out/'public-replay.html',out/'competition-replay.html');note('Created quality-aware competition replay from matched audit')
                    except Exception as err:note('Competition replay not available: '+str(err)[:180])
                optional('advanced assurance',assurance)
            if a.with_worlds:
                def worlds():
                    page.goto(a.url+'/worlds.html',wait_until='domcontentloaded');page.click('[data-world=moon]');page.wait_for_function("()=>document.getElementById('planetCanvas')?.dataset.missionMosaic==='ready'",timeout=100000);shot('supplementary_moon_archive')
                optional('Worlds',worlds)
        except Exception as e:note('CORE WORKFLOW STOPPED: '+str(e)[:400]);page.screenshot(path=str(out/'problem.png'))
        finally:
            note('Page errors: '+str(len(errors)));[note(x) for x in errors];ctx.close();browser.close()
            try:pathlib.Path(video.path()).replace(out/'supplementary_walkthrough.webm')
            except Exception as e:note('Video unavailable: '+str(e)[:200])
    note('Complete decision export: '+str(core_ok and package_ok));note('Raw recording may exceed 30 seconds. Use up to seven slides for official demo.');(out/'demo_report.txt').write_text('\n'.join(report)+'\n',encoding='utf-8');print('Saved:',out);return 0 if core_ok and package_ok and not errors and (not a.assurance or assurance_ok) else 1
if __name__=='__main__':sys.exit(main())
