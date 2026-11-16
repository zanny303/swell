# SWELL release notes — usability and reliability repair

## Preserved

- Earth Decision Studio remains the main application.
- Worlds remains a separate feature.
- The original Earth app/model computation files and existing data assets are retained.
- No synthetic data has been relabelled as real data.

## Changed

### Credentials

- Cesium ion public token can be remembered in the local browser profile.
- Saved token is restored automatically when the Earth dashboard opens.
- Added a clear Forget token action and explicit local-storage explanation.
- Terrain and buildings are initialized independently so a buildings failure does not conceal a successful terrain connection.

### Site Twin loading

- USGS 3DEP export requests now retry transient failures with exponential backoff.
- Provider error bodies and HTTP status are surfaced in the UI.
- Successful DEM requests are cached locally for 30 days by exact site/grid parameters.
- A Force fresh DEM request option bypasses cache.
- Incomplete DEM coverage is rejected; no synthetic terrain is interpolated into missing cells.
- The browser request has a 55-second timeout and a useful retry message.

### Earth dashboard usability

- Bottom workspace cards are now a single tabbed panel: Scenario, Timeline, Findings, Deliverables.
- Duplicate five-step workflow ribbon is removed; the main top navigation remains.
- Layer switches are grouped into Satellite imagery, Live hazards, Environment, and Site twin.
- The Decision Studio shows the selected stakeholder role rather than seven competing role cards.
- The role selector remains in the header; the duplicate role selector in the package panel is hidden.
- Synthetic bundled data is hidden by default. Users must explicitly open the sample twin to test synthetic map/simulation behavior.

### Data feeds and stakeholder interaction

- NASA CMR discovery includes OPERA DSWx-S1 and DSWx-HLS. NASA GIBS layers now use each product’s server default/latest available timestamp unless a date is explicitly selected; GIBS remains a tiled visualization service, not live video.
- FIRMS fire detections auto-load after zooming to a regional extent when `FIRMS_MAP_KEY` is configured.
- Stakeholder plans support local check-off state and evidence-file previews.

## Verification

- `python -m pytest -q`: 65 passed.
- `python tests/browser_site_twin.py`: passed in Chromium (actual Site Twin UI/interaction test with a synthetic test DEM fixture; it does not verify live USGS availability).
- `node --check` passed for `app.js`, `studio.js`, `upgrade.js`, `geo-upgrade.js`, `site-twin.js`, and `usability.js`.
- A full online Earth-dashboard browser test could not be completed in this build environment because Chromium navigation to the local app was blocked by the environment's browser policy. The changes to the main Earth dashboard are syntax-checked but still need a real-browser smoke test on the user's machine.

## Important limitations

- NASA GIBS is a tiled visualization service, not live video or raw scientific data.
- NISAR repeat observations are on a 12-day cycle; they cannot provide continuous real-time ground motion.
- The default bundled site dataset is still a synthetic fixture; it is now hidden by default in the main Earth dashboard. The map defaults to global Earth context, and the synthetic site marker is hidden until the user explicitly opens the sample twin.
- OPERA DSWx-S1/HLS are discoverable but their water-classification rasters are not yet automatically ingested/rendered.
- USGS 3DEP automatic terrain is U.S.-only; other regions need a global DEM adapter or user-provided DEM.
- The Site Twin flood kernel remains a screening model, not a validated 2-D flood solver.
