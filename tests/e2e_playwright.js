/* End-to-end browser test of the Earth workspace user flows. Uses the bundled, labelled demo data so it needs no NASA login.
   Run:  python run_swell.py   (in one window)   then   node tests/e2e_playwright.js
   Needs: npm install playwright   (and: npx playwright install chromium).  SWELL_VENDOR=<node_modules> serves Cesium/three locally when offline. */
const { chromium } = require('playwright'); const fs = require('fs');
const URL0 = process.env.SWELL_URL || 'http://127.0.0.1:8000', V = process.env.SWELL_VENDOR;
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1600, height: 900 }, acceptDownloads: true });
  const errs = []; p.on('pageerror', e => errs.push(e.message.slice(0, 200)));
  if (V) { await p.route('https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/**', r => { const f = V + '/cesium/Build/Cesium/' + r.request().url().split('/Build/Cesium/')[1].split('?')[0]; fs.existsSync(f) ? r.fulfill({ path: f }) : r.abort(); });
    await p.route('https://cdn.jsdelivr.net/npm/three@0.128.0/**', r => r.fulfill({ path: V + '/three/' + r.request().url().split('three@0.128.0/')[1] })); }
  const results = []; const ok = (name, cond, info = '') => { results.push([name, !!cond]); console.log((cond ? 'PASS ' : 'FAIL ') + name + (info ? '  ' + info : '')); };
  const click = sel => p.evaluate(s => { const e = document.querySelector(s); if (!e) return false; e.click(); return true; }, sel);
  const height = () => p.evaluate(() => viewer.camera.positionCartographic.height);

  const r1 = await p.goto(URL0 + '/earth', { waitUntil: 'domcontentloaded' }); ok('Earth is served at /earth', r1.ok() && /Decision Studio/.test(await p.title()));
  const w = await p.request.get(URL0 + '/worlds.html'); ok('Worlds is a separate page', w.ok() && /<title>SWELL Worlds/.test(await w.text()));
  await p.goto(URL0 + '/index.html?demo=1&nohelp=1', { waitUntil: 'domcontentloaded' }); await p.waitForFunction(() => typeof S !== 'undefined' && S && C && sampleDemoEnabled && lastField, null, { timeout: 60000 }); await p.waitForTimeout(4000);
  ok('Demo data is labelled as synthetic on screen', /SYNTHETIC|NOT NASA/i.test(await p.textContent('#siteCard')));

  await click('#toSite'); await p.waitForTimeout(3500); const h0 = await height(); await click('#zin'); await p.waitForTimeout(800); const h1 = await height(); await click('#zout'); await click('#zout'); await p.waitForTimeout(800); const h2 = await height();
  ok('Zoom in and out change the camera', h1 < h0 && h2 > h1, `${Math.round(h0)} -> ${Math.round(h1)} -> ${Math.round(h2)} m`);
  await click('#toEarth'); await p.waitForTimeout(3500); ok('Earth button shows the whole planet', (await height()) > 5e6); await click('#toSite'); await p.waitForTimeout(3500);
  await click('[data-v=twin]'); const twinOnly = await p.evaluate(() => document.getElementById('stage').className); await click('[data-v=map]'); const mapOnly = await p.evaluate(() => document.getElementById('stage').className); await click('[data-v=split]');
  ok('Map / Split / 3D twin toggle works', twinOnly === 'twin' && mapOnly === 'map');

  const lay = await p.evaluate(() => { const c = document.querySelector('[data-lay=nisar]'), fire = () => c.dispatchEvent(new Event('change', { bubbles: true })); c.checked = false; fire(); const off = overlay.show; c.checked = true; fire(); return [off, overlay.show]; });
  ok('Layer toggle hides and shows the radar layer', lay[0] === false && lay[1] === true);
  ok('Vegetation (NDVI) layer is listed with its source', /MODIS Terra/.test(await p.textContent('#layList')));

  await click('[data-step=investigate]'); await p.waitForTimeout(2500); const t0 = await p.textContent('#when'); await p.evaluate(() => document.querySelectorAll('#passes figure')[2].click()); const t1 = await p.textContent('#when');
  ok('Time strip changes the radar pass', t0 !== t1, `${t0} -> ${t1}`);
  await click('[data-s=forecast]'); await p.evaluate(() => { const d = document.getElementById('day'); d.value = 10; d.oninput({ target: d }); }); ok('Days-ahead slider updates the forecast date', /10 days ahead/.test(await p.textContent('#when')));

  await click('[data-step=simulate]'); await p.waitForTimeout(2500); await click('[data-bottom-tab=scenario]');
  ok('Chart sits beside the scenario controls', await p.evaluate(() => { const c = document.getElementById('chart'), r = document.getElementById('sliders'); return !!c && !!r && c.offsetParent !== null && r.offsetParent !== null; }));
  const before = await p.evaluate(() => curves().scen[H]);
  await click('[data-tool=pave]'); const box = await p.evaluate(() => { const r = viewer.scene.canvas.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; });
  const cx = box[0] + box[2] / 2, cy = box[1] + box[3] / 2; await p.mouse.move(cx - 40, cy - 30); await p.mouse.down(); for (let k = 0; k <= 8; k++) await p.mouse.move(cx - 40 + 10 * k, cy - 30 + 6 * k); await p.mouse.up(); await p.waitForTimeout(600);
  const painted = await p.evaluate(() => { let k = 0; for (let c = 0; c < n * n; c++) if (pPave[c]) k++; return k; }); ok('Dragging the Pave brush on the map changes cells', painted > 0, painted + ' cells');
  const after = await p.evaluate(() => curves().scen[H]); ok('The model re-computes after painting', Math.abs(after - before) > 1e-6 && (await p.evaluate(() => state)) === 'scenario', `${before.toFixed(2)} -> ${after.toFixed(2)} mm`);
  await click('#runModel'); ok('Run model button reports a re-run', /Model re-run/.test(await p.textContent('#runNote')));
  await click('[data-bottom-tab=report]'); await p.waitForTimeout(500); ok('Before / after report card shows numbers and 5 sensitivity bars', /Average movement, your scenario/.test(await p.textContent('#rcBody')) && (await p.evaluate(() => document.querySelectorAll('#rcTor .tor').length)) === 5);
  await p.evaluate(() => { const s = document.getElementById('viewSel'); s.value = 'diff'; s.onchange(); }); ok('Difference view is available', /minus doing nothing/.test(await p.textContent('#legT')));
  await p.evaluate(() => { const s = document.getElementById('viewSel'); s.value = 'unc'; s.onchange(); }); ok('Uncertainty view is available', /Uncertainty/.test(await p.textContent('#legT'))); await p.evaluate(() => { const s = document.getElementById('viewSel'); s.value = 'move'; s.onchange(); });
  ok('Chart states its error reference', /±|RMSE/.test(await p.textContent('#focusLbl')));
  await click('#undo'); await p.waitForTimeout(400); const left = await p.evaluate(() => { let k = 0; for (let c = 0; c < n * n; c++) if (pPave[c]) k++; return k; }); ok('Undo removes the painted change', left < painted, `${painted} -> ${left} cells`);
  await p.mouse.move(cx, cy); await p.mouse.move(cx + 6, cy + 4); await p.waitForTimeout(300); ok('Hover read-out shows cell facts', /clay/.test(await p.textContent('#hoverTip')));

  await click('[data-bottom-tab=usecases]'); await p.evaluate(() => setRole('planner')); await click('[data-uc=compare]'); ok('A stakeholder question returns an answer table', /Do nothing/.test(await p.textContent('#ucOut')));
  await click('[data-bottom-tab=deliverables]'); const dl = p.waitForEvent('download', { timeout: 15000 }).catch(() => null); await click('#gen'); const d = await dl; ok('Decision package downloads as a zip', d && /\.zip$/.test(d.suggestedFilename()));
  await p.evaluate(() => document.querySelector('header .right button[aria-label=Help]').click()); ok('Help lists the data sources', /NISAR L2 GUNW/.test(await p.textContent('#helpDlg')) && /demo data/i.test(await p.textContent('#helpState')));
  ok('No page errors', errs.length === 0, errs.join(' | '));
  const bad = results.filter(r => !r[1]).length; console.log(`\n${results.length - bad} of ${results.length} checks passed`); await b.close(); process.exit(bad ? 1 : 0);
})();
