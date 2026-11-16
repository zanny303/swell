/* SWELL conservative two-reservoir screening model. No external dependencies.
   Units: mm water, day, m depth, mm ground change. Explicit model assumptions, not calibration. */
(function(root){
'use strict';
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const VERSION='water-balance-1.0';
const defaults={depth:3,thetaMin:.12,thetaMax:.44,fieldCapacity:.28,initialTheta:.22,ks:18,percolation:3,et:2,drainMax:10,capillaryMax:4,groundwaterDepth:5,relaxation:18,restraint:.35};
function simulate(rain,lep,paved,opts={}){
 const p={...defaults,...opts}; const d=clamp(p.depth,.5,10), shallow=Math.min(.3,d/2), deep=d-shallow;
 const cap=[shallow,deep].map(z=>1000*z*(p.thetaMax-p.thetaMin));
 const fc=clamp((p.fieldCapacity-p.thetaMin)/(p.thetaMax-p.thetaMin),0,1);
 let a=cap[0]*clamp((p.initialTheta-p.thetaMin)/(p.thetaMax-p.thetaMin),0,1), b=cap[1]*a/cap[0], u=0;
 const out={motion:[],wet:[],shallow:[],deep:[],rain:[],runoff:[],infiltration:[],et:[],drain:[],recharge:[],capillary:[],residual:[],storage:[]};
 const target=()=>1000*d*(clamp(lep,0,30)/100)*p.restraint*(a+b)/(cap[0]+cap[1]); u=target();
 for(let t=0;t<rain.length;t++){
  const pre=a+b, r=Math.max(0,rain[t]), active=t>=(p.interventionDay??Infinity), pv=clamp(paved+(active?(p.paving||0):0),0,1), dr=active?clamp(p.drainage||0,0,1):0;
  const gw=Math.max(0,p.groundwaterDepth-(active?(p.groundwaterRise||0):0));
  const inf=Math.min(r*(1-pv), p.ks*(1-pv)*(1+.5*(1-a/cap[0])),cap[0]-a); a+=inf;
  const runoff=r-inf;
  const evap=Math.min(a,p.et*(1-pv)*Math.min(1,a/(cap[0]*Math.max(fc,.01)))); a-=evap;
  const transfer=Math.min(a,Math.max(0,a-cap[0]*fc),p.percolation,cap[1]-b); a-=transfer;b+=transfer;
  const up=Math.min(cap[1]-b,p.capillaryMax*Math.exp(-Math.max(0,gw-d)), Math.max(0,cap[1]*fc-b)); b+=up;
  const drain=Math.min(a+b,p.drainMax*dr*Math.max(0,(a+b)/(cap[0]+cap[1]))); const da=Math.min(a,drain);a-=da;b-=drain-da;
  const recharge=Math.min(b,Math.max(0,b-cap[1]*fc),p.percolation);b-=recharge;
  u+=(target()-u)*(1-Math.exp(-1/Math.max(1,p.relaxation)));
  const vals={motion:u,wet:(a+b)/(cap[0]+cap[1]),shallow:p.thetaMin+a/(1000*shallow),deep:p.thetaMin+b/(1000*deep),rain:r,runoff,infiltration:inf,et:evap,drain,recharge,capillary:up,residual:a+b-pre-r-up+runoff+evap+drain+recharge,storage:a+b};
  for(const k of Object.keys(out))out[k].push(vals[k]);
 }
 return out;
}
function compare(rain,lep,paved,opts={}){
 const H=opts.H||30, now=rain.length-1, future=opts.futureRain ? opts.futureRain.slice(0,H) : Array(H).fill(0), scenario=future.slice();
 if(future.length!==H||future.some(x=>!Number.isFinite(x)||x<0))throw Error("Future precipitation must cover every simulated day");
 for(let i=0;i<(opts.rainDays||1);i++){const j=(opts.dryDays||0)+i;if(j<H)scenario[j]+=(opts.rainMm||0)/(opts.rainDays||1);}
 const p={...opts,interventionDay:rain.length}; const base=simulate(rain.concat(future),lep,paved,{...p,paving:0,drainage:0,groundwaterRise:0});
 const scen=simulate(rain.concat(scenario),lep,paved,p);return {now,base,scen};
}
// Deterministic bounded sensitivity, not a probabilistic interval.
function sensitivity(rain,lep,paved,opts){return [.6,1,1.4].map(k=>compare(rain,lep,paved,{...opts,ks:defaults.ks*k,restraint:defaults.restraint*k,relaxation:defaults.relaxation/k})).map(r=>r.scen.motion.at(-1)-r.scen.motion[r.now]);}
const api={VERSION,defaults,simulate,compare,sensitivity}; if(typeof module!=='undefined')module.exports=api;else root.SwellHydro=api;
})(typeof globalThis!=='undefined'?globalThis:this);
