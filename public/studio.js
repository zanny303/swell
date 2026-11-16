/* SWELL Decision Studio. Reads data/site.json (written by `python -m swell.validate`).
   The map and the 3D cut-away are two views of the same per-cell model state.
   Painting on the map changes that state and both views redraw.
   Every number on screen comes from site.json or from the equations in model.js. */
const $ = id => document.getElementById(id), M = SwellModel;
const GIBS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi";
let imgDate = ""; // Let each NASA GIBS layer serve its own latest available default unless the user chooses a date.
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const f1 = v => (v >= 0 ? "+" : "") + v.toFixed(1), num = v => (v == null || Number.isNaN(v)) ? NaN : v;
const mean = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : NaN;

let S, n, state = "inferred", passK = 0, dayA = 30, H = 30, sel = null, tool = "select", step = "studio", role = "planner", sampleDemoEnabled = false;
let pWater, pDrain, pPave, C = null, lastField = null, quakes = [], liveOK = { usgs: null, gibs: null };
let decisionPinEntities = [], decisionPinsVisible = true, insightPinEntities = [], insightPinsVisible = true;
const G = { rainMm: 50, rainDays: 2, dryDays: 0, reduction: 0, pavedDelta: 0 };

/* ---------- colour ---------- */
const STOPS = [[0, [31, 63, 208]], [.25, [31, 195, 232]], [.5, [62, 207, 110]], [.75, [245, 214, 58]], [1, [229, 53, 43]]];
function ramp(t) { t = Math.max(0, Math.min(1, t)); for (let k = 1; k < STOPS.length; k++) if (t <= STOPS[k][0]) { const [a, ca] = STOPS[k - 1], [b, cb] = STOPS[k], u = (t - a) / (b - a); return ca.map((c, i) => Math.round(c + u * (cb[i] - c))); } return STOPS[4][1]; }
function range(field) { let m = 0; for (const r of field) for (const v of r) if (!Number.isNaN(v) && Math.abs(v) > m) m = Math.abs(v); return Math.max(2, Math.ceil(m / 5) * 5); }

/* ---------- Cesium: main map + mini globe ---------- */
Cesium.Ion.defaultAccessToken = undefined;
const natural = () => Cesium.ImageryLayer.fromProviderAsync(Cesium.SingleTileImageryProvider.fromUrl("assets/blue-marble.jpg", {credit:"NASA Blue Marble historical composite"}));
const vopts = { baseLayerPicker: false, geocoder: false, timeline: false, animation: false, homeButton: false, sceneModePicker: false, navigationHelpButton: false, fullscreenButton: false, infoBox: false, selectionIndicator: false };
const viewer = new Cesium.Viewer("globe", { ...vopts, baseLayer: natural() });
viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#16466b");
// Optional real 3D context. OSM buildings are extruded footprint geometry, not photorealistic textures.
let ionContext = { loaded:false, active:false, terrain:null, buildings:null, busy:false };
const ionButton = $("enable3D"), studioStatus = $("studioStatus");
if (ionButton) ionButton.addEventListener("click", async () => {
  if (ionContext.busy) return;
  if (ionContext.loaded) {
    ionContext.active = !ionContext.active;
    viewer.terrainProvider = ionContext.active ? ionContext.terrain : new Cesium.EllipsoidTerrainProvider();
    if (ionContext.buildings) ionContext.buildings.show = ionContext.active;
    ionButton.textContent = ionContext.active ? "3D context on · turn off" : "Load 3D terrain + buildings";
    if (studioStatus) studioStatus.textContent = ionContext.active ? "Cesium World Terrain + OSM 3D Buildings enabled (not photorealistic)." : "3D context hidden; analytical model unchanged.";
    return;
  }
  let token = "";
  try { token = localStorage.getItem("swell.cesiumIonToken.v1") || ""; } catch (_) {}
  if (!token) { if (studioStatus) studioStatus.textContent = "Add a restricted, public read-only Cesium ion token in Connections, then retry."; return; }
  ionContext.busy = true; ionButton.disabled = true; ionButton.textContent = "Loading 3D context…";
  try {
    Cesium.Ion.defaultAccessToken = token;
    ionContext.terrain = await Cesium.createWorldTerrainAsync();
    viewer.terrainProvider = ionContext.terrain;
    try { ionContext.buildings = await Cesium.createOsmBuildingsAsync(); viewer.scene.primitives.add(ionContext.buildings); }
    catch (e) { if (studioStatus) studioStatus.textContent = "Terrain connected; OSM buildings unavailable: " + e.message; }
    ionContext.loaded = true; ionContext.active = true;
    ionButton.textContent = "3D context on · turn off";
    if (studioStatus) studioStatus.textContent = "Cesium World Terrain + OSM 3D Buildings loaded. Building geometry is not photorealistic and is not a surveyed asset inventory.";
  } catch (e) {
    Cesium.Ion.defaultAccessToken = undefined;
    ionContext = { loaded:false, active:false, terrain:null, buildings:null, busy:false };
    ionButton.textContent = "Load 3D terrain + buildings";
    if (studioStatus) studioStatus.textContent = "3D connection failed: " + e.message + " · Check token restrictions in Connections.";
  } finally { ionContext.busy = false; ionButton.disabled = false; }
});
viewer.scene.skyAtmosphere.show = true;
const gibs = (layer, time, fmt = "image/png") => new Cesium.WebMapServiceImageryProvider({ url: GIBS, layers: layer, parameters: { transparent: true, format: fmt, ...(time ? { time } : {}) }, tilingScheme: new Cesium.GeographicTilingScheme(), maximumLevel: /SMAP|IMERG/.test(layer) ? 4 : /HLS/.test(layer) ? 10 : /BlueMarble/.test(layer) ? 5 : 8, credit: "NASA GIBS / NASA Earthdata" });
function addLayer(provider, show, alpha) { const l = viewer.imageryLayers.addImageryProvider(provider); l.show = show; l.alpha = alpha == null ? 1 : alpha; provider.errorEvent.addEventListener(() => { liveOK.gibs = false; liveTag(); }); return l; }
const L = {};
L.blue = addLayer(gibs("BlueMarble_ShadedRelief_Bathymetry", null, "image/jpeg"), true);
L.today = addLayer(gibs("VIIRS_SNPP_CorrectedReflectance_TrueColor", imgDate), true);
L.hls = addLayer(gibs("HLS_S30_Nadir_BRDF_Adjusted_Reflectance", imgDate), false);
L.sharp = null;
Cesium.ArcGisMapServerImageryProvider.fromUrl("https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer").then(p => { L.sharp = viewer.imageryLayers.addImageryProvider(p, 4); L.sharp.show = false; sharpCheck(); }).catch(() => { });
L.rain = addLayer(gibs("IMERG_Precipitation_Rate", imgDate), false, .6);
L.smap = addLayer(gibs("SMAP_L4_Analyzed_Surface_Soil_Moisture", imgDate), false, .6);
L.fire = addLayer(gibs("VIIRS_SNPP_Thermal_Anomalies_375m_All", imgDate), false);
const wantSharp = () => { const c = document.querySelector('[data-lay=sharp]'); return !c || c.checked; };
function sharpCheck() { if (L.sharp) L.sharp.show = wantSharp() && viewer.camera.positionCartographic.height < 6e5; }
viewer.camera.changed.addEventListener(sharpCheck); viewer.camera.percentageChanged = .05;

const mini = new Cesium.Viewer("mini", { ...vopts, baseLayer: natural(), requestRenderMode: true, skyBox: false, skyAtmosphere: false });
mini.scene.backgroundColor = Cesium.Color.fromCssColorString("#02060b"); mini.scene.screenSpaceCameraController.enableInputs = false;
mini.cesiumWidget.creditContainer.style.display = "none";
$("mini").addEventListener("click", () => flyEarth());

const overlay = viewer.entities.add({ rectangle: { coordinates: Cesium.Rectangle.fromDegrees(0, 0, 1, 1), material: Cesium.Color.TRANSPARENT, height: 0 } });
const outline = viewer.entities.add({ polyline: { positions: [], width: 2, material: Cesium.Color.fromCssColorString("#7fe3f2"), clampToGround: false } });
overlay.show = outline.show = false; // Hide any sample layer until provenance is known.
const selEnt = viewer.entities.add({ rectangle: { coordinates: Cesium.Rectangle.fromDegrees(0, 0, 1, 1), fill: false, outline: true, outlineColor: Cesium.Color.WHITE, outlineWidth: 3, height: 5 }, show: false });
let siteMarker=null, miniSiteMarker=null;
const quakeDS = new Cesium.CustomDataSource("quakes"); viewer.dataSources.add(quakeDS);
const oc = document.createElement("canvas"); oc.width = oc.height = 480; const octx = oc.getContext("2d");
const tiny = document.createElement("canvas");

function flySite(dur) { const [w, s, e, nn] = S.bbox; viewer.camera.flyTo({ destination: Cesium.Rectangle.fromDegrees(w - .12, s - .16, e + .12, nn + .06), duration: dur == null ? 1.6 : dur }); }
function flyEarth() { const [w, s, e, nn] = S.bbox; viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees((w + e) / 2, (s + nn) / 2, 1.5e7), duration: 1.6 }); }
const zoom = f => { const h = viewer.camera.positionCartographic.height; f < 1 ? viewer.camera.zoomIn(h * (1 - f)) : viewer.camera.zoomOut(h * (f - 1)); };
$("zin").onclick = () => zoom(.5); $("zout").onclick = () => zoom(2); $("toSite").onclick = () => flySite(); $("toEarth").onclick = flyEarth;
$("north").onclick = () => { const c = viewer.camera.positionCartographic; viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromRadians(c.longitude, c.latitude, c.height), orientation: { heading: 0, pitch: -Math.PI / 2, roll: 0 }, duration: .6 }); };

/* ---------- model: per-cell forecast and scenario ---------- */
let weatherForcing = null;
let engine = "legacy", hydroC = null, hydroCache = new Map(), hydroCacheKey = "";
function compute() {
  const p = S.params, nNow = S.rain.length, now = nNow - 1, base = S.rain.concat(new Array(H).fill(0));
  const wBase = M.wetness(base), s0 = M.unitResponse(wBase, p.T, p.tau), memo = new Map();
  const series = (extra, red) => { const key = extra + "|" + red; if (memo.has(key)) return memo.get(key);
    const r = base.slice(), st = nNow + G.dryDays, rd = Math.max(1, G.rainDays), tot = G.rainMm + extra;
    for (let k = 0; k < rd && st + k < r.length; k++) r[st + k] += tot / rd;
    for (let t = nNow; t < r.length; t++) r[t] *= 1 - red;
    const w = M.wetness(r), out = { w, s: M.unitResponse(w, p.T, p.tau) }; memo.set(key, out); return out; };
  const g0 = [], g1 = [], ser = [];
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { const c = i * n + j, lep = S.lep[i][j], pv = S.paved[i][j];
    const red = Math.round((1 - (1 - G.reduction) * (1 - pDrain[c])) * 100) / 100, pv1 = Math.max(0, Math.min(1, pv + G.pavedDelta + pPave[c]));
    g0.push(p.alpha * lep * (1 - p.b * pv)); g1.push(p.alpha * lep * (1 - p.b * pv1)); ser.push(series(pWater[c], red)); }
  C = { now, s0, wBase, g0, g1, ser, wScen: series(0, Math.round(G.reduction * 100) / 100).w };
  hydroC = null;
  if (engine === "hydro") {
    const key0=JSON.stringify([H,G,$("za").value,$("gwRise").value,S.name,weatherForcing]);if(key0!==hydroCacheKey){hydroCache.clear();hydroCacheKey=key0;}const cache=hydroCache; if(cache.size>n*n*2)cache.clear(); hydroC = [];
    for(let i=0;i<n;i++)for(let j=0;j<n;j++){
      const c=i*n+j, opts={H,depth:Math.max(.5,Math.min(10,+$("za").value||3)),futureRain:weatherForcing ? weatherForcing.daily.map(x=>x.rain_mm) : undefined,rainMm:G.rainMm+pWater[c],rainDays:Math.max(1,Math.round(G.rainDays)),dryDays:Math.max(0,Math.round(G.dryDays)),drainage:1-(1-G.reduction)*(1-pDrain[c]),paving:G.pavedDelta+pPave[c],groundwaterRise:Math.max(0,Math.min(5,+$("gwRise").value||0))};
      const lep=Number(S.lep[i][j]),pv=Number(S.paved[i][j]); const key=JSON.stringify([lep,pv,opts]);
      if(!cache.has(key))cache.set(key,SwellHydro.compare(S.rain,lep,pv,opts)); hydroC.push(cache.get(key));
    }
  }
}
function predicted(c,d,scenario){ if(hydroC){const a=hydroC[c],v=scenario?a.scen:a.base;return v.motion[a.now+d]-v.motion[a.now];} return scenario?C.g1[c]*(C.ser[c].s[C.now+d]-C.s0[C.now]):C.g0[c]*(C.s0[C.now+d]-C.s0[C.now]); }
const masked = (i, j) => S.unresolved[i][j] === 1;
function field(st, k, d) {
  const out = [];
  for (let i = 0; i < n; i++) { const row = []; for (let j = 0; j < n; j++) { const c = i * n + j; let v;
    if (st === "observed") v = num(S.observed_los[k][i][j]);
    else if (masked(i, j)) v = NaN;
    else if (st === "inferred") v = num(S.inferred_motion[k][i][j]);
    else if (st === "forecast") v = predicted(c,d,false);
    else v = predicted(c,d,true);
    row.push(v); } out.push(row); }
  return out;
}
function wetAt() { if (state === "observed" || state === "inferred") return S.wetness[Math.min(S.wetness.length - 1, S.pass_days[passK])]; if(hydroC){const cs=sel?[sel.i*n+sel.j]:focusCells().cells.map(([i,j])=>i*n+j);return mean(cs.map(c=>{const a=hydroC[c];return (state==="forecast"?a.base:a.scen).wet[a.now+dayA]}))||0;} return (state === "forecast" ? C.wBase : C.wScen)[C.now + dayA]; }
const zoneOf = (i, j) => `Z${Math.floor(i / 8)}${Math.floor(j / 8)}`;
function focusCells() {
  const painted = []; for (let c = 0; c < n * n; c++) if ((pWater[c] || pDrain[c] || pPave[c]) && !masked(Math.floor(c / n), c % n)) painted.push([Math.floor(c / n), c % n]);
  if (painted.length) return { cells: painted, label: `the ${painted.length} cells you changed on the map` };
  if (sel) { const zi = Math.floor(sel.i / 8) * 8, zj = Math.floor(sel.j / 8) * 8, cs = []; for (let i = zi; i < Math.min(n, zi + 8); i++) for (let j = zj; j < Math.min(n, zj + 8); j++) if (!masked(i, j)) cs.push([i, j]); if (cs.length) return { cells: cs, label: `zone ${zoneOf(sel.i, sel.j)} around the cell you clicked` }; }
  const cs = []; for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if (!masked(i, j) && !S.reference[i][j] && !S.control[i][j]) cs.push([i, j]);
  return { cells: cs, label: "all resolved clay ground in the study site (click a cell or paint to focus)" };
}
function curves() { const F = focusCells(), past = [], base = [], scen = [];
  const last = S.pass_days.length - 1, ref = mean(F.cells.map(([i, j]) => num(S.inferred_motion[last][i][j])).filter(v => !Number.isNaN(v)));
  S.pass_days.forEach((d, k) => { const m = mean(F.cells.map(([i, j]) => num(S.inferred_motion[k][i][j])).filter(v => !Number.isNaN(v))); past.push([d - S.pass_days[last], m - ref]); });
  for (let d = 0; d <= H; d++) { base.push(mean(F.cells.map(([i, j]) => predicted(i*n+j,d,false)))); scen.push(mean(F.cells.map(([i, j]) => { const c = i * n + j; return predicted(c,d,true); }))); }
  return { F, past, base, scen };
}

/* ---------- drawing: map overlay, legend, pass strip ---------- */
const UNIT = { observed: "Observed radar change, line of sight (mm)", inferred: "Estimated vertical movement (mm)", forecast: "Forecast change from today (mm)", scenario: "Scenario change from today (mm)" };
function drawOverlay() {
  const fld = field(state, passK, dayA), V = range(fld); lastField = { fld, V };
  tiny.width = tiny.height = n; const t = tiny.getContext("2d"), im = t.createImageData(n, n);
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { const v = fld[i][j], o = 4 * (i * n + j); if (Number.isNaN(v)) { im.data[o + 3] = 0; continue; } const c = ramp(.5 + v / (2 * V)); im.data[o] = c[0]; im.data[o + 1] = c[1]; im.data[o + 2] = c[2]; im.data[o + 3] = 205; }
  t.putImageData(im, 0, 0); octx.clearRect(0, 0, 480, 480); octx.imageSmoothingEnabled = true; octx.drawImage(tiny, 0, 0, 480, 480);
  const px = 480 / n; octx.lineWidth = 2;
  for (let c = 0; c < n * n; c++) { const i = Math.floor(c / n), j = c % n; const col = pWater[c] ? "#4aa3ff" : pDrain[c] ? "#3ecf8e" : pPave[c] ? "#d0d6dc" : null; if (!col) continue; octx.strokeStyle = col; octx.strokeRect(j * px + 1.5, i * px + 1.5, px - 3, px - 3); }
  overlay.rectangle.material = new Cesium.ImageMaterialProperty({ image: oc.toDataURL(), transparent: true });
  $("legT").textContent = UNIT[state]; $("legA").textContent = "−" + V; $("legB").textContent = "+" + V;
  $("legN").textContent = state === "observed" ? "includes the soil-moisture artifact" : "blank = unresolved";
  drawTwin(fld, V); stamp();
}
(function () { const g = $("legC").getContext("2d"); for (let x = 0; x < 120; x++) { g.fillStyle = `rgb(${ramp(x / 119)})`; g.fillRect(x, 0, 1, 10); } })();
function stamp() {
  const last = S.pass_days[S.pass_days.length - 1];
  $("when").textContent = (state === "observed" || state === "inferred") ? `pass ${passK + 1} of ${S.pass_days.length} · day ${S.pass_days[passK]}` : weatherForcing && hydroC ? `${weatherForcing.daily[dayA-1]?.date||"outside forecast"} UTC · conditional scenario` : `day ${last + dayA} · ${dayA} days ahead`;
  $("dayO").textContent = "+" + dayA + " d";
  document.querySelectorAll("#states button").forEach(b => b.classList.toggle("on", b.dataset.s === state));
  const fut = state === "forecast" || state === "scenario"; $("passes").style.display = fut ? "none" : "flex"; $("ahead").style.display = fut ? "flex" : "none";
  document.querySelectorAll("#passes figure").forEach((f, k) => f.classList.toggle("on", k === passK));
}
function buildPasses() {
  const V = range(S.inferred_motion.flat().map(r => r.map(num)));
  $("passes").innerHTML = ""; S.pass_days.forEach((d, k) => { const f = document.createElement("figure"), c = document.createElement("canvas"); c.width = c.height = n; const g = c.getContext("2d"), im = g.createImageData(n, n);
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { const v = num(S.inferred_motion[k][i][j]), o = 4 * (i * n + j); if (Number.isNaN(v) || masked(i, j)) continue; const col = ramp(.5 + v / (2 * V)); im.data[o] = col[0]; im.data[o + 1] = col[1]; im.data[o + 2] = col[2]; im.data[o + 3] = 255; }
    g.putImageData(im, 0, 0); f.appendChild(c); f.appendChild(document.createTextNode("day " + d)); f.title = "Radar pass on day " + d; f.onclick = () => { passK = k; if (state !== "observed") state = "inferred"; redraw(); }; $("passes").appendChild(f); });
}

/* ---------- three.js cut-away twin ---------- */
let T3 = null;
function initTwin() {
  if (typeof THREE === "undefined") { $("twin").innerHTML = '<div style="padding:60px 16px" class="mute">3D library did not load (needs internet for the three.js CDN).</div>'; return; }
  const el = $("twin"), r = new THREE.WebGLRenderer({ antialias: true, alpha: true }); r.setPixelRatio(Math.min(2, devicePixelRatio)); el.appendChild(r.domElement);
  const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(38, 1, .1, 200); cam.position.set(12.5, 9, 16.5);
  const ctl = new THREE.OrbitControls(cam, r.domElement); ctl.target.set(0, -1, 0); ctl.enableDamping = true; ctl.maxPolarAngle = 1.5; ctl.minDistance = 6; ctl.maxDistance = 40;
  scene.add(new THREE.HemisphereLight(0xdfefff, 0x23303c, .95)); const dl = new THREE.DirectionalLight(0xffffff, .75); dl.position.set(6, 12, 4); scene.add(dl);
  const top = new THREE.Mesh(new THREE.PlaneGeometry(10, 10, n - 1, n - 1).rotateX(-Math.PI / 2), new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide }));
  top.geometry.setAttribute("color", new THREE.BufferAttribute(new Float32Array(n * n * 3), 3)); scene.add(top);
  const walls = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide })); scene.add(walls);
  const slabs = new THREE.InstancedMesh(new THREE.BoxGeometry(10 / n * .6, 1, 10 / n * .6), new THREE.MeshLambertMaterial({ color: 0x8e9aa6 }), n * n); scene.add(slabs);
  const pin = new THREE.Mesh(new THREE.CylinderGeometry(.03, .03, 3, 8), new THREE.MeshBasicMaterial({ color: 0xffffff })); pin.visible = false; scene.add(pin);
  const marks = new THREE.InstancedMesh(new THREE.BoxGeometry(10 / n, .04, 10 / n), new THREE.MeshBasicMaterial({ color: 0xc58af9, transparent: true, opacity: .75 }), n * n); scene.add(marks);
  T3 = { r, scene, cam, ctl, top, walls, slabs, pin, marks, el };
  const size = () => { const w = el.clientWidth, h = el.clientHeight; if (!w || !h) return; r.setSize(w, h, false); r.domElement.style.width = w + "px"; r.domElement.style.height = h + "px"; cam.aspect = w / h; cam.updateProjectionMatrix(); };
  new ResizeObserver(size).observe(el); size();
  (function loop() { requestAnimationFrame(loop); if (el.clientWidth) { ctl.update(); r.render(scene, cam); } })();
}
const mix = (a, b, u) => a.map((x, k) => x + u * (b[k] - x));
function drawTwin(fld, V) {
  if (!T3) return;
  const ex = +$("exag").value, sc = ex * .22 / V, pos = T3.top.geometry.attributes.position, col = T3.top.geometry.attributes.color, hgt = new Float32Array(n * n);
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { const c = i * n + j, v = fld[i][j], nan = Number.isNaN(v); hgt[c] = nan ? 0 : v * sc; pos.setY(c, hgt[c]); const rgb = nan ? [70, 82, 94] : ramp(.5 + v / (2 * V)); col.setXYZ(c, rgb[0] / 255, rgb[1] / 255, rgb[2] / 255); }
  pos.needsUpdate = col.needsUpdate = true; T3.top.geometry.computeVertexNormals();
  // strata on the four cut faces: topsoil, the active clay zone (your input depth; colour follows the twin's wetness), stable ground
  const za = Math.max(.5, +$("za").value || 3), w = wetAt(), soil = [.36, .27, .2], clay = mix([.76, .55, .34], [.45, .2, .14], w), deep = [.3, .35, .4], aq = [.13, .32, .5];
  const d1 = .16, d2 = d1 + za * .3, d3 = Math.max(d2 + .5, 2.6), base = -(d3 + .5), P = [], Cc = [];
  const X = j => -5 + 10 * j / (n - 1), Z = i => -5 + 10 * i / (n - 1);
  const quad = (a, b, y0a, y1a, y0b, y1b, c0, c1) => { P.push(a[0], y0a, a[1], b[0], y0b, b[1], b[0], y1b, b[1], a[0], y0a, a[1], b[0], y1b, b[1], a[0], y1a, a[1]); [c0, c0, c1, c0, c1, c1].forEach(c => Cc.push(...c)); };
  const edge = pts => { for (let k = 0; k < pts.length - 1; k++) { const [a, ha] = pts[k], [b, hb] = pts[k + 1];
    quad(a, b, ha, ha - d1, hb, hb - d1, soil, soil); quad(a, b, ha - d1, ha - d2, hb - d1, hb - d2, clay, mix(clay, [.3, .14, .1], .35)); quad(a, b, ha - d2, -d3, hb - d2, -d3, deep, deep); quad(a, b, -d3, base, -d3, base, aq, mix(aq, [0, 0, 0], .4)); } };
  const idx = Array.from({ length: n }, (_, k) => k);
  edge(idx.map(j => [[X(j), Z(0)], hgt[j]])); edge(idx.map(j => [[X(j), Z(n - 1)], hgt[(n - 1) * n + j]])); edge(idx.map(i => [[X(0), Z(i)], hgt[i * n]])); edge(idx.map(i => [[X(n - 1), Z(i)], hgt[i * n + n - 1]]));
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3)); g.setAttribute("color", new THREE.Float32BufferAttribute(Cc, 3)); g.computeVertexNormals(); T3.walls.geometry.dispose(); T3.walls.geometry = g;
  const m4 = new THREE.Matrix4(); let k = 0, q = 0;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { const c = i * n + j, pv = Math.max(0, Math.min(1, S.paved[i][j] + (state === "scenario" ? G.pavedDelta + pPave[c] : 0)));
    if (pv > .7) { const h = .05 + .35 * (pv - .7); m4.makeScale(1, h, 1).setPosition(X(j), hgt[c] + h / 2, Z(i)); T3.slabs.setMatrixAt(k++, m4); }
    if (pWater[c] || pDrain[c] || pPave[c]) { m4.makeScale(1, 1, 1).setPosition(X(j), hgt[c] + .03, Z(i)); T3.marks.setMatrixAt(q++, m4); } }
  T3.slabs.count = k; T3.slabs.instanceMatrix.needsUpdate = true; T3.marks.count = q; T3.marks.instanceMatrix.needsUpdate = true;
  if (sel) { T3.pin.visible = true; T3.pin.position.set(X(sel.j), hgt[sel.i * n + sel.j] + 1.5, Z(sel.i)); } else T3.pin.visible = false;
  const [w0, s0, e0] = S.bbox, widthMm = (e0 - w0) * 111320 * Math.cos((s0 + S.bbox[3]) / 2 * Math.PI / 180) * 1000, exReal = sc / (10 / widthMm);
  const hex = c => `rgb(${c.map(x => Math.round(x * 255))})`;
  $("strata").innerHTML = `<div><i style="background:${hex(soil)}"></i>Surface and topsoil</div><div><i style="background:${hex(clay)}"></i>Active clay zone, 0–${za} m <span class="mute">(your input)</span></div><div><i style="background:${hex(deep)}"></i>Ground below the active zone</div><div><i style="background:#8e9aa6"></i>Mostly paved cells (not buildings)</div><div><i style="background:#c58af9"></i>Cells you changed</div><div class="mute">Clay colour: twin wetness ${(100 * w).toFixed(0)} % (pale = dry, dark = wet)</div>`;
  $("twinNote").innerHTML = `Drag to turn · scroll to zoom · height stretched about ${Math.round(exReal).toLocaleString()}× · layer depths illustrate your input, not a boring`;
}

/* ---------- chart ---------- */
function drawChart() {
  const cv = $("chart"), g = cv.getContext("2d"), Wd = cv.width, Hh = cv.height, { F, past, base, scen } = curves(), rm = hydroC ? 0 : S.params.rmse_train;
  $("focusLbl").textContent = "Average over " + F.label + (hydroC ? ". Water-balance screening; no calibrated forecast interval. Parameter sensitivity is not a probability band." : ". Training RMSE reference: " + rm.toFixed(1) + " mm; this is not a calibrated forecast interval.");
  g.clearRect(0, 0, Wd, Hh); const x0 = Math.min(-60, past[0][0]), x1 = H, ys = past.map(p => p[1]).concat(base, scen).filter(v => !Number.isNaN(v)), y0 = Math.min(...ys) - rm - 1, y1 = Math.max(...ys) + rm + 1;
  const L0 = 52, R = 14, Tp = 12, B = 34, X = x => L0 + (x - x0) / (x1 - x0) * (Wd - L0 - R), Y = y => Tp + (y1 - y) / (y1 - y0) * (Hh - Tp - B);
  g.font = "20px system-ui"; g.fillStyle = "#8fa5b8"; g.strokeStyle = "#1c3348"; g.lineWidth = 1;
  const stepY = Math.max(1, Math.ceil((y1 - y0) / 5)); for (let y = Math.ceil(y0 / stepY) * stepY; y <= y1; y += stepY) { g.beginPath(); g.moveTo(L0, Y(y)); g.lineTo(Wd - R, Y(y)); g.stroke(); g.fillText(y, 8, Y(y) + 7); }
  [[-60, "−60 d"], [-30, "−30 d"], [0, "today"], [Math.round(H / 2), "+" + Math.round(H / 2) + " d"], [H, "+" + H + " d"]].forEach(([x, t]) => { if (x >= x0) g.fillText(t, X(x) - (x === H ? 52 : 18), Hh - 8); });
  g.strokeStyle = "#5d7386"; g.setLineDash([5, 5]); g.beginPath(); g.moveTo(X(0), Tp); g.lineTo(X(0), Hh - B); g.stroke(); g.setLineDash([]);
  const line = (pts, col, w) => { g.strokeStyle = col; g.lineWidth = w; g.beginPath(); pts.forEach(([x, y], k) => k ? g.lineTo(X(x), Y(y)) : g.moveTo(X(x), Y(y))); g.stroke(); };
  // Training residual RMSE is a fit diagnostic, not a calibrated forecast interval.
  // Do not draw it as a probability/confidence band. The hydro engine also has
  // no calibrated predictive interval; its parameter range is shown separately.

  const pp = past.filter(p => p[0] >= x0 && !Number.isNaN(p[1])); line(pp, "#4aa3ff", 3); g.fillStyle = "#4aa3ff"; pp.forEach(([x, y]) => { g.beginPath(); g.arc(X(x), Y(y), 5, 0, 7); g.fill(); });
  line(base.map((v, d) => [d, v]), "#f2a33a", 3); line(scen.map((v, d) => [d, v]), "#c58af9", 4);
  if (state === "forecast" || state === "scenario") { g.strokeStyle = "#fff"; g.lineWidth = 1; g.beginPath(); g.moveTo(X(dayA), Tp); g.lineTo(X(dayA), Hh - B); g.stroke(); }
  return { F, past, base, scen };
}

/* ---------- findings ---------- */
function findings(cv) {
  const { F, past, base, scen } = cv, last = S.pass_days.length - 1, span = S.pass_days[last] - S.pass_days[0];
  const chg = -past[0][1], art = mean(F.cells.map(([i, j]) => Math.abs(num(S.artifact[last][i][j]))).filter(v => !Number.isNaN(v)));
  const unres = S.zones.filter(z => z.status !== "ok").length, pass = S.tests.filter(t => t.passed).length, kept = S.contracts.filter(c => c.arrival === "kept").length, contra = S.contracts.filter(c => c.arrival === "contradicted").length;
  const dB = base[H], dS = scen[H], diff = dS - dB, out = [];
  out.push(`Over ${span} days the estimated ground level in this area changed by <b>${f1(chg)} mm</b> (vertical, assuming no sideways motion).`);
  out.push(`About <b>${art.toFixed(1)} mm</b> of the raw radar signal at the last pass was the soil-moisture artifact. SWELL removed it before estimating movement.`);
  out.push(`${weatherForcing && hydroC ? "With AIFS weather forcing the screening model estimates" : "With no further rain the twin estimates"} <b>${f1(dB)} mm</b> in ${H} days ${hydroC ? "(uncalibrated screening; no calibrated interval)." : "(training RMSE reference " + S.params.rmse_train.toFixed(1) + " mm; not a predictive interval)."}`);
  out.push(Math.abs(diff) < .05 ? `Your scenario is the same as the baseline so far. Type a request, move a slider, or paint on the map.` : `Your scenario gives <b>${f1(dS)} mm</b>: ${f1(diff)} mm against the baseline.`);
  out.push(`${unres} of ${S.zones.length} zones are unresolved and need another pass, not a decision.`);
  out.push(`${pass} of ${S.tests.length} pre-set tests pass. Past promises: ${kept} kept, ${contra} contradicted.`);
  $("findings").innerHTML = out.map(t => `<li>${t}</li>`).join("");
}

/* ---------- roles, plans, files ---------- */
const FILES = { engineer_investigation_inputs_csv: ["engineer_investigation_inputs.csv", "Zone table for a geotechnical investigation"], engineer_json: ["engineer_investigation_inputs.json", "Same table with source, hash, approval field"], observe: ["observe_next_priority.csv", "Where one more measurement helps most"], planner: ["planner_zones.geojson", "Zone polygons for GIS, every number attached"], utility: ["utility_inspection_candidates.csv", "Inspection boxes; join with your asset IDs"], cap: ["emergency_draft_alert.cap.xml", "CAP 1.2 draft, status Draft, not issued"], land: ["land_manager_open_ground.csv", "Open ground with large moisture-driven movement"], resident: ["resident_summary.txt", "Plain-language summary"], tray: ["tray_experiment_log_template.csv", "Log sheet for the clay tray experiment"] };
const ROLES = {
  engineer: ["👷", "Engineer", "Where to investigate first, and what movement range to test for.", ["engineer_investigation_inputs_csv", "engineer_json", "observe"],
    z => [`Send the first borings and lab swell tests to zone ${z.zone}: modelled seasonal movement estimate ${z.est_seasonal_vertical_mm} mm; model spread ± ${z.uncertainty_mm} mm (not a validated confidence interval).`, `Check differential movement: the modelled spread inside that zone is ${z.est_within_zone_spread_mm} mm.`, "Use the structure screen below for an upper bound, then design from your own site data.", "Record what the next radar pass shows against the promise in the Verify step."]],
  planner: ["🏛", "City planner", "Which zones to look at before permits, roads and drainage money.", ["planner", "observe"],
    z => [`Overlay planner_zones.geojson on parcels and capital projects. Highest estimate: zone ${z.zone} (${z.est_seasonal_vertical_mm} mm).`, "Paint the drainage or paving you are considering on the map and compare the scenario line with the baseline.", "Treat UNRESOLVED zones as 'observe again', not as low risk.", "Ask engineering to confirm any zone before it changes a rule or a budget."]],
  utility: ["💧", "Water utility", "Which pipe corridors to inspect first.", ["utility", "observe"],
    z => [`Join utility_inspection_candidates.csv with your asset inventory (asset_id is blank on purpose). Start with zone ${z.zone}.`, "Use '+ Water' on the map to see how a leak-sized wetting changes the forecast around a main.", "Inspect joints and valves where the spread inside a zone is large.", "Log the outcome in the CSV's outcome column so the next pass can be compared."]],
  emergency: ["🚨", "Emergency manager", "A draft notice for human review, and the live hazard context.", ["cap"],
    z => ["Open the CAP 1.2 draft. Status is Draft and scope Restricted: SWELL never issues alerts.", `It names the zones with the largest estimates (top: ${z.zone}).`, "Use Explore for today's earthquakes, rain and fire layers around the site.", "A named person approves, edits or discards the draft."]],
  farmer: ["🌾", "Farmer / land manager", "Where open ground cracks and heaves most with wetting and drying.", ["land"],
    z => ["Open land_manager_open_ground.csv: open-ground zones ranked by moisture-driven movement.", "Set a dry spell in the Scenario lab to see how much further the ground drops.", "Take the table to your agronomist. SWELL gives no watering schedule.", "Compare with what you see in the field after the next pass."]],
  resident: ["🏠", "Resident", "What is happening in the neighbourhood, in plain words.", ["resident"],
    z => ["Read the one-page summary. It describes neighbourhoods about 80 m across, not your building.", "Clay soil shrinks when it dries and swells when it gets wet. That is the movement on the map.", "New cracks or sticking doors: ask a licensed foundation engineer.", "Check back after the next satellite pass (about every 12 days)."]],
  scientist: ["🔬", "Scientist", "The data, the tests and a physical experiment to repeat.", ["tray", "observe", "engineer_json"],
    z => ["Download site.json (link below): every array behind the map.", "Read PREREGISTRATION.md: pass marks were written before the tests ran.", "Run the clay tray experiment and log it with the template.", "Rerun on another site: python -m swell.ingest, then python -m swell.validate."]] };
function fillRoles() { const o = Object.entries(ROLES).map(([k, r]) => `<option value="${k}">${r[0]} ${r[1]}</option>`).join(""); $("role").innerHTML = o; $("role2").innerHTML = o; setRole(role); }
function setRole(r) { role = r; $("role").value = r; $("role2").value = r; $("pkgList").innerHTML = ROLES[r][3].map(f => "• " + FILES[f][0]).join("<br>") + "<br>• my_scenario.json<br>• my_scenario_zones.geojson<br>• README.txt"; if (step === "studio") panel(); }
const topZone = () => S.zones.filter(z => z.status === "ok").sort((a, b) => b.est_seasonal_vertical_mm - a.est_seasonal_vertical_mm)[0] || {};
function scenarioRecord() {
  const zones = S.zones.map(z => { const [w, s, e, nn] = z.bbox, cs = []; for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if (zoneOf(i, j) === z.zone && !masked(i, j)) cs.push(i * n + j);
    const b = mean(cs.map(c => predicted(c,H,false))), s2 = mean(cs.map(c => predicted(c,H,true)));
    return { zone: z.zone, status: z.status, bbox: z.bbox, baseline_mm: cs.length ? +b.toFixed(2) : null, scenario_mm: cs.length ? +s2.toFixed(2) : null, cells_changed_by_user: cs.filter(c => pWater[c] || pDrain[c] || pPave[c]).length }; });
  const painted = []; for (let c = 0; c < n * n; c++) if (pWater[c] || pDrain[c] || pPave[c]) painted.push({ row: Math.floor(c / n), col: c % n, water_mm: pWater[c], wetting_cut: pDrain[c], paving_added: pPave[c] });
  return { what: "A SWELL scenario: model output, not an observation and not a design.", data_source: S.source, site: S.name, horizon_days: H,
    uncertainty_mm: null, training_rmse_reference_mm: hydroC ? null : S.params.rmse_train,
    uncertainty_note: hydroC ? "No calibrated predictive interval; water-balance screening and parameter sensitivity only." : "Training residual RMSE is a fit diagnostic, not a calibrated predictive interval.",
    engine: hydroC ? SwellHydro.VERSION : "original-fitted", hydro_assumptions: hydroC ? {...SwellHydro.defaults,depth:+$("za").value,groundwaterRise:+$("gwRise").value} : null,
    weather_forcing: hydroC ? weatherForcing : null,
    inputs: { rain_mm: G.rainMm, rain_days: G.rainDays, dry_days_first: G.dryDays, wetting_cut_everywhere: G.reduction, paving_added_everywhere: G.pavedDelta, cells_changed_on_map: painted },
    fitted_parameters: S.params, role: ROLES[role][1], approval: "PENDING: named human approval required", safety: "Decision support only. Not a structural or safety certification. Needs review by a qualified professional.", made_at_utc: new Date().toISOString(), zones };
}

/* ---------- right panel per step ---------- */
const STEPS = { studio: ["Stakeholder Decision Room", "Shared decision workspace", "One shared Earth twin, live evidence, direct intervention and accountable decisions", "split", null],
  explore: ["Explore Earth", "Live planet", "The whole Earth with NASA and USGS layers. Zoom anywhere.", "map", null],
  investigate: ["Investigate", "What the radar saw", "Each NISAR pass over the site. Click any cell.", "map", "observed"],
  understand: ["Understand", "The physical twin", "What moved, why, and what was only an artifact.", "split", "inferred"],
  simulate: ["Simulate", "What if", "Change rain, drainage or paving and watch the ground respond.", "split", "scenario"],
  act: ["Act", "Plans and files", "The same evidence, shaped for each person who has to decide.", "split", null],
  verify: ["Verify", "Was it right?", "Promises checked against the next pass. Tests with pass marks set first.", "split", "forecast"] };
function cellInfo() {
  if (!sel) return `<div class="mute">Click a cell on the map over the study site.</div>`;
  const { i, j } = sel, k = passK, o = num(S.observed_los[k][i][j]), a = num(S.artifact[k][i][j]), m = num(S.inferred_motion[k][i][j]), sd = num(S.inferred_sd[k][i][j]);
  const kind = S.reference[i][j] ? "reference ground (held at zero)" : S.control[i][j] ? "control ground (artifact learned here)" : masked(i, j) ? "unresolved (low coherence)" : "clay ground";
  return `<div class="kv"><span>Cell</span><b>row ${i}, col ${j} · ${zoneOf(i, j)}</b><span>Role</span><b>${kind}</b><span>Radar change, line of sight</span><b style="color:var(--obs)">${Number.isNaN(o) ? "no data" : f1(o) + " mm"}</b><span>Soil-moisture artifact</span><b>${Number.isNaN(a) ? "–" : f1(a) + " mm"}</b><span>Estimated vertical movement</span><b style="color:var(--inf)">${Number.isNaN(m) || masked(i, j) ? "refused" : f1(m) + " mm"}</b><span>Model spread (±; not a validated confidence interval)</span><b>${Number.isNaN(sd) ? "not available" : sd.toFixed(1) + " mm"}</b><span>Coherence</span><b>${S.coh[i][j].toFixed(2)}</b><span>Shrink-swell rating</span><b>${S.lep[i][j].toFixed(1)} %</b><span>Paved</span><b>${(100 * S.paved[i][j]).toFixed(0)} %</b></div>`;
}
const KINDS = { "Unreinforced slab on grade": "Follows the ground closely: expect most of the upper bound.", "Stiffened (ribbed) slab": "Ribs spread edge movement across the slab: expect well under the upper bound.", "Post-tensioned slab": "Built to bridge edge and centre lift: well under the upper bound if designed for this movement.", "Pier and beam (suspended floor)": "Floor is held off the active clay: little reaches it if piers found below the active zone.", "Flexible pavement (road)": "No bending resistance: movement shows as cracking and roughness. Building limits do not apply.", "Buried pipe (segmented)": "Joints take the movement; rigid joints are the weak point. Building limits do not apply." };
function structHTML() { return `<h3>Structure screen (upper bound)</h3><div class="small mute">What a structure would see if it followed the ground exactly. A starting point for an engineer, who decides.</div>
  <select id="stKind" style="width:100%;margin:5px 0">${Object.keys(KINDS).map(k => `<option>${k}</option>`).join("")}</select>
  <div style="display:flex;gap:6px"><label class="small mute" style="flex:1">movement mm<input id="stMm" type="number" min="0" value="${Math.abs(curves().scen[H]).toFixed(1)}" style="width:100%"></label><label class="small mute" style="flex:1">edge distance m<input id="stEm" type="number" value="1.5" step=".1" style="width:100%"></label></div><div id="stOut" class="small" style="margin-top:6px"></div>`; }
function structRun() { if (!$("stKind")) return; const mm = Math.abs(+$("stMm").value || 0), em = Math.max(.3, +$("stEm").value || 1.5), ub = mm / (em * 1000), band = ub < 1 / 500 ? "below 1/500" : ub < 1 / 300 ? "between 1/500 and 1/300" : ub < 1 / 150 ? "between 1/300 and 1/150" : "above 1/150", bld = !/pavement|pipe/i.test($("stKind").value);
  $("stOut").innerHTML = `Upper-bound angular distortion <b>${ub > 0 ? "1/" + Math.round(1 / ub) : "0"}</b>${bld ? ` (${band}; guide values after Bjerrum 1963)` : ""}. ${KINDS[$("stKind").value]}`; }
function renderInsightPins() {
  insightPinEntities.forEach(e=>viewer.entities.remove(e)); insightPinEntities=[];
  if(!S||/SYNTH/i.test(S.source||""))return;
  const addPin=(lon,lat,label,color,description,size=10)=>{
    if(!Number.isFinite(+lon)||!Number.isFinite(+lat))return;
    const entity=viewer.entities.add({position:Cesium.Cartesian3.fromDegrees(+lon,+lat,100),
      point:{pixelSize:size,color,outlineColor:Cesium.Color.WHITE,outlineWidth:2,disableDepthTestDistance:Number.POSITIVE_INFINITY},
      label:{text:label,font:"600 11px system-ui",fillColor:Cesium.Color.WHITE,showBackground:true,backgroundColor:Cesium.Color.fromCssColorString("#081522dd"),pixelOffset:new Cesium.Cartesian2(0,-20),distanceDisplayCondition:new Cesium.DistanceDisplayCondition(0,650000)},
      description});
    entity.show=insightPinsVisible;insightPinEntities.push(entity);
  };
  const zones=(S.zones||[]).filter(z=>z.status==="ok"&&Number.isFinite(+z.lat)&&Number.isFinite(+z.lon));
  // Heuristic observation-priority pins: high movement amplitude combined with uncertainty.
  zones.slice().sort((a,b)=>(b.observe_next_score||0)-(a.observe_next_score||0)).slice(0,10).forEach((z,i)=>{
    let susceptibilityMean=null;
    if(Array.isArray(S.susceptibility)&&/^Z\d+\d+$/.test(z.zone||"")){
      const zi=Number(z.zone[1]),zj=Number(z.zone[2]),vals=[];
      for(let ri=zi*8;ri<Math.min(n,(zi+1)*8);ri++)for(let cj=zj*8;cj<Math.min(n,(zj+1)*8);cj++){const v=S.susceptibility[ri]?.[cj];if(Number.isFinite(v))vals.push(v);}
      if(vals.length)susceptibilityMean=vals.reduce((a,b)=>a+b,0)/vals.length;
    }
    addPin(z.lon,z.lat,`OBSERVE NEXT · ${z.zone}`,i<3?Cesium.Color.ORANGE:Cesium.Color.CYAN,
      `<b>Model-derived observation priority · ${esc(z.zone)}</b><br>Seasonal movement amplitude estimate: ${esc(z.est_seasonal_vertical_mm)} mm<br>Within-zone spread: ${esc(z.est_within_zone_spread_mm)} mm<br>Model uncertainty: ${esc(z.uncertainty_mm)} mm<br>Valid cells: ${esc(z.valid_cells)}<br>Observe-next score: ${esc(z.observe_next_score)}<br>Radar-derived wetness susceptibility: ${susceptibilityMean==null?"not available":susceptibilityMean.toFixed(2)+" mm/unit wetness"}<br>${esc(z.observe_next_reason)}<br><br>Priority is a heuristic movement × uncertainty score, not a formal value-of-information estimate, direct observation or calibrated probability.`,i<3?13:9);
  });
  // Q-learning sequence pins are distinct from observation-priority pins and retain the held-out comparison.
  const rl=S.rl;
  if(rl&&rl.source===S.source&&Array.isArray(rl.suggested_order)){
    const byName=new Map(zones.map(z=>[z.zone,z]));
    rl.suggested_order.slice(0,5).forEach((name,i)=>{
      const z=byName.get(name);if(!z)return;
      addPin(z.lon,z.lat,`RL ORDER ${i+1} · ${name}`,Cesium.Color.fromCssColorString("#bd8cff"),
        `<b>Experimental Q-learning sequence · ${esc(name)}</b><br>Suggested order: ${esc(rl.suggested_order.join(" → "))}<br>Learned policy exposure: ${esc(rl.exposure?.["learned policy"])}<br>Best simple rule: ${esc(rl.best_simple_rule)} · ${esc(rl.exposure?.[rl.best_simple_rule])}<br>Learned vs best simple rule: ${(100*Number(rl.learned_vs_best_rule||0)).toFixed(2)}%<br>Held-out sequences: ${esc(rl.heldout_sequences)}<br>Assumption: ${esc(rl.assumption||"")}<br><br>This is a research sequencing experiment, not an intervention-effect guarantee. Use the simple rule if it performs as well or better.`,12);
    });
  }
  // Highest positive per-cell moisture-susceptibility estimates, if the validated run exported them.
  if(Array.isArray(S.susceptibility)&&S.susceptibility.length===n){
    const cells=[];
    for(let i=0;i<n;i++)for(let j=0;j<n;j++){
      const v=S.susceptibility[i]?.[j];
      if(Number.isFinite(v))cells.push({i,j,v});
    }
    cells.sort((a,b)=>b.v-a.v);
    const [w,s,e,north]=S.bbox,dx=(e-w)/n,dy=(north-s)/n;
    cells.slice(0,5).forEach((c,i)=>addPin(w+(c.j+.5)*dx,north-(c.i+.5)*dy,
      `MOISTURE RESPONSE ${i+1}`,Cesium.Color.fromCssColorString("#55d6be"),
      `<b>Radar-derived moisture susceptibility</b><br>Grid cell: row ${c.i+1}, column ${c.j+1}<br>Estimated coefficient: ${c.v.toFixed(2)} mm per unit lagged wetness<br><br>This fitted association is not a direct movement measurement or proof of causation. Review coherence, reference stability, model residuals and independent ground data.`,10));
  }
}
const insightButton=$("insightPins");
if(insightButton)insightButton.onclick=()=>{insightPinsVisible=!insightPinsVisible;insightPinEntities.forEach(e=>e.show=insightPinsVisible);insightButton.classList.toggle("on",insightPinsVisible);};

function renderDecisionPins(records) {
  decisionPinEntities.forEach(e=>viewer.entities.remove(e)); decisionPinEntities=[];
  (records||[]).filter(r=>!r.synthetic&&r.location&&Number.isFinite(+r.location.lat)&&Number.isFinite(+r.location.lon)).forEach(r=>{
    const color=r.status==="approved_by_user"||r.status==="verified"?Cesium.Color.LIME:r.status==="rejected"?Cesium.Color.RED:r.status==="action_started"?Cesium.Color.CYAN:Cesium.Color.ORANGE;
    const entity=viewer.entities.add({position:Cesium.Cartesian3.fromDegrees(+r.location.lon,+r.location.lat,80),
      point:{pixelSize:12,color,outlineColor:Cesium.Color.WHITE,outlineWidth:2,disableDepthTestDistance:Number.POSITIVE_INFINITY},
      label:{text:`DECISION #${r.sequence} · ${String(r.status).replaceAll("_"," ")}`,font:"600 11px system-ui",fillColor:Cesium.Color.WHITE,showBackground:true,backgroundColor:Cesium.Color.fromCssColorString("#081522dd"),pixelOffset:new Cesium.Cartesian2(0,-20),distanceDisplayCondition:new Cesium.DistanceDisplayCondition(0,900000)},
      description:`<b>${esc(r.decision)}</b><br>${esc(r.actor)} · ${esc(r.role)}<br>${esc(r.rationale)}<br>Evidence: ${esc((r.evidence_ids||[]).join(", "))}`});
    entity.show=decisionPinsVisible; decisionPinEntities.push(entity);
  });
}
const pinButton=$("decisionPins");
if(pinButton)pinButton.onclick=()=>{decisionPinsVisible=!decisionPinsVisible;decisionPinEntities.forEach(e=>e.show=decisionPinsVisible);pinButton.classList.toggle("on",decisionPinsVisible);};

function stakeholderLandingPanel() {
  const R=ROLES[role];
  const useCases=[
    ["Infrastructure engineer","Prioritise geotechnical inspections and compare site evidence with asset condition"],
    ["City planner","Compare drainage, paving and land-use options before allocating capital"],
    ["Water utility","Link modelled ground-change zones to pipe, valve and service records"],
    ["Emergency manager","Prepare a human-reviewed, source-backed situational brief"],
    ["Farmer / land manager","Understand wetting–drying exposure and identify where field checks are needed"],
    ["Resident","Translate local evidence and uncertainty into plain-language questions"],
    ["Scientist","Audit acquisition quality, compare methods and reproduce validation tests"]
  ];
  return `<section class="decision-workbench decision-home" style="border:1px solid var(--line);border-radius:12px;padding:12px;background:linear-gradient(145deg,#102438,#0b1a28)">
    <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap"><b>Stakeholder Decision Room</b><span class="pill syn">WAITING FOR REAL STUDY</span></div>
    <h2 style="margin:12px 0 5px">Start with the decision, not the dashboard.</h2>
    <p class="small mute">Your shared Earth workspace is open, but no real site twin is loaded. The bundled test fixture is deliberately hidden and excluded from stakeholder decisions. Connect evidence before using site-specific numbers.</p>
    <div class="kv"><span>Stakeholder</span><b>${R[0]} ${esc(R[1])}</b><span>Purpose</span><b>${esc(R[2])}</b><span>Real site twin</span><b>Not loaded</b><span>Decision evidence</span><b>Not yet available</b><span>Scientific model</span><b>Waiting for compatible observations</b></div>
    <div style="display:flex;gap:7px;flex-wrap:wrap;margin:12px 0">
      <a class="big" href="connections.html" style="display:inline-block;text-decoration:none;width:auto;margin:0;padding:9px 12px">Connect data & build the real Earth twin →</a>
      <button id="homeExploreEarth" type="button">Explore global Earth context</button>
    </div>
    <div class="warn">A successful API-key test only confirms that a service answered. It does not mean NISAR acquisitions have been found, downloaded, processed or loaded into this Earth workspace.</div>
    <h3>Choose a decision pathway</h3>
    <div class="small" style="display:grid;gap:7px">${useCases.map(([name,desc])=>`<div class="lay"><div>◈</div><div><b>${name}</b><span>${desc}</span></div></div>`).join("")}</div>
    <h3>One shared decision cycle</h3>
    <div class="small" style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px">
      <div class="lay"><b>01 · Observe</b><span>Load real acquisitions and independent context</span></div>
      <div class="lay"><b>02 · Understand</b><span>Inspect evidence, masks and uncertainty</span></div>
      <div class="lay"><b>03 · Manipulate</b><span>Paint or parameterise a reviewable intervention</span></div>
      <div class="lay"><b>04 · Decide</b><span>Record owner, rationale, trade-offs and status</span></div>
      <div class="lay"><b>05 · Verify</b><span>Compare the next observation with the prior claim</span></div>
    </div>
    <p class="small mute" style="margin-top:10px">After a real site is loaded, this panel becomes the live decision workbench: the map, selected cell, scenario engine, research retrieval, decision ledger and map pins all use the same study context.</p>
  </section>`;
}
function stakeholderWorkbench() {
  const c=workspaceContext()||{}, synthetic=/SYNTH/i.test(S.source||""), cell=c.selected_cell;
  const scenario=synthetic?"Unavailable for real decisions":`${c.metrics?.delta_mm==null?"—":f1(c.metrics.delta_mm)+" mm"} modelled difference`;
  const pinn=!synthetic&&S.pinn?.heldout_rmse_mm?S.pinn:null, rl=!synthetic&&S.rl?.exposure?S.rl:null;
  const pinnCard=pinn?`<b>${pinn.physics_helps?"Physics-informed loss improved held-out fit":"Physics-informed loss did not improve held-out fit"}</b><span>Held-out RMSE · physics fit ${pinn.heldout_rmse_mm.physics_fit==null?"—":Number(pinn.heldout_rmse_mm.physics_fit).toFixed(2)} mm · network-only ${pinn.heldout_rmse_mm.network_only==null?"—":Number(pinn.heldout_rmse_mm.network_only).toFixed(2)} mm · physics-informed ${pinn.heldout_rmse_mm.physics_informed==null?"—":Number(pinn.heldout_rmse_mm.physics_informed).toFixed(2)} mm. ${esc(pinn.reading||"")}</span>`:`<b>Not run on a real site</b><span>Experimental inverse-model ablation; results will appear here only after a real-site validation pipeline runs.</span>`;
  const rlCard=rl?`<b>${rl.learned_beats_rules?"Learned sequence beat the best simple rule in held-out simulation":"Learned sequence did not beat the best simple rule"}</b><span>Modelled exposure change vs best simple rule: ${(100*Number(rl.learned_vs_best_rule||0)).toFixed(1)}%. Suggested order: ${esc((rl.suggested_order||[]).join(" → "))}. Assumption: ${esc(rl.assumption||"")}</span>`:`<b>Not run on a real site</b><span>Q-learning zone sequencing experiment; requires sufficient resolved zones and site-derived rainfall.</span>`;
  const statusOptions=synthetic?["proposed","reviewed"]:["proposed","reviewed","approved_by_user","rejected","action_started","verified"];
  return `<section class="decision-workbench" style="border:1px solid var(--line);border-radius:12px;padding:10px;background:linear-gradient(145deg,#102438,#0b1a28)">
    <div style="display:flex;align-items:center;justify-content:space-between;gap:8px"><b>Decision workbench</b><span class="pill ${synthetic?'syn':'ok'}">${synthetic?'SYNTHETIC · REVIEW ONLY':'LIVE SITE CONTEXT'}</span></div>
    <div class="small mute" style="margin:5px 0 8px">The map is the shared decision surface. Select a cell, paint an intervention, inspect the forecast, then record why the team chose an action.</div>
    <div class="kv"><span>Study</span><b>${esc(S.name)}</b><span>Evidence source</span><b>${esc(S.source.slice(0,48))}</b><span>Selected spatial unit</span><b>${cell?esc(cell.zone+' · '+cell.lat.toFixed(4)+', '+cell.lon.toFixed(4)):'Select a cell on the Earth map'}</b><span>Scenario comparison</span><b>${esc(scenario)}</b><span>Radar acquisitions</span><b>${S.pass_days.length} passes</b></div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin:9px 0"><button type="button" id="workbenchInspect">Inspect selected cell</button><button type="button" id="workbenchManipulate" class="big" style="width:auto;margin:0;padding:7px 10px">Manipulate Earth twin →</button><button type="button" id="workbenchCopilot">Ask SWELL</button></div>
    <h3>Record a stakeholder decision</h3>
    <div class="small mute">This is an append-only, local, tamper-evident review log. It is not multi-user authentication or a professional sign-off.</div>
    <label class="small mute">Person / team<input id="decisionActor" value="${esc(RolesActor(role))}" style="width:100%;margin:3px 0 6px"></label>
    <label class="small mute">Decision or next action<input id="decisionStatement" placeholder="e.g. commission a site inspection at the highlighted zone" style="width:100%;margin:3px 0 6px"></label>
    <label class="small mute">Rationale, evidence and unresolved questions<textarea id="decisionRationale" rows="3" placeholder="What evidence supports this? What remains uncertain? What would change the decision?" style="width:100%;margin:3px 0 6px"></textarea></label>
    <div style="display:flex;gap:6px;align-items:end;flex-wrap:wrap"><label class="small mute">Review status<select id="decisionStatus">${statusOptions.map(x=>`<option value="${x}">${({proposed:'Proposed',reviewed:'Reviewed',approved_by_user:'Stakeholder approved',rejected:'Rejected',action_started:'Action started',verified:'Verified by follow-up evidence'})[x]}</option>`).join("")}</select></label><button id="decisionSave" type="button">Record decision</button></div>
    ${synthetic?'<div class="warn">Synthetic fixture: only rehearsal records are allowed. Approval, action and verification statuses are disabled until a real site twin is loaded.</div>':''}
    <div id="decisionSaveStatus" class="small mute" aria-live="polite" style="margin-top:6px"></div>
    <h3>Decision history</h3><div id="decisionHistory" class="small mute">Loading local decision history…</div>
  </section>
  <section style="margin-top:12px"><h3>Research insights & methods</h3><p class="small mute">These are methods present in the codebase, not claims that they have been run or validated for this study.</p>
    <div class="small" style="display:grid;gap:6px">
      <div class="lay"><div>🧠</div><div><b>Physics-informed neural network (PINN)</b>${pinnCard}</div><span class="pill">${pinn?"Ran":"Research"}</span></div>
      <div class="lay"><div>🧭</div><div><b>Reinforcement-learning zone sequencing</b>${rlCard}</div><span class="pill">${rl?"Ran":"Research"}</span></div>
      <div class="lay"><div>🗺️</div><div><b>Cross-site physical-signature matching</b><span>Ranks validated studies by fitted clay gain, relaxation time, delay and radar-artifact signature. Similarity is not proof of transferability.</span></div><span class="pill">${synthetic?'Real site required':'Research'}</span></div>
      <div class="lay"><div>📈</div><div><b>Deterministic sensitivity ensemble</b><span>Nine rainfall/infiltration perturbations for the flood twin; not a calibrated probability forecast.</span></div><span class="pill">Screening</span></div>
    </div>
    <label class="small mute">Search research and methods<input id="stakeholderResearchQ" placeholder="e.g. radar moisture artifact, clay hysteresis, intervention evidence" style="width:100%;margin:4px 0"></label>
    <button id="stakeholderResearchRun" type="button">Retrieve cited research</button><div id="stakeholderResearchOut" class="small" style="margin-top:6px"></div>
    ${synthetic?'<div class="warn" style="margin-top:10px">Cross-site matching is disabled until a real site has passed its validation checks.</div>':`<h3>Compare with another validated SWELL site</h3><p class="small mute">Upload up to 8 previous <code>out/results.json</code> exports. Failed or synthetic studies are excluded. Files are processed locally and are not stored.</p><input id="siteSimilarityFiles" type="file" accept=".json,application/json" multiple><button id="siteSimilarityRun" type="button" style="margin-top:6px">Compare validated site signatures</button><div id="siteSimilarityOut" class="small" style="margin-top:6px"></div>`}
  </section>`;
}
function RolesActor(r) { return ({engineer:"Infrastructure engineering team",planner:"Planning team",utility:"Utility operations team",farmer:"Land manager",resident:"Community representative",scientist:"Research team"})[r]||"Stakeholder team"; }
function rolePanel() { const R = ROLES[role], synthetic=/SYNTH/i.test(S.source||""), z = topZone(), hasResolved=!!z.zone;
  const plan=synthetic
    ? ["Use this labelled sample only to rehearse the interface; do not report its values as observations.",
       "Select a stakeholder role and inspect the research methods without interpreting synthetic outputs as site findings.",
       "Try a scenario only as a software interaction test; inputs and outputs remain synthetic.",
       "Connect a real study and repeat the workflow before recording an operational decision."]
    : hasResolved ? R[4](z) : [
       "No spatial zone currently passes the evidence-quality mask. Do not interpret unresolved areas as low risk.",
       "Review acquisition coverage, coherence and reference stability; obtain another compatible pass or independent field evidence.",
       "Do not rank or approve a site action from missing or unresolved model outputs.",
       "Repeat the validation pipeline when new evidence is available and then review the stakeholder action plan."
      ];
  return `<div class="role on"><div class="ic">${R[0]}</div><div><b>${R[1]} workspace</b><div class="small mute">${R[2]}</div></div></div>${stakeholderWorkbench()}<h3>Role-specific action plan</h3><div id="actionProgress" class="small mute">0/${plan.length} actions reviewed</div><ol class="plan action-list">${plan.map((t,i) => `<li><label><input type="checkbox" data-action-check="${i}"> <span>${esc(t)}</span></label></li>`).join("")}</ol>
  <h3>Evidence files</h3><div class="files stakeholder-files">${R[3].map(f => `<div class="file-row"><a href="data/stakeholder/${FILES[f][0]}" download><b>${FILES[f][0]}</b><span>${FILES[f][1]}</span></a><button type="button" data-preview-file="data/stakeholder/${FILES[f][0]}">Preview</button></div>`).join("")}${role === "scientist" ? '<div class="file-row"><a href="data/site.json" download><b>site.json</b><span>all arrays behind the map</span></a><button type="button" data-preview-file="data/site.json">Preview</button></div>' : ""}</div><pre id="stakeholderPreview" class="stakeholder-preview" hidden></pre>
  ${role === "engineer" && !synthetic && hasResolved ? structHTML() : ""}<div class="warn">Decision support only. No output is a structural safety certification or construction instruction. The decision log is local and single-user in this prototype.</div>`; }
function panel() {
  const R = $("right"), src = `<span class="pill ${/SYNTH/i.test(S.source) ? "syn" : ""}">${esc(S.source.slice(0, 44))}</span>`; let h = "";
  if (step === "studio") h = (/SYNTH/i.test(S.source||"") && !sampleDemoEnabled)
    ? stakeholderLandingPanel()
    : `<h2>Decision Studio</h2><div class="mute small">One evidence base, one selected stakeholder role. Change the role in the top bar.</div>` + rolePanel();
  if (step === "explore") h = `<h2>The Earth right now</h2><div class="mute small">Live satellite context and event feeds. Zoom to a region to load detailed hotspot detections.</div><h3>Earthquakes, past day (USGS)</h3><div id="qList">${quakeList()}</div><div id="qInfo" class="small"></div><h3>Study site status</h3>${/SYNTH/i.test(S.source) ? `<div class="warn">No ground-motion twin is loaded yet, and SWELL does not show made-up data. Everything on this map is a real feed. The easy way: open <a href=\"connections.html\"><b>Connections and real data</b></a> and follow its three steps. Or, in the swell folder:<br><code>python real_site.py --site dallas --check</code> (1 minute, lists the real radar passes)<br><code>python real_site.py --site dallas</code> (downloads and builds)<br>then restart and this page opens on the real site.</div>` : `<div class="files"><a href="#" id="goSite"><b>${esc(S.name)}</b><span>loaded site twin</span></a></div>`}<div class="small mute">Search a place or enter latitude, longitude. A real local twin requires compatible acquisitions and site evidence; the map remains useful without one.</div><div id="searchOut" class="small"></div>`;
  if (step === "investigate") h = `<h2>What the radar saw</h2><div class="mute small">Data: ${src}. Pick a pass in the strip under the map.</div><h3>Selected cell, pass ${passK + 1}</h3>${cellInfo()}<h3>Raw and corrected, this cell</h3><canvas id="cellC" class="wide" width="660" height="230" style="height:120px"></canvas><div class="small mute">Blue: raw radar change. Green: estimated movement after the artifact is removed.</div><div class="warn">The radar phase shifts when soil gets wet even if the ground does not move. "Observed" still contains that. "Inferred" does not.</div>`;
  if (step === "understand") { const p = S.params; h = `<h2>What is happening here?</h2><ul style="padding-left:17px;margin:6px 0"><li>Rain wets the clay. Twin wetness now: <b>${(100 * S.wetness[S.wetness.length - 1]).toFixed(0)} %</b>.</li><li>Clay swells toward a level set by wetness, clay rating and paving. It gets there slowly: time constant <b>${p.T} days</b>, delay <b>${p.tau} days</b>.</li><li>Each extra percent of shrink-swell rating adds <b>${p.alpha.toFixed(1)} mm</b> at full wetness on open ground.</li><li>Paving shields the soil: a fully paved cell moves <b>${(100 * p.b).toFixed(0)} %</b> less.</li><li>Artifact learned on open low-clay ground: <b>${S.beta.toFixed(1)} mm</b> of false signal per unit wetness.</li></ul><h3>Selected cell</h3>${cellInfo()}<h3>Cut-away at this cell</h3><canvas id="xsec" class="wide" width="660" height="300" style="height:150px"></canvas><div class="small mute">An illustration driven by this cell's numbers. Not to scale.</div>`; }
  if (step === "simulate") h = `<h2>Change it and watch</h2><ol class="plan"><li>Pick <b>+ Water</b>, <b>Drainage</b> or <b>Pave</b> under the map and drag across cells.</li><li>Or type what happens in the Scenario lab, or move its sliders.</li><li>The map, the 3D block and the chart all redraw from the same equations.</li></ol><h3>Result at +${H} days</h3><div id="simOut"></div><h3>Zones that change most</h3><div id="simZones"></div><div class="warn">Scenario = model output under your inputs. It is not an observation and not an engineering design.</div>`;
  if (step === "act") h = rolePanel();
  if (step === "verify") h = `<h2>Was the twin right?</h2><h3>Promises checked at the next pass</h3><table><tr><th>Zone</th><th>Promised</th><th>Seen</th><th></th></tr>${S.contracts.map(c => `<tr><td>${c.zone}</td><td>${f1(c.expected_observable.mean_mm)} ± ${c.expected_observable.band90_mm.toFixed(1)}</td><td>${c.observed_mm == null ? "waiting" : f1(c.observed_mm)}</td><td class="${c.arrival === "kept" || c.arrival === "supported" ? "ok" : c.arrival === "inconclusive" ? "mute" : "bad"}">${c.arrival || "open"}</td></tr>`).join("")}</table><div class="small mute">Contradicted promises stay on the page. They are how the twin gets corrected.</div><h3>Tests, pass marks set in advance</h3><table>${S.tests.map(t => `<tr><td>${esc(t.name)}</td><td class="${t.passed == null ? "mute" : t.passed ? "ok" : "bad"}">${t.passed == null ? "not run" : t.passed ? "pass" : "fail"}</td></tr>`).join("")}</table><div class="small mute">Data: ${src}</div>${typeof window.studyHTML === "function" ? window.studyHTML(S) : ""}`;
  if(step === "understand") h+=`<details><summary>Research evidence assistant</summary><p class="small mute">Retrieves structured site evidence; no external LLM or invented citations.</p><input id="evidenceQ" placeholder="Ask about GPS, uncertainty, radar…" style="width:100%"><button id="evidenceRun">Retrieve evidence</button><div id="evidenceOut" class="small"></div></details>`;
  R.innerHTML = h; R.scrollTop = 0;
  if ($("homeExploreEarth")) $("homeExploreEarth").onclick = () => setStep("explore", true);
  if ($("workbenchManipulate")) $("workbenchManipulate").onclick = () => setStep("simulate");
  if ($("workbenchInspect")) $("workbenchInspect").onclick = () => setStep("investigate");
  if ($("workbenchCopilot")) $("workbenchCopilot").onclick = () => $("askSwell")?.click();
  async function loadDecisionHistory() {
    const box=$("decisionHistory"); if(!box)return;
    try {
      const r=await fetch("/api/decisions?site="+encodeURIComponent(S.name)+"&limit=6",{cache:"no-store"});
      const d=await r.json(); if(!r.ok)throw Error(d.error||"History unavailable");
      renderDecisionPins(d.records||[]);
      if(!d.records?.length){box.textContent="No decisions recorded for this site yet.";return;}
      box.innerHTML=d.records.map(x=>`<div style="border-top:1px solid var(--line);padding:6px 0"><b>#${x.sequence} · ${esc(x.status.replaceAll("_"," "))}</b><div>${esc(x.decision)}</div><div class="mute">${esc(x.actor)} · ${new Date(x.created_at_utc).toLocaleString()} · ${x.synthetic?"synthetic rehearsal":"site record"}</div>${x.location?`<button type="button" data-zoom-decision="${x.sequence}" data-lat="${x.location.lat}" data-lon="${x.location.lon}">Zoom to map pin</button>`:""}</div>`).join("")+`<div class="mute">Ledger integrity: ${d.integrity?.valid?"verified":"not verified"} · ${d.integrity?.records_checked||0} records</div>`;
      box.querySelectorAll("[data-zoom-decision]").forEach(b=>b.onclick=()=>viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(+b.dataset.lon,+b.dataset.lat,4500),duration:1.2}));
    } catch(e){box.textContent="Decision history unavailable: "+e.message;}
  }
  if ($("decisionSave")) $("decisionSave").onclick = async () => {
    const out=$("decisionSaveStatus"), actor=$("decisionActor").value.trim(), decision=$("decisionStatement").value.trim(), rationale=$("decisionRationale").value.trim(), status=$("decisionStatus").value, c=workspaceContext()||{};
    if(!actor||!decision||!rationale){out.textContent="Enter the person/team, decision and evidence-based rationale.";return;}
    if(c.synthetic&&!["proposed","reviewed"].includes(status)){out.textContent="A synthetic fixture cannot be approved, actioned or verified. Build a real site first.";return;}
    const evidenceIds=c.synthetic?["SYNTHETIC-FIXTURE"]:["SITE-METADATA",...(c.selected_cell?[`CELL-${c.selected_cell.row}-${c.selected_cell.col}-${c.pass_index}`]:[])];
    let scenario={}; try{scenario=captureScenario("Stakeholder decision",decision);}catch(_){}
    try {
      const r=await fetch("/api/decisions",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({actor,role:ROLES[role][1],status,decision,rationale,evidence_ids:evidenceIds,scenario,location:(!c.synthetic&&c.selected_cell)?{lat:c.selected_cell.lat,lon:c.selected_cell.lon,row:c.selected_cell.row,col:c.selected_cell.col,zone:c.selected_cell.zone}:null})});
      const d=await r.json(); if(!r.ok)throw Error(d.error||"Could not record decision");
      out.textContent=`Recorded #${d.sequence}. Hash ${String(d.record_hash||"").slice(0,18)}… · local tamper-evident ledger.`;
      $("decisionStatement").value=""; $("decisionRationale").value=""; loadDecisionHistory();
    }catch(e){out.textContent="Not recorded: "+e.message;}
  };
  if ($("decisionHistory")) loadDecisionHistory();
  if ($("stakeholderResearchRun")) $("stakeholderResearchRun").onclick = async () => {
    const out=$("stakeholderResearchOut"), question=$("stakeholderResearchQ").value.trim();
    if(!question){out.textContent="Enter a research question.";return;}
    out.textContent="Retrieving curated sources and site evidence…";
    try{
      const tasks=[fetch("/api/site-twin/literature",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question})}).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error||"RAG unavailable");return d;})];
      if(!/SYNTH/i.test(S.source||"")) tasks.push(fetch("/api/site-twin/research",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question})}).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error||"Site research unavailable");return d;}));
      const results=await Promise.allSettled(tasks), rag=results[0].status==="fulfilled"?results[0].value:null, research=results[1]?.status==="fulfilled"?results[1].value:null;
      const sources=[...(rag?.sources||[]),...(research?.sources||[])]; const unique=sources.filter((x,i,a)=>a.findIndex(y=>y.url===x.url&&y.title===x.title)===i).slice(0,6);
      const summary=[rag?.status||"Retrieval complete",research?.method||null,research?.limitations||null].filter(Boolean).join(" · ");
      out.innerHTML=`<div class="warn">${esc(summary||"Research retrieval only; applicability must be checked.")}</div>`+(unique.length?`<ul>${unique.map(x=>`<li><a href="${esc(x.url||"#")}" target="_blank" rel="noopener">${esc(x.title||"Research source")}</a> <span class="mute">${esc(x.curated_note||x.note||"")}</span></li>`).join("")}</ul>`:"<p>No matching cited sources were retrieved. Do not treat an empty result as evidence.")+( /SYNTH/i.test(S.source||"") ? '<p class="mute">Site-specific research analysis is withheld because the loaded site is a synthetic fixture.</p>'  : "");
    }catch(e){out.textContent="Research retrieval failed: "+e.message;}
  };
  if ($("siteSimilarityRun")) $("siteSimilarityRun").onclick = async () => {
    const out=$("siteSimilarityOut"), files=Array.from($("siteSimilarityFiles").files||[]);
    if(!files.length){out.textContent="Choose at least one results.json from another real, validated SWELL site.";return;}
    if(files.length>8||files.some(f=>f.size>2*1024*1024)){out.textContent="Choose up to 8 files, each no larger than 2 MB.";return;}
    out.textContent="Checking validation gates and comparing physical signatures…";
    try{
      const results=[];
      for(const file of files){const value=JSON.parse(await file.text());results.push(value);}
      const response=await fetch("/api/site-twin/cross-site-similarity",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({results})});
      const d=await response.json();if(!response.ok)throw Error(d.error||"Comparison failed");
      const matches=d.matches||[];
      const list=matches.length?`<ol>${matches.map(x=>`<li><b>${esc(x.site)}</b> · standardized distance ${Number(x.distance).toFixed(3)}</li>`).join("")}</ol>`:"No additional uploaded site passed the validation gate.";
      const excluded=(d.excluded||[]).length?`<p class="mute">Excluded: ${d.excluded.map(x=>esc(x.upload)+": "+esc(x.reason)).join(" · ")}</p>`:"";
      out.innerHTML=`<div class="warn">${esc(d.method||d.note||"Comparison complete")}</div><p>Active site: <b>${esc(d.site)}</b> · ${d.compared_sites} eligible site(s) compared. Lower distance means a closer fitted physical signature, not an equivalent site.</p>${list}${excluded}<p class="mute">${esc(d.limitation||"")}</p>`;
    }catch(e){out.textContent="Comparison unavailable: "+e.message;}
  };
  if($("evidenceRun"))$("evidenceRun").onclick=()=>{const a=SwellResearch.answer(S,$("evidenceQ").value);$("evidenceOut").textContent=[a.title,a.body,...a.evidence,...a.limitations].join(" • ")};
  R.querySelectorAll("[data-role]").forEach(e => e.onclick = () => setRole(e.dataset.role));
  const planBoxes=[...R.querySelectorAll('[data-action-check]')];
  if(planBoxes.length){const planKey=`swell.plan.${S.name}.${role}`;let done=[];try{done=JSON.parse(localStorage.getItem(planKey)||'[]')}catch(_){}const progress=()=>{const count=planBoxes.filter(x=>x.checked).length;const el=$("actionProgress");if(el)el.textContent=`${count}/${planBoxes.length} actions reviewed`;};planBoxes.forEach(box=>{box.checked=done.includes(Number(box.dataset.actionCheck));box.onchange=()=>{const next=planBoxes.filter(x=>x.checked).map(x=>Number(x.dataset.actionCheck));try{localStorage.setItem(planKey,JSON.stringify(next))}catch(_){}progress()}});progress();}
  R.querySelectorAll('[data-preview-file]').forEach(btn=>btn.onclick=async()=>{const pre=$("stakeholderPreview");if(!pre)return;pre.hidden=false;pre.textContent='Loading evidence file…';try{const response=await fetch(btn.dataset.previewFile);if(!response.ok)throw Error('File not found');const content=await response.text();pre.textContent=content.slice(0,12000)+(content.length>12000?'\n… preview truncated; download the full file above.':'')}catch(e){pre.textContent='Preview unavailable: '+e.message}});
  if ($("goSite")) $("goSite").onclick = e => { e.preventDefault(); flySite(); };
  R.querySelectorAll("[data-q]").forEach(e => e.onclick = () => showQuake(+e.dataset.q));
  ["stKind", "stMm", "stEm"].forEach(id => $(id) && ($(id).oninput = structRun)); structRun();
  if ($("cellC")) drawCell(); if ($("xsec")) drawXsec(); if (step === "simulate") simOut(); if(typeof renderHydroEvidence==="function") renderHydroEvidence();
}
function simOut() { if (!$("simOut")) return; const cv = curves(), b = cv.base[H], s = cv.scen[H];
  $("simOut").innerHTML = `<div class="kv"><span>No further rain</span><b style="color:var(--fc)">${f1(b)} mm</b><span>Your scenario</span><b style="color:var(--scn)">${f1(s)} mm</b><span>Difference</span><b>${f1(s - b)} mm</b></div><div class="small mute">${cv.F.label}</div>`;
  const z = scenarioRecord().zones.filter(x => x.baseline_mm != null).map(x => ({ ...x, d: x.scenario_mm - x.baseline_mm })).sort((a, b2) => Math.abs(b2.d) - Math.abs(a.d)).slice(0, 5);
  $("simZones").innerHTML = `<table><tr><th>Zone</th><th>Baseline</th><th>Scenario</th><th>Change</th></tr>${z.map(x => `<tr><td>${x.zone}</td><td>${f1(x.baseline_mm)}</td><td>${f1(x.scenario_mm)}</td><td>${f1(x.d)}</td></tr>`).join("")}</table>`; }
function drawCell() { const cv = $("cellC"), g = cv.getContext("2d"); g.clearRect(0, 0, cv.width, cv.height); if (!sel) return; const { i, j } = sel, o = S.observed_los.map(a => num(a[i][j])), m = S.inferred_motion.map(a => num(a[i][j])), all = o.concat(m).filter(v => !Number.isNaN(v)); if (!all.length) return;
  const y0 = Math.min(...all, 0) - 1, y1 = Math.max(...all, 0) + 1, d1 = S.pass_days[S.pass_days.length - 1], X = d => 46 + d / d1 * (cv.width - 60), Y = v => 12 + (y1 - v) / (y1 - y0) * (cv.height - 44);
  g.font = "18px system-ui"; g.fillStyle = "#8fa5b8"; g.fillText(y1.toFixed(0), 6, 24); g.fillText(y0.toFixed(0), 6, cv.height - 30); g.fillText("day 0", 46, cv.height - 6); g.fillText("day " + d1, cv.width - 90, cv.height - 6);
  g.strokeStyle = "#1c3348"; g.beginPath(); g.moveTo(46, Y(0)); g.lineTo(cv.width - 14, Y(0)); g.stroke();
  [[o, "#4aa3ff"], [m, "#3ecf8e"]].forEach(([a, c]) => { g.strokeStyle = g.fillStyle = c; g.lineWidth = 3; g.beginPath(); let st = false; a.forEach((v, k) => { if (Number.isNaN(v)) return; st ? g.lineTo(X(S.pass_days[k]), Y(v)) : g.moveTo(X(S.pass_days[k]), Y(v)); st = true; }); g.stroke(); a.forEach((v, k) => { if (!Number.isNaN(v)) { g.beginPath(); g.arc(X(S.pass_days[k]), Y(v), k === passK ? 7 : 4, 0, 7); g.fill(); } }); }); }
function drawXsec() { const cv = $("xsec"), g = cv.getContext("2d"), Wd = cv.width, Hh = cv.height; g.clearRect(0, 0, Wd, Hh);
  const i = sel ? sel.i : 0, j = sel ? sel.j : 0, v = sel && lastField ? lastField.fld[i][j] : 0, mv = Number.isNaN(v) ? 0 : v, w = wetAt(), pv = sel ? S.paved[i][j] : 0, top = 90 - Math.max(-30, Math.min(30, mv * 1.5));
  g.fillStyle = "#0d2236"; g.fillRect(0, 0, Wd, top); g.fillStyle = "#5c4433"; g.fillRect(0, top, Wd, 22); const cl = mix([194, 140, 87], [115, 51, 36], w); g.fillStyle = `rgb(${cl.map(Math.round)})`; g.fillRect(0, top + 22, Wd, 120); g.fillStyle = "#4d5966"; g.fillRect(0, top + 142, Wd, Hh);
  g.strokeStyle = "#2a1a12"; g.lineWidth = 2; for (let x = 30; x < Wd; x += 46) { const dep = (1 - w) * 95; if (dep < 6) break; g.beginPath(); g.moveTo(x, top + 22); g.lineTo(x + 6, top + 22 + dep * .5); g.lineTo(x - 3, top + 22 + dep); g.stroke(); }
  g.fillStyle = "#c9d2da"; g.fillRect(0, top - 9, Wd * pv, 9); g.strokeStyle = "#ffffff88"; g.setLineDash([6, 6]); g.beginPath(); g.moveTo(0, 90); g.lineTo(Wd, 90); g.stroke(); g.setLineDash([]);
  g.fillStyle = "#e9f1f7"; g.font = "19px system-ui"; g.fillText(sel ? `Ground ${mv >= 0 ? "raised" : "dropped"} ${Math.abs(mv).toFixed(1)} mm (dashed = start level)` : "Click a cell to see its cut-away", 14, 30);
  g.fillText(`Clay wetness ${(100 * w).toFixed(0)} %: ${w > .5 ? "swollen, cracks closed" : "dry, cracks open"}`, 14, top + 90); g.fillText(`Paved ${(100 * pv).toFixed(0)} %`, 14, 58); g.fillText("Ground below the active zone", 14, Math.min(Hh - 10, top + 172));
  g.strokeStyle = g.fillStyle = "#7fe3f2"; g.lineWidth = 4; const ax = Wd - 70, up = mv >= 0; g.beginPath(); g.moveTo(ax, top + 110); g.lineTo(ax, top + 40); g.stroke(); g.beginPath(); const ty = up ? top + 34 : top + 116, s = up ? 1 : -1; g.moveTo(ax, ty); g.lineTo(ax - 10, ty + 16 * s); g.lineTo(ax + 10, ty + 16 * s); g.fill(); }

/* ---------- earthquakes ---------- */
const quakeList = () => liveOK.usgs === false ? '<span class="mute">USGS feed not reachable from this network.</span>' : !quakes.length ? '<span class="mute">'+(liveOK.usgs?"No events in returned feed":"Loading…")+'</span>' : `<table>${quakes.slice(0, 7).map((q, k) => `<tr data-q="${k}" style="cursor:pointer"><td><b>M ${q.mag.toFixed(1)}</b></td><td>${esc(q.place || "")}</td></tr>`).join("")}</table>`;
function showQuake(k) { const q = quakes[k]; if (!q) return; viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(q.lon, q.lat, 1.2e6), duration: 1.4 }); const days = Math.max(.01, (Date.now() - q.time) / 864e5), r = M.aftershockRate(days, q.mag, Math.max(3, q.mag - 1.5));
  if ($("qInfo")) $("qInfo").innerHTML = `<div class="warn"><b>M ${q.mag.toFixed(1)}, ${esc(q.place || "")}</b><br>What happened: ${new Date(q.time).toUTCString()}, depth ${q.depth.toFixed(0)} km.<br>What is happening now: ${(days * 24).toFixed(1)} hours since the main shock.<br>What may happen next: about ${r.toFixed(2)} aftershocks per day of M ≥ ${Math.max(3, q.mag - 1.5).toFixed(1)} right now (generic Reasenberg–Jones rate, falling with time). A statistical rate, not a prediction of any single event.</div>`; }
function loadQuakes() { fetch("/api/geo/quakes", { cache: "no-store" }).then(r => {if(!r.ok)throw Error("USGS unavailable");return r.json()}).then(x => x.collection).then(d => {
  quakes = d.features.map(f => ({ mag: f.properties.mag, place: f.properties.place, time: f.properties.time, lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1], depth: f.geometry.coordinates[2] })).filter(q => q.mag != null).sort((a, b) => b.mag - a.mag);
  quakeDS.entities.removeAll(); quakes.forEach((q, k) => quakeDS.entities.add({ position: Cesium.Cartesian3.fromDegrees(q.lon, q.lat), point: { pixelSize: 4 + 2.2 * q.mag, color: Cesium.Color.fromCssColorString("#ff5d5d").withAlpha(.8), outlineColor: Cesium.Color.WHITE, outlineWidth: 1 }, properties: { q: k } }));
  liveOK.usgs = true; liveTag(); layerText(); if (step === "explore") panel(); }).catch(() => { liveOK.usgs = false; liveTag(); layerText(); if (step === "explore") panel(); }); }
function liveTag() { const t = $("liveTag"); if (liveOK.usgs) { t.textContent = "USGS loaded"; t.style.color = "var(--green)"; t.style.borderColor = "var(--green)"; } else if (liveOK.usgs === false) { t.textContent = "USGS unavailable"; t.style.color = "var(--amber)"; }
  $("imgNote").textContent = liveOK.usgs === false || liveOK.gibs === false ? "One or more external feeds failed. The fallback basemap may be visible. Layer availability is not confirmed." : "Imagery: NASA GIBS latest available layer default (each product has its own date and native resolution). Close-up: Esri World Imagery; capture date varies and is not live."; }

/* ---------- left layer list ---------- */
const LAYS = [["nisar", "Radar / model ground movement", "linear-gradient(135deg,#1f3fd0,#3ecf6e,#e5352b)", true], ["rain", "GPM rainfall (IMERG)", "linear-gradient(135deg,#0b2a5a,#33b1ff)", false], ["smap", "SMAP soil moisture", "linear-gradient(135deg,#7a5a2a,#2e8f6a)", false], ["quake", "USGS earthquakes", "radial-gradient(#ff5d5d,#40151a)", true], ["fire", "Fire hotspots (NASA FIRMS)", "radial-gradient(#ff554d,#5a1a08)", true], ["today", "Dated satellite imagery", "linear-gradient(135deg,#1c4f2a,#8fb7d6)", true], ["sharp", "Close-up city detail", "linear-gradient(135deg,#3a3f2f,#9aa08a)", true]];
function buildLayers() {
  const groups = [{title:"Satellite imagery",keys:["today","sharp"],open:true},{title:"Live hazards",keys:["quake","fire"],open:true},{title:"Environment",keys:["rain","smap"],open:false},{title:"Site twin",keys:["nisar"],open:false}];
  const item = k => { const [key,t,bg,on]=LAYS.find(x=>x[0]===k); const enabled=on && !(key==="nisar" && /SYNTH/i.test(S.source) && !sampleDemoEnabled); const disabled=key==="nisar" && /SYNTH/i.test(S.source) && !sampleDemoEnabled; return `<div class="lay"><div class="sw" style="background:${bg}"></div><div><b>${t}</b><span id="lt-${key}"></span></div><input type="checkbox" class="tog" data-lay="${key}" ${enabled?"checked":""} ${disabled?"disabled":""}></div>`; };
  $("layList").innerHTML=groups.map(g=>`<details class="layer-group" ${g.open?"open":""}><summary>${g.title}</summary>${g.keys.map(item).join("")}</details>`).join("");
  document.querySelectorAll("[data-lay]").forEach(c => { const apply=()=>{const k=c.dataset.lay;if(k==="nisar"){if(/SYNTH/i.test(S.source)&&!sampleDemoEnabled){c.checked=false;return}overlay.show=outline.show=c.checked}else if(k==="quake")quakeDS.show=c.checked;else if(k==="fire"){if(L.fire)L.fire.show=c.checked;if(window.SWELL_FIRMS_DATA_SOURCE)window.SWELL_FIRMS_DATA_SOURCE.show=c.checked;if(c.checked&&window.SWELL_LOAD_FIRMS)window.SWELL_LOAD_FIRMS()}else if(k==="sharp")sharpCheck();else if(L[k])L[k].show=c.checked};apply();c.onchange=apply;}); layerText(); }
function layerText() { if (!S || !lastField) return; const vals = lastField.fld.flat().filter(v => !Number.isNaN(v)), r7 = S.rain.slice(-7).reduce((a, b) => a + b, 0), wN = S.wetness[S.wetness.length - 1], w30 = mean(S.wetness.slice(-30));
  const set = (k, t) => { const e = $("lt-" + k); if (e) e.textContent = t; };
  set("nisar", `${/SYNTH/i.test(S.source) ? (sampleDemoEnabled ? "SYNTHETIC DEMO · not NISAR" : "No real site data · sample hidden") : `NISAR / ${S.source}`} · ${f1(Math.min(...vals))} to ${f1(Math.max(...vals))} mm`); set("rain", `Model input history, site record, last 7 days: ${r7.toFixed(1)} mm`); set("smap", "NASA surface moisture context; not the site model wetness");
  set("quake", liveOK.usgs ? `${quakes.length} events M ≥ 2.5, past day` : liveOK.usgs === false ? "feed not reachable" : "loading…"); set("fire", window.SWELL_FIRMS_STATUS || "FIRMS points load on regional zoom · requires FIRMS_MAP_KEY"); set("today", "VIIRS true colour, " + (imgDate || "latest available")); set("sharp", "Esri World Imagery, when zoomed in"); }

/* ---------- controls ---------- */
const SL = [["rainMm", "Rain to add", 0, 250, 5, "mm"], ["rainDays", "…spread over", 1, 14, 1, "days"], ["dryDays", "Dry days first", 0, 30, 1, "days"], ["reduction", "Drainage: wetting cut", 0, 80, 5, "%"], ["pavedDelta", "Extra paving", 0, 60, 5, "%"], ["H", "Look ahead", 10, 90, 5, "days"]];
function buildSliders() { $("sliders").innerHTML = SL.map(([k, t, a, b, s, u]) => `<div class="sl"><span>${t} <span class="mute">(${u})</span></span><input type="range" id="r-${k}" min="${a}" max="${b}" step="${s}"><input type="number" id="n-${k}" min="${a}" max="${b}" step="${s}"></div>`).join("");
  SL.forEach(([k]) => { const upd = e => { let v = +e.target.value; if (!Number.isFinite(v)) return; v=Math.max(+e.target.min,Math.min(+e.target.max,v)); if (k === "H") { H = Math.max(10, Math.min(weatherForcing && engine === "hydro" ? weatherForcing.daily.length : 90, v)); $("day").max = H; dayA = Math.min(dayA, H); } else G[k] = (k === "reduction" || k === "pavedDelta") ? v / 100 : v; state = "scenario"; syncSliders(); rerun(); }; $("r-" + k).oninput = upd; $("n-" + k).onchange = upd; }); syncSliders(); }
function syncSliders() { SL.forEach(([k]) => { const v = k === "H" ? H : (k === "reduction" || k === "pavedDelta") ? Math.round(G[k] * 100) : G[k]; $("r-" + k).value = v; $("n-" + k).value = v; }); $("day").max = H; $("day").value = dayA; }
function rerun() { compute(); redraw(); }
function redraw() { drawOverlay(); const cv = drawChart(); findings(cv); layerText(); selCard(); if (["investigate", "understand", "simulate"].includes(step)) panel(); if(typeof renderHydroEvidence==="function") renderHydroEvidence(); }
$("run").onclick = () => { const r = M.parseRequest($("ask").value); if (r.ignored) { $("understood").textContent = "I could not find rain, drought, drainage or paving in that. Try: 80 mm of rain over 3 days."; return; } const o = r.settings; G.rainMm = o.rainMm; G.rainDays = o.rainDays; G.dryDays = o.dryDays; G.reduction = o.reduction; G.pavedDelta = o.pavedDelta; H = Math.max(10, Math.min(weatherForcing && engine === "hydro" ? weatherForcing.daily.length : 90, o.horizon)); dayA = H; state = "scenario"; $("understood").textContent = "Understood: " + r.understood.join(", ") + "."; syncSliders(); rerun(); };
$("ask").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("run").click(); } });
$("day").oninput = e => { dayA = +e.target.value; redraw(); };
document.querySelectorAll("#states button").forEach(b => b.onclick = () => { state = b.dataset.s; redraw(); });
document.querySelectorAll("#view button").forEach(b => b.onclick = () => setView(b.dataset.v));
function setView(v) { $("stage").className = v === "split" ? "" : v; document.querySelectorAll("#view button").forEach(b => b.classList.toggle("on", b.dataset.v === v)); }
$("exag").oninput = () => lastField && drawTwin(lastField.fld, lastField.V); $("za").onchange = () => lastField && drawTwin(lastField.fld, lastField.V);
$("role").onchange = e => setRole(e.target.value); $("role2").onchange = e => setRole(e.target.value);
let playing = null; $("play").onclick = () => { if (playing) { clearInterval(playing); playing = null; $("play").textContent = "▶ Play"; return; } $("play").textContent = "❚❚ Pause"; let k = 0; const tot = S.pass_days.length + 10; playing = setInterval(() => { if (k < S.pass_days.length) { state = "inferred"; passK = k; } else { state = "scenario"; dayA = Math.max(1, Math.round((k - S.pass_days.length + 1) / 10 * H)); $("day").value = dayA; } redraw(); if (++k >= tot) { clearInterval(playing); playing = null; $("play").textContent = "▶ Play"; } }, 650); };

const AMT = { water: [60, "mm"], drain: [50, "%"], pave: [40, "%"] };
document.querySelectorAll("[data-tool]").forEach(b => b.onclick = () => { tool = b.dataset.tool; document.querySelectorAll("[data-tool]").forEach(x => x.classList.toggle("on", x === b)); if (AMT[tool]) { $("amt").value = AMT[tool][0]; $("amtU").textContent = AMT[tool][1]; } });
$("clearPaint").onclick = () => { pWater.fill(0); pDrain.fill(0); pPave.fill(0); rerun(); };
function cellAt(pos) { const ray=viewer.camera.getPickRay(pos);const c = (ray&&viewer.scene.globe.pick(ray,viewer.scene)) || viewer.camera.pickEllipsoid(pos, viewer.scene.globe.ellipsoid); if (!c) return null; const g = Cesium.Cartographic.fromCartesian(c), lon = Cesium.Math.toDegrees(g.longitude), lat = Cesium.Math.toDegrees(g.latitude), [w, s, e, nn] = S.bbox; if (lon < w || lon >= e || lat <= s || lat > nn) return null; return { i: Math.min(n - 1, Math.floor((nn - lat) / (nn - s) * n)), j: Math.min(n - 1, Math.floor((lon - w) / (e - w) * n)) }; }
function paintAt(pos) { const c = cellAt(pos); if (!c) return false; const r = Math.max(1, Math.min(6, +$("brush").value || 1)) - 1, a = Math.max(0, Math.min(tool==="water"?500:100,+$("amt").value || 0));
  for (let i = Math.max(0, c.i - r); i <= Math.min(n - 1, c.i + r); i++) for (let j = Math.max(0, c.j - r); j <= Math.min(n - 1, c.j + r); j++) { const k = i * n + j; if (tool === "water") pWater[k] = a; else if (tool === "drain") pDrain[k] = Math.min(.9, a / 100); else if (tool === "pave") pPave[k] = Math.min(1, a / 100); else if (tool === "green") pPave[k] = -Math.min(1, a / 100); else { pWater[k] = pDrain[k] = pPave[k] = 0; } }
  state = "scenario"; return true; }
let painting = false, raf = 0; const hnd = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas), ctlr = viewer.scene.screenSpaceCameraController;
hnd.setInputAction(e => { if (tool === "select") return; painting = true; ctlr.enableInputs = false; if (paintAt(e.position)) rerun(); }, Cesium.ScreenSpaceEventType.LEFT_DOWN);
hnd.setInputAction(e => { if (!painting) return; if (paintAt(e.endPosition) && !raf) raf = requestAnimationFrame(() => { raf = 0; rerun(); }); }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
hnd.setInputAction(() => { if (painting) { painting = false; ctlr.enableInputs = true; rerun(); } }, Cesium.ScreenSpaceEventType.LEFT_UP);
hnd.setInputAction(e => { if (tool !== "select") return; const p = viewer.scene.pick(e.position); if (p && p.id && p.id.properties && p.id.properties.q) { setStep("explore"); showQuake(p.id.properties.q.getValue()); return; } const c = cellAt(e.position); if (c) { sel = c; const [w, s, ee, nn] = S.bbox, dx = (ee - w) / n, dy = (nn - s) / n; selEnt.rectangle.coordinates = Cesium.Rectangle.fromDegrees(w + c.j * dx, nn - (c.i + 1) * dy, w + (c.j + 1) * dx, nn - c.i * dy); selEnt.show = true; redraw(); if (step === "studio" || step === "explore") setStep("investigate", true); } }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
function selCard() { const e = $("selCard"); if (!sel || !lastField) { e.style.display = "none"; return; } const v = lastField.fld[sel.i][sel.j], pd = S.pass_days, m = S.inferred_motion.map(a => num(a[sel.i][sel.j])), l = m.length - 1, tr = m[l] - m[l - 1];
  e.style.display = "block"; e.innerHTML = `<b>Selected cell · ${zoneOf(sel.i, sel.j)}</b><div class="kv" style="margin-top:4px"><span>${state[0].toUpperCase() + state.slice(1)}</span><b>${Number.isNaN(v) ? "refused" : f1(v) + " mm"}</b><span>Trend, last ${pd[l] - pd[l - 1]} d</span><b>${Number.isNaN(tr) ? "–" : (tr >= 0 ? "rising " : "sinking ") + Math.abs(tr).toFixed(1) + " mm"}</b><span>Coherence</span><b>${S.coh[sel.i][sel.j].toFixed(2)}</b></div>`; }

/* ---------- steps ---------- */
function buildSteps() { $("steps").innerHTML = Object.entries(STEPS).map(([k, s]) => `<button data-step="${k}">${s[0]}<i>${s[1]}</i></button>`).join(""); document.querySelectorAll("[data-step]").forEach(b => b.onclick = () => setStep(b.dataset.step));
  $("flow").innerHTML = [["explore", "Observe", "NASA / USGS"], ["understand", "Model", "physical twin"], ["simulate", "Manipulate", "what-if"], ["studio", "Decide", "stakeholder room"], ["verify", "Verify", "next pass"]].map(([k, a, b]) => `<span data-f="${k}"><b>${a}</b>${b}</span>`).join(""); }
function setStep(s, stay) {
  if (S && /SYNTH/i.test(S.source) && !sampleDemoEnabled && !["explore","studio"].includes(s)) {
    $("right").innerHTML = `<h2>No real site twin loaded</h2><div class="warn">${esc(S.source)} is a bundled synthetic test fixture. It is not a real NISAR observation and cannot support a real-world forecast or stakeholder decision.</div><p class="small mute">Use Explore Earth for real-source context. To test the sample controls, use “Show sample twin” in the top bar.</p>`;
    return;
  }
  step = s; const d = STEPS[s]; document.querySelectorAll("[data-step]").forEach(b => b.classList.toggle("on", b.dataset.step === s)); document.querySelectorAll("[data-f]").forEach(b => b.classList.toggle("on", b.dataset.f === s));
  $("stepTitle").textContent = d[0]; $("stepSub").textContent = d[2]; setView(d[3]); if (d[4]) state = d[4]; if (s === "verify") dayA = Math.min(H, 12);
  if (!stay) { if (s === "explore") flyEarth(); else flySite(); } redraw(); panel(); }

function setSampleDemo(enabled) {
  sampleDemoEnabled = !!enabled;
  const synthetic = !!S && /SYNTH/i.test(S.source);
  if (!synthetic) return;
  document.body.classList.toggle("no-sample-twin", !sampleDemoEnabled);
  overlay.show = outline.show = sampleDemoEnabled;
  const b = $("sampleMode"); if (b) { b.hidden = false; b.textContent = sampleDemoEnabled ? "Hide sample twin" : "Show sample twin (synthetic)"; }
  const nisar = document.querySelector('[data-lay="nisar"]');
  if (nisar) { nisar.checked = sampleDemoEnabled; nisar.disabled = !sampleDemoEnabled; }
  const card = $("siteCard");
  if (siteMarker) siteMarker.show=sampleDemoEnabled; if (miniSiteMarker) miniSiteMarker.show=sampleDemoEnabled;
  if (card) card.innerHTML = sampleDemoEnabled
    ? `<b>📍 ${esc(S.name)}</b><div class="small mute">Synthetic test grid · ${S.n} × ${S.n} cells · NOT NASA measurements</div><span class="pill syn">SYNTHETIC DEMO</span>`
    : `<b>🌍 Global Earth context</b><div class="small mute">Live-source imagery and event feeds · no local ground-motion twin loaded</div><span class="pill">REAL CONTEXT FEEDS</span><div class="small" style="margin-top:5px"><a href="connections.html"><b>Connect data and build a real study →</b></a></div>`;
  if (sampleDemoEnabled) setStep("studio", true); else { viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(0,0,2.15e7),duration:1.2}); setStep("studio", true); }
}

/* ---------- search ---------- */
$("search").onsubmit = async e => { e.preventDefault(); const q = $("q").value.trim(); if (!q) return; const say = t => { setStep("explore", true); const o = $("searchOut"); if (o) o.innerHTML = t; };
  const go = (lat, lon, name) => { viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(lon, lat, 9e4), duration: 2 }); const [w, s, ee, nn] = S.bbox; const inside = lon >= w && lon <= ee && lat >= s && lat <= nn; say(inside ? `<div class="warn">${esc(name)} is inside the loaded study area. ${/SYNTH/i.test(S.source)?'The bundled sample is synthetic; it is not a real site twin.':''}</div>` : `<div class="warn"><b>${esc(name)}</b> (${lat.toFixed(3)}, ${lon.toFixed(3)}). Live context layers are shown. No site-specific ground-motion twin is loaded here.<br><a href="site-twin.html?lat=${lat.toFixed(6)}&amp;lon=${lon.toFixed(6)}">Open Site Twin for this location ↗</a> to load real USGS terrain and run a clearly labelled screening scenario. NASA SAR data must be discovered and processed separately before any NISAR displacement claim is made.</div>`); };
  const m = q.match(/^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/); if (m) {if(Math.abs(+m[1])>90||Math.abs(+m[2])>180)return say("Coordinates out of range.");return go(+m[1], +m[2], "Your coordinates");}
  if (S.name.toLowerCase().includes(q.toLowerCase())) { flySite(); return; }
  try { const r = await fetch("https://nominatim.openstreetmap.org/search?format=json&limit=1&q=" + encodeURIComponent(q)); const d = await r.json(); if (!d.length) return say(`<div class="warn">No place found for "${esc(q)}".</div>`); go(+d[0].lat, +d[0].lon, d[0].display_name.split(",").slice(0, 2).join(",")); }
  catch (_) { say(`<div class="warn">Place search needs an internet connection (OpenStreetMap Nominatim). You can still type coordinates: lat, lon.</div>`); } };

/* ---------- package (zip, stored) ---------- */
const CRC = (() => { const t = new Uint32Array(256); for (let i = 0; i < 256; i++) { let c = i; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[i] = c >>> 0; } return b => { let c = ~0; for (let i = 0; i < b.length; i++) c = t[(c ^ b[i]) & 255] ^ (c >>> 8); return ~c >>> 0; }; })();
function zip(files) { const enc = new TextEncoder(), parts = [], cen = []; let off = 0;
  for (const [name, text] of files) { const nb = enc.encode(name), d = typeof text === "string" ? enc.encode(text) : text, crc = CRC(d), h = new DataView(new ArrayBuffer(30)); h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x0800, true); h.setUint32(14, crc, true); h.setUint32(18, d.length, true); h.setUint32(22, d.length, true); h.setUint16(26, nb.length, true);
    parts.push(new Uint8Array(h.buffer), nb, d); const c = new DataView(new ArrayBuffer(46)); c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(8, 0x0800, true); c.setUint32(16, crc, true); c.setUint32(20, d.length, true); c.setUint32(24, d.length, true); c.setUint16(28, nb.length, true); c.setUint32(42, off, true); cen.push(new Uint8Array(c.buffer), nb); off += 30 + nb.length + d.length; }
  const cs = cen.reduce((a, b) => a + b.length, 0), e = new DataView(new ArrayBuffer(22)); e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true); e.setUint32(12, cs, true); e.setUint32(16, off, true);
  return new Blob([...parts, ...cen, new Uint8Array(e.buffer)], { type: "application/zip" }); }
async function sha(text) { try { const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)); return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join(""); } catch (_) { return "unavailable in this browser context"; } }
$("gen").onclick = async () => { $("genOut").textContent = "Building…"; const R = ROLES[role], files = [];
  for (const f of R[3]) { try { const r = await fetch("data/stakeholder/" + FILES[f][0]); if (r.ok) files.push([FILES[f][0], await r.text()]); } catch (_) { } }
  const rec = scenarioRecord(), body = JSON.stringify(rec, null, 1); rec.sha256_of_content = await sha(body); files.push(["my_scenario.json", JSON.stringify(rec, null, 1)]);
  files.push(["my_scenario_zones.geojson", JSON.stringify({ type: "FeatureCollection", data_source: S.source, features: rec.zones.map(z => ({ type: "Feature", geometry: { type: "Polygon", coordinates: [[[z.bbox[0], z.bbox[1]], [z.bbox[2], z.bbox[1]], [z.bbox[2], z.bbox[3]], [z.bbox[0], z.bbox[3]], [z.bbox[0], z.bbox[1]]]] }, properties: { zone: z.zone, status: z.status, baseline_mm: z.baseline_mm, scenario_mm: z.scenario_mm, horizon_days: H, cells_changed_by_user: z.cells_changed_by_user } })) })]);
  files.push(["README.txt", `SWELL decision package for: ${R[1]}\nSite: ${S.name}\nData source: ${S.source}\nMade: ${rec.made_at_utc}\n\nAction plan\n${R[4](topZone()).map((t, k) => (k + 1) + ". " + t).join("\n")}\n\nFiles\n${files.map(f => "- " + f[0]).join("\n")}\n\nmy_scenario.json holds the exact inputs you set (typed, sliders, cells changed on the map) and the model result per zone.\nmy_scenario_zones.geojson opens in QGIS, ArcGIS or geojson.io.\n\n${rec.safety}\nApproval: ${rec.approval}\n`]);
  if(hydroC){files.push(["water_balance.csv", hydroCsv()]);} files.push(["scenario_zone_results.csv", "zone,status,baseline_mm,scenario_mm,changed_cells\n"+rec.zones.map(z=>[z.zone,z.status,z.baseline_mm??"",z.scenario_mm??"",z.cells_changed_by_user].join(",")).join("\n")]); files.push(["source_notes.txt", "Original stakeholder files are historical site evidence, not recalculated engineering designs. my_scenario files reflect this run. No professional certification.\n"]);
  const a = document.createElement("a"); a.href = URL.createObjectURL(zip(files)); a.download = `SWELL_${role}_package.zip`; a.click(); $("genOut").textContent = `Saved SWELL_${role}_package.zip (${files.length} files).`; };

/* ---------- public, read-only workspace contract for the copilot and scenario shelf ---------- */
function workspaceContext() {
  if (!S || !C) return null;
  const cv = curves(), F = cv.F, base = cv.base[H], scenario = cv.scen[H];
  let selectedCell = null;
  if (sel) {
    const { i, j } = sel, [w, south, east, north] = S.bbox;
    const unresolved = masked(i, j);
    selectedCell = {
      row: i, col: j, zone: zoneOf(i, j),
      lat: north - (i + .5) * (north - south) / n,
      lon: w + (j + .5) * (east - w) / n,
      unresolved,
      observed_los_mm: num(S.observed_los[passK][i][j]),
      inferred_vertical_mm: unresolved ? null : num(S.inferred_motion[passK][i][j]),
      inferred_sd_mm: unresolved ? null : num(S.inferred_sd[passK][i][j]),
      moisture_artifact_mm: num(S.artifact[passK][i][j]),
      coherence: num(S.coh[i][j]), clay_rating_pct: num(S.lep[i][j]),
      paved_fraction: num(S.paved[i][j])
    };
  }
  const changed = Array.from({length:n*n}, (_,c)=>c).filter(c=>pWater[c]||pDrain[c]||pPave[c]).length;
  return {
    site: S.name, source: S.source, synthetic: /SYNTH/i.test(S.source || ""),
    sample_demo_enabled: sampleDemoEnabled, can_simulate: !/SYNTH/i.test(S.source || "") || sampleDemoEnabled,
    bbox: S.bbox, grid_n: n, pass_count: S.pass_days.length,
    pass_index: passK, pass_day: S.pass_days[passK], active_step: step,
    active_state: state, role: ROLES[role]?.[1] || role, horizon_days: H, day_ahead: dayA,
    focus: F.label, focus_key: F.cells.map(([i,j])=>i*n+j).sort((a,b)=>a-b).join(","), selected_cell: selectedCell,
    scenario: { ...G, engine, model_version: hydroC ? SwellHydro.VERSION : "original-fitted", weather_source: weatherForcing?.source || null,
      weather_retrieved_utc: weatherForcing?.retrieved_utc || null,
      forcing_key: weatherForcing ? `${weatherForcing.source || "unknown"}|${weatherForcing.retrieved_utc || "unknown"}` : "manual/no-weather-forcing",
      changed_cells: changed },
    metrics: { baseline_mm: Number.isFinite(base) ? base : null, scenario_mm: Number.isFinite(scenario) ? scenario : null,
      delta_mm: Number.isFinite(base) && Number.isFinite(scenario) ? scenario-base : null },
    uncertainty: hydroC ? { status:"uncalibrated_screening", interval_available:false, note:"Parameter sensitivity is not a probability interval." }
      : { status:"fit_error_only", interval_available:false, training_rmse_reference_mm:S.params.rmse_train,
          note:"Training residual RMSE is not a calibrated forecast interval." }
  };
}
function previewScenario(text) {
  const parsed = M.parseRequest(String(text || ""));
  return { ...parsed, eligible: !parsed.ignored && !!S && (!/SYNTH/i.test(S.source || "") || sampleDemoEnabled) };
}
function applyScenarioSettings(settings, understood=[]) {
  if (!S) throw new Error("The Earth workspace is still loading.");
  if (/SYNTH/i.test(S.source || "") && !sampleDemoEnabled) throw new Error("No real site twin is loaded. Enable the synthetic sample explicitly for a demonstration, or connect a real NISAR site first.");
  const o = settings || {};
  if (Number.isFinite(Number(o.rainMm))) G.rainMm = Math.max(0,Math.min(250,Number(o.rainMm)));
  if (Number.isFinite(Number(o.rainDays))) G.rainDays = Math.max(1,Math.min(14,Math.round(Number(o.rainDays))));
  if (Number.isFinite(Number(o.dryDays))) G.dryDays = Math.max(0,Math.min(30,Math.round(Number(o.dryDays))));
  if (Number.isFinite(Number(o.reduction))) G.reduction = Math.max(0,Math.min(.8,Number(o.reduction)));
  if (Number.isFinite(Number(o.pavedDelta))) G.pavedDelta = Math.max(0,Math.min(.6,Number(o.pavedDelta)));
  const maxH = weatherForcing && engine === "hydro" ? weatherForcing.daily.length : 90;
  H = Math.max(10, Math.min(maxH, Math.round(Number(o.horizon) || H)));
  dayA = H; state = "scenario"; syncSliders(); rerun(); setStep("simulate", true);
  return { understood, context: workspaceContext() };
}
function captureScenario(name, note="") {
  if (!S || !C) throw new Error("No site data is loaded yet.");
  const cv = curves(), changed = Array.from({length:n*n},(_,c)=>c).filter(c=>pWater[c]||pDrain[c]||pPave[c]).length;
  return {
    id: (crypto?.randomUUID ? crypto.randomUUID() : "scn-"+Date.now()+"-"+Math.random().toString(16).slice(2)),
    name: String(name || "Untitled scenario").trim().slice(0,80) || "Untitled scenario",
    note: String(note || "").slice(0,1200), saved_at: new Date().toISOString(),
    site: S.name, source: S.source, synthetic: /SYNTH/i.test(S.source || ""),
    engine, model_version: hydroC ? SwellHydro.VERSION : "original-fitted",
    forcing_key: weatherForcing ? `${weatherForcing.source || "unknown"}|${weatherForcing.retrieved_utc || "unknown"}` : "manual/no-weather-forcing",
    horizon_days:H, role: ROLES[role]?.[1] || role,
    inputs: { ...G }, changed_cells: changed,
    selected_cell: sel ? { i:sel.i, j:sel.j } : null,
    focus_cells: cv.F.cells.map(([i,j])=>i*n+j),
    focus_key: cv.F.cells.map(([i,j])=>i*n+j).sort((a,b)=>a-b).join(","),
    metrics: { baseline_mm:cv.base[H], scenario_mm:cv.scen[H], delta_mm:cv.scen[H]-cv.base[H], focus:cv.F.label },
    uncertainty: hydroC ? "Uncalibrated water-balance screening; no predictive interval." : "Training RMSE is a fit diagnostic, not a calibrated predictive interval.",
    weather_forcing: weatherForcing ? { source:weatherForcing.source, retrieved_utc:weatherForcing.retrieved_utc, daily:weatherForcing.daily } : null,
    arrays: { water:Array.from(pWater), drain:Array.from(pDrain), pave:Array.from(pPave) }
  };
}
function restoreScenario(snapshot) {
  if (!S || !snapshot || snapshot.site !== S.name || snapshot.source !== S.source) throw new Error("This scenario belongs to a different site or data source. Open its original site before loading it.");
  const size=n*n, a=snapshot.arrays||{};
  for (const k of ["water","drain","pave"]) if (!Array.isArray(a[k]) || a[k].length !== size || a[k].some(v=>!Number.isFinite(Number(v)))) throw new Error("Scenario snapshot is incomplete or invalid.");
  pWater.set(a.water); pDrain.set(a.drain); pPave.set(a.pave);
  const v=snapshot.inputs||{};
  G.rainMm=Math.max(0,Math.min(250,Number(v.rainMm)||0));
  G.rainDays=Math.max(1,Math.min(14,Math.round(Number(v.rainDays)||2)));
  G.dryDays=Math.max(0,Math.min(30,Math.round(Number(v.dryDays)||0)));
  G.reduction=Math.max(0,Math.min(.8,Number(v.reduction)||0));
  G.pavedDelta=Math.max(0,Math.min(.6,Number(v.pavedDelta)||0));
  engine = snapshot.engine === "hydro" ? "hydro" : "legacy";
  if ($("engine")) $("engine").value=engine;
  if ($("gwLabel")) $("gwLabel").hidden=engine!=="hydro";
  weatherForcing = snapshot.weather_forcing || null;
  if (snapshot.selected_cell && Number.isInteger(snapshot.selected_cell.i) && Number.isInteger(snapshot.selected_cell.j) && snapshot.selected_cell.i>=0 && snapshot.selected_cell.i<n && snapshot.selected_cell.j>=0 && snapshot.selected_cell.j<n) {
    sel={i:snapshot.selected_cell.i,j:snapshot.selected_cell.j};
    const [w,s,ee,nn]=S.bbox,dx=(ee-w)/n,dy=(nn-s)/n;
    selEnt.rectangle.coordinates=Cesium.Rectangle.fromDegrees(w+sel.j*dx,nn-(sel.i+1)*dy,w+(sel.j+1)*dx,nn-sel.i*dy);selEnt.show=true;
  } else { sel=null; selEnt.show=false; }
  H=Math.max(10,Math.min(weatherForcing && engine==="hydro" ? weatherForcing.daily.length : 90,Math.round(snapshot.horizon_days||30)));
  dayA=H; state="scenario"; syncSliders(); rerun(); setStep("simulate",true);
  return workspaceContext();
}
window.SWELL_WORKSPACE = {
  getContext: workspaceContext, getSite: () => S || null,
  previewScenario, applyScenario: applyScenarioSettings,
  captureScenario, restoreScenario,
  setStep: (name) => setStep(name, true),
  getResearchAnswer: (question) => S && window.SwellResearch ? window.SwellResearch.answer(S, question) : null
};

/* ---------- live connection vs loaded-study status ---------- */
async function refreshDataStatus() {
  const b=$("dataStatus"); if(!b)return;
  if(window.SWELL_PUBLIC){const real=S&&!/SYNTH/i.test(S.source||"");b.textContent=real?`REAL STUDY · ${S.pass_days.length} PASSES · PUBLIC REPLAY`:"PUBLIC REPLAY";b.className="small "+(real?"ready":"warn");b.title="Read-only copy of the twin built from NASA NISAR data. Rebuilding, saving decisions and Ask SWELL run in the local app.";b.onclick=()=>setStep("verify");return;}
  try {
    const r=await fetch("/api/system/health",{cache:"no-store"}); const h=await r.json(); if(!r.ok)throw Error(h.error||"status unavailable");
    const real=!!h.site?.real_site_loaded, inMemorySynthetic=!!S&&/SYNTH/i.test(S.source||"");
    if(real&&inMemorySynthetic){b.textContent="REAL SITE BUILT · RELOAD TO LOAD";b.className="small warn";b.title="The server has a real site file, but this browser tab still has the previous synthetic fixture in memory. Click to reload.";b.onclick=()=>location.reload();}
    else if(real){b.textContent=`REAL STUDY · ${h.site.pass_count} PASSES`;b.className="small ready";b.title=`${h.site.name} · ${h.site.source} · ${h.connections?.ok_count??"?"}/${h.connections?.total_count??"?"} source checks passed · ${h.next_step}`;b.onclick=()=>setStep("studio");}
    else {const c=h.connections;b.textContent=c?`NO REAL SITE · ${c.ok_count}/${c.total_count} SOURCES OK`:"NO REAL SITE · CONNECT + BUILD";b.className="small warn";b.title=(h.next_step||"Provider connectivity does not mean data are loaded. Open Connections and build a real study.")+(c?.results?.filter(x=>x.status!=="ok").map(x=>`${x.name}: ${x.detail}`).join("\n")||"");b.onclick=()=>location.href="connections.html";}
  } catch(e) {b.textContent="DATA STATUS UNAVAILABLE";b.className="small warn";b.title=e.message;b.onclick=()=>location.href="connections.html";}
}
window.addEventListener("focus",refreshDataStatus);
setInterval(refreshDataStatus,15000);

/* ---------- start ---------- */
fetch("data/site.json").then(r => r.json()).then(d => {
  S = d; n = S.n; pWater = new Float32Array(n * n); pDrain = new Float32Array(n * n); pPave = new Float32Array(n * n); passK = S.pass_days.length - 1;
  const [w, s, e, nn] = S.bbox; overlay.rectangle.coordinates = Cesium.Rectangle.fromDegrees(w, s, e, nn);
  outline.polyline.positions = Cesium.Cartesian3.fromDegreesArrayHeights([w, s, 20, e, s, 20, e, nn, 20, w, nn, 20, w, s, 20]);
  $("siteCard").innerHTML = `<b>📍 ${esc(S.name)}</b><div class="small mute">${((s + nn) / 2).toFixed(3)}°, ${((w + e) / 2).toFixed(3)}° · ${n}×${n} cells · ${S.pass_days.length} radar passes</div><span class="pill ${/SYNTH/i.test(S.source) ? "syn" : ""}">${esc(S.source.slice(0, 40))}</span>`;
  siteMarker=viewer.entities.add({ position: Cesium.Cartesian3.fromDegrees((w + e) / 2, (s + nn) / 2), point: { pixelSize: 11, color: Cesium.Color.fromCssColorString("#22c55e"), outlineColor: Cesium.Color.WHITE, outlineWidth: 2, distanceDisplayCondition: new Cesium.DistanceDisplayCondition(1.2e6, 1e9) }, label: { text: S.name + " · press Site to zoom in", font: "600 13px system-ui", fillColor: Cesium.Color.WHITE, showBackground: true, backgroundColor: Cesium.Color.fromCssColorString("#081522"), pixelOffset: new Cesium.Cartesian2(0, -26), distanceDisplayCondition: new Cesium.DistanceDisplayCondition(1.2e6, 1e9) } });
  miniSiteMarker=mini.entities.add({ position: Cesium.Cartesian3.fromDegrees((w + e) / 2, (s + nn) / 2), point: { pixelSize: 9, color: Cesium.Color.fromCssColorString("#22c55e"), outlineColor: Cesium.Color.WHITE, outlineWidth: 2 } });
  mini.camera.setView({ destination: Cesium.Cartesian3.fromDegrees((w + e) / 2, (s + nn) / 2 - 8, 1.25e7) }); mini.scene.requestRender();
  viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees((w+e)/2,(s+nn)/2,1.5e7) });
  buildSteps(); buildLayers(); buildSliders(); buildPasses(); fillRoles(); initTwin(); compute(); loadQuakes(); liveTag();
  const sampleButton=$("sampleMode");
  if (/SYNTH/i.test(S.source)) {
    sampleDemoEnabled=false; document.body.classList.add("no-sample-twin"); overlay.show=outline.show=false;
    if(siteMarker)siteMarker.show=false;if(miniSiteMarker)miniSiteMarker.show=false;
    viewer.camera.setView({destination:Cesium.Cartesian3.fromDegrees(0,0,2.15e7)});
    if(sampleButton){sampleButton.hidden=!/[?&](dev|demo)=1/.test(location.search);sampleButton.textContent="Developer: show test fixture";sampleButton.onclick=()=>setSampleDemo(!sampleDemoEnabled);} // synthetic fixture is for tests only; never shown unless ?dev=1
    if($("siteCard"))$("siteCard").innerHTML=`<b>🌍 Global Earth context</b><div class="small mute">Live-source imagery and event feeds · no local ground-motion twin loaded</div><span class="pill">REAL CONTEXT FEEDS</span><div class="small" style="margin-top:5px"><a href="connections.html"><b>Connect data and build a real study →</b></a></div>`;
    setStep("explore",true);
  } else {
    sampleDemoEnabled=true; overlay.show=outline.show=true;if(siteMarker)siteMarker.show=true;if(miniSiteMarker)miniSiteMarker.show=true; if(sampleButton)sampleButton.hidden=true; setStep("studio",true); setView("map");
  }
  renderInsightPins();
  window.dispatchEvent(new CustomEvent("swell:ready", { detail: workspaceContext() }));
  refreshDataStatus();
}).catch(err => { $("right").innerHTML = `<div class="warn">Could not load data/site.json (${esc(err.message)}). Start the app with <code>python run_swell.py</code>, or run <code>python -m swell.validate</code> first.</div>`; });
