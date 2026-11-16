# SWELL polish update

Install after Stakeholder Mission (compatible with Scientific Assurance as well; its server routes are preserved). Stop the server. Extract the archive in the SWELL project directory; run the installer with `--check` before installing. It refuses mismatched local source files, backs up replaced files, and never writes the study, `.env`, existing solver, AI provider, prior evidence packages or datasets.

```
python .\SWELL_polish_patch\apply_polish_patch.py --project . --check
python .\SWELL_polish_patch\apply_polish_patch.py --project .
python run_swell.py
```

Open Earth Studio at `/index.html` and refresh (Ctrl+F5). The layer selector offers the runoff and latest LOS layers explicitly. The real-observation badge is separate from clay-model warnings. The 3D city opens Google photorealistic context; OSM remains explicit, with terrain-aware camera and removed analytical rectangles. The actual OSM visual result still needs a live Cesium check. The Copilot collapses references and starts at the answer. Site Twin loads aligned imagery automatically when available and keeps the raw terrain view, original numerical solver and user controls. Its 3D recorder scrolls the actual canvas into view.

Worlds: Mission data searches the selected target and `Product_Observational` class through the documented PDS API, excludes context records and rejects contradictory target metadata. No unrelated fallback records. Environment now has opt-in native MOLA/LOLA elevation and slope. The server requests a 65×65-or-smaller native raster window from an allowlisted USGS GeoTIFF only after a range-request capability check. It refuses to download the entire multi-gigabyte global file via a non-range provider. Body radius is checked; native no-data cells withheld. Geodesic spacing uses the body's own ellipsoid. This adapter cannot certify landing sites, calculate illumination or temperature, or replace mission archives. Live PDS/USGS retrieval was not available in the sandbox.

Sources:
- https://nasa-pds.github.io/pds-api/guides/search/endpoints.html
- https://astrogeology.usgs.gov/search/map/mars_mgs_mola_dem_463m
- https://astrogeology.usgs.gov/search/map/moon_lro_lola_dem_118m
- https://cesium.com/downloads/cesiumjs/releases/1.127/Build/Documentation/Cesium3DTileset.html

Recording in a second active venv terminal:
```
python record_recovery_demo.py
python record_recovery_demo.py --planetary-terrain
python record_stakeholder_demo.py --role engineer --assurance --with-worlds
```
The second command requests the live numeric planetary windows; use it instead of the first if desired. The third requires the Scientific Assurance patch. The longer recordings are supplemental, not the official NASA demo. No change to existing scientific gates: unvalidated clay forecasts remain withheld. To perform radar and independent GNSS assurance, run the previous patch's `radar_assurance.py` and `gnss_assurance.py` with original cached granules and verified geometry. No actual Dallas raw granules or live service credentials were available for this update.

Tests: 134 Python regression tests passed on retained tree plus update; new PDS and planetary tests use controlled data. JS syntax and targeted Chromium native-DEM UI test passed. Installer reinstallation and dataset, solver, AI-provider hashes verified. Live external sources and the full Windows browser recording require verification.
