const assert=require('node:assert/strict'),{compare,simulate,sensitivity}=require('../site/hydro.js');
const rain=Array(90).fill(0),o={H:30,rainMm:120,rainDays:4,depth:3};const base=compare(rain,8,.1,o),end=(r,k)=>r[k].motion.at(-1)-r[k].motion[r.now],sum=(r,k)=>r.scen[k].slice(r.now+1).reduce((x,y)=>x+y,0);
assert(end(base,'scen')>end(base,'base'));assert(Math.max(...base.scen.residual.map(Math.abs))<1e-9);
const drain=compare(rain,8,.1,{...o,drainage:.8});assert(sum(drain,'drain')>0);assert(drain.scen.storage.at(-1)<base.scen.storage.at(-1));
const pave=compare(rain,8,.1,{...o,paving:.8});assert(sum(pave,'infiltration')<sum(base,'infiltration'));assert(sum(pave,'runoff')>sum(base,'runoff'));
const gw=compare(rain,8,.1,{...o,groundwaterRise:3});assert(sum(gw,'capillary')>sum(base,'capillary'));
const zero=compare(rain,8,.1,{H:30,rainMm:0});assert.deepEqual(zero.base.motion,zero.scen.motion);
assert.equal(end(compare(rain,0,.1,o),'scen'),0);assert.equal(base.scen.motion[base.now],base.base.motion[base.now]);
assert.deepEqual(compare(rain,8,.1,o),base);assert.equal(sensitivity(rain,8,.1,o).length,3);
for(const r of [base,drain,pave,gw])for(const s of [r.base,r.scen]){assert(s.wet.every(x=>x>=0&&x<=1+1e-12));assert(Math.max(...s.residual.map(Math.abs))<1e-9)}
console.log('PASS: 12 hydro invariants (mass balance, bounded storage, response direction in controlled cases, zero intervention, reproducibility)');
const weather=compare(rain,8,.1,{H:10,futureRain:Array(10).fill(10),rainMm:0});assert.equal(weather.base.rain.slice(-10).reduce((a,b)=>a+b),100);assert.deepEqual(weather.base.motion,weather.scen.motion);const edit=compare(rain,8,.1,{H:10,futureRain:Array(10).fill(10),rainMm:50,rainDays:2});assert.equal(edit.scen.rain.slice(-10).reduce((a,b)=>a+b),150);assert.throws(()=>compare(rain,8,.1,{H:10,futureRain:[1]}));console.log('PASS: AI-forcing conservation, intervention delta and incomplete forecast rejection');
