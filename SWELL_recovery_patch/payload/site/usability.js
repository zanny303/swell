/* Small progressive-disclosure layer. Keeps the original panels and their event handlers intact. */
(()=>{
 const $=id=>document.getElementById(id);
 const tabs=$('bottomTabs'),bottom=$('bottom');
 if(tabs&&bottom){
   const panels=[...bottom.querySelectorAll('[data-bottom-panel]')];
   const activate=name=>{
     for(const b of tabs.querySelectorAll('[data-bottom-tab]')){const on=b.dataset.bottomTab===name;b.setAttribute('aria-selected',String(on));b.classList.toggle('active',on)}
     for(const p of bottom.querySelectorAll('[data-bottom-panel]')){const on=p.dataset.bottomPanel===name;p.hidden=!on;p.classList.toggle('active',on)}
     try{localStorage.setItem('swell.analysisPanel',name)}catch(_){}
   };
   tabs.addEventListener('click',e=>{const b=e.target.closest('[data-bottom-tab]');if(b)activate(b.dataset.bottomTab)});
   let saved='scenario';try{saved=localStorage.getItem('swell.analysisPanel')||saved}catch(_){}
   activate(panels.some(p=>p.dataset.bottomPanel===saved)?saved:'scenario');
 }
 const layers=$('layList');
 if(layers&&window.MutationObserver){
   const group=()=>{
     if(layers.dataset.progressive==='1')return;
     const items=[...layers.querySelectorAll(':scope > .lay')];if(!items.length)return;
     const cats=[['Satellite imagery',['today','sharp']],['Live hazards',['quake','fire']],['Environment',['rain','smap']],['Site twin',['nisar']]];
     const map=new Map(items.map(x=>[x.querySelector('[data-lay]')?.dataset.lay,x]));
     const fragment=document.createDocumentFragment();
     for(const [title,keys] of cats){const details=document.createElement('details');details.className='layer-group';details.open=['Satellite imagery','Live hazards'].includes(title);const summary=document.createElement('summary');summary.textContent=title;details.append(summary);for(const key of keys){const item=map.get(key);if(item)details.append(item)}if(details.children.length>1)fragment.append(details)}
     layers.replaceChildren(fragment);layers.dataset.progressive='1';
   };
   new MutationObserver(group).observe(layers,{childList:true});group();
 }
 const right=$('right');
 if(right&&window.MutationObserver){
   const compact=()=>{const cards=[...right.querySelectorAll('.role[data-role]')];if(cards.length){for(const c of cards)c.hidden=!c.classList.contains('on')}};
   new MutationObserver(compact).observe(right,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});compact();
 }
})();
