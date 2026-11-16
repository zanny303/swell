/* Compare two radar dates with a swipe slider: raw NISAR change, SWELL's clay movement, the false wet-soil signal it removed,
   or NISAR's own brightness change (GCOV). Same colour scale on both sides, so the difference is real, not a rescale. */
(function () {
  const $ = id => document.getElementById(id);
  const css = document.createElement("style");
  css.textContent = `#swDlg{max-width:min(1040px,96vw);width:1040px;background:#0b1622;color:#e6eef4;border:1px solid #23405a;border-radius:14px;padding:16px}
  #swDlg::backdrop{background:#000a}#swWrap{position:relative;width:min(640px,88vw);aspect-ratio:1;margin:10px auto;border:1px solid #23405a;border-radius:10px;overflow:hidden;background:#06111c}
  #swWrap canvas{position:absolute;inset:0;width:100%;height:100%;image-rendering:pixelated}#swLine{position:absolute;top:0;bottom:0;width:2px;background:#fff;box-shadow:0 0 6px #000}
  #swDlg select{background:#122436;color:#e6eef4;border:1px solid #23405a;border-radius:8px;padding:5px}#swDlg .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:center}
  #swTagA,#swTagB{position:absolute;top:8px;background:#0b1622d0;padding:3px 8px;border-radius:6px;font:600 12px system-ui}#swTagA{left:8px}#swTagB{right:8px}
  #swLeg{display:flex;align-items:center;gap:8px;justify-content:center;font-size:12px;color:#9fb3c3}#swBar{width:220px;height:10px;border-radius:5px}`;
  document.head.appendChild(css);
  const LAYERS = {
    obs: ["Raw NISAR change since the first pass (mm)", k => S.observed_los && S.observed_los[k]],
    mov: ["SWELL clay movement (mm)", k => S.inferred_motion && S.inferred_motion[k]],
    art: ["False wet-soil signal SWELL removed (mm)", k => S.artifact && S.artifact[k]],
    gco: ["NISAR brightness change, co-pol (dB)", k => { const g = S.sensors && S.sensors.gcov; if (!g || !g.d_co_db) return null; const d = S.pass_days[k]; let b = 0; g.days.forEach((x, i) => { if (Math.abs(x - d) < Math.abs(g.days[b] - d)) b = i; }); return g.d_co_db[b]; }] };
  let dlg;
  function build() {
    dlg = document.createElement("dialog"); dlg.id = "swDlg";
    const opts = S.pass_days.map((d, k) => `<option value="${k}">pass ${k + 1} · day ${d}</option>`).join("");
    dlg.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center"><b style="font-size:17px">Compare two radar dates</b><button id="swX" type="button">Close</button></div>
      <div class="row" style="margin-top:8px"><select id="swL">${Object.entries(LAYERS).filter(([k, v]) => k !== "gco" || (S.sensors && S.sensors.gcov && S.sensors.gcov.d_co_db)).map(([k, v]) => `<option value="${k}">${v[0]}</option>`).join("")}</select>
      <label>left <select id="swA">${opts}</select></label><label>right <select id="swB">${opts}</select></label></div>
      <div id="swWrap"><canvas id="swCb"></canvas><canvas id="swCa"></canvas><div id="swLine"></div><span id="swTagA"></span><span id="swTagB"></span></div>
      <input id="swR" type="range" min="0" max="100" value="50" style="width:min(640px,88vw);display:block;margin:0 auto" aria-label="Swipe position">
      <div id="swLeg"><span id="swMin"></span><canvas id="swBar" width="220" height="10"></canvas><span id="swMax"></span></div>
      <div class="small mute" style="text-align:center;margin-top:6px">Drag the slider. North is up. Blank cells are where the radar is too unreliable for SWELL to answer.</div>`;
    document.body.appendChild(dlg);
    $("swX").onclick = () => dlg.close(); ["swL", "swA", "swB"].forEach(id => $(id).onchange = draw); $("swR").oninput = clip;
    $("swA").value = 1 < S.pass_days.length ? 1 : 0; $("swB").value = S.pass_days.length - 1;
  }
  function grid(a) { return a ? a.map(r => r.map(v => (v == null || Number.isNaN(+v)) ? NaN : +v)) : null; }
  function paint(cv, g, V) { const n = g.length; cv.width = n; cv.height = n; const x = cv.getContext("2d"), im = x.createImageData(n, n);
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { const v = g[i][j], o = 4 * (i * n + j); if (!Number.isFinite(v)) { im.data[o + 3] = 0; continue; } const c = ramp(.5 + v / (2 * V)); im.data[o] = c[0]; im.data[o + 1] = c[1]; im.data[o + 2] = c[2]; im.data[o + 3] = 255; }
    x.putImageData(im, 0, 0); }
  function draw() { const L = LAYERS[$("swL").value], a = +$("swA").value, b = +$("swB").value, A = grid(L[1](a)), B = grid(L[1](b));
    if (!A || !B) return; const vals = [...A.flat(), ...B.flat()].filter(Number.isFinite).map(Math.abs).sort((p, q) => p - q);
    const V = Math.max(1e-6, vals.length ? vals[Math.floor(.95 * (vals.length - 1))] : 1);
    paint($("swCa"), A, V); paint($("swCb"), B, V); $("swTagA").textContent = "day " + S.pass_days[a]; $("swTagB").textContent = "day " + S.pass_days[b];
    const u = L[0].match(/\((.*)\)/)[1]; $("swMin").textContent = "−" + V.toFixed(1) + " " + u; $("swMax").textContent = "+" + V.toFixed(1) + " " + u;
    const bar = $("swBar").getContext("2d"); for (let x = 0; x < 220; x++) { const c = ramp(x / 219); bar.fillStyle = `rgb(${c})`; bar.fillRect(x, 0, 1, 10); } clip(); }
  function clip() { const p = +$("swR").value; $("swCa").style.clipPath = `inset(0 ${100 - p}% 0 0)`; $("swLine").style.left = `calc(${p}% - 1px)`; }
  function open() { if (typeof S === "undefined" || !S || !S.pass_days) return; if (!dlg) build(); dlg.showModal(); draw(); }
  window.openSwipe = open;
  function addButton() { const t = $("tools"); if (!t || $("swBtn")) return !!t; const b = document.createElement("button"); b.id = "swBtn"; b.type = "button"; b.textContent = "⇆ Compare dates"; b.title = "Swipe between two radar dates";
    b.onclick = open; t.appendChild(b); return true; }
  window.addEventListener("swell:ready", addButton); let tries = 0; const iv = setInterval(() => { if (addButton() || ++tries > 30) clearInterval(iv); }, 1000);
})();
