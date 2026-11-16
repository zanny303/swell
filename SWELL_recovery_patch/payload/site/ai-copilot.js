/* Evidence-first copilot: selected-cell context + deterministic model tools + curated RAG.
   Optional local Ollama generation is server-side; this browser code never holds API keys. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id), opener=$('askSwell');
  if (!opener) return;
  const dialog=document.createElement('dialog'); dialog.id='swellCopilot';
  dialog.innerHTML=`<div class="sc-head"><div><h2>SWELL Copilot</h2><p>Ask about this place, the evidence, uncertainty or a possible intervention.</p></div><button id="scClose" type="button" aria-label="Close copilot">✕</button></div>
    <div id="scContext" class="sc-context">Loading active Earth context…</div>
    <div class="sc-quick"><button type="button" data-question="What is the strongest evidence at this site?">Strongest evidence</button><button type="button" data-question="What is uncertain or missing?">Uncertainty & gaps</button><button type="button" data-question="Explain the selected cell.">Explain selected cell</button><button type="button" data-question="What should this stakeholder verify next?">Next verification</button></div>
    <div id="scMessages" class="sc-messages" role="log" aria-live="polite"></div>
    <form id="scForm" class="sc-compose"><textarea id="scInput" rows="2" maxlength="1200" placeholder="Ask a question, or try: What if 80 mm of rain falls over 3 days and drainage cuts wetting by 40%?"></textarea><button type="submit">Send</button></form>
    <div class="sc-foot"><span id="scProviderStatus">Checking AI provider…</span> · Generative AI is optional. Quantitative claims must come from loaded observations and SWELL's scientific engines, never the language model alone.</div>`;
  document.body.append(dialog);
  const messages=$('scMessages'), contextEl=$('scContext'); let pending=null, busy=false, providerStatus=null;
  const ctx = () => window.SWELL_WORKSPACE?.getContext?.() || null;
  async function refreshProvider() {
    try {
      const r=await fetch('/api/ai/status'); providerStatus=await r.json();
      const names={anthropic:'Anthropic Claude',openai:'OpenAI',meta:'Meta Model API',ollama:'Local Ollama',compatible:'Compatible AI endpoint',none:'Evidence-only'};
      $('scProviderStatus').textContent=providerStatus.configured
        ? `${names[providerStatus.provider]||providerStatus.provider} configured · ${providerStatus.model} · ${providerStatus.last_test?.ok?'live generation verified':'live test pending'} · server-side key`
        : 'Evidence + research mode · optional AI provider can be configured in Connections';
    } catch (_) { providerStatus={configured:false}; $('scProviderStatus').textContent='Evidence-only mode · AI provider status unavailable'; }
  }
  function refreshContext() {
    const c=ctx();
    if (!c) { contextEl.textContent='Earth workspace is still loading. No site-specific answer is available yet.'; return; }
    const cell=c.selected_cell?` · ${c.selected_cell.zone} (${c.selected_cell.lat.toFixed(4)}, ${c.selected_cell.lon.toFixed(4)})`: ' · no cell selected';
    contextEl.textContent=`${c.site} · ${c.source}${c.synthetic?' · SYNTHETIC DEMO':''} · ${c.role} · ${c.active_state} · ${c.horizon_days}-day horizon${cell}`;
  }
  function message(role, label, text, extra={}) {
    const box=document.createElement('div'); box.className='sc-msg '+role;
    const head=document.createElement('div'); head.className='sc-label'; head.textContent=label; box.append(head);
    const body=document.createElement('div'); body.textContent=text; box.append(body);
    if (extra.warning) { const w=document.createElement('div'); w.className='sc-warning'; w.textContent=extra.warning; box.append(w); }
    if (extra.sources?.length) { const ul=document.createElement('ul'); ul.className='sc-sources'; for (const s of extra.sources.slice(0,6)) { const li=document.createElement('li'); if(s.url){const a=document.createElement('a');a.href=s.url;a.target='_blank';a.rel='noopener';a.textContent=s.title;li.append(a);}else li.textContent=s.title; const provenance=[s.id,s.file?(s.file+' · word '+(s.word_offset??0)):null,s.score!=null?('BM25 '+s.score):null,s.sha256?('SHA-256 '+String(s.sha256).slice(0,12)+'…'):null].filter(Boolean).join(' · ');if(provenance)li.append(document.createTextNode(' ['+provenance+']'));if(s.note)li.append(document.createTextNode(' — '+s.note));ul.append(li); } box.append(ul); }
    if (extra.actions?.length) { const row=document.createElement('div'); row.className='sc-actions'; for (const a of extra.actions) { const b=document.createElement('button'); b.type='button'; b.textContent=a.label; b.disabled=!!a.disabled; b.addEventListener('click',a.run); row.append(b); } box.append(row); }
    messages.append(box); messages.scrollTop=messages.scrollHeight; return box;
  }
  function fmt(v, unit='') { return v != null && Number.isFinite(Number(v)) ? Number(v).toFixed(2)+unit : 'not available'; }
  function selectedCellAnswer(c) {
    const x=c?.selected_cell; if (!x) return 'Select a cell on the map first. Then ask me to explain the selected cell.';
    if (c?.synthetic) return 'This selected cell belongs to the bundled synthetic software fixture. Its values are deliberately withheld from site-specific answers. Build a real site twin from compatible observations before asking for measured ground movement. I can still explain the relevant science and what evidence to collect.';
    if (x.unresolved) return `${x.zone} is unresolved in the active pass. SWELL deliberately leaves this cell without an inferred movement value. Do not interpolate it or treat a nearby cell as a measurement.`;
    return `${x.zone}, row ${x.row+1}, column ${x.col+1} (${x.lat.toFixed(5)}, ${x.lon.toFixed(5)}):
Observed line-of-sight value: ${fmt(x.observed_los_mm,' mm')}
Inferred vertical movement: ${fmt(x.inferred_vertical_mm,' mm')}
Inferred standard deviation field: ${fmt(x.inferred_sd_mm,' mm')}
Moisture-artifact estimate: ${fmt(x.moisture_artifact_mm,' mm')}
Coherence: ${fmt(x.coherence)}
Clay rating: ${fmt(x.clay_rating_pct,'%')}
Paved fraction: ${fmt(x.paved_fraction)}

The vertical value assumes negligible horizontal motion and is an inference, not a direct vertical measurement. Check acquisition geometry, quality mask, reference stability and independent GNSS before acting.`;
  }
  function scenarioIntent(q) { return !!window.SwellModel && (/\b(what if|simulate|scenario|try|test|apply|set|change|increase|reduce|add|assume)\b/i.test(q) || /\b\d+(?:\.\d+)?\s*(?:mm|cm|inches?)\b.*\b(rain|storm|precipitation)\b/i.test(q)); }
  function preview(q) {
    const w=window.SWELL_WORKSPACE, r=w?.previewScenario?.(q), c=ctx();
    if (!r || r.ignored) return false;
    const summary=r.understood.join('; ') || 'Scenario parameters parsed';
    const s=r.settings;
    const details=`I translated your request into a reviewable scenario:
• Added rain: ${s.rainMm} mm over ${s.rainDays} days
• Dry period first: ${s.dryDays} days
• Reduced wetting from drainage: ${(100*s.reduction).toFixed(0)}%
• Additional paving: ${(100*s.pavedDelta).toFixed(0)}%
• Forecast horizon: ${s.horizon} days

Interpretation: ${summary}.
Nothing has changed yet. Review the assumptions and explicitly apply them if they match your intent.`;
    const warnings=[];
    if (c?.synthetic) warnings.push('The loaded dataset is synthetic. This can only be a labelled software demonstration, not a real-site forecast.');
    warnings.push('This parser uses explicit defaults when you say “storm”, “drought” or “drainage”. Replace assumed values with measured or sourced inputs before relying on the output.');
    if (!r.eligible) warnings.push('No real site twin is loaded. Connect a real site, or explicitly enable the synthetic sample for a software demo.');
    const proposal=r.eligible?{settings:s,understood:r.understood}:null;
    message('assistant','SCENARIO PROPOSAL',details,{warning:warnings.join(' '),actions:[
      {label:'Apply to active twin',disabled:!proposal,run:()=>{try{const result=w.applyScenario(proposal.settings,proposal.understood);message('assistant','MODEL UPDATED',`Scenario applied. The active map, chart and findings have been recomputed. Estimated baseline: ${fmt(result.context.metrics.baseline_mm,' mm')}; scenario: ${fmt(result.context.metrics.scenario_mm,' mm')}; difference: ${fmt(result.context.metrics.delta_mm,' mm')}. These are model outputs, not observations.`,{warning:result.context.synthetic?'Synthetic demonstration only. Do not report as real Earth evidence.':result.context.uncertainty.note});refreshContext();}catch(e){message('assistant','NOT APPLIED',e.message);} }},
      {label:'Open scenario shelf',run:()=>{dialog.close();const b=document.querySelector('[data-bottom-tab="shelf"]');b?.click();}}
    ]});
    return true;
  }
  async function post(path, payload) {
    const ctl=new AbortController(), timer=setTimeout(()=>ctl.abort(),path==='/api/ai/chat'?255000:25000);
    try { const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:ctl.signal}); const d=await r.json(); if(!r.ok)throw Error(d.error||`HTTP ${r.status}`); return d; }
    finally { clearTimeout(timer); }
  }
  async function answer(q) {
    const c=ctx(), w=window.SWELL_WORKSPACE, site=w?.getSite?.();
    if (providerStatus?.configured) {
      try {
        const ai=await post('/api/ai/chat',{question:q,context:{
          role:c?.role||'stakeholder', active_state:c?.active_state||'unknown', horizon_days:c?.horizon_days,
          pass_index:c?.pass_index??0,
          site:c?.site, source:c?.source, synthetic:!!c?.synthetic,
          selected_cell:!c?.synthetic&&c?.selected_cell?{row:c.selected_cell.row,col:c.selected_cell.col}:null,
          scenario_summary:!c?.synthetic&&c?{engine:c.scenario?.engine,model_version:c.scenario?.model_version,horizon_days:c.horizon_days,
            baseline_mm:c.metrics?.baseline_mm,scenario_mm:c.metrics?.scenario_mm,delta_mm:c.metrics?.delta_mm,
            changed_cells:c.scenario?.changed_cells,uncertainty:c.uncertainty?.status}:null
        }});
        const actions=[];
        if (ai.proposal?.proposal) {
          const proposal=ai.proposal.proposal, rationale=ai.proposal.rationale||'AI scenario proposal';
          actions.push({label:'Review & apply proposal',disabled:!c?.can_simulate,run:()=>{
            try { const result=w.applyScenario(proposal,[`AI proposal ${ai.proposal.proposal_id}`,rationale]);
              message('assistant','SCENARIO APPLIED',`The proposal was applied after your explicit confirmation. Baseline ${fmt(result.context.metrics.baseline_mm,' mm')}; scenario ${fmt(result.context.metrics.scenario_mm,' mm')}; difference ${fmt(result.context.metrics.delta_mm,' mm')}. These remain model outputs, not observations.`,{warning:result.context.uncertainty.note});refreshContext();
            } catch(e) { message('assistant','NOT APPLIED',e.message); }
          }});
        }
        message('assistant',`${String(ai.provider||'AI').toUpperCase()} · EVIDENCE REVIEW`,ai.answer||'No answer returned.',{
          sources:ai.sources||[], warning:[ai.warning,c?.synthetic?'The active site is a synthetic fixture; do not report its values as real Earth observations.':null,
            ai.proposal?'A scenario proposal is a draft only. The model has not been run or changed.':null].filter(Boolean).join(' '), actions
        });
        return;
      } catch(e) {
        message('assistant','AI PROVIDER UNAVAILABLE',`${e.message}. No model inputs have changed. Try the question again after checking the provider. Evidence-only retrieval is available by selecting that mode in Connections.`);
        await refreshProvider(); return;
      }
    }
    if (/\b(selected cell|this cell|explain (the )?cell|what am i looking at here)\b/i.test(q)) {
      const t=selectedCellAnswer(c); message('assistant','ACTIVE MAP CONTEXT',t,{warning:c?.synthetic?'Synthetic fixture: this is not a real NISAR measurement.':null}); return;
    }
    if (/\b(current scenario|this scenario|what does (this|my) scenario|compare (the )?baseline)\b/i.test(q) && c) {
      if (c.synthetic) { message('assistant','NO REAL STUDY LOADED','The active study is the bundled synthetic software fixture. Its scenario numbers are not site evidence and are withheld from decision answers. Build a real site twin from compatible observations first.'); return; }
      const t=`Current site: ${c.site} (${c.source})\nFocus: ${c.focus}\nHorizon: ${c.horizon_days} days\nBaseline: ${fmt(c.metrics.baseline_mm,' mm')}\nScenario: ${fmt(c.metrics.scenario_mm,' mm')}\nDifference: ${fmt(c.metrics.delta_mm,' mm')}\nEdited cells: ${c.scenario.changed_cells}\nEngine: ${c.scenario.engine}\nUncertainty: ${c.uncertainty.note}`;
      message('assistant','LIVE MODEL STATE',t,{warning:'Scenario outputs are conditional on the current inputs and are not certified design results.'}); return;
    }
    const local=!c?.synthetic&&site&&window.SwellResearch?window.SwellResearch.answer(site,q):null;
    let research=null, rag=null;
    const jobs=[post('/api/site-twin/literature',{question:q})];
    if(!c?.synthetic) jobs.push(post('/api/site-twin/research',{question:q}));
    const fetched=await Promise.allSettled(jobs);
    if(c?.synthetic) { if(fetched[0].status==='fulfilled')rag=fetched[0].value; }
    else { if(fetched[0].status==='fulfilled')rag=fetched[0].value; if(fetched[1]?.status==='fulfilled')research=fetched[1].value; }
    const pieces=[];
    if (local?.body) pieces.push(local.body);
    if (rag?.draft) pieces.push(`Optional local-model draft (unverified):\n${rag.draft}`);
    else if (rag?.status) pieces.push(rag.status);
    if (research?.saved_run_evidence) pieces.push(`Saved run ${research.saved_run_evidence.run_id}: baseline ${fmt(research.saved_run_evidence.final_baseline)}; intervention ${fmt(research.saved_run_evidence.final_intervention)}.`);
    const sources=[];
    for (const x of (research?.sources||[])) sources.push({id:x.id,title:x.title,url:x.url,note:x.curated_note,file:x.file,sha256:x.sha256,word_offset:x.word_offset,score:x.score});
    for (const x of (rag?.sources||[])) if (!sources.some(s=>s.url===x.url)) sources.push({id:x.id,title:x.title,url:x.url,note:x.text,file:x.file,sha256:x.sha256,word_offset:x.word_offset,score:x.score});
    const warning=[];
    if (c?.synthetic) warning.push('No real study site is loaded. The bundled synthetic fixture is excluded from this answer; only general research context is available.');
    if (local?.limitations) warning.push(local.limitations);
    if (research?.method) warning.push(research.method);
    if (rag?.status && /unverified|draft/i.test(rag.status)) warning.push('Local-model wording is an unverified explanatory draft. Check every scientific claim against the linked source and the active data record.');
    if (!pieces.length) pieces.push('I could not retrieve enough relevant evidence to answer that confidently. Try asking about the active site, NISAR GUNW/GCOV, soil moisture, the model assumptions, forecast uncertainty or a stakeholder verification step.');
    message('assistant','EVIDENCE REVIEW',pieces.join('\n\n'),{warning:warning.join(' '),sources});
  }
  async function submit(q) {
    q=String(q||'').trim(); if (!q || busy) return; busy=true; $('scInput').value=''; message('user','YOU',q); refreshContext();
    try { await refreshProvider(); if (scenarioIntent(q) && preview(q)) return; await answer(q); }
    catch(e) { message('assistant','RETRIEVAL UNAVAILABLE',`I could not complete the evidence lookup: ${e.message}. The current map and model are unchanged.`); }
    finally { busy=false; refreshContext(); }
  }
  opener.addEventListener('click',()=>{refreshContext();refreshProvider();dialog.showModal();$('scInput').focus();if(!messages.children.length)message('assistant','WELCOME','I can inspect the active evidence, explain uncertainty, retrieve research, and help shape a stakeholder decision. Connect Anthropic, OpenAI, Meta Model API or local Ollama for generative answers; evidence retrieval and scientific models work without an AI key. I never silently change or approve a scenario.');});
  refreshProvider();
  $('scClose').addEventListener('click',()=>dialog.close());
  $('scForm').addEventListener('submit',e=>{e.preventDefault();submit($('scInput').value);});
  dialog.querySelectorAll('[data-question]').forEach(b=>b.addEventListener('click',()=>submit(b.dataset.question)));
  window.addEventListener('swell:ready',refreshContext);
  window.addEventListener('swell:selection',refreshContext);
})();
