/* SWELL Worlds dashboard. Mission metadata and user data are kept distinct from illustrative globe art. */
(() => {
"use strict";
const $=id=>document.getElementById(id);
const bodies={
 mars:{name:"Mars",code:"MARS / IAU",mission:"MRO · MSL · InSight",data:"PDS · ODE",mode:"ARCHIVE",status:"ARCHIVED OBSERVATIONS",subtitle:"Explore orbital observations, surface context and candidate habitation regions.",radius:"3,389.5 km",gravity:"3.71 m/s²",day:"24 h 37 min",air:"CO₂-dominated · thin",temp:"~−65 °C global mean*",radiation:"Surface exposure varies by site",water:"Subsurface ice evidence varies by region",light:"Solar flux ~43% of Earth at Mars orbit",facts:"Mars is explored through orbital and landed mission archives. Terrain, atmospheric observations, mineralogy and surface imagery have different resolutions, dates and uncertainty. A global live-weather feed is not available here.",environment:"<ul><li>Orbital terrain: MOLA / HRSC / CTX / HiRISE products, depending on coverage.</li><li>Atmospheric context: mission observations and numerical climate models; not continuous live global weather.</li><li>Surface environment: temperature, dust, radiation and pressure require location- and season-specific sources.</li><li>Subsurface ice: infer from instrument-specific evidence; distinguish detections, proxies and hypotheses.</li></ul>",habitat:"<ul><li>Screen slope, roughness, elevation and landing hazards.</li><li>Assess thermal environment, radiation and dust exposure.</li><li>Evaluate solar access, communications geometry and rover traversability.</li><li>Model water/oxygen production only where feedstock and process assumptions are explicit.</li></ul>",links:[["PDS Mars archive","https://pds.nasa.gov/"],["Mars Orbital Data Explorer","https://ode.rsl.wustl.edu/mars/"],["NASA Mars Trek / WMTS","https://trek.nasa.gov/mars/"],["NASA Mars 2020 mission","https://mars.nasa.gov/mars2020/"]] },
 moon:{name:"Moon",code:"MOON / IAU",mission:"LRO · LCROSS · GRAIL",data:"PDS · LOLA · ODE",mode:"ARCHIVE",status:"ARCHIVED OBSERVATIONS",subtitle:"Explore lunar terrain, illumination, thermal context and candidate south-pole operations.",radius:"1,737.4 km",gravity:"1.62 m/s²",day:"29.5 Earth days (solar cycle)",air:"Exosphere · near vacuum",temp:"Extreme day/night variation",radiation:"No global magnetic shielding",water:"Polar volatiles: evidence is spatially variable",light:"Terrain-dependent polar illumination",facts:"The lunar south pole is a high-value planning region because terrain, low-angle illumination and permanently shadowed regions create complex trade-offs. LOLA topography and LROC imagery are archive observations, not live surface feeds.",environment:"<ul><li>LOLA elevation and slope products support terrain screening.</li><li>LROC imagery supports surface context and hazard interpretation.</li><li>Diviner thermal measurements inform temperature context.</li><li>Illumination depends on local horizon geometry and time; shadow maps require a terrain model and ephemeris.</li></ul>",habitat:"<ul><li>Assess slope, boulder hazards and landing ellipse.</li><li>Compute sunlight windows from terrain horizons and solar ephemeris.</li><li>Evaluate thermal cycling and permanently shadowed-region proximity.</li><li>Water-ice potential is not equivalent to proven accessible reserves.</li></ul>",links:[["LRO mission archive","https://pds.nasa.gov/"],["LOLA PDS archive","https://imbrium.mit.edu/"],["Lunar Orbital Data Explorer","https://ode.rsl.wustl.edu/moon/"],["NASA Moon Trek","https://trek.nasa.gov/moon/"]] },
 earth:{name:"Earth",code:"EARTH / WGS84",mission:"NISAR · Landsat · SMAP · GPM",data:"Earthdata · GIBS",mode:"LIVE + ARCHIVE",status:"RETURN TO EARTH PLATFORM",subtitle:"Earth's full operational monitoring and Decision Studio remain in the original dashboard.",radius:"6,371 km",gravity:"9.81 m/s²",day:"24 hours",air:"N₂ / O₂ atmosphere",temp:"Live feeds in Earth platform",radiation:"Regional and time-varying",water:"Hydrology and soil moisture feeds",light:"Current solar and weather services",facts:"Earth is handled by the existing SWELL Earth platform. This Worlds dashboard does not replace or alter its Earth workflows.",environment:"<ul><li>Use the original Earth platform for NISAR, GIBS, physical twin and stakeholder workflows.</li><li>Earth live weather and satellite products are separate from archived planetary mission observations.</li></ul>",habitat:"<ul><li>For Earth engineering, planning and stakeholder deliverables, return to the original SWELL dashboard.</li><li>Worlds provides a cross-planet data and custom-upload workspace.</li></ul>",links:[["Open SWELL Earth platform","index.html"],["NASA Earthdata","https://www.earthdata.nasa.gov/"],["NASA GIBS","https://www.earthdata.nasa.gov/data/tools/gibs"]] },
 venus:{name:"Venus",code:"VENUS / IAU",mission:"Magellan · Venus Express",data:"PDS · mission archives",mode:"ARCHIVE",status:"ARCHIVED OBSERVATIONS",subtitle:"Investigate radar-mapped geology and the extreme Venusian atmosphere.",radius:"6,051.8 km",gravity:"8.87 m/s²",day:"243 Earth days (retrograde)",air:"Dense CO₂ atmosphere",temp:"~465 °C surface",radiation:"Atmospheric shielding differs from space",water:"No stable surface liquid water",light:"High cloud opacity; surface solar design constrained",facts:"Venus surface mapping relies heavily on radar observations, especially Magellan. Surface conditions are extremely hot and high-pressure. Surface habitation concepts are not interchangeable with cloud-layer aerostat concepts.",environment:"<ul><li>Magellan radar imagery and altimetry provide major surface context.</li><li>Atmospheric profiles and cloud observations come from specific mission eras.</li><li>Surface conditions are harsh; do not infer local current weather from archival maps.</li></ul>",habitat:"<ul><li>Separate surface robotic operations from high-altitude aerostat concepts.</li><li>Model temperature, pressure, chemistry and materials compatibility.</li><li>Evaluate power, communications and atmospheric mobility constraints.</li></ul>",links:[["PDS Venus archive","https://pds.nasa.gov/"],["Venus Orbital Data Explorer","https://ode.rsl.wustl.edu/venus/"],["NASA Magellan mission","https://science.nasa.gov/mission/magellan/"]] },
 europa:{name:"Europa",code:"EUROPA / IAU",mission:"Galileo · Europa Clipper (en route)",data:"PDS · mission archives",mode:"ARCHIVE + FUTURE MISSION",status:"ARCHIVED OBSERVATIONS",subtitle:"Explore icy surface observations and plan future reconnaissance questions.",radius:"1,560.8 km",gravity:"1.31 m/s²",day:"3.55 Earth days (orbit)",air:"Extremely tenuous exosphere",temp:"~−160 °C average surface context",radiation:"Jupiter's radiation environment is severe",water:"Strong evidence for subsurface ocean; access unknown",light:"Low solar flux at Jupiter orbit",facts:"Europa has strong evidence for a global subsurface ocean, but its accessibility, habitability and detailed ice-shell structure remain active research questions. Galileo data are archival; Europa Clipper is a future/ongoing mission context, not a live surface weather feed.",environment:"<ul><li>Galileo imaging and spectroscopy are archival and spatially uneven.</li><li>Jovian magnetospheric radiation is a major mission-design constraint.</li><li>Surface geology and ocean inferences carry substantial uncertainty.</li></ul>",habitat:"<ul><li>Prioritize robotic science and radiation-aware mission architecture.</li><li>Do not treat the subsurface ocean as an accessible water supply.</li><li>Any human surface settlement concept faces severe radiation and thermal challenges.</li></ul>",links:[["PDS Europa / Galileo archive","https://pds.nasa.gov/"],["Europa Clipper mission","https://science.nasa.gov/mission/europa-clipper/"],["PDS Imaging Node","https://pds-imaging.jpl.nasa.gov/"]] },
 titan:{name:"Titan",code:"TITAN / IAU",mission:"Cassini-Huygens",data:"PDS · Cassini archive",mode:"ARCHIVE",status:"ARCHIVED OBSERVATIONS",subtitle:"Explore Titan's haze-shrouded surface, lakes, dunes and methane-cycle science.",radius:"2,574.7 km",gravity:"1.35 m/s²",day:"15.95 Earth days (rotation)",air:"Dense nitrogen atmosphere",temp:"~−179 °C surface",radiation:"Atmosphere provides shielding context",water:"Water ice bedrock; methane/ethane liquids",light:"Very low sunlight at Saturn orbit",facts:"Titan's surface is observed through radar, infrared windows and in-situ Huygens measurements. Its methane cycle is not Earth-like water weather. Cassini-Huygens measurements are archival.",environment:"<ul><li>Cassini RADAR mapped selected areas through haze.</li><li>Infrared observations and Huygens data add regional context.</li><li>Hydrocarbon lakes, dunes and weather are governed by Titan-specific physics.</li></ul>",habitat:"<ul><li>Account for cryogenic temperatures and low solar availability.</li><li>Consider atmospheric composition, pressure and methane/ethane chemistry.</li><li>Evaluate nuclear power, thermal management and material compatibility.</li></ul>",links:[["PDS Cassini archive","https://pds.nasa.gov/"],["Cassini Orbital Data Explorer","https://ode.rsl.wustl.edu/"],["NASA Dragonfly mission","https://science.nasa.gov/mission/dragonfly/"]] }
};
let selected="mars", renderer,scene,camera,controls,mesh,rotating=true,raycaster,mouse;
const materials={mars:[0x9b5037,0x5a2926],moon:[0xaeb2b4,0x515861],earth:[0x267d9b,0x153c61],venus:[0xd39a4d,0x77411f],europa:[0xb4d2d9,0x527b8b],titan:[0xc58a45,0x693a22]};
function noiseTexture(key){
 const c=document.createElement("canvas");c.width=1024;c.height=512;const ctx=c.getContext("2d"),im=ctx.createImageData(c.width,c.height),base=materials[key][0],dark=materials[key][1];
 let seed=key.split("").reduce((a,x)=>a+x.charCodeAt(0),17);const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296};
 const craterCount=key==="moon"?900:key==="mars"?500:key==="europa"?750:220;
 for(let y=0;y<c.height;y++)for(let x=0;x<c.width;x++){let n=(rnd()-.5)*30,lat=Math.sin(y/c.height*Math.PI),i=(y*c.width+x)*4;im.data[i]=Math.max(0,Math.min(255,((base>>16)&255)+n));im.data[i+1]=Math.max(0,Math.min(255,((base>>8)&255)+n));im.data[i+2]=Math.max(0,Math.min(255,(base&255)+n));im.data[i+3]=255;}
 ctx.putImageData(im,0,0);
 for(let i=0;i<craterCount;i++){let x=rnd()*c.width,y=rnd()*c.height,r=(key==="moon"?2:1)+rnd()*(key==="moon"?14:9);ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=`rgba(0,0,0,${.06+rnd()*.17})`;ctx.fill();ctx.beginPath();ctx.arc(x-r*.13,y-r*.18,r*.77,0,Math.PI*2);ctx.strokeStyle=`rgba(255,220,180,${.08+rnd()*.16})`;ctx.lineWidth=Math.max(.5,r*.09);ctx.stroke();}
 if(key==="earth"){for(let i=0;i<130;i++){let x=rnd()*1024,y=rnd()*512;ctx.fillStyle="rgba(65,139,81,.32)";ctx.beginPath();ctx.ellipse(x,y,10+rnd()*50,4+rnd()*22,rnd()*3,0,Math.PI*2);ctx.fill();}}
 if(key==="venus"){ctx.fillStyle="rgba(255,225,160,.12)";for(let y=20;y<512;y+=32){ctx.fillRect(0,y,1024,6+rnd()*14);}}
 if(key==="titan"){ctx.fillStyle="rgba(48,26,18,.22)";for(let i=0;i<150;i++){ctx.beginPath();let x=rnd()*1024,y=rnd()*512;ctx.ellipse(x,y,5+rnd()*28,2+rnd()*5,rnd()*3,0,7);ctx.fill();}}
 const tex=new THREE.CanvasTexture(c);tex.encoding=THREE.sRGBEncoding;return tex;
}
function initGlobe(){
 const host=$("planetCanvas");if(!window.THREE){host.textContent="3D globe requires WebGL and the Three.js library.";return;}
 scene=new THREE.Scene();scene.background=new THREE.Color(0x06101a);
 camera=new THREE.PerspectiveCamera(38,host.clientWidth/host.clientHeight,.1,100);camera.position.set(0,0,4.6);
 renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});renderer.setPixelRatio(Math.min(2,devicePixelRatio||1));renderer.setSize(host.clientWidth,host.clientHeight);host.appendChild(renderer.domElement);
 controls=new THREE.OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.minDistance=2.1;controls.maxDistance=8;
 scene.add(new THREE.AmbientLight(0x8195a8,.75));const light=new THREE.DirectionalLight(0xffffff,2.0);light.position.set(4,3,5);scene.add(light);
 const stars=new THREE.BufferGeometry(),pts=[];for(let i=0;i<700;i++)pts.push((Math.random()-.5)*30,(Math.random()-.5)*18,-5-Math.random()*20);stars.setAttribute("position",new THREE.Float32BufferAttribute(pts,3));scene.add(new THREE.Points(stars,new THREE.PointsMaterial({color:0x94c4d9,size:.018,transparent:true,opacity:.55})));
 mesh=new THREE.Mesh(new THREE.SphereGeometry(1,96,64),new THREE.MeshStandardMaterial({map:noiseTexture(selected),roughness:.96,metalness:0}));scene.add(mesh);
 const glow=new THREE.Mesh(new THREE.SphereGeometry(1.015,64,48),new THREE.MeshBasicMaterial({color:0x3f9cb5,transparent:true,opacity:.045,side:THREE.BackSide}));scene.add(glow);
 raycaster=new THREE.Raycaster();mouse=new THREE.Vector2();
 renderer.domElement.addEventListener("click",pickPlanet);
 const resize=new ResizeObserver(()=>{const w=host.clientWidth,h=host.clientHeight;if(!w||!h)return;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h);});resize.observe(host);
 const animate=()=>{requestAnimationFrame(animate);if(rotating&&mesh)mesh.rotation.y+=.0007;controls.update();renderer.render(scene,camera);};animate();
}
function pickPlanet(e){
 const r=renderer.domElement.getBoundingClientRect();mouse.x=((e.clientX-r.left)/r.width)*2-1;mouse.y=-((e.clientY-r.top)/r.height)*2+1;raycaster.setFromCamera(mouse,camera);const hit=raycaster.intersectObject(mesh)[0];if(!hit)return;
 const p=hit.point.clone().normalize();const lat=Math.asin(p.y)*180/Math.PI,lon=Math.atan2(p.z,p.x)*180/Math.PI;
 $("globeCoords").textContent=`Body-fixed pick · ${lat.toFixed(3)}° lat, ${lon.toFixed(3)}° lon · reference coordinates`;
}
function setWorld(key){
 selected=key;clearUserOverlay();const b=bodies[key];document.querySelectorAll(".world-choice").forEach(x=>x.classList.toggle("active",x.dataset.world===key));
 $("worldTitle").textContent=`${b.name} · Physical environment`;$("worldSubtitle").textContent=b.subtitle;$("worldStatus").textContent=b.status;$("globeName").textContent=b.name.toUpperCase();$("bodyCode").textContent=b.code;
 $("worldFacts").innerHTML=`<p>${b.facts}</p><div class="tiny">Mean radius ${b.radius} · surface gravity ${b.gravity} · rotation ${b.day}</div>`;
 $("environmentText").innerHTML=b.environment;$("habitatText").innerHTML=b.habitat;
 $("metricMission").textContent=b.mission;$("metricData").textContent=b.data;$("metricMode").textContent=b.mode;
 $("envMetrics").innerHTML=[["Surface gravity",b.gravity],["Atmosphere",b.air],["Temperature",b.temp],["Radiation",b.radiation],["Water / volatiles",b.water],["Illumination",b.light]].map(x=>`<div class="env"><b>${x[1]}</b><span>${x[0]}</span></div>`).join("");
 $("envMode").textContent=key==="earth"?"EARTH PLATFORM":"ARCHIVE / MODEL";
 $("envNote").textContent=key==="earth"?"Earth's operational data feeds remain in the original SWELL Earth dashboard.":"These are contextual reference statements, not point-specific live measurements. Mission data, model output and climatology must be selected and cited independently.";
 $("sourceLinks").innerHTML=b.links.map(x=>`<a href="${x[1]}" target="_blank" rel="noopener">${x[0]} <span>↗</span></a>`).join("");
 $("globeDisclaimer").textContent="Procedural illustrative globe · not mission terrain";
 if(mesh){mesh.material.map.dispose();mesh.material.map=noiseTexture(key);mesh.material.needsUpdate=true;mesh.rotation.set(0,0,0);}
 if(key==="earth")$("habitatResult").textContent="Earth planning is available in the original Earth platform. Worlds keeps this workspace separate.";
 else $("habitatResult").textContent="Adjust assumptions and run a screening summary. This is not a landing-site safety certification or engineering design.";
 $("catalogQuery").value=key==="moon"?"Moon":b.name;
 $("catalogResults").innerHTML='<div class="tiny">Choose Search NASA PDS archive to retrieve current catalog metadata for this target.</div>';
}
async function searchCatalog(){
 const q=$("catalogQuery").value.trim()||bodies[selected].name;const st=$("catalogStatus"),box=$("catalogResults");st.textContent="Querying NASA PDS Search API…";box.innerHTML='<div class="tiny">Contacting archive…</div>';
 try{
  const r=await fetch(`/api/worlds/pds-search?keywords=${encodeURIComponent(q)}&limit=12`);const d=await r.json();if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);
  const records=d.results||[];st.textContent=`NASA PDS response · ${records.length} records shown · ${d.total??"count not supplied"} total / matching archive response`;
  if(!records.length){box.innerHTML=`<div class="tiny">The API returned no records for “${q}”. Try a mission or instrument name, or use the PDS / ODE links. This does not prove the archive contains no relevant data.</div>`;return;}
  box.innerHTML=records.map(x=>`<div class="catalog-item"><b>${esc(x.title||x.name||x["ops:Harvest_Info"]?.["ops:harvest_date_time"]||"PDS product record")}</b><small>${esc(x.id||x.lid||x.product_lid||"Identifier not supplied")} · ${esc(x.start_date_time||x.time||"Date not supplied")}</small><small>${esc(x.description||x.target_name||"Metadata record; inspect the source label for product details.")}</small>${x.url?`<a href="${esc(x.url)}" target="_blank" rel="noopener">Open product ↗</a>`:""}</div>`).join("");
 }catch(e){st.textContent="PDS search unavailable";box.innerHTML=`<div class="tiny">Could not query the PDS API: ${esc(e.message)}. Check internet access or use the official archive links below. No sample results have been substituted.</div>`;}
}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
const uploaded=[];
let userOverlay=null;
function ensureUserOverlay(){
 if(!scene||userOverlay)return;
 userOverlay=new THREE.Group();scene.add(userOverlay);
}
function clearUserOverlay(){if(!userOverlay)return;scene.remove(userOverlay);userOverlay.traverse(o=>{o.geometry?.dispose?.();if(o.material){if(Array.isArray(o.material))o.material.forEach(m=>m.dispose?.());else o.material.dispose?.();}});userOverlay=null;}
function bodyVector(lon,lat,r=1.012){
 const la=lat*Math.PI/180,lo=lon*Math.PI/180;
 return new THREE.Vector3(-Math.cos(la)*Math.cos(lo)*r,Math.sin(la)*r,Math.cos(la)*Math.sin(lo)*r);
}
function drawCoordinateFeatures(features,label){
 ensureUserOverlay();const pointMat=new THREE.MeshBasicMaterial({color:0x72e6d4}),lineMat=new THREE.LineBasicMaterial({color:0x72d8e7,transparent:true,opacity:.9});
 const pointGeom=new THREE.SphereGeometry(.012,8,6);
 const addPoint=c=>{if(!Array.isArray(c)||c.length<2)return;const lon=Number(c[0]),lat=Number(c[1]);if(!Number.isFinite(lon)||!Number.isFinite(lat)||Math.abs(lat)>90)return;const m=new THREE.Mesh(pointGeom,pointMat);m.position.copy(bodyVector(lon,lat));userOverlay.add(m);};
 const addLine=coords=>{if(!Array.isArray(coords)||coords.length<2)return;const pts=coords.map(c=>bodyVector(Number(c[0]),Number(c[1]),1.006)).filter(v=>Number.isFinite(v.x)&&Number.isFinite(v.y)&&Number.isFinite(v.z));if(pts.length<2)return;userOverlay.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),lineMat));};
 const walk=(g)=>{if(!g)return;switch(g.type){case"FeatureCollection":g.features?.forEach(walk);break;case"Feature":walk(g.geometry);break;case"Point":addPoint(g.coordinates);break;case"MultiPoint":g.coordinates?.forEach(addPoint);break;case"LineString":addLine(g.coordinates);break;case"MultiLineString":g.coordinates?.forEach(addLine);break;case"Polygon":g.coordinates?.forEach(addLine);break;case"MultiPolygon":g.coordinates?.forEach(poly=>poly.forEach(addLine));break;case"GeometryCollection":g.geometries?.forEach(walk);break;}};
 features.forEach(walk);
 $("globeDisclaimer").textContent=`User overlay: ${label} · assumed body-fixed lon/lat; verify datum`;
}
async function inspectFile(file){
 const ext=file.name.split(".").pop().toLowerCase();let meta={name:file.name,size:file.size,format:ext.toUpperCase(),body:selected,status:"Stored locally",details:"Metadata inspection only; no scientific interpretation inferred."};
 if(ext==="geojson"||ext==="json"){
  try{const j=JSON.parse(await file.text());meta.features=j.features?.length??(j.type==="Feature"?1:0);meta.geometry=j.type;meta.geojson=j;meta.details=`${meta.features} feature(s) · ${j.type||"JSON"} · CRS must be checked against the selected body reference.`;}catch{meta.status="Invalid JSON";meta.details="Could not parse JSON.";}
 }else if(ext==="csv"){
  const text=await file.slice(0,200000).text(),lines=text.split(/\r?\n/).filter(Boolean);meta.rows=Math.max(0,lines.length-1);meta.columns=(lines[0]||"").split(",").length;meta.details=`${meta.rows} sampled rows · ${meta.columns} columns · coordinate and unit fields need mapping.`;meta.preview=lines.slice(0,4).join("\n");meta.csvText=text;
 }else if(["tif","tiff","geotiff","cog"].includes(ext)){
  if(window.GeoTIFF){try{const t=await GeoTIFF.fromBlob(file),im=await t.getImage();meta.width=im.getWidth();meta.height=im.getHeight();meta.bands=im.getSamplesPerPixel();meta.crs=im.getGeoKeys()?.ProjectedCSTypeGeoKey||im.getGeoKeys()?.GeographicTypeGeoKey||"CRS key not found";meta.details=`${meta.width} × ${meta.height} · ${meta.bands} band(s) · CRS code ${meta.crs} · raster preview requires projection-aware renderer.`;}catch(e){meta.status="GeoTIFF metadata read failed";meta.details=e.message;}}else meta.details="GeoTIFF.js unavailable; file retained but not decoded.";
 }else if(["glb","gltf"].includes(ext)){meta.details="3D model file accepted. Validate units, origin, orientation and planetary body before spatial placement.";}
 else if(["nc","netcdf","h5","hdf5"].includes(ext)){meta.details="Scientific array file catalogued. NetCDF/HDF5 variable decoding and coordinate mapping require a backend adapter.";}
 else if(["img","lbl","xml"].includes(ext)){meta.details="PDS / label candidate. Pair detached labels and binary assets where required; parse instrument-specific metadata before rendering.";}
 else if(["las","laz"].includes(ext)){meta.details="Point-cloud file accepted. Use a LAS/LAZ decoder and coordinate-reference validation before 3D rendering.";}
 return meta;
}
async function uploadFiles(files){
 const list=[...files];if(!list.length)return;const zone=$("uploadList");zone.innerHTML='<div class="tiny">Inspecting and uploading selected files…</div>';
 for(const f of list){
  const meta=await inspectFile(f);
  try{
   const fd=new FormData();fd.append("file",f);fd.append("body",selected);fd.append("crs",$("uploadCrs").value);fd.append("units",$("uploadUnits").value);fd.append("observation_time",$("uploadDate").value);fd.append("description",$("uploadDescription").value);
   const r=await fetch("/api/worlds/upload",{method:"POST",body:fd});const d=await r.json();if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);
   meta.storedPath=d.path;meta.status="Saved to SWELL workspace";meta.id=d.id;meta.crs=d.crs;
  }catch(e){meta.status="Local inspection only";meta.details+=` Server storage unavailable: ${e.message}`;}
  meta.body=selected;meta.fileName=f.name;uploaded.push(meta);
 }
 renderUploads();
}
async function loadStoredUploads(){
 try{const r=await fetch(`/api/worlds/files?body=${encodeURIComponent(selected)}`);const d=await r.json();if(!r.ok)return;
  const existing=new Set(uploaded.filter(x=>x.body===selected).map(x=>x.name));
  (d.files||[]).forEach(f=>{const name=f.name.replace(/^[a-f0-9]{12}-/,"");if(!existing.has(name))uploaded.push({name,size:f.size,format:name.split(".").pop().toUpperCase(),body:selected,status:"Stored on server",crs:f.crs,storedPath:f.url,details:`Persistent workspace file · ${f.url}${f.units?" · "+f.units:""}${f.observation_time?" · "+f.observation_time:""}${f.description?" · "+f.description:""}`});});
 }catch{}
 renderUploads();
}
function renderUploads(){
 $("uploadList").innerHTML=uploaded.filter(x=>x.body===selected).map((x)=>{const idx=uploaded.indexOf(x);const canMap=!!x.geojson||!!x.csvText;return `<div class="file-row"><div><b>${esc(x.name)}</b><small>${esc(x.format)} · ${(x.size/1048576).toFixed(2)} MB · ${esc(x.details)}${x.crs?` · ${esc(x.crs)}`:""}</small></div><div style="display:flex;gap:6px;align-items:center"><span class="tiny">${esc(x.status)}</span>${x.storedPath?`<a href="${esc(x.storedPath)}" target="_blank" rel="noopener" style="font-size:9px">Open file</a>`:""}${canMap?`<button class="btn secondary" data-overlay="${idx}" style="padding:6px 8px">Map layer</button>`:""}</div></div>`;}).join("")||'<div class="tiny">No uploaded files assigned to this world yet.</div>';
 $("uploadList").querySelectorAll("[data-overlay]").forEach(btn=>btn.addEventListener("click",()=>{const x=uploaded[Number(btn.dataset.overlay)];if(x.geojson){clearUserOverlay();drawCoordinateFeatures([x.geojson],x.name);}else if(x.csvText){const lines=x.csvText.split(/\r?\n/).filter(Boolean),headers=lines[0].split(",").map(v=>v.trim().toLowerCase()),lonI=headers.findIndex(v=>["lon","longitude","long","x"].includes(v)),latI=headers.findIndex(v=>["lat","latitude","y"].includes(v));if(lonI<0||latI<0){$("uploadList").insertAdjacentHTML("beforeend",'<div class="tiny">CSV needs longitude/lon and latitude/lat columns to map point locations.</div>');return;}const pts=lines.slice(1).map(line=>{const a=line.split(",");return {type:"Feature",geometry:{type:"Point",coordinates:[Number(a[lonI]),Number(a[latI])]}};});clearUserOverlay();drawCoordinateFeatures(pts,x.name);}}));
}
function runHabitat(){
 if(selected==="earth"){$("habitatResult").textContent="Use the original SWELL Earth platform for Earth physical models and stakeholder actions.";return;}
 const solar=+$("solarInput").value,shield=+$("shieldInput").value,water=+$("waterInput").value,type=$("siteType").value;
 const body=bodies[selected];let flags=[];
 if(solar<35)flags.push("Low assumed solar availability: investigate nuclear or hybrid power and storage.");
 if(shield<1.5)flags.push("Shielding allowance is a planning placeholder; radiation transport analysis and local material data are required.");
 if(water<30)flags.push("Short water reserve assumption: evaluate recycling, storage redundancy and resupply.");
 if(selected==="moon"&&solar<50)flags.push("For polar sites, calculate local illumination windows from high-resolution terrain and ephemerides; this slider is not a sunlight simulation.");
 if(selected==="mars")flags.push("Include dust deposition, atmospheric opacity, seasonal variation and surface radiation in a validated site model.");
 if(selected==="europa")flags.push("Radiation exposure may dominate mission design; this simple slider cannot assess dose.");
 if(selected==="venus")flags.push("Surface temperature and pressure make a conventional crewed surface outpost infeasible with current known materials and systems; consider robotic or high-altitude concepts separately.");
 const concept=type==="outpost"?"crewed research outpost":type==="robotic"?"robotic science station":"ISRU pilot facility";
 $("habitatResult").innerHTML=`<b>${body.name} · ${concept}</b><br>Assumptions recorded: solar availability ${solar}%; shielding allowance ${shield.toFixed(1)} m; reserve ${water} ${selected==="mars"?"sols":"days"}.<br><br><b>Screening flags</b><ul>${flags.map(x=>`<li>${esc(x)}</li>`).join("")||"<li>No threshold flags from these user-entered assumptions. This is not evidence of site safety.</li>"}</ul><span class="tiny">This is a transparent checklist, not a physical prediction, risk score, landing approval or engineering design. No environmental observations are generated by these sliders.</span>`;
}
$("worldList").addEventListener("click",e=>{const b=e.target.closest("[data-world]");if(!b)return;setWorld(b.dataset.world);loadStoredUploads();});
$("searchCatalog").addEventListener("click",searchCatalog);
$("worldFiles").addEventListener("change",e=>uploadFiles(e.target.files));
$("dropZone").addEventListener("dragover",e=>{e.preventDefault();$("dropZone").style.borderColor="#65d3e5";});
$("dropZone").addEventListener("dragleave",()=>{$("dropZone").style.borderColor="";});
$("dropZone").addEventListener("drop",e=>{e.preventDefault();$("dropZone").style.borderColor="";uploadFiles(e.dataTransfer.files);});
let zoomPercent=100;
function updateZoomLabel(){const d=camera.position.distanceTo(controls.target);zoomPercent=Math.round(100*4.6/d);$("zoomLevel").textContent=zoomPercent+"%";}
function zoomBy(factor){
 const offset=camera.position.clone().sub(controls.target);
 const next=Math.max(controls.minDistance,Math.min(controls.maxDistance,offset.length()*factor));
 offset.setLength(next);camera.position.copy(controls.target).add(offset);controls.update();updateZoomLabel();
}
initGlobe();
$("zoomIn").addEventListener("click",()=>zoomBy(.82));
$("zoomOut").addEventListener("click",()=>zoomBy(1.22));
$("rotateToggle").addEventListener("click",()=>{rotating=!rotating;$("rotateToggle").textContent=rotating?"Pause":"Resume";});
$("resetView").addEventListener("click",()=>{camera.position.set(0,0,4.6);controls.target.set(0,0,0);controls.update();updateZoomLabel();});
controls.addEventListener("change",updateZoomLabel);
document.querySelectorAll(".workspace-tab").forEach(btn=>btn.addEventListener("click",()=>{
 document.querySelectorAll(".workspace-tab").forEach(b=>{const active=b===btn;b.classList.toggle("active",active);b.setAttribute("aria-selected",active?"true":"false");});
 document.querySelectorAll(".workspace-view").forEach(v=>v.classList.toggle("active",v.dataset.panel===btn.dataset.view));
 if(btn.dataset.view==="explore" && renderer){const host=$("planetCanvas");if(host.clientWidth){camera.aspect=host.clientWidth/Math.max(1,host.clientHeight);camera.updateProjectionMatrix();renderer.setSize(host.clientWidth,host.clientHeight);}}
 if(btn.dataset.view==="studio") $("worldFiles").focus({preventScroll:true});
}));
updateZoomLabel();
["solarInput","shieldInput","waterInput"].forEach(id=>$(id).addEventListener("input",()=>{$("solarVal").textContent=$("solarInput").value+"%";$("shieldVal").textContent=(+$("shieldInput").value).toFixed(1)+" m";$("waterVal").textContent=$("waterInput").value+(selected==="mars"?" sols":" days");}));
$("runHabitat").addEventListener("click",runHabitat);
setWorld("mars");loadStoredUploads();
})();
