/* Evidence-grounded research assistant. No LLM is connected in this build.
   Every statement is derived from the loaded site.json test records; unknowns are stated. */
(function(root){
  const test=(site,prefix)=> (site.tests||[]).find(t=>String(t.name||"").startsWith(prefix));
  const num=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"not available";
  function report(site){
    const t1=test(site,"T1"),t2=test(site,"T2"),t3=test(site,"T3"),t5=test(site,"T5"),ctrl=test(site,"Control");
    const candidates=[];
    if(t3 && Number.isFinite(t3.rmse_no_change)) candidates.push({id:"M0",name:"No-change baseline",rmse:t3.rmse_no_change});
    if(t3 && Number.isFinite(t3.rmse_rain_only)) candidates.push({id:"M1",name:"Rain-only baseline",rmse:t3.rmse_rain_only});
    if(t3 && Number.isFinite(t3.rmse_swell)) candidates.push({id:"M2",name:"SWELL hybrid",rmse:t3.rmse_swell});
    candidates.sort((a,b)=>a.rmse-b.rmse);
    const synthetic=String(site.source||"").toUpperCase().includes("SYNTHETIC");
    return {
      source:site.source||"UNSPECIFIED",synthetic,candidates,best:candidates[0]||null,
      artifact:{beta:site.beta,gpsNaive:t1?.rms_naive_mm,gpsCorrected:t1?.rms_swell_mm,n:t1?.n,passed:t1?.passed},
      clay:{rho:t2?.spearman,nullQuantile:t2?.null_quantile,n:t2?.n,passed:t2?.passed},
      forecast:{coverage:t3?.coverage90,band:t3?.mean_band_mm,rmse:t3?.rmse_swell,gain:t3?.gain_vs_best_baseline,passed:t3?.passed},
      refusal:{kept:t5?.kept_fraction,passed:t5?.passed},
      control:{naive:ctrl?.amp_naive_mm,corrected:ctrl?.amp_corrected_mm,noise:ctrl?.noise_range_mm,passed:ctrl?.passed},
      unresolved:(site.zones||[]).filter(z=>z.status!=="ok").length,
      zoneCount:(site.zones||[]).length,
      passCount:(site.pass_days||[]).length
    };
  }
  function answer(site,question){
    const q=String(question||"").toLowerCase(),r=report(site),ev=[];
    const cite=(s)=>ev.push(s);
    let title,body,limits=[];
    if(/artifact|moist|phase|radar|wet/.test(q)){
      title="Moisture-artifact evidence";
      body=`The fitted moisture-artifact coefficient is ${num(r.artifact.beta)} mm per unit wetness.`;
      if(Number.isFinite(r.artifact.gpsNaive)&&Number.isFinite(r.artifact.gpsCorrected)){
        body+=` In the GPS line-of-sight comparison, RMS error changed from ${num(r.artifact.gpsNaive)} mm before correction to ${num(r.artifact.gpsCorrected)} mm after correction (${r.artifact.n} paired values).`;
        cite("T1 GPS referee");
      }
      if(Number.isFinite(r.control.naive)&&Number.isFinite(r.control.corrected)){
        body+=` Control-ground amplitude changed from ${num(r.control.naive)} mm naive to ${num(r.control.corrected)} mm corrected; estimated reference noise range is ${num(r.control.noise)} mm.`;
        cite("Control ground");
      }
      limits.push("This is evidence from the loaded site's validation record, not proof that every phase change is moisture artifact.");
    } else if(/forecast|predict|performance|rmse|baseline/.test(q)){
      title="Forecast comparison";
      body=r.candidates.length?r.candidates.map(c=>`${c.id} ${c.name}: ${num(c.rmse)} mm RMSE`).join("; "):"No forecast comparison metrics are available in this site file.";
      if(r.forecast.coverage!==undefined)body+=` Nominal model interval coverage is ${num(100*r.forecast.coverage,1)}% with mean 90% band half-width ${num(r.forecast.band)} mm.`;
      if(r.forecast.gain!==undefined)body+=` Reported gain versus the best baseline is ${num(100*r.forecast.gain,1)}%.`;
      cite("T3 Forecast holdout");
      limits.push("Conditional hindcast using realized rainfall; no independent forecast validation. Coverage and interval width must be assessed together. A wider interval can achieve higher coverage without being more informative.");
    } else if(/clay|soil|shrink|swell/.test(q)){
      title="Soil-response evidence";
      body=`The clay-map test reports Spearman correlation ${num(r.clay.rho)} and shuffled-map null quantile ${num(r.clay.nullQuantile,3)} across ${r.clay.n??"an unavailable number of"} cells.`;
      cite("T2 Clay map");
      limits.push("A spatial association does not establish causation. Soil proxy quality, spatial dependence and site transfer remain important.");
    } else if(/gps|gnss|reference|ground truth/.test(q)){
      title="Independent reference comparison";
      body=Number.isFinite(r.artifact.gpsNaive)?`GPS-projected LOS RMS is ${num(r.artifact.gpsNaive)} mm for naive phase-as-motion and ${num(r.artifact.gpsCorrected)} mm after SWELL correction, using ${r.artifact.n} paired values.`:"The loaded file does not contain usable T1 GPS comparison metrics.";
      cite("T1 GPS referee");
      limits.push("GPS comparison is only as reliable as station stability, spatial representativeness, temporal alignment and LOS projection.");
    } else if(/uncertain|confidence|refus|unresolved|quality/.test(q)){
      title="Uncertainty and refusal";
      body=`The refusal test retains ${(100*(r.refusal.kept??0)).toFixed(1)}% of candidate cells. ${r.unresolved} of ${r.zoneCount} zones are unresolved.`;
      if(Number.isFinite(r.forecast.coverage))body+=` Forecast interval coverage is ${num(100*r.forecast.coverage,1)}%.`;
      cite("T5 Refusal");cite("T3 Forecast holdout");
      limits.push("A retained-cell fraction is not a probability of correctness. Forecast calibration must be checked on independent real acquisitions.");
    } else if(/next|improve|real data|nisar|limitation|weak/.test(q)){
      title="Highest-value next validation steps";
      body="1. Process compatible real NISAR GUNW pairs and record product maturity and all applied corrections. 2. Validate LOS motion against independent GNSS projected into the radar geometry. 3. Keep reference and moisture-control areas independent. 4. Compare SWELL against no-change and rain-only baselines on temporal and spatial holdouts. 5. Report missingness, coherence, interval coverage and abstention. 6. Repeat at a second site without refitting before claiming transfer.";
      cite("PREREGISTERED validation protocol");cite("NISAR product provenance manifest");
      limits.push("These are recommended validation steps, not completed results.");
    } else {
      title="What the evidence can answer";
      body=`Loaded site: ${site.name||"unnamed"}; source label: ${r.source}; ${r.passCount} acquisitions; ${r.zoneCount} zones, ${r.unresolved} unresolved. Ask about moisture artifacts, clay response, GPS comparison, forecast performance, uncertainty or next validation steps.`;
      limits.push("This assistant retrieves and summarizes structured validation evidence. It is not a generative LLM and does not infer facts absent from the loaded dataset.");
    }
    if(!r.synthetic && !site.scientific_validity?.approval_allowed) limits.unshift("EXPERIMENTAL: no independent scientific clearance; real radar observations do not establish reliable forecasts or intervention effectiveness.");
    if(r.synthetic)limits.unshift("SYNTHETIC FIXTURE: all reported numerical results are software-validation results, not real NASA observations or field validation.");
    return {title,body,evidence:ev,limitations:limits,source:r.source,synthetic:r.synthetic};
  }
  const api={report,answer};
  if(typeof module!=="undefined"&&module.exports)module.exports=api;else root.SwellResearch=api;
})(this);
