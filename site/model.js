// The same equations as swell/physics.py, in the browser. Kept in its own file so Node can test it.
(function (root) {
  const K = 0.9, A_HALF = 40;
  function wetness(rain) { let a = 0; return rain.map(p => { a = K * a + p; return a / (a + A_HALF); }); }
  function unitResponse(w, T, tau) {
    let s = w[0]; const out = [];
    for (let t = 0; t < w.length; t++) { const d = w[Math.max(t - tau, 0)]; s = s + (d - s) / T; out.push(s); }
    return out;
  }
  // Returns {days, base[], scen[]} = mean vertical change (mm) from "now", over cells with gain weights g0, g1.
  function scenario(site, o) {
    const H = o.horizon || 30, n = site.rain.length, HH = H;
    const base = site.rain.concat(new Array(H).fill(0)), scen = base.slice();
    const start = n + (o.dryDays || 0), rd = o.rainDays || 2;
    for (let k = 0; k < rd && start + k < scen.length; k++) scen[start + k] += (o.rainMm || 0) / rd;
    if (o.futureRain) for (let t = 0; t < H; t++) scen[n + t] = (o.futureRain[t] || 0) + (scen[n + t] - base[n + t]);
    for (let t = n; t < scen.length; t++) scen[t] *= 1 - (o.reduction || 0);
    const p = site.params, s0 = unitResponse(wetness(base), p.T, p.tau), s1 = unitResponse(wetness(scen), p.T, p.tau);
    const cells = o.cells, g0 = [], g1 = [];
    for (const [i, j] of cells) {
      const lep = site.lep[i][j], pv = site.paved[i][j], pv1 = Math.min(1, pv + (o.pavedDelta || 0));
      g0.push(p.alpha * lep * (1 - p.b * pv)); g1.push(p.alpha * lep * (1 - p.b * pv1));
    }
    const mean = a => a.reduce((x, y) => x + y, 0) / a.length, G0 = mean(g0), G1 = mean(g1), now = n - 1;
    const days = [], b = [], s = [];
    for (let d = 1; d <= HH; d++) { days.push(d); b.push(G0 * (s0[now + d] - s0[now])); s.push(G1 * (s1[now + d] - s0[now])); }
    return { days, base: b, scen: s, G0, G1, bEnd: s0[now + H] - s0[now], sEnd: s1[now + H] - s0[now] };
  }
  // Reasenberg & Jones (1989) generic aftershock rate per day, magnitude >= minMag.
  function aftershockRate(tDays, mainMag, minMag) {
    return Math.pow(10, -1.67 + 0.91 * (mainMag - (minMag || 5))) * Math.pow(tDays + 0.05, -1.08);
  }
  // Turn a typed request into scenario settings. Rule-based on purpose: the words choose the inputs,
  // the equations produce the numbers. Returns {settings, understood[], ignored}.
  function parseRequest(text) {
    const t = " " + text.toLowerCase().replace(/,/g, " ") + " ", o = { rainMm: 0, rainDays: 2, dryDays: 0, reduction: 0, pavedDelta: 0, horizon: 30 }, u = [];
    const num = "(\\d+(?:\\.\\d+)?)";
    let m;
    if ((m = t.match(new RegExp(num + "\\s*(mm|millimet\\w*|cm|in\\b|inch\\w*)[^.;]*?(rain|storm|downpour|precip)"))) || (m = t.match(new RegExp("(rain|storm|downpour)[^.;]*?" + num + "\\s*(mm|millimet\\w*|cm|in\\b|inch\\w*)")))) {
      const v = parseFloat(isNaN(+m[1]) ? m[2] : m[1]), unit = isNaN(+m[1]) ? m[3] : m[2];
      o.rainMm = unit.startsWith("in") ? v * 25.4 : unit === "cm" ? v * 10 : v; u.push(`${o.rainMm.toFixed(0)} mm of rain`);
    } else if (/\b(storm|heavy rain|downpour|flood)/.test(t)) { o.rainMm = 75; u.push("a storm (assumed 75 mm)"); }
    if ((m = t.match(new RegExp("(?:over|in|across|during)\\s+" + num + "\\s*days?")))) { o.rainDays = Math.max(1, Math.round(+m[1])); u.push(`spread over ${o.rainDays} days`); }
    if ((m = t.match(new RegExp("(?:after|following|then)?\\s*" + num + "\\s*(day|week|month)s?\\s*(?:of\\s*)?(?:drought|dry|no rain|without rain)"))) || (m = t.match(new RegExp("(?:drought|dry spell|no rain)[^.;]*?" + num + "\\s*(day|week|month)")))) {
      o.dryDays = Math.round(+m[1] * (m[2] === "week" ? 7 : m[2] === "month" ? 30 : 1)); u.push(`${o.dryDays} dry days first`);
    } else if (/\b(drought|dry spell|no rain)\b/.test(t)) { o.dryDays = 30; u.push("a drought (assumed 30 dry days)"); }
    if ((m = t.match(new RegExp("(?:drain\\w*|gutter\\w*|french drain|grading|membrane|moisture barrier)[^.;]*?" + num + "\\s*(?:%|percent)"))) || (m = t.match(new RegExp(num + "\\s*(?:%|percent)[^.;]*?(?:drain\\w*|less wetting|less water|reduc\\w*|cut)")))) {
      o.reduction = Math.min(.9, +m[1] / 100); u.push(`${(100 * o.reduction).toFixed(0)} % less wetting`);
    } else if (/\b(drain\w*|gutter\w*|grading|membrane|moisture barrier)\b/.test(t)) { o.reduction = .3; u.push("drainage (assumed 30 % less wetting)"); }
    if ((m = t.match(new RegExp("(?:pav\\w*|asphalt|concrete|parking)[^.;]*?" + num + "\\s*(?:%|percent)"))) || (m = t.match(new RegExp(num + "\\s*(?:%|percent)[^.;]*?(?:pav\\w*|asphalt|concrete)")))) {
      o.pavedDelta = Math.min(1, +m[1] / 100); u.push(`${(100 * o.pavedDelta).toFixed(0)} % more paving`);
    } else if (/\b(pave|paving|asphalt|parking lot|subdivision)\b/.test(t)) { o.pavedDelta = .4; u.push("paving (assumed +40 %)"); }
    if ((m = t.match(new RegExp("(?:next|for|over the next|horizon)\\s+" + num + "\\s*(day|week|month)s?\\b(?!\\s*(?:of\\s*)?(?:drought|dry))")))) {
      const h = Math.round(+m[1] * (m[2] === "week" ? 7 : m[2] === "month" ? 30 : 1)); if (h >= 5 && h <= 120 && h !== o.rainDays) { o.horizon = h; u.push(`looking ${h} days ahead`); } }
    if (o.dryDays + o.rainDays + 15 > o.horizon) o.horizon = Math.min(120, o.dryDays + o.rainDays + 20);
    return { settings: o, understood: u, ignored: u.length === 0 };
  }
  // Conservative kinematic upper-bound structure screen. No stiffness or safety model.
  const STRUCTURE_TYPES = {
    "Unreinforced slab on grade": "building", "Stiffened (ribbed) slab": "building",
    "Post-tensioned slab": "building", "Pier and beam (suspended floor)": "building",
    "Flexible pavement (road)": "transport", "Buried pipe (segmented)": "utility"
  };
  function structureScreen(movementMm, kind, spanM, edgeM, edgeReduction) {
    if (!(kind in STRUCTURE_TYPES) || movementMm < 0 || spanM <= 0 || edgeM <= 0 || edgeReduction < 0 || edgeReduction > 1)
      throw new Error("Invalid structure screening inputs");
    const edgeMovementMm = movementMm * (1 - edgeReduction), gradientLengthM = Math.min(spanM, edgeM);
    const distortion = edgeMovementMm / (1000 * gradientLengthM), family = STRUCTURE_TYPES[kind];
    const band = family !== "building" ? null : distortion <= 1/500 ? "below 1/500" :
      distortion <= 1/300 ? "1/500 to 1/300" : distortion <= 1/150 ? "1/300 to 1/150" : "above 1/150";
    return {family, edgeMovementMm, gradientLengthM, distortion, band, oneIn: distortion > 0 ? Math.round(1/distortion) : null,
      status:"SCREENING_SCENARIO_NOT_STRUCTURAL_ANALYSIS"};
  }
  const api = { wetness, unitResponse, scenario, aftershockRate, parseRequest, structureScreen };
  if (typeof module !== "undefined") module.exports = api; else root.SwellModel = api;
})(this);
