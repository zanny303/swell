const assert=require('node:assert/strict'),E=require('../site/evidence-screen.js');
const S={n:2,paved:[[.4,.7],[null,.2]],observed_los:[[[0,0],[0,0]],[[2,-4],[null,-9999]]],coh:[[.5,.6],[.7,.8]],reference:[[0,0],[0,0]]};
assert.equal(E.observations(S).length,2);assert.equal(E.zones(E.observations(S))[0].mean_abs_los_mm,3);
const rows=E.compare(S,{rainMm:100,rainDays:1,reduction:.5,pavedDelta:0});assert.equal(rows.length,3);
for(const r of rows){assert.equal(r.baseline.input,r.scenario.input);assert.ok(Math.abs(r.scenario.residual)<1e-8);assert.ok(r.scenario.excess<=r.baseline.excess)}
assert.equal(E.compare(S,{rainMm:100,rainDays:1,reduction:0,pavedDelta:0}).every(r=>r.delta_mm===0),true);
assert.equal(E.avg([]),null);assert.equal(E.budget(20,null,10,.5),null);console.log('Evidence screen invariants passed');
