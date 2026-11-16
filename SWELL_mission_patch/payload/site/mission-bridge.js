/* Preserve the current Earth workspace; carry its selected cell to the guided decision. */
(()=>{const a=document.getElementById('guidedMission');if(!a)return;a.addEventListener('click',()=>{try{if(typeof S!=='undefined'&&S&&typeof sel!=='undefined'&&sel&&!/SYNTH/i.test(S.source||'')){a.href='decision-mission.html?'+new URLSearchParams({row:sel.i,col:sel.j})}}catch{}})})();
