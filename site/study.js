/* Verify step: the correction study (compare_corrections.py). Same site, four correction chains, every score shown. */
window.studyHTML = function (S) {
  const st = S && S.correction_study; if (!st || !st.variants) return "";
  const e = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const keys = Object.keys(st.variants), names = [];
  keys.forEach(k => (st.variants[k].tests || []).forEach(t => { if (!names.includes(t.name)) names.push(t.name); }));
  const cell = (v, n) => { const t = (v.tests || []).find(t => t.name === n); if (!t) return '<td class="mute">—</td>';
    return t.passed == null ? '<td class="mute">not run</td>' : t.passed ? '<td class="ok">pass</td>' : '<td class="bad">fail</td>'; };
  const ho = v => { const h = v.heldout || {}; return h.no_change == null ? "" : `<div class="mute" style="font-size:11px">held-out mm: no change ${(+h.no_change).toFixed(1)}, model ${(+(h.physics_informed ?? h.physics_fit)).toFixed(1)}</div>`; };
  return `<h3>Correction study: same data, four processing chains</h3>
  <table><tr><th>Test</th>${keys.map(k => `<th title="${e(st.variants[k].label)}">${k}${k === st.kept ? " ✓" : ""}</th>`).join("")}</tr>
  ${names.map(n => `<tr><td>${e(n)}</td>${keys.map(k => cell(st.variants[k], n)).join("")}</tr>`).join("")}
  <tr><td class="mute">NISAR layers</td>${keys.map(k => { const l = (st.variants[k].nisar_layers || {}); return `<td class="mute" style="font-size:11px">${l.pairs ? (l.variance_removed_pct + " % var.") : "—"}</td>`; }).join("")}</tr></table>
  <div class="small mute">${keys.map(k => `<b>${k}</b> ${e(st.variants[k].label)} (${e(st.variants[k].status)})${ho(st.variants[k])}`).join("<br>")}</div>
  <div class="small mute" style="margin-top:4px">${e(st.rule)} ✓ = what the app shows now.</div>`;
};
