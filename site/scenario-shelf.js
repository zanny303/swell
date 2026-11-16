/* Save, compare and restore explicit scenario branches. Stored locally in this browser only. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id), KEY = 'swell.scenarioShelf.v1', LIMIT = 6;
  const tabs = $('bottomTabs'), bottom = $('bottom');
  if (!tabs || !bottom || !bottom.querySelector('[data-bottom-panel="scenario"]')) return;
  let memory = [];
  const safe = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const read = () => { try { const a = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(a) ? a.slice(0,LIMIT) : []; } catch (_) { return memory; } };
  const write = a => { memory = a.slice(0,LIMIT); try { localStorage.setItem(KEY, JSON.stringify(memory)); return true; } catch (_) { return false; } };
  const btn = document.createElement('button'); btn.type='button'; btn.dataset.bottomTab='shelf'; btn.setAttribute('aria-selected','false'); btn.textContent='Scenario shelf'; tabs.append(btn);
  const panel = document.createElement('div'); panel.className='card'; panel.dataset.bottomPanel='shelf'; panel.hidden=true;
  panel.innerHTML = `<div id="swellShelf">
    <section class="ss-col"><h2>Save a decision alternative</h2><p class="mute small">Freeze the current inputs, painted cells, forecast forcing and model outputs so alternatives can be compared on the same study site.</p>
      <label class="small">Scenario name<input id="ssName" value="Alternative 1" maxlength="80" placeholder="e.g. Drainage + native planting"></label>
      <label class="small" style="display:block;margin-top:8px">Decision note<textarea id="ssNote" maxlength="1200" placeholder="Why are you considering this option? What evidence or stakeholder concern motivates it?"></textarea></label>
      <div class="ss-actions" style="margin-top:8px"><button id="ssSave" type="button">Save current alternative</button><button id="ssExport" type="button">Export comparison JSON</button></div>
      <p id="ssStatus" class="ss-note" aria-live="polite">Saved alternatives stay in this browser profile. They are not shared with other stakeholders.</p>
      <div class="warn" style="margin-top:8px">A saved scenario is a model branch, not an approved intervention. The review status is local and unauthenticated.</div>
    </section>
    <section class="ss-col"><h2>Compare alternatives</h2><div id="ssList" class="ss-list"></div><div id="ssCompare"></div>
      <hr style="border:0;border-top:1px solid var(--line);margin:14px 0">
      <h2>Stakeholder decision record</h2>
      <p class="mute small">Append the current scenario and rationale to the local, hash-chained decision ledger. This is shared by browser sessions on this computer, not authenticated multi-user cloud governance.</p>
      <label class="small">Reviewer / team<input id="ssActor" maxlength="100" placeholder="e.g. Flood resilience team"></label>
      <label class="small" style="display:block;margin-top:7px">Workflow status<select id="ssDecisionStatus"><option value="proposed">Proposed</option><option value="reviewed">Reviewed</option><option value="approved_by_user">Approved by me / team</option><option value="rejected">Rejected</option><option value="action_started">Action started</option><option value="verified">Verified with new evidence</option></select></label>
      <label class="small" style="display:block;margin-top:7px">Decision / next action<input id="ssDecision" maxlength="160" placeholder="e.g. Commission a field soil-moisture survey"></label>
      <label class="small" style="display:block;margin-top:7px">Rationale<textarea id="ssRationale" maxlength="4000" placeholder="Why this option? Which evidence, uncertainties and stakeholder concerns were considered?"></textarea></label>
      <label class="small" style="display:block;margin-top:7px">Evidence IDs (comma separated)<input id="ssEvidence" maxlength="800" placeholder="SITE-METADATA, T1-GPS, FIELD-OBS-01"></label>
      <div class="ss-actions" style="margin-top:8px"><button id="ssRecordDecision" type="button">Record decision</button><button id="ssVerifyLedger" type="button">Verify ledger integrity</button></div>
      <p id="ssLedgerStatus" class="ss-note" aria-live="polite">No decision records loaded.</p><div id="ssLedgerList" class="ss-list"></div>
      <p class="ss-note">“Approved by me / team” records a human workflow decision only. It is not a licensed engineering approval, safety certification, permit, or authorization to construct.</p>
    </section>
  </div>`;
  bottom.append(panel);
  const activate = name => {
    for (const b of tabs.querySelectorAll('[data-bottom-tab]')) { const on=b.dataset.bottomTab===name; b.setAttribute('aria-selected',String(on)); b.classList.toggle('active',on); }
    for (const p of bottom.querySelectorAll('[data-bottom-panel]')) { const on=p.dataset.bottomPanel===name; p.hidden=!on; p.classList.toggle('active',on); }
  };
  tabs.addEventListener('click', e => { const b=e.target.closest('[data-bottom-tab]'); if (b) { activate(b.dataset.bottomTab); if (b.dataset.bottomTab==='shelf') render(); } });
  function fmt(v) { return v!==null && v!==undefined && Number.isFinite(Number(v)) ? Number(v).toFixed(1) : '—'; }
  async function renderLedger(ctx) {
    const status=$('ssLedgerStatus'), list=$('ssLedgerList');
    if (!status || !list) return;
    try {
      const url='/api/decisions?limit=20'+(ctx?.site?'&site='+encodeURIComponent(ctx.site):'');
      const r=await fetch(url); const d=await r.json(); if(!r.ok)throw Error(d.error||`HTTP ${r.status}`);
      const v=d.integrity||{}; status.textContent=`${v.records_checked||0} records · hash-chain ${v.valid?'verified':'FAILED'} · ${v.note||'local ledger'}`;
      list.replaceChildren();
      for(const x of (d.records||[])){
        const a=document.createElement('article');a.className='ss-item';
        const h=document.createElement('strong');h.textContent=`${x.status.replaceAll('_',' ')} · ${x.decision}`;a.append(h);
        const meta=document.createElement('div');meta.className='ss-meta';meta.textContent=`${x.site_name} · ${x.role} · ${x.actor} · ${new Date(x.created_at_utc).toLocaleString()}${x.synthetic?' · SYNTHETIC':''}`;a.append(meta);
        const p=document.createElement('p');p.textContent=x.rationale;a.append(p);
        const hash=document.createElement('div');hash.className='ss-meta';hash.textContent=`SHA-256 ${String(x.record_hash||'').slice(0,20)}… · ${x.evidence_ids?.length||0} evidence ID(s)`;a.append(hash);
        list.append(a);
      }
      if(!(d.records||[]).length){const empty=document.createElement('div');empty.className='ss-empty';empty.textContent='No stakeholder decisions recorded yet.';list.append(empty);}
    } catch(e) { status.textContent=`Decision ledger unavailable: ${e.message}. Start SWELL with python run_swell.py on this computer.`; list.replaceChildren(); }
  }
  $('ssRecordDecision').addEventListener('click',async()=>{
    const w=window.SWELL_WORKSPACE,ctx=w?.getContext?.(),status=$('ssLedgerStatus');
    if(!ctx){status.textContent='The active site is not ready.';return;}
    try{
      const scenario=w.captureScenario($('ssName').value,$('ssNote').value);
      const payload={actor:$('ssActor').value,role:ctx.role,status:$('ssDecisionStatus').value,decision:$('ssDecision').value,
        rationale:$('ssRationale').value,evidence_ids:$('ssEvidence').value.split(',').map(x=>x.trim()).filter(Boolean),scenario};
      status.textContent='Recording decision…';
      const r=await fetch('/api/decisions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();if(!r.ok)throw Error(d.error||`HTTP ${r.status}`);
      status.textContent=`Recorded ${d.id.slice(0,8)} · sequence ${d.sequence} · hash ${d.record_hash.slice(0,16)}…`;
      await renderLedger(ctx);
    }catch(e){status.textContent=`Not recorded: ${e.message}`;}
  });
  $('ssVerifyLedger').addEventListener('click',async()=>{
    const status=$('ssLedgerStatus');status.textContent='Verifying…';
    try{const r=await fetch('/api/decisions/verify');const d=await r.json();if(!r.ok)throw Error(d.error||`HTTP ${r.status}`);status.textContent=`${d.valid?'Integrity verified':'INTEGRITY FAILURE'} · ${d.records_checked} records · ${d.head_hash||''}`;}
    catch(e){status.textContent=`Verification unavailable: ${e.message}`;}
  });
  function render() {
    const list=$('ssList'), compare=$('ssCompare'), rows=read(), ctx=window.SWELL_WORKSPACE?.getContext?.();
    list.replaceChildren(); compare.replaceChildren(); renderLedger(ctx);
    if (!ctx) { list.innerHTML='<div class="ss-empty">Waiting for the Earth workspace to finish loading.</div>'; return; }
    if (!rows.length) { list.innerHTML='<div class="ss-empty">No saved alternatives yet. Change the rainfall, drainage, paving or painted map interventions, then save the result here.</div>'; return; }
    const sameSite=rows.filter(x=>x.site===ctx.site && x.source===ctx.source);
    const branchKey=x=>[x.engine,x.model_version||x.engine,x.horizon_days,x.forcing_key||'legacy',x.focus_key||'unknown'].join('|');
    const compareKeyCurrent=[ctx.scenario.engine,ctx.scenario.model_version||ctx.scenario.engine,ctx.horizon_days,ctx.scenario.forcing_key||'legacy',ctx.focus_key||'unknown'].join('|');
    const comparable=sameSite.filter(x=>branchKey(x)===compareKeyCurrent && Math.abs(Number(x.metrics?.baseline_mm)-Number(ctx.metrics?.baseline_mm))<0.05);
    const compatible=comparable;
    for (const x of rows) {
      const item=document.createElement('article'); item.className='ss-item';
      const compatibleHere=x.site===ctx.site && x.source===ctx.source;
      item.innerHTML=`<strong>${safe(x.name)}</strong>${x.synthetic?' <span class="pill syn">SYNTHETIC</span>':''}<div class="ss-meta">${safe(x.site)} · ${safe(x.engine)} / ${safe(x.model_version||x.engine)} · ${x.horizon_days} days · ${new Date(x.saved_at).toLocaleString()}</div>
        <div>Baseline <b>${fmt(x.metrics?.baseline_mm)} mm</b> → alternative <b>${fmt(x.metrics?.scenario_mm)} mm</b> · Δ <b>${fmt(x.metrics?.delta_mm)} mm</b></div>
        <div class="ss-meta">${safe(x.metrics?.focus || '')} · ${Number(x.changed_cells)||0} edited cells</div>
        <div class="ss-actions"><button type="button" data-load="${safe(x.id)}" ${compatibleHere?'':'disabled'}>Load</button><button type="button" data-delete="${safe(x.id)}">Remove</button></div>`;
      list.append(item);
    }
    if (compatible.length) {
      const base=compatible[0].metrics?.baseline_mm;
      const head=document.createElement('div'); head.className='ss-metrics';
      head.innerHTML=`<div><span>Alternatives</span><b>${compatible.length}</b></div><div><span>Shared baseline</span><b>${fmt(base)} mm</b></div><div><span>Current site</span><b style="font-size:11px">${safe(ctx.site)}</b></div>`; compare.append(head);
      const table=document.createElement('table'); table.style.width='100%'; table.style.fontSize='11px'; table.style.borderCollapse='collapse';
      table.innerHTML='<thead><tr><th style="text-align:left;padding:5px">Alternative</th><th>Baseline</th><th>Scenario</th><th>Δ</th><th>Horizon</th></tr></thead>';
      const body=document.createElement('tbody');
      for (const x of compatible) { const tr=document.createElement('tr'); tr.innerHTML=`<td style="padding:5px;border-top:1px solid #294153">${safe(x.name)}</td><td style="text-align:right;border-top:1px solid #294153">${fmt(x.metrics?.baseline_mm)}</td><td style="text-align:right;border-top:1px solid #294153">${fmt(x.metrics?.scenario_mm)}</td><td style="text-align:right;border-top:1px solid #294153">${fmt(x.metrics?.delta_mm)}</td><td style="text-align:right;border-top:1px solid #294153">${Number(x.horizon_days)||'—'} d</td>`; body.append(tr); }
      table.append(body); compare.append(table);
      const note=document.createElement('p'); note.className='ss-note'; note.textContent=`Compared only branches with the same site, source, engine/version, horizon, weather forcing, selected analysis cells and baseline. ${sameSite.length-comparable.length} saved branch(es) are excluded because their conditions differ. Values are model outputs, not calibrated probabilities, engineering designs or cost-benefit rankings.`; compare.append(note);
    } else compare.innerHTML='<div class="ss-empty">No compatible comparison group yet. Save at least one alternative, then save another with the same site, source, model version, horizon, weather forcing and baseline. Different branches can still be loaded individually.</div>';
  }
  $('ssSave').addEventListener('click', () => {
    const w=window.SWELL_WORKSPACE, ctx=w?.getContext?.();
    if (!ctx) { $('ssStatus').textContent='The site twin is not ready yet.'; return; }
    try {
      const x=w.captureScenario($('ssName').value, $('ssNote').value); x.changed_cells=ctx.scenario.changed_cells;
      const rows=read().filter(a=>a.id!==x.id); rows.unshift(x); const ok=write(rows);
      $('ssStatus').textContent=ok?`Saved “${x.name}” locally. ${rows.length} of ${LIMIT} alternatives retained.`:'Browser storage is unavailable; the alternative is kept only for this page session.';
      $('ssName').value=`Alternative ${Math.min(LIMIT,rows.length+1)}`; render();
    } catch(e) { $('ssStatus').textContent=e.message; }
  });
  $('ssList').addEventListener('click', e => {
    const load=e.target.closest('[data-load]'), del=e.target.closest('[data-delete]');
    if (load) { const x=read().find(a=>a.id===load.dataset.load); try { window.SWELL_WORKSPACE.restoreScenario(x); $('ssStatus').textContent=`Loaded “${x.name}”. Review the map, assumptions and validation before acting.`; render(); } catch(err) { $('ssStatus').textContent=err.message; } }
    if (del) { const rows=read().filter(a=>a.id!==del.dataset.delete); write(rows); render(); }
  });
  $('ssExport').addEventListener('click', () => {
    const rows=read(); if (!rows.length) { $('ssStatus').textContent='Save an alternative before exporting.'; return; }
    const blob=new Blob([JSON.stringify({format:'SWELL_SCENARIO_SHELF_V1',exported_at:new Date().toISOString(),scenarios:rows},null,2)],{type:'application/json'});
    const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='SWELL_scenario_comparison.json'; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),1500);
  });
  window.addEventListener('swell:ready', render);
  activate('scenario');
})();
