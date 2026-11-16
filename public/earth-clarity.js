/* Earth clarity pass (additive; loaded after app.js).
   1. The planet is always visible: Cesium's bundled Natural Earth II picture sits under the NASA layers,
      so the globe is never an empty dark screen if a live layer is slow or blocked.
   2. The app opens on the whole Earth with the study site marked, then you zoom in.
   3. The drawer shows three steps; only the chosen step's tools are listed. */
(function () {
  const $ = id => document.getElementById(id);
  // 1. always-on Earth picture (public-domain Natural Earth II, shipped inside CesiumJS)
  try {
    Cesium.TileMapServiceImageryProvider.fromUrl(Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII"))
      .then(p => { const l = viewer.imageryLayers.addImageryProvider(p, 0); l.brightness = .9; })
      .catch(e => console.warn("Natural Earth base unavailable", e));
    viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#16466b");
  } catch (e) { console.warn(e); }

  // 2. open on the whole planet; outline + label the study site so it can be found
  const marker = new Cesium.CustomDataSource("siteMarker"); viewer.dataSources.add(marker);
  let opened = false;
  const wait = setInterval(() => {
    if (typeof S === "undefined" || !S || opened) return;
    opened = true; clearInterval(wait);
    const [w, s, e, n] = S.bbox, lon = (w + e) / 2, lat = (s + n) / 2;
    marker.entities.add({ rectangle: { coordinates: Cesium.Rectangle.fromDegrees(w, s, e, n), fill: false, outline: true, outlineColor: Cesium.Color.fromCssColorString("#f2a33a"), outlineWidth: 2, height: 0 } });
    marker.entities.add({ position: Cesium.Cartesian3.fromDegrees(lon, lat), point: { pixelSize: 10, color: Cesium.Color.fromCssColorString("#f2a33a"), outlineColor: Cesium.Color.WHITE, outlineWidth: 2, distanceDisplayCondition: new Cesium.DistanceDisplayCondition(1.5e6, 1e9) },
      label: { text: S.name + "  (click Study site to zoom in)", font: "600 13px system-ui", fillColor: Cesium.Color.WHITE, showBackground: true, backgroundColor: Cesium.Color.fromCssColorString("#0b1a28cc"), pixelOffset: new Cesium.Cartesian2(0, -24), distanceDisplayCondition: new Cesium.DistanceDisplayCondition(1.5e6, 1e9) } });
    viewer.camera.cancelFlight();
    viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees(lon - 18, Math.max(-50, Math.min(50, lat - 8)), 1.45e7) });
  }, 200);

  // 3. three-step navigation
  const tabs = $("tabs"); if (!tabs) return;
  const STEPS = [["1", "Understand", "What happened, and how sure are we?", ["evidence", "copilot", "quake"]],
                 ["2", "Explore", "What could happen next, or if you change something?", ["lab", "structures", "worlds"]],
                 ["3", "Act", "Who does what, and how is it checked?", ["people", "contracts", "decisions"]],
                 ["+", "Your data", "Load your own site or rain forecast.", ["own"]]];
  tabs.querySelectorAll(".tab-group").forEach(x => x.remove());
  const bar = document.createElement("div"); bar.id = "steps";
  const hint = document.createElement("div"); hint.id = "stepHint";
  tabs.parentElement.insertBefore(bar, tabs); tabs.parentElement.insertBefore(hint, tabs);
  const show = k => { const st = STEPS[k];
    bar.querySelectorAll("button").forEach((b, i) => b.classList.toggle("on", i === k));
    tabs.querySelectorAll("button").forEach(b => b.style.display = st[3].includes(b.dataset.t) ? "" : "none");
    hint.textContent = st[2]; };
  STEPS.forEach((st, k) => { const b = document.createElement("button"); b.type = "button"; b.innerHTML = `<i>${st[0]}</i>${st[1]}`;
    b.onclick = () => { show(k); const first = tabs.querySelector(`button[data-t=${st[3][0]}]`); if (first) first.click(); }; bar.appendChild(b); });
  // keep the step in sync when a tool is opened from anywhere else
  tabs.addEventListener("click", ev => { const t = ev.target.closest("button"); if (!t) return; const k = STEPS.findIndex(st => st[3].includes(t.dataset.t)); if (k >= 0) show(k); }, true);
  new MutationObserver(() => { const on = tabs.querySelector("button.on"); if (!on) return; const k = STEPS.findIndex(st => st[3].includes(on.dataset.t)); if (k >= 0 && !bar.children[k].classList.contains("on")) show(k); })
    .observe(tabs, { subtree: true, attributes: true, attributeFilter: ["class"] });
  show(0);
})();
