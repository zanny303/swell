/* Focus pass (15 Nov, afternoon). Loaded last. Three jobs:
   1. Less clutter: every step visible in the header, the app opens on the study site, secondary tools tucked behind "All tools".
   2. A real 3D city: with the user's Cesium ion token, terrain + OpenStreetMap buildings coloured by the ground estimate under
      them, or Google photorealistic 3D tiles with the estimate draped over the city. Nothing is faked: without a token the
      buttons say what is needed.
   3. Honest labels on what those views are. */
(function () {
  const $ = id => document.getElementById(id);
  const real = () => typeof S !== "undefined" && S && C && (!/SYNTH/i.test(S.source) || (typeof sampleDemoEnabled !== "undefined" && sampleDemoEnabled));
  const css = document.createElement("style"); css.textContent = `
  header{gap:8px!important}header .logo span{display:none}header #steps{flex:0 1 auto;min-width:0;overflow:visible;gap:2px}
  header #steps button{padding:7px 9px!important;font-size:12.5px;white-space:nowrap}header #steps button i{display:none!important}
  header #search{max-width:150px!important;min-width:70px}header #enable3D{display:none!important}
  @media (max-width:1500px){header #search{display:none!important}}
  body:not(.all-tools) #bottomTabs [data-bottom-tab="findings"],body:not(.all-tools) #bottomTabs [data-bottom-tab="scenario-shelf"],body:not(.all-tools) #bottomTabs [data-bottom-tab="shelf"]{display:none}
  #allTools{margin-left:auto;font-size:11.5px;padding:4px 9px}
  #tools{font-size:11.5px;padding:6px 8px!important;gap:4px!important}#tools button{padding:4px 7px!important}
  #cityBar{position:absolute;left:8px;top:8px;z-index:6;display:none;gap:6px;align-items:center;flex-wrap:wrap;max-width:calc(100% - 70px)}
  #cityBar button{padding:5px 9px;font-size:12px}#cityBar button.on{border-color:#22c55e;color:#22c55e}
  #cityNote{position:absolute;left:8px;right:60px;bottom:8px;z-index:6;font-size:11px;color:#c5d2dc;background:#081522e0;border:1px solid var(--line);border-radius:8px;padding:5px 9px;display:none}
  body.city #legend,body.city #siteCard,body.city #selCard,body.city #tools{display:none!important}body.city #cityBar{display:flex}body.city #cityNote{display:block}`; document.head.appendChild(css);

  /* 1a. "All tools" switch for the rarely used tabs */
  const tabs = $("bottomTabs"); if (tabs) { const b = document.createElement("button"); b.id = "allTools"; b.type = "button"; b.textContent = "All tools ▸"; b.title = "Show or hide the less used tabs";
    b.onclick = () => { const on = document.body.classList.toggle("all-tools"); b.textContent = on ? "Fewer tools ◂" : "All tools ▸"; }; tabs.appendChild(b); }

  /* 2. 3D city */
  const mapBox = $("mapBox"), rail = $("rail"); if (!mapBox || typeof viewer === "undefined") return;
  const bar = document.createElement("div"); bar.id = "cityBar"; bar.className = "float";
  bar.innerHTML = `<b class="small">3D city</b><button data-city="osm" class="on">Buildings + terrain (preview)</button><button data-city="photo">Photorealistic (Google)</button><button data-city="tilt">Tilt</button><button data-city="top">Top view</button><button data-city="exit">Back to analysis map</button>`; mapBox.appendChild(bar);
  const note = document.createElement("div"); note.id = "cityNote"; mapBox.appendChild(note);
  const cb = document.createElement("button"); cb.className = "txt"; cb.id = "cityBtn"; cb.textContent = "3D city"; cb.title = "Real 3D geographic context; analytical layers remain separate"; if (rail) rail.insertBefore(cb, rail.children[1] || null);
  const token = () => { try { return localStorage.getItem("swell.cesiumIonToken.v1") || ""; } catch (_) { return ""; } };
  const say = t => { note.textContent = t; note.style.display = "block"; };
  let terrain = null, osm = null, photo = null, drape = null, mode = null, ver = 0, flatTerrain = null, savedVisibility=null, busy=false;
  const hideScience=()=>{overlay.show=outline.show=selEnt.show=false;if(drape)drape.show=false;};

  const colourOf = (lon, lat) => { if (!lastField) return null; const [w, s, e, nn] = S.bbox; if (lon < w || lon >= e || lat <= s || lat > nn) return null;
    const i = Math.min(n - 1, Math.floor((nn - lat) / (nn - s) * n)), j = Math.min(n - 1, Math.floor((lon - w) / (e - w) * n)), v = lastField.fld[i][j]; if (!Number.isFinite(v)) return null; return ramp(.5 + v / (2 * lastField.V)); };
  function paintBuildings(tile) { try { if (!osm || tile._swellVer === ver) return; tile._swellVer = ver; const c = tile.content, k = c && c.featuresLength; if (!k) return;
      for (let f = 0; f < k; f++) { const ft = c.getFeature(f), lon = ft.getProperty("cesium#longitude"), lat = ft.getProperty("cesium#latitude"), col = null;
        ft.color = col ? Cesium.Color.fromBytes(col[0], col[1], col[2], 255) : Cesium.Color.fromCssColorString("#d9dee3"); } } catch (_) { } }
  function buildDrape() { if (!drape) { drape = new Cesium.CustomDataSource("drape"); viewer.dataSources.add(drape); } drape.entities.removeAll(); if (!lastField) return;
    const [w, s, e, nn] = S.bbox, m = Math.min(n, 24), dx = (e - w) / m, dy = (nn - s) / m, k = n / m;
    for (let a = 0; a < m; a++) for (let b = 0; b < m; b++) { let sum = 0, cnt = 0; for (let i = Math.floor(a * k); i < Math.floor((a + 1) * k); i++) for (let j = Math.floor(b * k); j < Math.floor((b + 1) * k); j++) { const v = lastField.fld[i][j]; if (Number.isFinite(v)) { sum += v; cnt++; } }
      if (!cnt) continue; const c = ramp(.5 + (sum / cnt) / (2 * lastField.V));
      drape.entities.add({ rectangle: { coordinates: Cesium.Rectangle.fromDegrees(w + b * dx, nn - (a + 1) * dy, w + (b + 1) * dx, nn - a * dy), material: Cesium.Color.fromBytes(c[0], c[1], c[2], 120), classificationType: Cesium.ClassificationType.BOTH } }); } }
  // aim the city view at the most built-up part of the site (real land cover), close enough to see buildings
  const hub = () => { let best = -1, bi = 0, bj = 0; for (let i = 1; i < n - 1; i++) for (let j = 1; j < n - 1; j++) { let v = 0; for (let a = -1; a <= 1; a++) for (let c = -1; c <= 1; c++) v += S.paved[i + a][j + c] || 0; if (v > best) { best = v; bi = i; bj = j; } }
    const g=geoCenter(bi,bj);return [g.lon,g.lat]; };
  const tilt = async top => { const [lon, lat] = hub(); if (top) { viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(lon, lat, 9000), orientation: { heading: 0, pitch: -Math.PI / 2, roll: 0 }, duration: 2 }); return; }
    if(mode==="photo"){viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(Cesium.Cartesian3.fromDegrees(lon,lat,180),700),{offset:new Cesium.HeadingPitchRange(Cesium.Math.toRadians(25),Cesium.Math.toRadians(-32),3200),duration:2.2});return;}let h=0;try{const [p]=await Cesium.sampleTerrainMostDetailed(terrain,[Cesium.Cartographic.fromDegrees(lon,lat)]);if(!Number.isFinite(p.height))throw Error('No finite terrain height');h=p.height;}catch(e){say('Terrain height unavailable; using conservative overhead context.');return tilt(true);}if(!mode)return;
    viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(Cesium.Cartesian3.fromDegrees(lon, lat, h+150), 900), { offset: new Cesium.HeadingPitchRange(Cesium.Math.toRadians(25), Cesium.Math.toRadians(-55), 5500), duration: 2.2 }); };
  async function enter(which) {
    if (!real()) { say("Build a real site first (Connections), or open the labelled demo. The 3D city shows the estimate for that site."); return; }
    const t = token(); if (!t) { say('3D city needs your free Cesium ion token. Open <a href="connections.html">Connections</a>, paste it under "Cesium ion token", save, then press 3D city again.'); return; }
    if(busy)return;busy=true;bar.dataset.cityState="loading";if(!savedVisibility)savedVisibility=[overlay.show,outline.show,selEnt.show];hideScience();document.body.classList.add("city"); cb.classList.add("on"); say("Loading real terrain and buildings…");
    try { Cesium.Ion.defaultAccessToken = t; if (!flatTerrain) flatTerrain = viewer.terrainProvider;
      try { viewer.scene.screenSpaceCameraController.enableTilt = true; if (viewer.scene.mode !== Cesium.SceneMode.SCENE3D) viewer.scene.morphTo3D(0); } catch (_) { }
      if (!terrain) terrain = await Cesium.createWorldTerrainAsync(); viewer.scene.screenSpaceCameraController.enableCollisionDetection=true; viewer.terrainProvider = terrain; viewer.scene.globe.depthTestAgainstTerrain = true;
      hideScience(); // Keep analytical rectangles off the city entirely.
      if (which === "photo") {
        if (!photo) { photo = await Cesium.createGooglePhotorealistic3DTileset(); viewer.scene.primitives.add(photo); }
        photo.show = true; if (osm) osm.show = false; if(ionContext.buildings)ionContext.buildings.show=false; overlay.show = false; if(drape)drape.show=false; viewer.scene.globe.show = false; mode = "photo";
        say("Photorealistic 3D city: Google Photorealistic 3D Tiles through your Cesium ion account. Clean imagery for geographic context. Return to the analysis map for scientific layers; imagery is not a building-level deformation measurement.");
      } else {
        if (!osm) { osm = ionContext.buildings || await Cesium.createOsmBuildingsAsync(); if(!ionContext.buildings)viewer.scene.primitives.add(osm); } if("enableCollision" in osm)osm.enableCollision=true;
        osm.show = true; if (photo) photo.show = false; if (drape) drape.show = false; viewer.scene.globe.show = true; overlay.show = false; ver++; mode = "osm";
        say("Real terrain (Cesium World Terrain) and real building shapes (OpenStreetMap). Building geometry provides context. Return to the analysis map to inspect radar cells; no ground plane is drawn over terrain.");
      }
      bar.querySelectorAll("[data-city]").forEach(x => x.classList.toggle("on", x.dataset.city === mode)); await tilt(false);bar.dataset.cityState=mode;
    } catch (e) { say("3D city could not load: " + (e && e.message ? e.message : e) + ". Check that the Cesium token is valid and allows these assets (for the photorealistic view, add \"Google Photorealistic 3D Tiles\" to your ion assets)."); } finally {busy=false;if(bar.dataset.cityState==="loading")bar.dataset.cityState="unavailable";}
  }
  // Restore the flat analytical view before re-enabling scientific overlays.
  function exit() { if(busy)return; document.body.classList.remove("city"); cb.classList.remove("on"); note.style.display = "none"; try { if (osm) osm.show = false; if (photo) photo.show = false; if (drape) drape.show = false; viewer.scene.globe.show = true; if(savedVisibility){[overlay.show,outline.show,selEnt.show]=savedVisibility;savedVisibility=null;} const layer=document.querySelector("[data-lay=nisar]");if(layer)overlay.show=outline.show=layer.checked;
      if (flatTerrain) viewer.terrainProvider = flatTerrain; viewer.scene.globe.depthTestAgainstTerrain = false; overlay.rectangle.height = 0; mode = null;bar.dataset.cityState="map"; viewer.camera.cancelFlight(); const [w,s,e,nn]=projectedGrid?projectedGrid.bbox:S.bbox;viewer.camera.setView({destination:Cesium.Rectangle.fromDegrees(w-.12,s-.12,e+.12,nn+.12),orientation:{heading:0,pitch:-Math.PI/2,roll:0}});redraw();viewer.scene.requestRender(); } catch (_) { } }
  cb.onclick = () => document.body.classList.contains("city") ? exit() : enter("photo");
  bar.addEventListener("click", ev => { const t = ev.target.closest("[data-city]"); if (!t) return; const k = t.dataset.city; if (k === "exit") exit(); else if (k === "tilt") tilt(false); else if (k === "top") tilt(true); else enter(k); });
  /* pins stay as dots; their text overlapped into noise. Click a pin for its details. */
  const tame = () => { try { if (typeof insightPinEntities !== "undefined") insightPinEntities.forEach(e => { if (e.label) e.label.show = false; }); } catch (_) { } };
  setInterval(tame, 2000);
  const rd = window.redraw; window.redraw = function () { rd.apply(this, arguments); tame(); try { if (mode || busy) hideScience(); } catch (_) { } };

  /* 1b. open on the study site, not on the whole planet */
  const wait = setInterval(() => { if (typeof S === "undefined" || !S || !C) return; clearInterval(wait);
    if (real() && !/SYNTH/i.test(S.source)) setTimeout(() => { try { if (viewer.camera.positionCartographic.height > 2e6) flySite(0); } catch (_) { } }, 1200); }, 300);
})();
