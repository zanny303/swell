/* Decision loop polish, following the 15 Nov audit: chart always beside the scenario controls, Run model + Undo,
   before/after report card with a sensitivity (tornado) plot, hover read-out, onboarding and data-source cards, an NDVI layer,
   and a less crowded map. Additive: loaded last; changes no model code. */
(function () {
  const $ = id => document.getElementById(id), bottom = $("bottom"), tabs = $("bottomTabs"); if (!bottom || !tabs) return;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const sg = v => !Number.isFinite(v) ? "–" : (v >= 0 ? "+" : "") + v.toFixed(1), live = () => typeof S !== "undefined" && S && C && (!/SYNTH/i.test(S.source) || sampleDemoEnabled);
  const css = document.createElement("style"); css.textContent = `
  .sc-two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:14px;height:100%}.sc-two>div{min-width:0;overflow:auto}
  #runModel{background:#22c55e;border-color:#22c55e;color:#04130a;font-weight:700;white-space:nowrap}#runNote{font-size:11.5px;color:var(--mute)}
  .rc-wrap{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;height:100%}.rc-wrap>div{min-width:0;overflow:auto}
  .rc-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:8px 0}.rc-grid div{background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:8px}
  .rc-grid b{display:block;font-size:17px}.rc-grid span{font-size:11px;color:var(--mute)}
  .tor{display:grid;grid-template-columns:150px 1fr 96px;gap:8px;align-items:center;font-size:12px;margin:5px 0}.tor .tr{position:relative;height:14px;background:#0a1826;border-radius:4px}
  .tor .tr i{position:absolute;top:0;bottom:0;background:#c58af9;border-radius:3px}.tor .tr u{position:absolute;top:-2px;bottom:-2px;width:2px;background:#fff}
  #hoverTip{position:absolute;z-index:8;pointer-events:none;background:#081522f0;border:1px solid var(--line);border-radius:8px;padding:5px 8px;font-size:11.5px;display:none;white-space:nowrap}
  header #search{max-width:210px;min-width:90px}
  #helpDlg{border:1px solid var(--line);border-radius:14px;background:var(--card);color:var(--ink);max-width:760px;width:calc(100vw - 40px);padding:20px 22px}#helpDlg::backdrop{background:#000a}
  #helpDlg h2{font-size:19px}#helpDlg table{width:100%;border-collapse:collapse;font-size:12px;margin-top:6px}#helpDlg td,#helpDlg th{padding:4px 6px;border-bottom:1px solid #14283a;text-align:left;vertical-align:top}
  #helpDlg .acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}#helpDlg .acts a,#helpDlg .acts button{padding:8px 12px;border:1px solid var(--line);border-radius:8px;text-decoration:none;color:var(--ink);background:var(--card2)}
  #helpDlg .acts .go{background:#22c55e;border-color:#22c55e;color:#04130a;font-weight:700}`; document.head.appendChild(css);

  /* 1. the chart sits beside the scenario controls, so every change is seen at once */
  const sc = bottom.querySelector('[data-bottom-panel="scenario"]'), tl = bottom.querySelector('[data-bottom-panel="timeline"]');
  if (sc && tl) { const left = document.createElement("div"), right = document.createElement("div"); while (sc.firstChild) left.appendChild(sc.firstChild); while (tl.firstChild) right.appendChild(tl.firstChild);
    const two = document.createElement("div"); two.className = "sc-two"; two.append(left, right); sc.appendChild(two); const tb = tabs.querySelector('[data-bottom-tab="timeline"]'); if (tb) tb.remove(); tl.remove();
    const run = $("run"); if (run) { const b = document.createElement("button"); b.id = "runModel"; b.type = "button"; b.textContent = "▶ Run model"; b.title = "Re-run the twin with everything you typed, set and painted"; const nt = document.createElement("span"); nt.id = "runNote"; run.parentElement.insertBefore(b, run.nextSibling); run.parentElement.appendChild(nt);
      b.onclick = () => { state = "scenario"; rerun(); let k = 0; for (let c = 0; c < n * n; c++) if (pWater[c] || pDrain[c] || pPave[c]) k++; nt.textContent = `Model re-run at ${new Date().toLocaleTimeString()} · ${k} cells changed on the map · the map also re-runs by itself as you paint`; }; } }

  /* 2. undo */
  const stack = []; const snap = () => ({ w: Float32Array.from(pWater), d: Float32Array.from(pDrain), p: Float32Array.from(pPave), G: { ...G }, H });
  const same = (a, b) => a && b && JSON.stringify(a.G) === JSON.stringify(b.G) && a.H === b.H && a.w.every((v, i) => v === b.w[i]) && a.d.every((v, i) => v === b.d[i]) && a.p.every((v, i) => v === b.p[i]);
  const maybe = () => { if (typeof pWater === "undefined" || !pWater) return; const s = snap(); if (!same(s, stack[stack.length - 1])) { stack.push(s); if (stack.length > 40) stack.shift(); } ub.disabled = stack.length < 2; };
  const ub = document.createElement("button"); ub.id = "undo"; ub.type = "button"; ub.textContent = "↶ Undo"; ub.title = "Undo the last change to the scenario"; ub.disabled = true; const cp = $("clearPaint"); if (cp) cp.parentElement.insertBefore(ub, cp);
  ub.onclick = () => { if (stack.length < 2) return; stack.pop(); const s = stack[stack.length - 1]; pWater.set(s.w); pDrain.set(s.d); pPave.set(s.p); Object.assign(G, s.G); H = s.H; dayA = Math.min(dayA, H); syncSliders(); rerun(); ub.disabled = stack.length < 2; };
  ["pointerup", "change", "click"].forEach(ev => document.addEventListener(ev, () => setTimeout(maybe, 80), true));
  if (typeof AMT !== "undefined") AMT.green = [40, "%"];

  /* 3. before / after report card + sensitivity */
  const btn = document.createElement("button"); btn.type = "button"; btn.dataset.bottomTab = "report"; btn.setAttribute("aria-selected", "false"); btn.textContent = "Before / after"; tabs.insertBefore(btn, tabs.children[2] || null);
  const pn = document.createElement("div"); pn.className = "card"; pn.dataset.bottomPanel = "report"; pn.hidden = true; pn.innerHTML = `<div class="rc-wrap"><div><h2>Before / after report card</h2><div class="mute small" id="rcSub"></div><div id="rcBody"></div></div><div><h2>What the answer depends on most</h2><div class="mute small">Each bar: the scenario result when one input is 20 % lower or higher. White mark = current value.</div><div id="rcTor"></div></div></div>`; bottom.appendChild(pn);
  const flat = f => { const o = []; for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if (Number.isFinite(f[i][j])) o.push(f[i][j]); return o; }, mabs = a => a.reduce((x, y) => x + Math.abs(y), 0) / Math.max(1, a.length);
  function report() { if (!live() || pn.hidden) return; const bf = window.__baseField || window.field, b = flat(bf("forecast", passK, H)), s = flat(bf("scenario", passK, H)), rm = S.params.rmse_train, thr = 5;
    const mb = mabs(b), ms = mabs(s), d = ms - mb, nb = b.filter(v => Math.abs(v) > thr).length, ns = s.filter(v => Math.abs(v) > thr).length; let ch = 0; for (let c = 0; c < n * n; c++) if (pWater[c] || pDrain[c] || pPave[c]) ch++;
    const z = scenarioRecord().zones.filter(x => x.baseline_mm != null).map(x => ({ ...x, d: Math.abs(x.scenario_mm) - Math.abs(x.baseline_mm) })).sort((a, c) => a.d - c.d), best = z[0], worst = z[z.length - 1];
    $("rcSub").textContent = `${H} days ahead · all resolved cells · data: ${S.source.slice(0, 40)}`;
    $("rcBody").innerHTML = `<div class="rc-grid"><div><span>Average movement, no-rain baseline</span><b style="color:#f2a33a">${mb.toFixed(1)} mm</b></div><div><span>Average movement, your scenario</span><b style="color:#c58af9">${ms.toFixed(1)} mm</b></div><div><span>Change</span><b>${sg(d)} mm (${mb > 0 ? sg(100 * d / mb) : "–"} %)</b></div>
      <div><span>Cells moving more than ${thr} mm, doing nothing</span><b>${nb}</b></div><div><span>…in your scenario</span><b>${ns}</b></div><div><span>Cells you changed on the map</span><b>${ch}</b></div></div>
      <div>${Math.abs(d) < .05 ? "Your scenario is effectively unchanged from doing nothing in this run. Type a request, move a slider, or paint on the map." : `The full scenario ${d < 0 ? "reduces" : "increases"} average modeled ground movement by <b>${Math.abs(d).toFixed(1)} mm</b>.`}
      ${best && worst && Math.abs(d) >= .05 ? ` Largest modelled decrease: <b>${best.zone}</b> (${sg(best.d)} mm). Largest modelled increase: <b>${worst.zone}</b> (${sg(worst.d)} mm).` : ""}</div>
      <div class="warn" style="margin-top:8px">${hydroC ? "Water-balance screening is uncalibrated; its parameter sensitivity is not a probability interval." : `Training RMSE reference: ${rm.toFixed(1)} mm. This is a fit diagnostic, not a calibrated forecast interval or a significance test.`} Weather and intervention inputs may both differ; comparison does not isolate intervention benefit. Experimental model output, not validated field effect. Switch the map to "scenario minus doing nothing" to see where. Not an engineering design.</div>`;
    const cur = curves().scen[H], rows = []; const tryv = (label, get, set, lo, hi) => { const v0 = get(); set(lo(v0)); compute(); const a = curves().scen[H]; set(hi(v0)); compute(); const c2 = curves().scen[H]; set(v0); rows.push([label, a, c2]); };
    tryv("Rain added", () => G.rainMm, v => G.rainMm = v, v => v * .8, v => v * 1.2); tryv("Dry days first", () => G.dryDays, v => G.dryDays = v, v => Math.round(v * .8), v => Math.round(v * 1.2));
    tryv("Clay response (α)", () => S.params.alpha, v => S.params.alpha = v, v => v * .8, v => v * 1.2); tryv("Response time (T)", () => S.params.T, v => S.params.T = v, v => v * .8, v => v * 1.2);
    tryv("Paving shield (b)", () => S.params.b, v => S.params.b = v, v => v * .8, v => Math.min(1, v * 1.2)); compute();
    rows.sort((a, c) => Math.abs(c[2] - c[1]) - Math.abs(a[2] - a[1])); const lo = Math.min(cur, ...rows.flatMap(r => [r[1], r[2]])), hi = Math.max(cur, ...rows.flatMap(r => [r[1], r[2]])), X = v => hi - lo < 1e-9 ? 50 : 100 * (v - lo) / (hi - lo);
    $("rcTor").innerHTML = rows.map(([t, a, c2]) => `<div class="tor"><span>${t}</span><div class="tr"><i style="left:${Math.min(X(a), X(c2))}%;width:${Math.max(1, Math.abs(X(c2) - X(a)))}%"></i><u style="left:${X(cur)}%"></u></div><span>${sg(Math.min(a, c2))} to ${sg(Math.max(a, c2))} mm</span></div>`).join("") + `<div class="small mute" style="margin-top:6px">Current scenario result for the focus area: ${sg(cur)} mm. The longest bar is the input worth measuring better.</div>`; }
  const rd = window.redraw; window.redraw = function () { rd.apply(this, arguments); try { report(); } catch (e) { console.warn("report card", e); } };
  btn.addEventListener("click", () => setTimeout(() => { try { report(); } catch (e) { console.warn(e); } }, 60));

  /* 4. hover read-out on the map */
  const mb = $("mapBox"); if (mb && typeof viewer !== "undefined") { const tip = document.createElement("div"); tip.id = "hoverTip"; mb.appendChild(tip); let last = 0;
    new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas).setInputAction(e => { if (Date.now() - last < 60) return; last = Date.now(); if (!live() || !lastField) { tip.style.display = "none"; return; } const c = cellAt(e.endPosition); if (!c) { tip.style.display = "none"; return; }
      const v = lastField.fld[c.i][c.j]; tip.innerHTML = `<b>${zoneOf(c.i, c.j)}</b> · ${Number.isFinite(v) ? sg(v) : "no estimate"} · clay ${S.lep[c.i][c.j].toFixed(1)} % · paved ${(100 * S.paved[c.i][c.j]).toFixed(0)} % · quality ${S.coh[c.i][c.j].toFixed(2)}`;
      tip.style.display = "block"; tip.style.left = Math.min(mb.clientWidth - 260, e.endPosition.x + 14) + "px"; tip.style.top = Math.max(4, e.endPosition.y - 30) + "px"; }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
    mb.addEventListener("mouseleave", () => tip.style.display = "none"); }

  /* 5. a calmer map: the location buttons and coordinate read-out fold behind one rail button */
  const rail = $("rail"); const fold = () => { const lb = [...document.querySelectorAll("#mapBox button")].find(b => /Inspect GPS point/.test(b.textContent)), bar = lb && lb.parentElement, gr = $("gpsReadout"); return [bar && bar.id !== "tools" && bar.id !== "rail" ? bar : null, gr].filter(Boolean); };
  if (rail) { const g = document.createElement("button"); g.className = "txt"; g.textContent = "GPS"; g.title = "Show or hide coordinates and location tools"; rail.appendChild(g); let open = false; const apply = () => fold().forEach(e => e.style.display = open ? "" : "none"); g.onclick = () => { open = !open; apply(); }; setTimeout(apply, 1500); setTimeout(apply, 4000); }

  /* 6. NDVI layer (NASA GIBS, MODIS 8-day) with its source shown */
  try { const d8 = new Date(Date.now() - 12 * 864e5).toISOString().slice(0, 10), lay = viewer.imageryLayers.addImageryProvider(new Cesium.WebMapServiceImageryProvider({ url: GIBS, layers: "MODIS_Terra_NDVI_8Day", parameters: { transparent: true, format: "image/png", time: d8 }, tilingScheme: new Cesium.GeographicTilingScheme(), maximumLevel: 7, credit: "NASA GIBS · MODIS Terra NDVI 8-day" })); lay.show = false; lay.alpha = .7;
    const addRow = () => { const list = [...document.querySelectorAll("#layList details.layer-group")].find(d => /Environment/.test(d.querySelector("summary").textContent)); if (!list || $("lay-ndvi")) return; const r = document.createElement("div"); r.className = "lay"; r.id = "lay-ndvi"; r.innerHTML = `<div class="sw" style="background:linear-gradient(135deg,#8a6a2a,#1f9d3a)"></div><div><b>Vegetation (NDVI)</b><span>Data: MODIS Terra 8-day, 250 m, NASA GIBS</span></div><input type="checkbox" class="tog" aria-label="Vegetation layer">`; r.querySelector("input").onchange = e => lay.show = e.target.checked; list.appendChild(r); };
    let tries = 0; const iv = setInterval(() => { addRow(); if (++tries > 40) clearInterval(iv); }, 1000); } catch (e) { console.warn("NDVI layer", e); }

  /* 7. onboarding + data sources */
  const SRC = [["Ground movement", "NASA NISAR L2 GUNW (L-band radar pairs)", "about 80 m, regridded per site", "about 3 days after each pass"], ["Rain driving the twin", "NASA POWER daily precipitation", "site-centre point", "about 2 to 5 days"], ["Clay", "ISRIC SoilGrids 2.0, 30 to 60 cm", "250 m", "static"], ["Paving", "ESA WorldCover 2021 built-up", "10 m", "static"],
    ["Evidence: rain", "NASA GPM IMERG daily (late run)", "0.1°, about 10 km", "about 1 day"], ["Evidence: soil moisture", "NASA SMAP L3 enhanced", "9 km", "about 2 days"], ["Evidence: second radar", "NASA OPERA DISP-S1 (Sentinel-1 C-band)", "30 m, North America", "weeks"], ["Evidence: vegetation", "NASA HLS Landsat", "30 m", "days"], ["Evidence: water", "NASA OPERA DSWx-HLS", "30 m", "days"],
    ["Map pictures", "NASA GIBS (VIIRS, MODIS, IMERG, SMAP), Esri World Imagery", "250 m to sub-metre", "daily"], ["Earthquakes", "USGS GeoJSON feed", "points", "minutes"]];
  const dlg = document.createElement("dialog"); dlg.id = "helpDlg"; dlg.innerHTML = `<h2>SWELL: Earth is the main workspace</h2><div class="mute small">Other worlds is a separate page under More. This page is the Earth twin.</div>
    <ol style="padding-left:18px;margin:10px 0"><li><b>Look:</b> zoom with +, − or the wheel. Switch Map, Split or 3D twin. Use the time strip under the map.</li><li><b>Ask:</b> pick your role (top right), then a question in <b>My decisions</b>.</li><li><b>Change:</b> under the map pick + Water, Drainage, Pave or Green and drag over the ground. Or type a scenario. Undo steps back.</li><li><b>Compare:</b> <b>Before / after</b> gives the report card; the map can show "scenario minus doing nothing".</li><li><b>Trust:</b> unresolved ground is left blank; the current forecast does not have a calibrated predictive interval. Training RMSE and parameter sensitivity are labelled as diagnostics, not probabilities. <b>Verify</b> shows the available tests.</li></ol>
    <div id="helpState" class="warn"></div><details><summary style="cursor:pointer;margin-top:8px"><b>Where every number comes from</b></summary><table><tr><th>What</th><th>Source</th><th>Detail</th><th>Delay</th></tr>${SRC.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</table><div class="small mute" style="margin-top:6px">Coarse sources (9 to 10 km) are used only as checks for the whole site, never to colour individual cells. Radar motion is along the line of sight and is converted to vertical assuming no sideways motion.</div></details>
    <div class="acts"><a class="go" href="connections.html">Connect real data</a><a href="index.html?demo=1">Try the bundled demo data</a><button id="helpClose">Start exploring</button></div>`; document.body.appendChild(dlg);
  const hb = document.createElement("button"); hb.type = "button"; hb.textContent = "?"; hb.title = "How this works and where the data comes from"; hb.setAttribute("aria-label", "Help"); hb.style.cssText = "width:34px;font-weight:700"; const hr = document.querySelector("header .right"); if (hr) hr.insertBefore(hb, hr.firstChild);
  const openHelp = () => { $("helpState").innerHTML = live() ? (/SYNTH/i.test(S.source) ? "You are looking at <b>bundled demo data</b>: a synthetic test site, labelled on screen. It is not a NASA measurement." : `Loaded site: <b>${esc(S.name)}</b> · ${esc(S.source)}`) : "No real site is loaded yet, and SWELL does not show made-up data by default. Connect real data, or open the labelled demo."; dlg.showModal(); };
  hb.onclick = openHelp; dlg.querySelector("#helpClose").onclick = () => dlg.close();
  const wait = setInterval(() => { if (typeof S === "undefined" || !S || !C) return; clearInterval(wait); maybe();
    if (/[?&]demo=1/.test(location.search) && /SYNTH/i.test(S.source) && !sampleDemoEnabled) setSampleDemo(true);
    let seen = false; try { seen = localStorage.getItem("swell.onboarded.v1") === "1"; localStorage.setItem("swell.onboarded.v1", "1"); } catch (_) { }
    if (!seen && !/[?&](dev|demo|nohelp)=1/.test(location.search)) openHelp(); }, 300);
})();
