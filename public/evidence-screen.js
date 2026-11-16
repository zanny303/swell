/* SWELL real-input evidence and event water accounting. No displacement inference. */
(function(root){'use strict';
const finite=x=>typeof x==='number'&&Number.isFinite(x)&&x!==-9999;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:null;
function observations(site){
 const stack=site.observed_los||[], k=stack.length-1, n=site.n, rows=[];if(k<1)return rows;
 for(let i=0;i<n;i++)for(let j=0;j<n;j++){
  const a=stack[k-1]?.[i]?.[j],b=stack[k]?.[i]?.[j],q=site.coh?.[i]?.[j];
  if(!finite(a)||!finite(b)||!finite(q)||q<.30||site.reference?.[i]?.[j])continue;
  rows.push({i,j,zone:`Z${Math.floor(i/8)}${Math.floor(j/8)}`,los_mm:b-a,coherence:q});
 }return rows;
}
function budget(rain,paved,capacity,capture){
 if(![rain,paved,capacity,capture].every(finite)||rain<0||capacity<0||paved<0||paved>1||capture<0||capture>1)return null;
 const infiltrated=(1-paved)*Math.min(rain,capacity), gross=rain-infiltrated, captured=gross*capture, excess=gross-captured;
 return {input:rain,infiltrated,captured,excess,residual:rain-infiltrated-captured-excess};
}
function compare(site,settings,paint={},capacityHour=5){
 const n=site.n, storm=Number(settings.rainMm), days=Number(settings.rainDays), cap=capacityHour*24*days, rows=[];
 if(!finite(storm)||storm<0||!finite(days)||days<=0||!finite(cap)||cap<0)return rows;
 for(let i=0;i<n;i++)for(let j=0;j<n;j++){
  const c=i*n+j,pv=site.paved?.[i]?.[j];if(!finite(pv)||pv<0||pv>1)continue;
  const water=Number(paint.water?.[c]||0),rain=storm+water;if(!finite(rain)||rain<0)continue;
  const delta=Number(settings.pavedDelta||0)+Number(paint.pave?.[c]||0),dr=1-(1-Number(settings.reduction||0))*(1-Number(paint.drain?.[c]||0));
  const a=budget(rain,pv,cap,0),b=budget(rain,clamp(pv+delta,0,1),cap,clamp(dr,0,1));if(!a||!b)continue;
  rows.push({i,j,zone:`Z${Math.floor(i/8)}${Math.floor(j/8)}`,baseline:a,scenario:b,delta_mm:b.excess-a.excess});
 }return rows;
}
function zones(obs){const z=new Map();for(const r of obs){if(!z.has(r.zone))z.set(r.zone,[]);z.get(r.zone).push(r);}return [...z].map(([zone,a])=>({zone,cells:a.length,mean_abs_los_mm:avg(a.map(x=>Math.abs(x.los_mm))),coherence:avg(a.map(x=>x.coherence))})).sort((a,b)=>b.mean_abs_los_mm-a.mean_abs_los_mm);}
const api={observations,budget,compare,zones,avg,finite};if(typeof module!=='undefined')module.exports=api;else root.SwellEvidenceScreen=api;
})(typeof globalThis!=='undefined'?globalThis:this);
