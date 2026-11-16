/* SWELL front end. Reads data/site.json (written by `python -m swell.validate`).
   Global layers are live NASA / USGS context. Only the site overlay is the twin. */
const $ = id => document.getElementById(id);
const GIBS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi";
// NASA GIBS daily satellite imagery. GIBS serves pre-generated NASA Earth-observation
// visualizations; the selected date is deliberately lagged to avoid requesting an
// acquisition that has not yet been processed. See NASA GIBS access documentation.
const imageryDate = new Date(Date.now() - 2 * 864e5).toISOString().slice(0, 10);
const GIBS_LAYERS = {
  terra: "MODIS_Terra_CorrectedReflectance_TrueColor",
  aqua: "MODIS_Aqua_CorrectedReflectance_TrueColor",
  viirs: "VIIRS_SNPP_CorrectedReflectance_TrueColor"
};
const gibs = (layer, time, transparent = true) => new Cesium.WebMapServiceImageryProvider({
  url: GIBS, layers: layer,
  parameters: { transparent, format: transparent ? "image/png" : "image/jpeg", ...(time ? { time } : {}) },
  tilingScheme: new Cesium.GeographicTilingScheme(), credit: "NASA GIBS / NASA Earthdata"
});
const baseProvider = gibs(GIBS_LAYERS.terra, imageryDate, false);
const viewer = new Cesium.Viewer("globe", {
  baseLayer: new Cesium.ImageryLayer(baseProvider),
  baseLayerPicker: false, geocoder: false, timeline: false, animation: false, homeButton: false,
  sceneModePicker: false, navigationHelpButton: false, infoBox: false, selectionIndicator: false });
viewer.scene.globe.enableLighting = true;
viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b1a28");
viewer.scene.skyAtmosphere.show = true;
viewer.scene.screenSpaceCameraController.minimumZoomDistance = 120;
viewer.scene.screenSpaceCameraController.maximumZoomDistance = 4.0e7;
viewer.scene.screenSpaceCameraController.enableCollisionDetection = true;
let baseLayer = viewer.imageryLayers.get(0);
function setSatelliteSource(source) {
  let provider, labelText;
  if (source === "esri") {
    // High-resolution geographic reference imagery; not a current observation.
    provider = new Cesium.UrlTemplateImageryProvider({
      url: "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      credit: "Esri World Imagery · reference basemap"
    });
    labelText = "ESRI WORLD IMAGERY · REFERENCE ONLY";
  } else {
    const layer = GIBS_LAYERS[source] || GIBS_LAYERS.terra;
    provider = gibs(layer, imageryDate, false);
    labelText = `NASA ${source.toUpperCase()} · ${imageryDate} · DAILY COMPOSITE`;
  }
  const next = new Cesium.ImageryLayer(provider);
  viewer.imageryLayers.add(next, 0);
  if (baseLayer && baseLayer !== next) viewer.imageryLayers.remove(baseLayer, true);
  baseLayer = next;
  const label = document.getElementById("imageryDate");
  if (label) label.textContent = labelText;
}
document.getElementById("imagerySource")?.addEventListener("change", e => setSatelliteSource(e.target.value));
setSatelliteSource("terra");
const imageryStamp = document.getElementById("imageryDate");
if (imageryStamp) imageryStamp.textContent = `NASA GIBS · ${imageryDate} · daily composite`;

// Layer names are NASA GIBS visualizations, not raw instrument swaths.
const rainLayer = viewer.imageryLayers.addImageryProvider(gibs("IMERG_Precipitation_Rate", imageryDate)); rainLayer.alpha = .6;
const fireLayer = viewer.imageryLayers.addImageryProvider(gibs("VIIRS_SNPP_Thermal_Anomalies_375m_All", imageryDate)); fireLayer.show = false;
const cloudLayer = viewer.imageryLayers.addImageryProvider(gibs("MODIS_Terra_Cloud_Top_Pressure", imageryDate)); cloudLayer.show = false; cloudLayer.alpha = .55;
$("lyRain").onchange = e => rainLayer.show = e.target.checked;
$("lyFire").onchange = e => fireLayer.show = e.target.checked;
$("lyCloud").onchange = e => cloudLayer.show = e.target.checked;

/* ---- earthquakes: USGS feed, refreshed every minute ---- */
const quakes = new Cesium.CustomDataSource("quakes"); viewer.dataSources.add(quakes);
async function loadQuakes() {
  try {
    const response = await fetch("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson", { cache: "no-store" });
    if (!response.ok) throw new Error(`USGS returned ${response.status}`);
    const g = await response.json();
    quakes.entities.removeAll();
    for (const f of g.features) {
      const [lon, lat] = f.geometry.coordinates, m = f.properties.mag || 0;
      quakes.entities.add({ position: Cesium.Cartesian3.fromDegrees(lon, lat),
        point: { pixelSize: 4 + m * 2.2, color: Cesium.Color.fromCssColorString("#ff6b6b").withAlpha(.75),
                 outlineColor: Cesium.Color.WHITE, outlineWidth: 1 }, properties: { quake: f.properties, lon, lat } });
    }
    const count = g.features.length;
    if ($("quakeCount")) $("quakeCount").textContent = `· ${count} M2.5+ events`;
    if ($("feedStatus")) $("feedStatus").textContent = `USGS updated ${new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}`; 
    const feedStamp = document.getElementById("usgsStamp");
    if (feedStamp) feedStamp.textContent = `USGS catalog · refreshed ${new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}`;

    if ($("feed-pill")) $("feed-pill").title = `USGS M2.5+ 24-hour catalog refreshed ${new Date().toISOString()}. NASA GIBS satellite imagery requested for ${imageryDate}.`;
  } catch (e) {
    if ($("feedStatus")) $("feedStatus").textContent = "USGS feed unavailable";
    console.warn("USGS feed unavailable", e);
  }
}
loadQuakes(); setInterval(loadQuakes, 60000);
$("lyQuake").onchange = e => quakes.show = e.target.checked;

/* ---- site twin ---- */
let S = null, state = "observed", ti = 0, overlay = null, scen = null, sel = null, timer = null;
const STATE_NOTE = {
  observed: "Observed layer: line-of-sight change represented in the loaded dataset (mm).",
  inferred: "Model-estimated motion after the fitted moisture-artifact adjustment (mm). Hatched = unresolved.",
  forecast: "Conditional model trajectory over 30 days under the baseline assumptions. Not an observation.",
  scenario: "Hypothetical model response under your selected inputs. Not an intervention outcome." };
const ramp = v => { // blue (down) - dark - orange (up)
  const t = Math.max(-1, Math.min(1, v)), a = 40 + 190 * Math.abs(t); return t < 0 ? [60, 140, 255, a] : [255, 150, 40, a]; };

function grid() {
  const n = S.n, now = S.rain.length - 1, p = S.params;
  if (state === "observed") return S.observed_los[ti];
  if (state === "inferred") return S.inferred_motion[ti];
  const all = []; for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) all.push([i, j]);
  const o = state === "scenario" ? labInputs() : { rainMm: 0 };
  const r = SwellModel.scenario(S, { ...o, cells: [[0, 0]], horizon: o.horizon || 30 });
  const useS = state === "scenario";
  return S.lep.map((row, i) => row.map((lep, j) => {
    const pv = Math.min(1, S.paved[i][j] + (useS ? (o.pavedDelta || 0) : 0));
    const unit = useS ? r.sEnd : r.bEnd;
    return p.alpha * lep * (1 - p.b * pv) * unit; }));
}
function draw() {
  if (!S) return;
  const n = S.n, g = grid(), c = document.createElement("canvas"); c.width = c.height = n * 8;
  const x = c.getContext("2d"), flat = g.flat().filter(v => Number.isFinite(v) && v > -9000).map(Math.abs).sort((a, b) => a - b), vmax = flat[Math.floor(flat.length * .98)] || 1;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    if (!Number.isFinite(g[i][j]) || g[i][j] <= -9000) continue;
    const [r, gg, b, a] = ramp(g[i][j] / vmax); x.fillStyle = `rgba(${r | 0},${gg | 0},${b | 0},${a / 255})`; x.fillRect(j * 8, i * 8, 8, 8);
    if (state === "inferred" && S.unresolved[i][j]) { x.fillStyle = "rgba(0,0,0,.55)"; x.fillRect(j * 8, i * 8, 8, 8); x.strokeStyle = "#fff8"; x.beginPath(); x.moveTo(j * 8, i * 8 + 8); x.lineTo(j * 8 + 8, i * 8); x.stroke(); }
  }
  if (overlay) viewer.imageryLayers.remove(overlay);
  const [w, s, e, nn] = S.bbox;
  overlay = viewer.imageryLayers.addImageryProvider(new Cesium.SingleTileImageryProvider({
    url: c.toDataURL(), rectangle: Cesium.Rectangle.fromDegrees(w, s, e, nn), tileWidth: c.width, tileHeight: c.height }));
  overlay.alpha = .85;
  $("stateNote").textContent = STATE_NOTE[state];
  $("legendScale").textContent = `±${vmax.toFixed(1)} mm · 98th pct scale`;
  $("when").textContent = (state === "observed" || state === "inferred") ? `PASS ${ti + 1}/${S.pass_days.length} · DAY ${S.pass_days[ti]}` : `DAY +${state === "scenario" ? (labInputs().horizon || 30) : 30}`;
  $("time").disabled = !(state === "observed" || state === "inferred");
  if ($("timeStart")) $("timeStart").textContent = `DAY ${S.pass_days[0]}`;
  if ($("timeEnd")) $("timeEnd").textContent = `DAY ${S.pass_days[S.pass_days.length - 1]}`;
}
let extra = { rainDays: 2, horizon: 30, futureRain: null };
function labInputs() { return { rainMm: +$("sRain").value, dryDays: +$("sDry").value, reduction: +$("sRed").value / 100, pavedDelta: +$("sPav").value / 100, ...extra }; }
function zoneCells() { const n = S.n, out = []; const c = sel || [n >> 1, n >> 1];
  for (let i = Math.max(0, c[0] - 3); i < Math.min(n, c[0] + 4); i++) for (let j = Math.max(0, c[1] - 3); j < Math.min(n, c[1] + 4); j++) out.push([i, j]); return out; }
function lab() {
  ["Rain", "Dry", "Red", "Pav"].forEach(k => $("o" + k).textContent = $("s" + k).value);
  const li = labInputs(), HZ = li.horizon || 30;
  scen = SwellModel.scenario(S, { ...li, cells: zoneCells() });
  const c = $("chart"), x = c.getContext("2d"), W = c.width, H = c.height; x.clearRect(0, 0, W, H);
  const all = scen.base.concat(scen.scen, [0]), lo = Math.min(...all), hi = Math.max(...all), sp = (hi - lo) || 1;
  const X = d => 40 + (d - 1) / (HZ - 1) * (W - 60), Y = v => H - 30 - (v - lo) / sp * (H - 50);
  x.strokeStyle = "#263039"; x.beginPath(); x.moveTo(40, Y(0)); x.lineTo(W - 20, Y(0)); x.stroke();
  [["#f2a33a", scen.base, "baseline"], ["#c58af9", scen.scen, "scenario"]].forEach(([col, a, lab], k) => {
    x.strokeStyle = col; x.lineWidth = 3; x.beginPath(); a.forEach((v, i) => i ? x.lineTo(X(i + 1), Y(v)) : x.moveTo(X(1), Y(v))); x.stroke();
    x.fillStyle = col; x.font = "20px system-ui"; x.fillText(lab, 50 + k * 120, 24); });
  x.fillStyle = "#8b98a5"; x.fillText(`${lo.toFixed(1)} to ${hi.toFixed(1)} mm, days 1-${HZ}`, W - 290, 24);
  $("labOut").innerHTML = `Zone ${sel ? `around cell ${sel}` : "at site centre"}: baseline <b>${scen.base[HZ - 1].toFixed(1)} mm</b>, scenario <b>${scen.scen[HZ - 1].toFixed(1)} mm</b> at day ${HZ} (estimated vertical change from today).`;
  if (state === "scenario") draw();
}
function fillPanels() {
  const sourceName = String(S.source || "UNSPECIFIED SOURCE");
  const isSynthetic = sourceName.toUpperCase().includes("SYNTHETIC");
  $("src").textContent = isSynthetic ? "SYNTHETIC DEMO · NOT NASA DATA" : `USER-LOADED · ${sourceName}`;
  $("src").title = isSynthetic ? "Synthetic fixture data for software testing; not a satellite observation." : "Source label supplied by the loaded site file; verify product provenance and maturity independently.";
  if ($("siteTitle")) $("siteTitle").textContent = S.name || "Loaded study region";
  if ($("siteSub")) $("siteSub").textContent = `${sourceName} · ${S.n} × ${S.n} grid · ${S.bbox.map(v => Number(v).toFixed(2)).join(", ")}`;
  const twinStamp = document.getElementById("twinStamp");
  if (twinStamp) twinStamp.textContent = isSynthetic ? "Synthetic test grid · not live NISAR" : "Loaded site dataset · acquisition dates shown below";

  const validZones = (S.zones || []).filter(z => z.status === "ok").length;
  const unresolvedZones = (S.zones || []).filter(z => z.status !== "ok").length;
  if ($("metricPasses")) $("metricPasses").textContent = S.pass_days.length;
  if ($("metricZones")) $("metricZones").textContent = validZones;
  if ($("metricUnresolved")) $("metricUnresolved").textContent = unresolvedZones;
  const p = S.params;
  $("params").innerHTML = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:9px"><div style="background:#132333;border:1px solid var(--line);border-radius:8px;padding:9px"><small style="color:var(--muted)">MOISTURE ARTIFACT</small><br><b style="font:700 18px Manrope">${Number(S.beta).toFixed(1)} mm</b><br><small>per unit wetness</small></div><div style="background:#132333;border:1px solid var(--line);border-radius:8px;padding:9px"><small style="color:var(--muted)">CLAY RESPONSE</small><br><b style="font:700 18px Manrope">${Number(p.alpha).toFixed(2)} mm</b><br><small>per rating unit</small></div></div>
    Delay <b>${p.tau} d</b> · settling time <b>${p.T} d</b> · paving damping <b>${(100 * p.b).toFixed(0)}%</b>.<br><br><b style="color:var(--amber)">Interpretation boundary:</b> fitted model parameters are not direct measurements of soil properties.`;
  $("tests").innerHTML = S.tests.map(t => `<tr><td>${t.name}</td><td class="${t.passed === null ? "na" : t.passed ? "ok" : "bad"}">${t.passed === null ? "not run" : t.passed ? "pass" : "fail"}</td></tr>`).join("");
  $("contracts").innerHTML = S.contracts.map(c => `<h2>${c.id}</h2><div class="note"><b>${c.stakeholder}</b>: ${c.proposed_action}<br>
    Expected: ${c.expected_observable.mean_mm.toFixed(1)} +/- ${c.expected_observable.band90_mm.toFixed(1)} mm by day ${c.expected_observable.day}.<br>
    Competing explanation: ${c.competing_explanation}.<br>Observed: ${c.observed_mm === undefined ? "n/a" : c.observed_mm.toFixed(1) + " mm"}.
    Arrival check: <b class="${c.arrival === "supported" ? "ok" : c.arrival === "contradicted" ? "bad" : "na"}">${c.arrival}</b><br>
    Approval: ${c.approval}. Digest ${c.digest.slice(0, 12)}… (full SHA-256 in the file).<br>${c.safety}</div>`).join("");
  const Z = (S.zones || []).filter(z => z.status === "ok"), unres = (S.zones || []).filter(z => z.status !== "ok").length;
  const zt = (rows, cols) => rows.length ? `<table><tr>${cols.map(c => `<th>${c[1]}</th>`).join("")}</tr>` + rows.map(r => `<tr>${cols.map(c => `<td>${r[c[0]]}</td>`).join("")}</tr>`).join("") + "</table>" : "<div class='note'>No resolved zones.</div>";
  const open = Z.filter(z => z.paved_fraction < .3), built = Z.filter(z => z.paved_fraction >= .3);
  const WHO = {
    "Civil engineer": { ctx: "Where to send a geotechnical investigation first. These are model estimates at about 80 m, not site measurements and not a foundation design.",
      plan: ["Start borings and lab swell tests in the zones with the largest estimated movement and spread.", "Use the estimated range to choose which movement to test for; confirm with a level survey.", "Record what the investigation finds in the outcome column so the twin can be scored."],
      rows: Z.slice(0, 5), cols: [["zone", "Zone"], ["est_seasonal_vertical_mm", "Est. seasonal (mm)"], ["est_within_zone_spread_mm", "Spread (mm)"], ["uncertainty_mm", "+/- (mm)"]], files: ["engineer_investigation_inputs.csv", "engineer_investigation_inputs.json"] },
    "City planner": { ctx: `Zones as polygons for your GIS. ${unres} zone(s) are unresolved and need another pass, not a decision.`,
      plan: ["Overlay the zones on roads, parcels and pending permits.", "Add monitoring before approving development where estimated movement is high and the zone is still mostly open ground.", "Re-check after the next NISAR pass."],
      rows: open.slice(0, 5), cols: [["zone", "Zone"], ["est_seasonal_vertical_mm", "Est. seasonal (mm)"], ["paved_fraction", "Paved"], ["storm_75mm_mm", "After 75 mm storm (mm)"]], files: ["planner_zones.geojson"] },
    "Water utility": { ctx: "Inspection candidates as boxes. The asset_id column is blank: join it to your own pipe inventory.",
      plan: ["Join the candidate boxes to your mains and valves.", "Inspect built-up zones with the largest estimated movement after a dry-to-wet swing.", "Approve, edit or reject each line; record the outcome."],
      rows: built.slice(0, 5), cols: [["zone", "Zone"], ["est_seasonal_vertical_mm", "Est. seasonal (mm)"], ["further_30_dry_days_mm", "30 more dry days (mm)"], ["paved_fraction", "Paved"]], files: ["utility_inspection_candidates.csv"] },
    "Emergency manager": { ctx: "A draft alert in the Common Alerting Protocol 1.2 format, checked for required elements. Status is Draft: SWELL never issues anything.",
      plan: ["After a major storm or earthquake, order inspections by zone.", "Review the draft; a named person approves or discards it.", "Compare with the next pass before standing down."],
      rows: Z.slice(0, 3), cols: [["zone", "Zone"], ["storm_75mm_mm", "After 75 mm storm (mm)"], ["mean_coherence", "Coherence"]], files: ["emergency_draft_alert.cap.xml"] },
    "Farmer / land manager": { ctx: "Open ground where moisture-driven movement is largest. No watering schedule is given: that needs your crop, soil and agronomist.",
      plan: ["Expect cracking in these zones when dry.", "Take the table to your agronomist or extension office.", "Compare with what you see in the field and tell us."],
      rows: open.slice(0, 5), cols: [["zone", "Zone"], ["est_seasonal_vertical_mm", "Est. seasonal (mm)"], ["further_30_dry_days_mm", "30 more dry days (mm)"]], files: ["land_manager_open_ground.csv"] },
    "Resident": { ctx: "What the measurements mean for a neighbourhood. They cannot say anything about one building.",
      plan: ["Read the summary.", "New cracks or sticking doors: ask a licensed foundation engineer.", "Check back after the next satellite pass."],
      rows: [], cols: [], files: ["resident_summary.txt"] },
    "Scientist": { ctx: "Everything behind the map: grids, fitted constants, every test including failures.",
      plan: ["Download the site data and rerun: python -m swell.validate.", "Read PREREGISTRATION.md, then try to break a test.", "Run the adversarial fixtures."],
      rows: [], cols: [], files: ["observe_next_priority.csv", "tray_experiment_log_template.csv"] } };
  $("who").innerHTML = Object.keys(WHO).map(k => `<option>${k}</option>`).join("");
  const show = () => { const p = WHO[$("who").value];
    $("plan").innerHTML = `<div class="note">${p.ctx}</div><h2>Action plan</h2><ol>${p.plan.map(x => `<li>${x}</li>`).join("")}</ol>` +
      (p.rows.length ? "<h2>Where</h2>" + zt(p.rows, p.cols) : "") + "<h2>Files</h2>" +
      p.files.map(f => `<div><a href="data/stakeholder/${f}" download>${f.split("/").pop()}</a></div>`).join("") +
      `<div class="note">Each file carries its data source, a SHA-256, an approval field and an outcome column. All values are estimates that need review by a qualified professional.</div>`; };
  $("who").onchange = show; show();
  renderResearchPanel();
}
function escapeHTML(v) { return String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function renderResearchPanel() {
  if (!S || !window.SwellResearch) return;
  const r = SwellResearch.report(S);
  $("researchSource").textContent = `${S.name || "Unnamed site"} · ${r.passCount} acquisitions · ${r.zoneCount} zones`;
  $("researchStatus").textContent = r.synthetic
    ? "SYNTHETIC FIXTURE · metrics demonstrate software behaviour, not real-world performance"
    : "User-loaded dataset · provenance and processing maturity must be independently verified";
  $("hypothesisCards").innerHTML = r.candidates.length ? r.candidates.map(c => {
    const best = r.best && c.id === r.best.id;
    const desc = c.id === "M0" ? "Treats observed phase-derived change as motion; no physical response model."
      : c.id === "M1" ? "Rain-only response; no explicit moisture-artifact separation or delayed clay dynamics."
      : "SWELL artifact-adjusted, delayed-response model.";
    return `<div class="hypothesis-card ${best ? "best" : ""}"><div class="hyp-top"><b>${escapeHTML(c.id)} · ${escapeHTML(c.name)}</b>${best ? '<span class="ok">LOWEST RMSE</span>' : ""}</div><strong>${Number(c.rmse).toFixed(2)} mm</strong><small>${desc}</small></div>`;
  }).join("") : '<div class="note">No comparable holdout RMSE values are available in this site file.</div>';
  const parts = [];
  if (r.artifact.gpsNaive !== undefined) parts.push(`GPS LOS RMS: ${Number(r.artifact.gpsNaive).toFixed(2)} → ${Number(r.artifact.gpsCorrected).toFixed(2)} mm`);
  if (r.clay.rho !== undefined) parts.push(`Clay-map Spearman ρ: ${Number(r.clay.rho).toFixed(2)} · shuffled null quantile ${Number(r.clay.nullQuantile).toFixed(3)}`);
  if (r.forecast.coverage !== undefined) parts.push(`Forecast interval coverage: ${(100*r.forecast.coverage).toFixed(1)}% · mean band half-width ${Number(r.forecast.band).toFixed(2)} mm`);
  if (r.refusal.kept !== undefined) parts.push(`Refusal retained fraction: ${(100*r.refusal.kept).toFixed(1)}%`);
  $("hypothesisEvidence").textContent = parts.length ? parts.join(" · ") : "Supporting diagnostic metrics are not present in the loaded validation record.";
  $("researchAnswer").innerHTML = '<b>Ask a question to retrieve relevant evidence.</b>';
}
function renderResearchAnswer(question) {
  if (!S || !window.SwellResearch) return;
  const a = SwellResearch.answer(S, question);
  $("researchAnswer").innerHTML = `<b>${escapeHTML(a.title)}</b><div>${escapeHTML(a.body)}</div>` +
    (a.evidence.length ? `<div class="answer-refs">EVIDENCE: ${a.evidence.map(escapeHTML).join(" · ")}</div>` : "") +
    (a.limitations.length ? `<div class="answer-limits"><b>Limitations</b><br>${a.limitations.map(escapeHTML).join("<br>")}</div>` : "");
}
function clickCell(lon, lat) {
  const [w, s, e, nn] = S.bbox, n = S.n; if (lon < w || lon > e || lat < s || lat > nn) return false;
  const j = Math.min(n - 1, Math.floor((lon - w) / (e - w) * n)), i = Math.min(n - 1, Math.floor((nn - lat) / (nn - s) * n)); sel = [i, j]; if (typeof updateDecisionCell === "function") updateDecisionCell(i, j, lon, lat);
  const fmt = v => v !== null && v !== undefined && Number.isFinite(Number(v)) ? Number(v).toFixed(1) : "missing";
  $("cell").innerHTML = `<b>Grid cell ${i + 1}, ${j + 1}</b><br>Shrink-swell proxy ${fmt(S.lep[i][j])} · paved ${(100 * S.paved[i][j]).toFixed(0)}% · coherence ${fmt(S.coh[i][j])}.<br>
    <span style="color:var(--obs)">Observed layer</span> ${fmt(S.observed_los[ti][i][j])} mm LOS · fitted moisture component ${fmt(S.artifact[ti][i][j])} mm.<br>
    <span style="color:var(--inf)">Inferred layer</span> ${fmt(S.inferred_motion[ti][i][j])} mm · illustrative 90% half-width ${fmt(1.645 * S.inferred_sd[ti][i][j])} mm.
    ${S.unresolved[i][j] ? '<br><b style="color:var(--amber)">Unresolved: obtain another valid observation before making a decision.</b>' : ""}`;
  lab(); xsec(); return true;
}
function quakePanel(q) {
  const p = q.quake.getValue(), days = [1, 3, 7, 30], m = p.mag;
  const rows = days.map(d => { let n = 0; for (let t = 0; t < d; t += .05) n += SwellModel.aftershockRate(t, m, Math.max(3, m - 2)) * .05; return `<tr><td>next ${d} d</td><td>${n.toFixed(1)}</td></tr>`; }).join("");
  $("quake").innerHTML = `<b>M ${m} ${p.place}</b><br>${new Date(p.time).toUTCString()}<br><a href="${p.url}" target="_blank" rel="noopener">USGS event page (shaking map and official aftershock forecast, where published)</a>
    <h2>Expected aftershocks of M ${Math.max(3, m - 2).toFixed(1)} or larger</h2><table>${rows}</table>
    <div class="note">Generic Reasenberg-Jones (1989) rates: a standard statistical forecast, not a SWELL result and not a prediction of any single earthquake. NISAR revisits every 12 days per direction; its before/after interferogram shows the ground shift once both passes exist.</div>`;
  tab("quake");
}
function tab(t) { document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("on", b.dataset.t === t));
  ["evidence", "copilot", "lab", "people", "structures", "contracts", "decisions", "quake", "own", "worlds"].forEach(k => $("tab-" + k).hidden = k !== t);
  if (t === "lab") lab();
  if (t === "structures") runStructureScreen();
  if (window.matchMedia("(max-width: 820px)").matches) $("drawer").scrollTop = 0;
}

/* ---- structure screening: upper-bound kinematic scenario, not structural analysis ---- */
function runStructureScreen() {
  const kind = $("structureType").value, move = +$("structureMove").value;
  const span = +$("structureSpan").value, edge = +$("structureEdge").value;
  const reduction = +$("structureReduce").value / 100;
  if (![move, span, edge, reduction].every(Number.isFinite) || move < 0 || span <= 0 || edge <= 0 || reduction < 0 || reduction > 1) {
    $("structureOut").textContent = "Check the inputs: movement must be non-negative, span and edge distance positive, reduction 0–100%.";
    return;
  }
  let calc;
  try { calc = SwellModel.structureScreen(move, kind, span, edge, reduction); }
  catch (e) { $("structureOut").textContent = e.message; return; }
  const family = calc.family, edgeMove = calc.edgeMovementMm, distortion = calc.distortion;
  const oneIn = calc.oneIn, band = calc.band || "not applicable", gradientLength = calc.gradientLengthM;
  const response = {
    "Unreinforced slab on grade":"A shallow slab may follow differential near-surface movement; actual response depends on geometry, reinforcement, soil contact and loads.",
    "Stiffened (ribbed) slab":"Stiffening can redistribute movement, but its effect depends on engineered design and soil-structure interaction.",
    "Post-tensioned slab":"Performance depends on tendon layout, joints, design assumptions and actual ground movement; the label alone cannot establish capacity.",
    "Pier and beam (suspended floor)":"A suspended floor may decouple from shallow active soil if supports extend below the active zone; pier movement remains possible.",
    "Flexible pavement (road)":"Road distress depends on pavement layers, subgrade, drainage, traffic and maintenance. Building angular-distortion guides do not apply.",
    "Buried pipe (segmented)":"Pipe response depends on material, joints, burial depth, bedding, restraint, pressure and soil-pipe interaction. Building guides do not apply."
  }[kind];
  const guide = family === "building" ? `<br><b>Context band:</b> ${band}. Commonly cited angular-distortion guide only; not a damage prediction or safety threshold.` : `<br><b>Building distortion guides:</b> not applicable to this asset type.`;
  $("structureOut").innerHTML = `<b>${kind}</b><br>Input differential movement: ${move.toFixed(1)} mm; after assumed edge reduction: ${edgeMove.toFixed(1)} mm.<br><b>Kinematic upper-bound distortion:</b> ${distortion.toExponential(3)} over ${gradientLength.toFixed(2)} m${oneIn ? ` (about 1 in ${oneIn})` : ""}.${guide}<br><br>${response}<br><br><b>Professional review:</b> obtain drawings, geotechnical profile, field crack/condition survey and precise levelling or asset-specific measurements. This calculation does not model stiffness, reinforcement, foundations, loads, pipe joints, pavement layers, crack probability or structural safety.`;
  const c=$("structureSketch"), x=c.getContext("2d"), W=c.width,H=c.height; x.clearRect(0,0,W,H);
  const amp=Math.max(0,Math.min(55,edgeMove*1.5)), y0=130;
  x.fillStyle="#172431";x.fillRect(0,0,W,y0);x.fillStyle="#70513b";x.fillRect(0,y0,W,H-y0);
  x.fillStyle="#4aa3ff";x.globalAlpha=.25;x.fillRect(0,y0+25,W,55);x.globalAlpha=1;
  x.strokeStyle="#c58af9";x.lineWidth=4;x.beginPath();x.moveTo(0,y0+amp);x.lineTo(W,y0);x.stroke();
  x.fillStyle="#d5dce4";x.fillRect(180,y0-55,340,55);x.fillStyle="#aab7c5";x.fillRect(205,y0-100,290,45);
  x.fillStyle="#0e1216";for(let k=0;k<4;k++)x.fillRect(225+k*65,y0-88,30,25);
  x.fillStyle="#e8edf2";x.font="18px system-ui";x.fillText("Schematic only · differential ground movement exaggerated",16,24);
  x.font="16px system-ui";x.fillText(`Movement ${edgeMove.toFixed(1)} mm · span ${span.toFixed(1)} m · assumed reduction ${(100*reduction).toFixed(0)}%`,16,H-18);
}
$("structureRun").onclick = runStructureScreen;
["structureType","structureMove","structureSpan","structureEdge","structureReduce"].forEach(id => $(id).addEventListener("change", runStructureScreen));
$("structureUseCell").onclick = () => {
  if (!S || !sel) { $("structureOut").textContent = "Select a cell on the map first."; return; }
  const v = Math.abs(S.inferred_motion[ti][sel[0]][sel[1]]);
  $("structureMove").value = v.toFixed(1); runStructureScreen();
  $("structureOut").insertAdjacentHTML("afterbegin", `<b>Imported from selected cell:</b> ${v.toFixed(1)} mm absolute inferred displacement. This is NOT measured differential movement across a building; replace it with a site survey for meaningful structural screening.<br>`);
};

document.querySelectorAll("#tabs button").forEach(b => b.onclick = () => tab(b.dataset.t));
$("researchAsk").onclick = () => {
  const q = $("researchQuestion").value.trim();
  if (!q) { $("researchAnswer").textContent = "Enter a question about the loaded study's evidence."; return; }
  renderResearchAnswer(q);
};
document.querySelectorAll(".copilot-prompts button").forEach(b => b.onclick = () => {
  $("researchQuestion").value = b.dataset.q; renderResearchAnswer(b.dataset.q);
});
$("researchQuestion").addEventListener("keydown", e => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") renderResearchAnswer($("researchQuestion").value); });

document.querySelectorAll("#states button").forEach(b => b.onclick = () => { state = b.dataset.s;
  document.querySelectorAll("#states button").forEach(x => x.classList.toggle("on", x === b)); draw(); });
["sRain", "sDry", "sRed", "sPav"].forEach(id => $(id).oninput = lab);
$("run").onclick = () => {
  const r = SwellModel.parseRequest($("ask").value), o = r.settings;
  if (r.ignored) { $("understood").textContent = "I could not find rain, drought, drainage or paving in that. Try: 80 mm of rain after 2 weeks of drought."; return; }
  $("sRain").value = Math.min(200, o.rainMm); $("sDry").value = Math.min(30, o.dryDays); $("sRed").value = 100 * o.reduction; $("sPav").value = Math.min(60, 100 * o.pavedDelta);
  extra = { ...extra, rainDays: o.rainDays, horizon: o.horizon };
  $("understood").textContent = "Understood: " + r.understood.join("; ") + ".";
  state = "scenario"; document.querySelectorAll("#states button").forEach(x => x.classList.toggle("on", x.dataset.s === "scenario")); lab(); draw();
};
$("upSite").onchange = async e => { try { const d = JSON.parse(await e.target.files[0].text());
    for (const k of ["bbox", "n", "pass_days", "rain", "lep", "paved", "coh", "params", "observed_los", "inferred_motion", "inferred_sd", "artifact", "unresolved", "wetness", "tests", "contracts", "zones"]) if (!(k in d)) throw new Error("missing " + k);
    if (!Array.isArray(d.pass_days) || !d.pass_days.length || !Number.isInteger(d.n) || d.n < 1) throw new Error("invalid grid dimensions or acquisition timeline");
    S = d; ti = S.pass_days.length - 1; $("time").max = ti; $("time").value = ti; sel = null; fillPanels(); draw(); lab(); flySite();
    $("ownOut").textContent = `Loaded "${S.name}" (${S.source}).`; } catch (err) { $("ownOut").textContent = "Could not load that file: " + err.message; } };
$("upRain").onchange = async e => { const v = (await e.target.files[0].text()).split(/[\r\n,;]+/).map(Number).filter(x => isFinite(x) && x >= 0);
  if (!v.length) { $("ownOut").textContent = "No numbers found in that file."; return; }
  extra = { ...extra, futureRain: v, horizon: Math.min(120, Math.max(10, v.length)) }; $("ownOut").textContent = `Using your ${v.length}-day rain forecast (${v.reduce((a, b) => a + b, 0).toFixed(0)} mm total) in the What-if lab.`; lab(); };

function xsec() {
  const c = $("xsec"), x = c.getContext("2d"), W = c.width, H = c.height; x.clearRect(0, 0, W, H);
  if (!S || !sel) { x.fillStyle = "#8b98a5"; x.font = "22px system-ui"; x.fillText("Click a cell on the site to see what is happening under it.", 30, H / 2); return; }
  const [i, j] = sel, d = S.pass_days[ti], w = S.wetness[d], w0 = S.wetness[S.pass_days[0]], m = S.inferred_motion[ti][i][j];
  const jn = Math.min(S.n - 1, j + 1), mN = S.inferred_motion[ti][i][jn], lep = S.lep[i][j], pv = S.paved[i][j];
  const rain7 = S.rain.slice(Math.max(0, d - 6), d + 1).reduce((a, b) => a + b, 0);
  const all = S.inferred_motion.flat(2).map(Math.abs), mmax = Math.max(1, ...all), EX = 60 / mmax;       // px per mm
  const g0 = 150, yL = g0 - m * EX, yR = g0 - mN * EX;
  x.fillStyle = "#16202b"; x.fillRect(0, 0, W, g0 - 70);                                                  // sky
  x.strokeStyle = "#4aa3ff"; x.lineWidth = 2; const drops = Math.min(60, Math.round(rain7 * 1.2));
  for (let k = 0; k < drops; k++) { const px = 20 + (k * 97) % (W - 40), py = 10 + (k * 53) % 60; x.beginPath(); x.moveTo(px, py); x.lineTo(px - 4, py + 12); x.stroke(); }
  const depthWet = 30 + 150 * w;                                                                          // wetting front depth (px), illustrative
  const top = xx => yL + (yR - yL) * (xx / W);
  x.beginPath(); x.moveTo(0, top(0)); x.lineTo(W, top(W)); x.lineTo(W, H); x.lineTo(0, H); x.closePath();
  x.fillStyle = `rgb(${70 + 12 * lep | 0},${52 + 4 * lep | 0},40)`; x.fill();                             // clay: darker = higher rating
  x.beginPath(); x.moveTo(0, top(0)); x.lineTo(W, top(W)); x.lineTo(W, top(W) + depthWet); x.lineTo(0, top(0) + depthWet); x.closePath();
  x.fillStyle = `rgba(74,163,255,${.15 + .45 * w})`; x.fill();                                            // wet zone
  x.strokeStyle = "#8b98a5"; x.setLineDash([6, 6]); x.beginPath(); x.moveTo(0, g0); x.lineTo(W, g0); x.stroke(); x.setLineDash([]);
  x.fillStyle = "#8b98a5"; x.font = "17px system-ui"; x.fillText("ground level at first pass", W - 230, g0 - 6);
  x.save(); x.translate(W / 2, (yL + yR) / 2); x.rotate(Math.atan2(yR - yL, W)); x.fillStyle = "#cfd6dd"; x.fillRect(-150, -14, 300, 14);
  x.fillStyle = "#e8edf2"; x.fillRect(-120, -84, 240, 70); x.fillStyle = "#12161b"; for (let k = 0; k < 4; k++) x.fillRect(-100 + k * 56, -66, 30, 30); x.restore();
  if (pv > .5) { x.fillStyle = "#39424c"; x.beginPath(); x.moveTo(0, top(0)); x.lineTo(W, top(W)); x.lineTo(W, top(W) + 8); x.lineTo(0, top(0) + 8); x.fill(); }
  x.fillStyle = "#e8edf2"; x.font = "19px system-ui";
  x.fillText(`Rain, last 7 days: ${rain7.toFixed(0)} mm    Wetness: ${(100 * w).toFixed(0)} % (was ${(100 * w0).toFixed(0)} %)`, 16, H - 62);
  x.fillText(`Clay rating ${lep} %   Paved ${(100 * pv).toFixed(0)} %   Inferred motion ${m >= 0 ? "+" : ""}${m} mm, next cell ${mN >= 0 ? "+" : ""}${mN} mm`, 16, H - 36);
  x.fillStyle = "#f2a33a"; x.fillText(`ILLUSTRATION. Vertical exaggeration x${(EX * 80000 / W).toFixed(0)}. ${S.unresolved[i][j] ? "This cell is UNRESOLVED." : ""}`, 16, H - 10);
}
$("time").oninput = e => { ti = +e.target.value; draw(); xsec(); };
$("play").onclick = () => {
  if (!S || !S.pass_days || !S.pass_days.length) return;
  if (timer) { clearInterval(timer); timer = null; $("play").textContent = "Play"; return; }
  if (state !== "observed" && state !== "inferred") {
    state = "observed"; document.querySelectorAll("#states button").forEach(x => x.classList.toggle("on", x.dataset.s === state));
  }
  $("play").textContent = "Pause"; timer = setInterval(() => { ti = (ti + 1) % S.pass_days.length; $("time").value = ti; draw(); xsec(); }, 950);
};
const flySite = () => { const [w, s, e, n] = S.bbox; viewer.camera.flyTo({ destination: Cesium.Rectangle.fromDegrees(w - .15, s - .15, e + .15, n + .15), duration: 2.5 }); };
$("fly").onclick = flySite; $("home").onclick = () => viewer.camera.flyHome(2);
const quickPlaces = {
  "Dallas–Fort Worth": [32.7767, -96.7970, 180000],
  "Toulouse": [43.6045, 1.4440, 180000],
  "Nagpur": [21.1458, 79.0882, 180000]
};
document.querySelectorAll("[data-place]").forEach(btn => btn.addEventListener("click", () => {
  const p = quickPlaces[btn.dataset.place]; if (!p) return;
  viewer.camera.flyTo({destination: Cesium.Cartesian3.fromDegrees(p[1], p[0], p[2]), duration: 2.2});
  $("coordinateSearch").value = `${p[0].toFixed(4)}, ${p[1].toFixed(4)}`;
  document.querySelectorAll("[data-place]").forEach(b => b.classList.toggle("active", b === btn));
}));

new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas).setInputAction(ev => {
  const picked = viewer.scene.pick(ev.position);
  if (picked && picked.id && picked.id.properties && picked.id.properties.quake) return quakePanel(picked.id.properties);
  const c = viewer.camera.pickEllipsoid(ev.position); if (!c || !S) return;
  const g = Cesium.Cartographic.fromCartesian(c), lon = Cesium.Math.toDegrees(g.longitude), lat = Cesium.Math.toDegrees(g.latitude); updateDecisionLocation(lon, lat); if (clickCell(lon, lat)) tab("evidence");
}, Cesium.ScreenSpaceEventType.LEFT_CLICK);

fetch("data/site.json").then(r => { if (!r.ok) throw new Error(`site.json returned ${r.status}`); return r.json(); }).then(d => {
  S = d; decisionPoint.lon=(S.bbox[0]+S.bbox[2])/2; decisionPoint.lat=(S.bbox[1]+S.bbox[3])/2; decisionPoint.i=Math.floor(S.n/2); decisionPoint.j=Math.floor(S.n/2); decisionPoint.inside=true; updateDecisionLocation(decisionPoint.lon,decisionPoint.lat); $("time").max = S.pass_days.length - 1; ti = S.pass_days.length - 1; $("time").value = ti;
  $("time").disabled = false; $("play").disabled = false; fillPanels(); draw();
  const [west, south, east, north] = S.bbox, mid = S.n >> 1;
  let chosen = [mid, mid];
  for (let radius = 0; radius < S.n && S.unresolved[mid][mid]; radius++) {
    let found = false;
    for (let i = Math.max(0, mid-radius); i <= Math.min(S.n-1, mid+radius) && !found; i++) for (let j = Math.max(0, mid-radius); j <= Math.min(S.n-1, mid+radius); j++) if (!S.unresolved[i][j]) { chosen = [i,j]; found = true; break; }
    if (found) break;
  }
  clickCell(west + (chosen[1] + .5) / S.n * (east-west), north - (chosen[0] + .5) / S.n * (north-south));
  draw(); xsec(); flySite();
}).catch(e => {
  $("src").textContent = "NO STUDY DATA"; $("siteTitle").textContent = "No study region loaded";
  $("siteSub").textContent = "Run the validation workflow or load a site.json";
  $("feedStatus").textContent = "Context feeds may still be available";
  console.error(e);
});

/* ---- other worlds: real radar elsewhere, no twin (NISAR observes Earth) ---- */
let WORLDS = [], worldLayer = null, worldTileErrors = 0; const worldPins = new Cesium.CustomDataSource("worldPins"); viewer.dataSources.add(worldPins);
const earthBase = viewer.imageryLayers.get(0);
function setWorld(id) {
  const w = WORLDS.find(x => x.id === id), earth = !w || w.twin;
  earthBase.show = earth; rainLayer.show = earth && $("lyRain").checked; fireLayer.show = earth && $("lyFire").checked; quakes.show = earth && $("lyQuake").checked;
  if (overlay) overlay.show = earth;
  if (typeof coordinatePin !== "undefined") coordinatePin.show = earth; $("bottom").style.display = earth ? "" : "none";
  if (worldLayer) { viewer.imageryLayers.remove(worldLayer); worldLayer = null; } worldPins.entities.removeAll(); worldTileErrors = 0;
  if (earth) { tab("evidence"); return; }
  const prov = new Cesium.UrlTemplateImageryProvider({ url: w.tiles, tilingScheme: new Cesium.GeographicTilingScheme(), maximumLevel: w.maxLevel, credit: "NASA Solar System Treks" });
  prov.errorEvent.addEventListener(() => { if (++worldTileErrors === 3) $("worldCard").insertAdjacentHTML("afterbegin", `<div class="bad">The ${w.name} image layer is not loading (${w.confidence}). The facts below still stand; fix the product name in worlds.json.</div>`); });
  worldLayer = viewer.imageryLayers.addImageryProvider(prov);
  for (const m of w.markers) worldPins.entities.add({ position: Cesium.Cartesian3.fromDegrees(m.lon > 180 ? m.lon - 360 : m.lon, m.lat),
    point: { pixelSize: 12, color: Cesium.Color.fromCssColorString("#f2a33a"), outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
    label: { text: m.name, font: "14px system-ui", pixelOffset: new Cesium.Cartesian2(0, -22), fillColor: Cesium.Color.WHITE, showBackground: true } });
  $("worldCard").innerHTML = `<h2>${w.name}</h2><b>Radar that has flown:</b> ${w.radar}.` +
    w.markers.map(m => `<h2>${m.name}${m.approx ? " (position approximate)" : ""}</h2>${m.what} <a href="${m.source}" target="_blank" rel="noopener">Source</a>`).join("") +
    `<h2>What a twin here would need</h2>${w.twin_needs}<h2>Status</h2>No SWELL twin exists for ${w.name}. This view shows real radar findings and the globe is drawn at Earth's size. Load your own processed site in "Your data" for any world you have repeat radar for.`;
  tab("worlds"); const m = w.markers[0]; viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(m.lon > 180 ? m.lon - 360 : m.lon, Math.max(-60, Math.min(60, m.lat)), 9e6), duration: 2 });
}
fetch("worlds.json").then(r => r.json()).then(d => { WORLDS = d.worlds; $("world").innerHTML = WORLDS.map(w => `<option value="${w.id}">${w.name}</option>`).join(""); $("world").onchange = e => setWorld(e.target.value); })
  .catch(() => { $("world").style.display = "none"; });


/* ---- application chrome: map tools, responsive analysis drawer, and keyboard access ---- */
const setDrawer = open => {
  document.body.classList.toggle("drawer-hidden", !open);
  $("drawerToggle").setAttribute("aria-expanded", String(open));
  $("drawerToggle").title = open ? "Hide analysis panel" : "Show analysis panel";
};
$("drawerToggle").onclick = () => setDrawer(document.body.classList.contains("drawer-hidden"));
$("drawerClose").onclick = () => setDrawer(false);
$("zoomIn").onclick = () => viewer.camera.zoomIn(Math.max(250, viewer.camera.positionCartographic.height * .35));
$("zoomOut").onclick = () => viewer.camera.zoomOut(Math.max(500, viewer.camera.positionCartographic.height * .45));
$("resetBearing").onclick = () => viewer.camera.setView({ orientation: { heading: 0, pitch: -Cesium.Math.PI_OVER_TWO, roll: 0 } });
document.addEventListener("keydown", e => { if (e.key === "Escape") setDrawer(false); });
window.addEventListener("resize", () => { viewer.resize(); });

const coordinatePin = new Cesium.CustomDataSource("coordinateSearch"); viewer.dataSources.add(coordinatePin);
$("goCoordinates").onclick = () => {
  const parts = $("coordinateSearch").value.split(/[ ,]+/).map(Number);
  if (parts.length !== 2 || !parts.every(Number.isFinite) || Math.abs(parts[0]) > 90 || Math.abs(parts[1]) > 180) {
    $("coordinateSearch").setCustomValidity("Enter latitude, longitude (for example 32.78, -96.80)");
    $("coordinateSearch").reportValidity(); return;
  }
  $("coordinateSearch").setCustomValidity("");
  const [lat, lon] = parts; updateDecisionLocation(lon, lat); coordinatePin.entities.removeAll();
  coordinatePin.entities.add({position:Cesium.Cartesian3.fromDegrees(lon,lat),point:{pixelSize:12,color:Cesium.Color.fromCssColorString("#e7b477"),outlineColor:Cesium.Color.WHITE,outlineWidth:2},label:{text:`${lat.toFixed(4)}, ${lon.toFixed(4)}`,font:"12px DM Mono",pixelOffset:new Cesium.Cartesian2(0,-22),fillColor:Cesium.Color.WHITE,showBackground:true,backgroundColor:Cesium.Color.fromCssColorString("#091522").withAlpha(.85)}});
  viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(lon,lat,450000),duration:1.8});
  if (S && lon >= S.bbox[0] && lon <= S.bbox[2] && lat >= S.bbox[1] && lat <= S.bbox[3]) clickCell(lon,lat);
};
$("coordinateSearch").addEventListener("keydown", e => { if (e.key === "Enter") $("goCoordinates").click(); });


/* ---- Decision Studio: one physical evidence base, role-specific draft deliverables ---- */
let decisionPoint = {lon:null,lat:null,i:null,j:null,inside:false};
let decisionLast = null;
const d$ = id => document.getElementById(id);
const dnum = (id, fallback=0) => { const v = Number(d$(id)?.value); return Number.isFinite(v) ? v : fallback; };
const dformat = (v, digits=1) => Number.isFinite(v) ? v.toFixed(digits) : "—";
function updateDecisionLocation(lon,lat) {
  decisionPoint.lon=lon; decisionPoint.lat=lat;
  decisionPoint.inside=!!(S && lon>=S.bbox[0] && lon<=S.bbox[2] && lat>=S.bbox[1] && lat<=S.bbox[3]);
  if (d$("decisionLocation")) {
    d$("decisionLocation").textContent = decisionPoint.inside ? (S.name || "Loaded study area") : "Geographic context · no loaded physical study";
    d$("decisionCoords").textContent = `${lat.toFixed(5)}° N, ${lon.toFixed(5)}° E · ${decisionPoint.inside ? "inside loaded study footprint" : "outside loaded study footprint"}`;
  }
}
function updateDecisionCell(i,j,lon,lat) {
  decisionPoint.i=i; decisionPoint.j=j; updateDecisionLocation(lon,lat);
}
function decisionRoleChanged() {
  const role=d$("decisionRole")?.value || "engineer";
  if(d$("plannerAssumptions")) d$("plannerAssumptions").hidden=role!=="planner";
  if(d$("engineerAssumptions")) d$("engineerAssumptions").hidden=role!=="engineer";
  if(decisionLast) runDecisionStudio();
}
function decisionScenario() {
  if(!S) throw new Error("The study data has not loaded yet.");
  const role=d$("decisionRole").value, rain=dnum("decisionRain",120), drain=dnum("decisionDrain",50)/100;
  const groundwater=dnum("decisionWater",.3), horizon=dnum("decisionHorizon",12);
  let i=decisionPoint.i, j=decisionPoint.j;
  if(!Number.isFinite(decisionPoint.lon) || !Number.isFinite(decisionPoint.lat)) {
    decisionPoint.lon=(S.bbox[0]+S.bbox[2])/2; decisionPoint.lat=(S.bbox[1]+S.bbox[3])/2;
    decisionPoint.i=Math.floor(S.n/2); decisionPoint.j=Math.floor(S.n/2); decisionPoint.inside=true;
    updateDecisionLocation(decisionPoint.lon,decisionPoint.lat);
  }
  const inside=decisionPoint.inside && Number.isInteger(i) && Number.isInteger(j);
  if(!inside) throw new Error("No physical study coverage at this coordinate. The globe can show geographic context, but a site-specific physical scenario is disabled until a real, quality-controlled dataset is available.");
  const cells=[[i,j]];
  const result=SwellModel.scenario(S,{horizon:Math.max(1,Math.min(60,horizon))*30,rainMm:rain,rainDays:7,reduction:drain,cells});
  const baseline=SwellModel.scenario(S,{horizon:Math.max(1,Math.min(60,horizon))*30,rainMm:0,rainDays:7,reduction:0,cells});
  const endBase=result.base[result.base.length-1] || 0;
  const endScenario=result.scen[result.scen.length-1] || 0;
  const delta=endScenario-endBase;
  const obs=Number(S.observed_los?.[ti]?.[i]?.[j]);
  const inferred=Number(S.inferred_motion?.[ti]?.[i]?.[j]);
  const sd=Number(S.inferred_sd?.[ti]?.[i]?.[j]);
  const unresolved=!!S.unresolved?.[i]?.[j];
  const p=S.params || {};
  const dataSource=String(S.source||"unknown");
  return {created:new Date().toISOString(),role,location:{name:S.name||"Study region",lon:decisionPoint.lon,lat:decisionPoint.lat,i,j,insideStudy:inside},fixture:/synthetic|fixture/i.test(dataSource),
    source:dataSource,model:{name:"SWELL moisture-response scenario",alpha:p.alpha,b:p.b,T:p.T,tau:p.tau},inputs:{rainfall7d_mm:rain,drainageEffectiveness:drain,groundwaterRiseContextOnly_m:groundwater,horizonMonths:horizon},
    output:{baselineEndMm:endBase,scenarioEndMm:endScenario,deltaMm:delta,observedLOSmm:Number.isFinite(obs)?obs:null,inferredMotionMm:Number.isFinite(inferred)?inferred:null,uncertaintyHalfWidth90mm:Number.isFinite(sd)?1.645*sd:null,unresolved},
    series:{days:result.days,baseline:result.base,scenario:result.scen},
    planning:{assets:dnum("decisionAssets",120),assetValueUSD:dnum("decisionAssetValue",180000),budgetUSD:dnum("decisionBudget",2400000),annualLossUSD:dnum("decisionLoss",650000)},
    engineering:{depthM:dnum("decisionDepth",8),boreholes:dnum("decisionBores",5),spacingM:dnum("decisionSpacing",25),areaHa:dnum("decisionArea",4)},
    disclaimer:"The bundled study is a synthetic research fixture. Scenario outputs are illustrative model responses, not observations, forecasts, engineering design values, safety assessments or construction instructions. Groundwater rise is recorded as context only and is not coupled to the current moisture-response equation."};
}
function decisionInterpretation(x) {
  const o=x.output, i=x.inputs;
  const evidence=o.unresolved?"The selected grid cell is marked unresolved. Its measurements must not be used to prioritize a site-specific intervention.":"The selected cell has a model value in the loaded study fixture. Review the acquisition, quality and independent validation before operational interpretation.";
  const direction=o.deltaMm>0?"increases":"decreases";
  return `${evidence} Under the chosen assumptions, the modeled response at the end of ${i.horizonMonths} months ${direction} by ${Math.abs(o.deltaMm).toFixed(2)} mm relative to the baseline run. This is a conditional sensitivity result, not a real-world forecast.`;
}
function money(v){return new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(Number(v)||0);}
function renderDecisionResults(x) {
  const role=d$("decisionRole").value, o=x.output, loc=x.location;
  const coord=Number.isFinite(loc.lon)?`${loc.lat.toFixed(5)}, ${loc.lon.toFixed(5)}`:"study centroid / selected cell";
  let cards="";
  if(role==="planner") {
    const exposure=x.planning.assets*x.planning.assetValueUSD;
    const fiveYearLoss=x.planning.annualLossUSD*5;
    const ratio=x.planning.annualLossUSD>0?x.planning.budgetUSD/x.planning.annualLossUSD:null;
    cards=`<div class="decision-card"><h4>Planning interpretation</h4><p>${decisionInterpretation(x)}</p><p>Spatial priority: use this evidence to screen where additional surveys, drainage studies or land-use review may be warranted. Do not convert a coarse radar pixel directly into a parcel-level designation.</p></div>
    <div class="decision-card"><h4>Economic scenario · editable assumptions</h4><table class="decision-compare"><tr><th>Metric</th><th>Assumption / result</th></tr><tr><td>Assets in planning area</td><td>${x.planning.assets.toLocaleString()}</td></tr><tr><td>Aggregate asset value assumption</td><td>${money(exposure)}</td></tr><tr><td>Intervention budget assumption</td><td>${money(x.planning.budgetUSD)}</td></tr><tr><td>Annual disruption loss assumption</td><td>${money(x.planning.annualLossUSD)}</td></tr><tr><td>Five-year undiscounted loss sensitivity</td><td>${money(fiveYearLoss)}</td></tr><tr><td>Budget / annual-loss ratio</td><td>${ratio===null?"not calculable":ratio.toFixed(2)+" years"}</td></tr></table><p>These are editable planning assumptions, not measured exposure or proven avoided losses. The ratio is not a payback forecast. A formal appraisal needs intervention effectiveness evidence, discounting, distributional impacts and alternatives. No risk reduction is inferred from radar.</p></div>`;
  } else if(role==="engineer") {
    cards=`<div class="decision-card"><h4>Engineering interpretation</h4><p>${decisionInterpretation(x)}</p><ul><li>Confirm movement with independent survey / GNSS observations.</li><li>Review radar geometry, coherence, atmospheric effects and quality masks.</li><li>Undertake geotechnical investigation before selecting foundation or ground-improvement measures.</li><li>Design only after loads, soil profile, groundwater and applicable codes are established.</li></ul></div>
    <div class="decision-card"><h4>Draft investigation scope</h4><table class="decision-compare"><tr><td>Study area assumption</td><td>${x.engineering.areaHa} ha</td></tr><tr><td>Initial borehole planning allowance</td><td>${x.engineering.boreholes}</td></tr><tr><td>Target depth assumption</td><td>${x.engineering.depthM} m</td></tr><tr><td>Survey grid spacing</td><td>${x.engineering.spacingM} m</td></tr></table><p>These are user-editable scoping assumptions, not a geotechnical design or a prescribed borehole layout.</p></div>`;
  } else {
    const copy={
      utility:["Asset inspection plan","Overlay actual utility asset records before dispatch. Prioritize records intersecting validated observation footprints; inspect leaks, joints, valves and drainage where field evidence supports it."],
      emergency:["Preparedness plan","Use official hazard feeds and local emergency protocols. This prototype does not issue warnings, predict disasters or replace an incident command authority."],
      land:["Land management plan","Compare soil moisture, rainfall history, land cover and field observations. Test drainage and irrigation scenarios with local agronomic advice."],
      resident:["Community explanation","Satellite measurements cover areas, not necessarily individual homes. Do not infer that a specific property is unsafe from this prototype. Seek local professional assessment."],
      scientist:["Reproducibility plan","Preserve source granules, product maturity, processing parameters, quality masks, coordinate reference systems and independent holdout measurements."]
    }[role] || ["Decision plan","Review the source evidence and obtain professional approval."];
    cards=`<div class="decision-card"><h4>${copy[0]}</h4><p>${copy[1]}</p><p>${decisionInterpretation(x)}</p></div><div class="decision-card"><h4>Next steps</h4><ul><li>Confirm coverage and source provenance.</li><li>Match the spatial result to authoritative local asset or land records.</li><li>Assign a responsible reviewer and field verification task.</li><li>Record outcomes and compare with subsequent observations.</li></ul></div>`;
  }
  const evidenceStatus=o.unresolved?"UNRESOLVED CELL · NO SITE-SPECIFIC ACTION":"SYNTHETIC FIXTURE · ILLUSTRATIVE ONLY";
  d$("decisionResults").innerHTML=`<div class="decision-metrics"><div class="decision-metric"><strong>${dformat(o.scenarioEndMm,2)} mm</strong><span>Scenario response · model output</span></div><div class="decision-metric"><strong>${dformat(o.deltaMm,2)} mm</strong><span>Difference from baseline</span></div><div class="decision-metric"><strong>${o.uncertaintyHalfWidth90mm===null?"—": "±"+dformat(o.uncertaintyHalfWidth90mm,2)+" mm"}</strong><span>Fixture uncertainty half-width · 90%</span></div></div>
  <div class="decision-card"><div class="decision-status">${evidenceStatus}</div><h4>What is happening at ${coord}</h4><p>${decisionInterpretation(x)}</p><p>Source study: ${x.source}. Grid cell: ${loc.i+1}, ${loc.j+1}. Selected coordinate inside study footprint: ${loc.insideStudy?"yes":"no"}.</p></div>${cards}`;
}
function buildDecisionFiles(x) {
  const role=x.role, loc=x.location, lat=Number.isFinite(loc.lat)?loc.lat:0, lon=Number.isFinite(loc.lon)?loc.lon:0;
  const slug=(loc.name||"swell-site").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");
  const files=[];
  const add=(name,mime,content,description)=>files.push({name,mime,content,description});
  const reportTitle={engineer:"Geotechnical investigation brief",planner:"Municipal resilience and economic options report",utility:"Infrastructure inspection work package",emergency:"Preparedness and verification brief",land:"Land management assessment",resident:"Community location explainer",scientist:"Reproducibility and observation package"}[role];
  const summary=decisionInterpretation(x);
  const htmlReport=`<!doctype html><html><head><meta charset="utf-8"><title>${reportTitle}</title><style>body{font:15px/1.55 Arial;max-width:900px;margin:40px auto;padding:0 24px;color:#182632}h1,h2{color:#16465b}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd6dd;padding:8px;text-align:left}.warning{padding:14px;background:#fff1d9;border-left:4px solid #c78a35}</style></head><body><h1>SWELL · ${reportTitle}</h1><p>Generated ${x.created}</p><div class="warning"><b>Scientific status:</b> ${x.disclaimer}</div><h2>Location</h2><p>${loc.name}; ${Number.isFinite(lat)?lat.toFixed(6):"unknown"}, ${Number.isFinite(lon)?lon.toFixed(6):"unknown"}. Study grid ${loc.i+1}, ${loc.j+1}.</p><h2>Scenario inputs</h2><table>${Object.entries(x.inputs).map(([k,v])=>`<tr><th>${k}</th><td>${v}</td></tr>`).join("")}</table><h2>Model outputs</h2><table>${Object.entries(x.output).map(([k,v])=>`<tr><th>${k}</th><td>${v===null?"not available":v}</td></tr>`).join("")}</table><h2>Interpretation</h2><p>${summary}</p><h2>Required verification</h2><ul><li>Confirm actual source acquisition and product maturity.</li><li>Inspect quality masks, geolocation and native spatial resolution.</li><li>Validate against independent field or GNSS observations.</li><li>Obtain local professional review before operational use.</li></ul></body></html>`;
  add(`${slug}-${role}-report.html`,"text/html",htmlReport,"Readable report with assumptions, outputs and limitations.");
  add(`${slug}-scenario.json`,"application/json",JSON.stringify(x,null,2),"Machine-readable inputs, outputs and provenance status.");
  const csv=[["day","baseline_response_mm","scenario_response_mm"],...x.series.days.map((d,i)=>[d,x.series.baseline[i],x.series.scenario[i]])].map(r=>r.join(",")).join("\n");
  add(`${slug}-scenario-timeseries.csv`,"text/csv",csv,"Editable time-series export.");
  const d=0.001;
  const polygon=[[lon-d,lat-d],[lon+d,lat-d],[lon+d,lat+d],[lon-d,lat+d],[lon-d,lat-d]];
  const gj={type:"FeatureCollection",features:[{type:"Feature",properties:{name:"Selected location context buffer",status:"context-only geometry; not a risk boundary",source:x.source,synthetic_fixture:true},geometry:{type:"Polygon",coordinates:[polygon]}}]};
  add(`${slug}-location-context.geojson`,"application/geo+json",JSON.stringify(gj,null,2),"Spatial context geometry only; explicitly not a hazard or risk boundary.");
  if(role==="engineer") {
    const n=x.engineering.boreholes, area=Math.sqrt(x.engineering.areaHa*10000), rows=[["point_id","east_local_m","north_local_m","target_depth_m","purpose"],...Array.from({length:n},(_,k)=>[`BH-${String(k+1).padStart(2,"0")}`,((k%Math.ceil(Math.sqrt(n)))-((Math.ceil(Math.sqrt(n))-1)/2))*x.engineering.spacingM, (Math.floor(k/Math.ceil(Math.sqrt(n)))-((Math.ceil(Math.sqrt(n))-1)/2))*x.engineering.spacingM,x.engineering.depthM,"proposed investigation point; verify by survey and engineer"])].map(r=>r.join(",")).join("\n");
    add(`${slug}-borehole-planning-schedule.csv`,"text/csv",rows,"Draft borehole planning schedule in local ENU coordinates; not a set-out file.");
    const dxf=`0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n6\n999\nConceptual local ENU sketch. Origin ${lat}, ${lon}. Not for construction or survey set-out.\n0\nENDSEC\n0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n8\nSTUDY_AREA_CONCEPT\n90\n4\n70\n1\n10\n${-area/2}\n20\n${-area/2}\n10\n${area/2}\n20\n${-area/2}\n10\n${area/2}\n20\n${area/2}\n10\n${-area/2}\n20\n${area/2}\n${Array.from({length:n},(_,k)=>{const q=rows;const cols=Math.ceil(Math.sqrt(n));const xx=((k%cols)-((cols-1)/2))*x.engineering.spacingM,yy=(Math.floor(k/cols)-((cols-1)/2))*x.engineering.spacingM;return `0\\nCIRCLE\\n8\\nPROPOSED_BH_NOT_SET_OUT\\n10\\n${xx}\\n20\\n${yy}\\n30\\n0\\n40\\n1.5\\n0\\nTEXT\\n8\\nLABELS\\n10\\n${xx+2}\\n20\\n${yy+2}\\n30\\n0\\n40\\n1.5\\n1\\nBH-${String(k+1).padStart(2,"0")}\\n`;}).join("")}0\nENDSEC\n0\nEOF\n`;
    add(`${slug}-concept-investigation-layout.dxf`,"application/dxf",dxf,"Conceptual CAD exchange drawing in local ENU metres; not construction geometry.");
    const section=`<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="520" viewBox="0 0 1000 520"><rect width="1000" height="520" fill="#f7fafc"/><path d="M0 180 Q250 150 500 180 T1000 160 L1000 520 L0 520Z" fill="#c5a47b"/><path d="M0 290 Q300 250 600 300 T1000 270 L1000 520 L0 520Z" fill="#8f9e9e"/><path d="M0 390 Q300 350 600 395 T1000 380 L1000 520 L0 520Z" fill="#638aa0"/><path d="M0 180 Q250 150 500 180 T1000 160" fill="none" stroke="#354e5b" stroke-width="5"/><g fill="#253e50" font-family="Arial"><text x="30" y="40" font-size="24">Conceptual subsurface section — not site geology</text><text x="30" y="220" font-size="18">Near-surface soil · requires borehole confirmation</text><text x="30" y="330" font-size="18">Underlying stratum · conceptual only</text><text x="30" y="445" font-size="18">Groundwater zone · depth unknown unless measured</text><text x="30" y="490" font-size="14">Vertical scale not calibrated. Replace with surveyed geotechnical logs.</text></g></svg>`;
    add(`${slug}-concept-subsurface-section.svg`,"image/svg+xml",section,"Conceptual section diagram, clearly marked as uncalibrated.");
  }
  if(role==="planner") {
    const assets=x.planning.assets, value=x.planning.assetValueUSD, budget=x.planning.budgetUSD, loss=x.planning.annualLossUSD;
    const econ=[["planning_assumption","value","unit"],["assets_in_area",assets,"count"],["average_asset_value",value,"USD"],["aggregate_asset_value",assets*value,"USD"],["intervention_budget",budget,"USD"],["annual_disruption_loss_assumption",loss,"USD/year"],["five_year_undiscounted_loss_sensitivity",loss*5,"USD, undiscounted"],["budget_to_annual_loss_ratio",loss>0?budget/loss:"not calculable","years; not a payback forecast"]].map(r=>r.join(",")).join("\n");
    add(`${slug}-economic-scenario.csv`,"text/csv",econ,"Editable assumption-led economic sensitivity; not an audited cost-benefit analysis.");
    const plan=`# Municipal resilience options — ${loc.name}\n\n## Decision context\n${summary}\n\n## Options to appraise\n1. No-regrets monitoring and independent survey.\n2. Targeted drainage and water-network investigation.\n3. Development review overlay only after parcel-scale evidence and legal review.\n4. Capital intervention only after engineering feasibility and cost estimation.\n\n## Economic assumptions\n- Assets: ${assets}\n- Average asset value: ${money(value)}\n- Intervention budget: ${money(budget)}\n- Annual disruption loss assumption: ${money(loss)}\n- Five-year undiscounted loss sensitivity: ${money(loss*5)}\n\nThese are user inputs, not measured losses or proven benefits. Commission a formal appraisal with discounting, distributional impacts, uncertainty and alternatives.\n`;
    add(`${slug}-municipal-options-memo.md`,"text/markdown",plan,"Planning options memo with editable economic assumptions and appraisal caveats.");
  }
  if(role==="utility") add(`${slug}-inspection-work-orders.csv`,"text/csv","asset_id,inspection_type,priority,status,required_validation\n,field verification,review after asset join,draft,match to authoritative utility GIS\n","Draft template; no actual utility assets were supplied.");
  if(role==="emergency") add(`${slug}-preparedness-checklist.csv`,"text/csv","task,owner,status\nverify official hazard bulletin,incident duty officer,draft\nconfirm vulnerable facilities,local authority,draft\nfield-check critical assets,asset owner,draft\n","Preparedness checklist only; not a warning or CAP alert.");
  if(role==="scientist") add(`${slug}-reproducibility-record.json`,"application/json",JSON.stringify({source:x.source,model:x.model,inputs:x.inputs,outputs:x.output,validation:"not established by this synthetic fixture",required:"real granules, quality masks, GNSS/field holdout, versioned code"},null,2),"Reproducibility and validation checklist.");
  return files;
}
function renderDecisionFiles(files) {
  d$("decisionDeliverables").innerHTML=files.map((f,i)=>`<div class="decision-file"><div><b>${f.name}</b><small>${f.description}</small></div><button class="decision-download" data-dl="${i}">Download</button></div>`).join("");
  d$("decisionDeliverables").querySelectorAll("[data-dl]").forEach(btn=>btn.addEventListener("click",()=>downloadDecisionFile(files[Number(btn.dataset.dl)])));
}
function downloadDecisionFile(f) {
  const blob=new Blob([f.content],{type:f.mime+";charset=utf-8"}),url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download=f.name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
function runDecisionStudio() {
  try {
    if(!S) throw new Error("Study data is still loading.");
    const x=decisionScenario(); decisionLast=x; renderDecisionResults(x); renderDecisionFiles(buildDecisionFiles(x));
    const notice=d$("decisionDataNotice");
    if(notice) notice.textContent=`Loaded source: ${x.source}. This bundled study is a synthetic fixture; no real NISAR measurement is being represented as observed at this point.`;
  } catch(e) { decisionLast=null; d$("decisionResults").innerHTML=`<div class="decision-empty">Unable to run scenario: ${String(e.message||e)}</div>`; d$("decisionDeliverables").innerHTML=`<div class="decision-empty">No deliverables generated: a valid physical study dataset is required for this location.</div>`; }
}
["decisionRain","decisionDrain","decisionWater","decisionHorizon"].forEach(id=>d$(id)?.addEventListener("input",()=>{
  const map={decisionRain:["rainValue",v=>`${v} mm`],decisionDrain:["drainValue",v=>`${v}%`],decisionWater:["waterValue",v=>`${Number(v).toFixed(2)} m`],decisionHorizon:["horizonValue",v=>`${v} months`]};
  const [target,fmt]=map[id];d$(target).textContent=fmt(d$(id).value);
}));
d$("decisionRole")?.addEventListener("change",decisionRoleChanged);
d$("runDecision")?.addEventListener("click",runDecisionStudio);
d$("resetDecision")?.addEventListener("click",()=>{
  d$("decisionRain").value=120;d$("decisionDrain").value=50;d$("decisionWater").value=.3;d$("decisionHorizon").value=12;
  ["decisionRain","decisionDrain","decisionWater","decisionHorizon"].forEach(id=>d$(id).dispatchEvent(new Event("input")));
  runDecisionStudio();
});
d$("tabs")?.querySelector('[data-t="decisions"]')?.addEventListener("click",()=>{decisionRoleChanged();initDecisionTwin3D();if(!decisionLast)runDecisionStudio();});
if(d$("decisionRole")) decisionRoleChanged();



/* Three-dimensional conceptual section. It is deliberately labelled conceptual until real boreholes/DEM/asset geometry are loaded. */
let decision3D={ready:false,renderer:null,scene:null,camera:null,controls:null,objects:{}};
function initDecisionTwin3D(){
  const host=d$("decisionTwin3D");
  if(!host || decision3D.ready || !window.THREE) {
    if(host && !window.THREE) d$("twin3dStatus").textContent="3D library unavailable · use the 2D evidence view";
    return;
  }
  try {
    const T=window.THREE,scene=new T.Scene();scene.background=new T.Color(0x081522);
    const camera=new T.PerspectiveCamera(42,host.clientWidth/Math.max(1,host.clientHeight),.1,1000);
    camera.position.set(19,15,23);
    const renderer=new T.WebGLRenderer({antialias:true,alpha:false});renderer.setPixelRatio(Math.min(2,window.devicePixelRatio||1));renderer.setSize(host.clientWidth,host.clientHeight);host.appendChild(renderer.domElement);
    const controls=new T.OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.target.set(0,0,0);controls.minDistance=9;controls.maxDistance=65;
    scene.add(new T.HemisphereLight(0xb8d9e8,0x26313b,1.45));
    const key=new T.DirectionalLight(0xffffff,1.5);key.position.set(12,20,10);scene.add(key);
    const mat=(color,opacity=1)=>new T.MeshStandardMaterial({color,transparent:opacity<1,opacity,roughness:.88,metalness:0});
    const objects={};
    const strata=[
      {y:-.2,h:1.3,c:0x9b7958},{y:-1.45,h:1.2,c:0x777f78},{y:-2.75,h:1.4,c:0x627d91},{y:-4.2,h:1.5,c:0x526273}
    ];
    strata.forEach((s,k)=>{const mesh=new T.Mesh(new T.BoxGeometry(15,s.h,10),mat(s.c));mesh.position.set(0,s.y-s.h/2,0);scene.add(mesh);});
    const ground=new T.Mesh(new T.BoxGeometry(15,.18,10),mat(0x657d65));ground.position.y=.42;scene.add(ground);
    // Terrain surface grid, for visual orientation only.
    const grid=new T.GridHelper(15,15,0x9bb6c1,0x506879);grid.position.y=.53;scene.add(grid);
    const buildingGroup=new T.Group();
    const foundation=new T.Mesh(new T.BoxGeometry(3.8,.35,2.6),mat(0xb7c3c8));foundation.position.set(1.4,.72,.2);buildingGroup.add(foundation);
    const building=new T.Mesh(new T.BoxGeometry(3.5,2.6,2.3),mat(0xd5dce0));building.position.set(1.4,2.18,.2);buildingGroup.add(building);
    const roof=new T.Mesh(new T.BoxGeometry(3.7,.18,2.5),mat(0x6b8998));roof.position.set(1.4,3.5,.2);buildingGroup.add(roof);
    scene.add(buildingGroup);objects.building=buildingGroup;
    const water=new T.Mesh(new T.BoxGeometry(14,.035,9.5),new T.MeshStandardMaterial({color:0x3aa9d2,transparent:true,opacity:.48,roughness:.35,metalness:.1,side:T.DoubleSide}));water.position.set(0,-1.7,0);scene.add(water);objects.water=water;
    const boreGroup=new T.Group();
    for(let k=0;k<5;k++){
      const x=-5.2+(k%3)*5.2,z=-2.8+Math.floor(k/3)*5.2;
      const rod=new T.Mesh(new T.CylinderGeometry(.045,.045,4.3,8),mat(0xf1c17d));rod.position.set(x,-1.75,z);boreGroup.add(rod);
      const collar=new T.Mesh(new T.CylinderGeometry(.12,.12,.12,10),mat(0xf0a85e));collar.position.set(x,.62,z);boreGroup.add(collar);
    }
    scene.add(boreGroup);objects.bores=boreGroup;
    const deform=new T.Group();
    const arrow=new T.ArrowHelper(new T.Vector3(0,-1,0),new T.Vector3(-4,.8,0),2.1,0xf19c63,.65,.38);deform.add(arrow);
    const ring=new T.Mesh(new T.TorusGeometry(1.4,.035,8,48),new T.MeshBasicMaterial({color:0xf19c63}));ring.rotation.x=Math.PI/2;ring.position.set(-4,.58,0);deform.add(ring);
    scene.add(deform);objects.deform=deform;
    const axes=new T.AxesHelper(2.2);axes.position.set(-7,.55,-4.5);scene.add(axes);
    decision3D={ready:true,renderer,scene,camera,controls,objects};
    const resize=()=>{if(!host.clientWidth)return;camera.aspect=host.clientWidth/Math.max(1,host.clientHeight);camera.updateProjectionMatrix();renderer.setSize(host.clientWidth,host.clientHeight);};
    if(window.ResizeObserver)new ResizeObserver(resize).observe(host);else window.addEventListener("resize",resize);
    const animate=()=>{if(!decision3D.ready)return;requestAnimationFrame(animate);controls.update();renderer.render(scene,camera);};animate();
    ["Water","Bores","Building","Deform"].forEach((name)=>d$("twinShow"+name)?.addEventListener("change",e=>{const key={Water:"water",Bores:"bores",Building:"building",Deform:"deform"}[name];objects[key].visible=e.target.checked;}));
  } catch(e) {
    d$("twin3dStatus").textContent="3D renderer could not initialize in this browser; scientific data panels remain available.";
    console.warn("SWELL 3D view:",e);
  }
}


/* Optional real raster connection: TiTiler-served COG tiles rendered on the Cesium globe. */
let swellCogLayer=null;
d$("loadCogLayer")?.addEventListener("click",()=>{
  const endpoint=(d$("cogEndpoint")?.value||"").trim().replace(/\/+$/,"");
  const asset=(d$("cogAssetUrl")?.value||"").trim();
  const status=d$("cogLayerStatus");
  if(!endpoint||!asset){status.textContent="Enter both a TiTiler endpoint and a georeferenced COG URL.";return;}
  try {
    const url=`${endpoint}/cog/tiles/{z}/{x}/{y}?url=${encodeURIComponent(asset)}&rescale=-20,20&colormap_name=rdylbu&format=png`;
    const provider=new Cesium.UrlTemplateImageryProvider({url,tilingScheme:new Cesium.WebMercatorTilingScheme(),credit:"SWELL · TiTiler COG overlay"});
    const next=viewer.imageryLayers.addImageryProvider(provider);next.alpha=.82;
    if(swellCogLayer)viewer.imageryLayers.remove(swellCogLayer,true);
    swellCogLayer=next;status.textContent="Raster layer added. Check the globe for tile loading; values are stretched −20 to +20 in source units. Change rescaling in the URL if your product uses different units.";
  } catch(e){status.textContent=`Could not add COG layer: ${String(e.message||e)}`;}
});
d$("removeCogLayer")?.addEventListener("click",()=>{
  if(swellCogLayer){viewer.imageryLayers.remove(swellCogLayer,true);swellCogLayer=null;}
  if(d$("cogLayerStatus"))d$("cogLayerStatus").textContent="External COG overlay removed.";
});
