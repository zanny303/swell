# SWELL — Gap Analysis, Product Blueprint & NASA Submission Strategy

**Prepared:** 15 November 2026  
**Basis:** `SWELL-audit-build`, `SWELL-real-data`, `SWELL-science-to-decision` archives and the code/tests contained in them.  
**Status:** implementation-specific audit, not a claim of operational scientific validation.

---

## Executive decision

Build SWELL as an **Earth-to-Action Decision Twin**: a place where people can move continuously from a real observation, to a defensible explanation, to an editable counterfactual, to a human decision, and then to verification against what actually happened.

The map is the spatial workspace, not a decorative background. The scientific model is the calculation engine, not a hidden black box. The AI is an evidence navigator and tool orchestrator, not an authority that invents measurements. The stakeholder experience is the product, not a collection of export templates.

The distinctive SWELL proposition should be:

> **See what changed. Understand what the radar can and cannot tell you. Change the physical assumptions. Compare possible futures. Agree on an action. Return to the next observation and check whether it worked.**

Do not try to win by adding the largest number of AI features, layers or 3D effects. Win by demonstrating one complete, real, repeatable decision loop that another team cannot reproduce by putting a map and chatbot beside each other.

## 1. What the uploaded code actually contains

### 1.1 Audit findings

The three archives are related revisions of the same project. The audit build is the most complete code base and is the correct starting point.

- The bundled `site/data/site.json` in all three archives is labelled `SYNTHETIC` / `Synthetic test site`.
- The archives do **not** contain a processed real NISAR study site, raw NISAR HDF5 acquisitions, or a validated local GeoTIFF observation stack. Test fixtures and exported reports are present; they are not real-world evidence.
- The audit build's Python test suite initially passed **81 tests**. The Site Twin browser harness passed against explicitly synthetic test terrain. The online Earth-view browser test could not be completed in the sandbox because external browser navigation/providers were unavailable.
- A passing test suite demonstrates software behavior under its test fixtures. It does not demonstrate that a live NASA feed, a particular NISAR granule, a real site forecast, a city-scale 3D twin, or a geotechnical prediction has been validated.

### 1.2 Existing application surfaces

| Area | Main implementation | What it already does |
|---|---|---|
| Earth Decision Studio | `site/index.html`, `site/studio.js` | Cesium globe, place/coordinate search, observation/inference/forecast/scenario states, map selection, painted water/drainage/paving/green interventions, time strip, chart, role-specific panel and export |
| Earth observatory | `site/live.html`, `site/live.js` | Global Earth context, location/GPS controls, NASA imagery and event overlays |
| Local Site Twin | `site/site-twin.html`, `site/site-twin.js`, `site_twin.py` | Real DEM acquisition/upload, aligned imagery, terrain mesh, direct cell edits, rainfall input, baseline/intervention run, numerical review, asset/soil screening, stakeholder plan and export |
| NISAR preparation | `real_site.py`, `nisar_preflight.py`, `radar_change.py`, `science_observations.py` | ASF/CMR discovery, GUNW/GCOV file handling, product preflight, selected-window processing and provenance records |
| Science and decision | `swell/`, `decision_engine.py`, `science_plans.py`, `forecast_ensemble.py` | Shrink–swell model, moisture-artifact correction, validation contracts, reduced-order water-balance/flood screening, ensemble sensitivity, review and decision packages |
| Data discovery | `earth_services.py`, `connections.py` | NASA CMR collection/granule discovery for NISAR, OPERA, GPM, SMAP, DEM and optical families |
| Location context | `location_services.py` | NWS alerts, USGS monitoring/gage context, GloFAS, modeled soil moisture and SSURGO soil-map context |
| Evidence retrieval | `literature_rag.py`, `decision_engine.py`, `site/research.js` | Curated-source retrieval and deterministic summaries; optional local Ollama generation is possible if configured |
| Worlds | `site/worlds.html`, `site/worlds.js` | Separate non-Earth workspace; should remain separate |

### 1.3 Existing external feeds and APIs

The code already contains adapters for:

- NASA CMR and Earthdata discovery, including NISAR GUNW/GCOV and OPERA DSWx-S1, DSWx-HLS and DISP-S1 collection families.
- ASF NISAR product discovery and Earthdata-authenticated file access paths.
- NASA GIBS imagery/WMTS and WMS capabilities.
- NASA GPM IMERG and SMAP discovery/context.
- NASA FIRMS VIIRS fire detections (requires `FIRMS_MAP_KEY`).
- USGS 3DEP elevation and USGS water-data context.
- Copernicus DEM fallback, where configured/available.
- ECMWF AIFS single-run daily precipitation via Open-Meteo.
- GloFAS river-discharge forecast via Open-Meteo.
- NWS active alerts and USGS earthquake feeds.
- USDA NRCS SSURGO soil-map queries.
- OSM Nominatim place search, Esri World Imagery, Cesium ion terrain and OSM 3D buildings (some require a user token/key or provider access).

**Important distinction:** a code adapter or catalogue query is not proof that a product was retrieved, ingested, quality-checked, aligned, scientifically interpreted or validated for a selected location. The UI must show those states separately.

## 2. The biggest gaps — ranked by impact

| Priority | Gap | Current state | What SWELL must become |
|---|---|---|---|
| P0 | No real end-to-end NISAR proof in the archives | Synthetic fixture; no real NISAR pair in uploaded bundles | One selected real site, granule IDs, maturity, exact acquisition dates, processing log, quality masks, derived rasters and a reproducible result package |
| P0 | Earth experience is fragmented | Earth Studio, observatory, connections and Site Twin are separate pages | One obvious Earth home; connect data without abandoning the map; drill from globe to site without losing place/time/role context |
| P0 | Forecast uncertainty is easy to misread | Training RMSE and parameter sensitivity can look like prediction intervals | Show calibrated intervals only when measured on independent holdouts; otherwise explicitly show “interval unavailable” and label sensitivity as sensitivity |
| P0 | AI is not a true generative agent | Deterministic evidence assistant and optional local RAG; no default LLM | Evidence-first copilot with selected-cell context, source citations, model tools, scenario proposals and explicit human confirmation; optional server-side model provider |
| P0 | One scenario is easier to make than compare | Baseline vs one active intervention | Save and branch multiple alternatives, compare identical baselines, retain inputs, outputs, source and reviewer note |
| P0 | Local 3D is not a full digital twin | DEM mesh and conceptual subsurface cutaway; optional Cesium terrain/OSM buildings | Separate visual reality from simulation geometry; add real 3D assets only where source and date are known; tie each editable asset to its model representation |
| P1 | No persistent multi-stakeholder collaboration | Role views and local checklists; no authenticated shared review | Shared scenario versions, comments, assignments, approval trail, permissions and audit history |
| P1 | No full geospatial data plane | Many raster layers are browsed as images or small grids | STAC catalog, immutable asset manifests, COG/Zarr, dynamic tile service, PostGIS and versioned processing workers |
| P1 | Model hierarchy is too coarse | Reduced-order SWELL and water-balance screening; not a full hydraulic/geomechanical solver | Solver selection by question and scale; calibrated local models; preserve SWELL as the soil-motion hypothesis model |
| P1 | Asset impact is not yet a true asset twin | Survey CSV screening and generic zones | Georeferenced roads, buildings, drainage, utilities and parcel/critical assets with source, date, elevation datum and inspection status |
| P1 | No complete forecast verification loop | Forecast connectors and sensitivity experiments | Issue time, valid time, lead, ensemble members, hindcast skill, calibration, reliability plots and later observed outcome |
| P2 | Field workflows are thin | Export files and local review checkboxes | Mobile field observations, geotagged photos, survey imports, offline capture and sync conflict resolution |
| P2 | Equity and trade-offs are not first-class | Role-specific plans, little distributional analysis | Who benefits, who bears residual risk, cost, access, vulnerable populations, uncertainty and maintenance burden |

### 2.1 The scientific issue that matters most

NISAR is not a live video feed. NASA describes a 12-day exact repeat cycle, with ascending and descending observations giving an average revisit of about six days over the mission. That supports repeat-observation analysis, not minute-by-minute deformation tracking. Its L-band wavelength is about 24 cm; the NISAR mission page lists acquisition-dependent SAR resolution of roughly 3–10 m, but the derived product grids have their own posting and support characteristics.

For SWELL's core ground-motion story, use the correct product semantics:

- **GUNW** is an L2 geocoded unwrapped interferogram. Current NISAR GUNW production is co-polarized HH or VV, nearest-neighbor 12-day, Frequency A. The unwrapped phase is posted at 80 m; wrapped complex interferogram is posted at 20 m; coherence is available at 20 m and 80 m. The product also includes connected components, sub-pixel offsets, ionospheric phase screen and its uncertainty, and external correction lookup tables. Some corrections are supplied but are not automatically applied to the interferometric data. Phase in radians is not itself vertical millimetres. Conversion requires the correct wavelength, LOS geometry, reference, phase convention, masks, correction choices and validation.
- **GCOV** is a calibrated, radiometrically and terrain-corrected backscatter/covariance product. Its pixel spacing depends on acquisition mode/bandwidth (10, 20 or 80 m for common L-band configurations). It is useful for intensity/backscatter change, soil moisture and inundation context; it is not a displacement product.
- **OPERA DSWx-S1/HLS** are independent water-extent products. JPL describes a common 30 m product structure but explicitly says the sensor products are not harmonized across sensors. The current JPL product page lists **DSWx-NI as under development**. Do not present it as a validated live NISAR water product.
- **OPERA DISP-NI** is listed as coming soon. Do not claim an operational NISAR displacement feed from it before release.

The app must never collapse these distinct products into one generic “radar layer”.

### 2.2 A forecast band is not the same thing as uncertainty

The main Earth chart previously drew a band using the model's training residual RMSE. That is not a calibrated future prediction interval. A three-parameter sensitivity range is also not a probability interval. This build removes the RMSE band and labels the training RMSE as a fit diagnostic. It also labels the water-balance engine as uncalibrated screening. That is less visually dramatic but substantially more scientifically credible.

The target forecast panel should show four separate things:

1. **Prediction:** central forecast conditional on a named model and inputs.
2. **Predictive uncertainty:** calibrated interval/quantiles from held-out residuals or an ensemble, with coverage and width.
3. **Sensitivity:** how the answer changes under alternate plausible parameters; never call this probability.
4. **Data/structural uncertainty:** missing observations, low coherence, uncertain boundaries, unknown assets, datum mismatch and model-form limitations.

## 3. The innovative product concept: the Evidence-to-Action Graph

The most valuable innovation is not another dashboard. It is one shared, versioned graph that connects the physical Earth, evidence, model state and human decision.

### 3.1 The five synchronized spaces

**A. Earth — where**
- Global globe → region → study footprint → cell/asset.
- 2D/3D navigation, terrain, buildings, roads, water, parcels and infrastructure where source coverage permits.
- Selection is persistent: moving from the globe to a site view preserves place, date, role and scenario.

**B. Evidence — what was actually observed**
- Raw acquisition, derived product, source granule, maturity, orbit/direction, polarization, issue/acquisition time, native posting, CRS, processing version, masks and hashes.
- Before/after swipe, linked time series, quality/coherence, coverage gaps and independent reference data.
- Every layer has a visible state: `observed`, `derived`, `inferred`, `forecast`, `scenario`, `verified`, or `unavailable`.

**C. Physical twin — how the place behaves**
- Existing SWELL shrink–swell model for soil/moisture-driven surface response.
- Separate hydrology and drainage solver for water routing; separate soil mechanics when real profiles and material coefficients exist.
- Editable interventions are typed physical objects: drainage change, rain garden, permeable surface, vegetation, retention, levee, pump, pipe or asset change.
- A user edit changes the model inputs/geometry, not the satellite observation layer.

**D. Futures — what could happen**
- Branching scenarios with common baseline and exact input snapshots.
- Forecast timeline, ensemble spread, parameter sensitivity, causal assumptions, threshold crossings and impact on selected assets/zones.
- Compare outcomes across role objectives: reduce movement, reduce runoff, protect access, protect utilities, reduce cost, reduce exposure or improve equity.

**E. Decisions — who does what next**
- Stakeholder role views over the same evidence and model state.
- Decision brief with alternatives, assumptions, uncertainty, dissent, owner, review status, cost/maintenance notes, approval and success criteria.
- Field action and follow-up observation return to the same evidence graph.

### 3.2 The state machine

Every location should move through explicit states rather than appearing to be a twin merely because it has a marker on a globe:

`CONTEXT_ONLY → COVERAGE_FOUND → ACQUISITION_SELECTED → DOWNLOADED → PROCESSED → QUALITY_CHECKED → VALIDATED_OBSERVATION → INFERRED_STATE → FORECAST → SCENARIO → HUMAN_REVIEW → APPROVED_ACTION → VERIFIED_OUTCOME`

A failed state stays visible. A site with no NISAR acquisition is `CONTEXT_ONLY` or `NO_COVERAGE`, not an empty “real-time twin”. A provisional product is not silently upgraded to validated. A model result is never painted as an observation.

### 3.3 The interaction that should define SWELL

1. Search or click a place on the Earth.
2. See what data exist there and what is missing.
3. Choose a real acquisition and inspect the raw/derived layers and quality.
4. Ask the copilot: “What changed here, and what evidence supports that?”
5. Select a cell, asset or zone and inspect its source values.
6. Paint or place a physical intervention on the map.
7. Compare several alternatives against the same baseline and timeline.
8. Switch to a stakeholder role and create a reviewable action proposal.
9. Record the human decision and the next measurement needed to verify it.

The map, charts, AI context, scenario record and exported package must all update from the same state. No parallel copies of the scenario are allowed.

## 4. Human needs SWELL should serve

People facing environmental risk do not primarily need more layers. They need to answer:

- What changed, where, and when?
- Is that change measured, inferred, forecast, or only a scenario?
- How confident should I be, and what could make the answer wrong?
- What can I change, and what is outside my control?
- What happens if I choose option A rather than B?
- Who benefits, who carries the residual risk, and who pays for maintenance?
- What evidence would change this recommendation?
- Who owns the next action, and how will we know whether it worked?

Design implications:

- Use plain-language headlines before technical detail; let experts expand into equations, metadata and validation.
- Make uncertainty interactive: click an uncertain result to see why it is uncertain and what measurement would reduce that uncertainty.
- Show no-data explicitly; do not interpolate an empty region into apparent certainty.
- Support keyboard navigation, contrast, screen readers, reduced motion and mobile layouts.
- Keep a low-bandwidth/field mode with cached site context and offline notes; clearly distinguish cached from current.
- Provide role-specific decision paths without creating separate, contradictory versions of the science.
- Show costs and maintenance only when sourced or explicitly user-entered; do not fabricate budgets or benefits.

## 5. Target technical architecture

### 5.1 Geospatial data plane

- **STAC** for collections, items, assets, time, geometry, platform, processing version and links.
- **pgSTAC + PostGIS** for indexed catalogue, footprints, sites, zones, assets, users, scenario geometry and review records.
- **Cloud Optimized GeoTIFF (COG)** for raster layers; **Zarr** for large multidimensional/time-series arrays; preserve original HDF5 files and checksums.
- **TiTiler** for dynamic raster tiles, band selection, mosaics and COG previews.
- **3D Tiles / CesiumJS** for terrain and city-scale 3D context. Use `deck.gl` or MapLibre only where an analytical layer benefits from it; avoid maintaining two unrelated map states.
- **Object storage** (S3-compatible/MinIO) for raw granules, COGs, imagery, model outputs and immutable manifests.
- **Worker queue** for NISAR processing, raster conversion, model inference, forecasts and exports; keep long jobs out of request/response handlers.

### 5.2 Science services

Keep model types separate and choose by question:

- SWELL shrink–swell model: moisture-artifact correction and soil-driven vertical response; retain as the project's unique core.
- NISAR GUNW/GCOV processing: product-specific observation pipeline, quality control and geophysical conversion.
- ANUGA or SFINCS/LISFLOOD-FP for 2D shallow-water/flood routing when boundary data and calibration are available.
- EPA SWMM for urban stormwater/drainage network modeling when sewer/pipe topology and parameters exist.
- HydroMT for reproducible geospatial model setup and model plugins.
- OpenGeoSys only for a future coupled groundwater/soil-mechanics branch when real stratigraphy and constitutive parameters are available.

Do not use a flood solver to claim geotechnical safety. Do not use a 40×40 screening grid to claim building-level inundation. Do not infer foundation depth, pipe location, soil profile or structural capacity from satellite pixels.

### 5.3 AI services

Use a layered system:

1. **Evidence retrieval:** query only the active site's manifests, validation records, selected cell, model run, relevant scientific notes and official product docs.
2. **Scientific tools:** deterministic, versioned tools for NISAR quality, phase conversion, moisture-artifact tests, model execution, forecast comparison and scenario evaluation.
3. **LLM orchestration:** a server-side model may choose which read-only tool to call and explain the results. It cannot create data, change the physics, approve actions or certify safety.
4. **Scenario proposal:** the model produces a structured proposal (parameters, assumptions, evidence IDs, affected geometry and expected metrics). The user reviews and explicitly applies it.
5. **Answer contract:** every quantitative claim must carry evidence ID, time, units, state type, model version, uncertainty status and limitation.
6. **Abstention:** no answer if source, quality, temporal alignment or evidence is insufficient. Ask for a new measurement instead.

Never place an Anthropic/OpenAI/other provider key in browser JavaScript or localStorage. Use server-side secrets, rate limits, user permissions and audit logs.

### 5.4 Realistic 3D without scientific deception

- Cesium terrain and OSM buildings provide useful geographic context, not a survey-grade asset model.
- Photorealistic 3D Tiles may be used where licensing, coverage and terms permit; do not assume global uniform coverage.
- Gaussian splatting/photogrammetry can add compelling local visual reality when captured from drone/airborne/ground imagery. It is appearance geometry, not automatically a metrically authoritative engineering mesh.
- Keep separate layers for: visual surface, surveyed geometry, model mesh, soil horizons, water table and underground infrastructure. Each requires its own source and accuracy metadata.
- For subsurface, display measured borehole intervals and geotechnical surfaces only when supplied; otherwise show a clearly labelled conceptual section.
- For direct manipulation, edit parametric interventions and model geometry, not arbitrary pixels of a photorealistic texture.

## 6. AI, forecasting and visualization priorities

### AI features worth building

1. **Ask this place:** the copilot receives map selection, acquisition, active layer, date, role and scenario.
2. **Explain this pixel/asset:** translate the selected cell's values, quality and provenance into plain language.
3. **Competing hypotheses:** moisture artifact vs actual motion vs decorrelation vs reference instability vs atmospheric/ionospheric contribution.
4. **Scenario composer:** translate natural language into explicit, editable model inputs; show assumptions before running.
5. **Evidence-gap agent:** identify which missing measurement most reduces uncertainty (GNSS, soil profile, gauge, DEM, drainage plan, next acquisition).
6. **Decision brief generator:** prepare a stakeholder-specific, cited draft with options, trade-offs and verification steps.

### Forecasting features worth building

- Forecast issue time and valid time; if unavailable, show that fact (the current AIFS connector does not receive a model run/issue timestamp from its endpoint).
- Multiple ensemble members or calibrated residual distributions; reliability diagram, coverage and sharpness on held-out periods.
- Temporal holdouts and whole-region holdouts; no random pixel splits as evidence of transfer.
- Hindcast replay: what would the model have forecast using only information available on that date?
- Forecast vs actual: after the next observation, score the previous forecast and record the error.
- Separate weather forcing, hydrologic response, soil moisture and ground motion. AIFS precipitation is weather forcing, not “ground-motion AI”.

### Visualizations that directly support decisions

| Visualization | User question it answers | Must connect to |
|---|---|---|
| Globe → site drill-down | Where is the problem and what is covered? | STAC footprint, acquisition and quality status |
| Before/after swipe | What changed in the observation? | Same product, date pair, mask and radiometry |
| Phase/coherence/ionosphere panel | Is the radar signal usable and what could bias it? | GUNW layers, correction state, phase convention |
| Linked time series | When did change occur and how does it relate to rain/moisture? | Acquisition time, weather/soil observations and model state |
| 3D terrain/asset view | Which real objects are exposed? | Terrain datum, asset geometry and source date |
| Cross-section | What is happening below ground? | Boreholes/profile or explicit conceptual label |
| Scenario branches | Which intervention changes the outcome? | Identical baseline, model version and input snapshots |
| Tornado/sensitivity chart | Which assumptions matter most? | Parameter ranges and rerun outputs; not a probability band |
| Uncertainty map | Where should we abstain or collect more data? | Quality mask, model spread and validation residuals |
| Stakeholder impact matrix | Who is affected and what action is possible? | Assets, access, service, cost and equity data |
| Verification timeline | Did the action work? | Subsequent NISAR/OPERA/field observation and predeclared success criteria |

## 7. Stakeholder journeys

| Stakeholder | Primary decision | Experience SWELL should provide |
|---|---|---|
| Geoscientist / remote-sensing analyst | Is this surface-change signal real? | Product maturity, phase/coherence/connected components, corrections, competing hypotheses, reference choice, LOS geometry and reproducible processing |
| Geotechnical / civil engineer | What needs investigation before design? | Ground-motion evidence, surveyed asset geometry, borehole/profile imports, parameter sensitivity, numerical checks and a non-certifying investigation plan |
| City planner | Which intervention should be prioritized? | Editable zones, alternative branches, runoff/movement impacts, cost inputs, equity and maintenance trade-offs |
| Utility operator | Which assets warrant inspection? | Asset overlays, elevation/datum checks, exposure screen, inspection task, evidence and later closure verification |
| Emergency manager | What can be said now? | Official alerts and observations, clear freshness, conservative uncertainty and explicit no-go on unvalidated road-safety claims |
| Resident / community group | What does this mean for my place? | Plain-language explanation, location context, visible uncertainty, questions to ask and transparent action/appeal record |
| Field team | What should we measure next? | Mobile checklist, GPS/photo/soil/gauge forms, offline capture, chain of custody and upload back into the same site record |

A stakeholder “approval” must mean an authenticated person with an authorized role, timestamp and decision record. A checkbox stored in one browser is a local review marker, not shared approval.

## 8. NASA Space Apps submission strategy

The supplied science-to-decision release identifies the project challenge as **“Dancing with the SARs”** and describes the requirement as an interactive, location-based visualization of NISAR surface change. I could not independently locate that exact title on the public official challenge pages, so confirm the exact challenge statement from your registered team page; the technical strategy here is aligned to the NISAR/SAR surface-change problem in your project materials. The [official 2026 Space Apps portal](https://www.spaceappschallenge.org/2026/) confirms the event dates as 14–15 November 2026 and says project submissions close on 15 November at 11:59 PM local time.

### 8.1 The strongest SWELL story

Keep the unique SWELL hypothesis as the flagship: **separate moisture-driven radar phase effects from actual clay-related ground movement, then turn the validated signal into a site-specific investigation/mitigation decision.** This is more distinctive than presenting a generic flood dashboard.

A convincing real-site proof should show:

1. A real location and an actual NISAR GUNW pair (or a clearly identified NISAR product appropriate to the surface-change question).
2. Product IDs, validated/provisional/beta maturity, acquisition dates, orbit/direction, polarization, native posting, source hashes and QA.
3. Raw unwrapped phase, coherence, connected components, ionospheric screen and correction state as separate evidence layers.
4. Correct phase-to-LOS displacement conversion and a carefully stated vertical-motion assumption; independent GNSS/leveling projected into the radar geometry where available.
5. Competing hypotheses and a clear abstention when evidence cannot distinguish them.
6. A scenario that a stakeholder can manipulate and compare against the same baseline.
7. A follow-up measurement plan and an explicit way to score the next acquisition/field observation.

### 8.2 Optimize explicitly for the judging criteria

The 2026 Space Apps local-event pages list five evaluation criteria: Impact, Creativity, Validity, Relevance and Presentation. SWELL should make each one visible in the demo:

| Criterion | What judges need to see from SWELL | Evidence to show |
|---|---|---|
| Impact | A real stakeholder decision that becomes faster, more transparent or better targeted | Named use case, affected assets/people, measurable action and verification plan |
| Creativity | The unique loop from NISAR signal interpretation to editable physical counterfactual and human decision | Moisture-artifact vs actual-motion hypotheses; interactive scenario branches; verification loop |
| Validity | Real NASA product use, correct product semantics, QA, uncertainty and independent checks | NISAR granule IDs, product maturity, phase/coherence/masks, model version, validation or explicit limitation |
| Relevance | Direct response to the assigned challenge, not a generic Earth dashboard | One focused NISAR surface-change story and a working end-to-end prototype |
| Presentation | A clear story that a judge can understand in under three minutes | One site, one insight, one intervention, one decision, one verification step |

### 8.3 Why “global digital twin” is not the submission claim

A global globe is useful navigation. It is not a global real-time digital twin. Product revisit, spatial posting, processing latency, cloud/coverage, sensor mode and local data quality vary. Demonstrate one real site end-to-end, then show how the architecture generalizes. Do not claim all locations are fully modeled.

### 8.4 Current public project comparison

A public 2026 repository named `dmanpark/dancing-with-the-sars` describes a flood-focused comparison of L-band NISAR and C-band Sentinel-1, including water-under-vegetation and optical cross-check ideas. Treat it as a public prototype/architecture example, not a judged winner or validated benchmark. The lesson is to tell a narrow, falsifiable radar story with independent cross-checks.

### 8.5 Suggested 2–3 minute demo sequence

- **0:00–0:20 — The human problem:** show a real place and a concrete decision (e.g. where to investigate seasonal ground movement before infrastructure damage).
- **0:20–0:45 — NASA data:** select a real NISAR acquisition pair; show product ID, dates, maturity, resolution and coverage.
- **0:45–1:10 — Scientific insight:** toggle phase, coherence and moisture context; show what is observed, what is inferred and what remains unresolved.
- **1:10–1:35 — Manipulation:** select a zone, adjust a physical intervention or parameter, and compare at least two saved scenario branches.
- **1:35–2:00 — Stakeholder decision:** switch role, show action owner, required field evidence, trade-off and human review.
- **2:00–2:20 — Verification:** show the next observation/measurement that would confirm or contradict the prediction.
- **2:20–2:30 — Impact:** “We do not just map change. We connect the observation to a testable decision and verify the outcome.”

If no real NISAR pair and independent reference can be processed before submission, say so. A clearly labelled software prototype is better than a synthetic result presented as a NASA measurement.

## 9. Implementation roadmap

### P0 — Submission-critical

- [x] Make Earth Decision Studio the home route; keep the real-data connection page available from the map.
- [x] Add an evidence-first copilot that sees active site/role/state and selected-cell values.
- [x] Require explicit confirmation before a natural-language scenario changes model inputs.
- [x] Add a scenario shelf with saved input snapshots, same-site comparison and restore.
- [x] Stop drawing training RMSE as a predictive uncertainty band; label fit diagnostics honestly.
- [ ] Process one real NISAR study pair and create a reproducible evidence manifest.
- [ ] Validate the selected signal against independent GNSS/field evidence or state clearly why such evidence is unavailable.
- [ ] Record a real browser walkthrough on the connected target machine with all API statuses visible.

### P1 — Product-grade next release

- Move raster delivery to COG + TiTiler; add STAC/pgSTAC/PostGIS and immutable manifests.
- Build a single site route with synchronized global/local camera, date, role and scenario.
- Add 3D Tiles for real city context; link editable assets to their engineering geometry and provenance.
- Add calibrated ensemble forecasting, hindcast replay and reliability plots.
- Add shared review records, permissions, assignments and immutable decision history.
- Add real asset, drainage and soil-profile imports with datum and accuracy validation.

### P2 — Differentiating platform

- Mobile field app with offline-first observations and conflict-aware sync.
- Multi-party scenario workshop with comments, alternative proposals and transparent dissent.
- Cost, maintenance, distributional equity and resilience metrics from sourced/user-entered values.
- Model registry and plugin selection for SWELL, flood hydraulics, stormwater, soil mechanics and remote-sensing inference.
- Continuous verification: forecast → observation → score → update calibration → next decision.

## 10. Acceptance criteria for calling SWELL a real decision twin

- One real NISAR location has acquisition IDs, raw files, source hashes, processing versions, quality masks and reproducible outputs.
- Observed, derived, inferred, forecast, scenario and verified layers are visually and semantically distinct.
- Native posting and effective resolution are shown; no false upscaling is implied.
- Phase, coherence, masks and correction state are available for a GUNW analysis; GCOV is not mislabeled as displacement.
- Forecast issue/valid time, holdout metrics, uncertainty coverage and interval width are reported; unavailable calibration is stated.
- At least three scenario branches can be saved and compared against the same baseline and model version.
- A stakeholder can edit a scenario, see which values changed, review the evidence and create a human-owned action proposal.
- The exported package preserves source, inputs, model version, output, uncertainty note, decision note and verification criteria.
- A later observation can be matched to the earlier forecast and scored.
- All claims in the demo can be traced to a source or are explicitly labelled as assumptions.

---

## Research companion

See [`RESEARCH_REPOSITORIES_AND_PAPERS_2026.md`](RESEARCH_REPOSITORIES_AND_PAPERS_2026.md) for current GitHub repositories, model choices, papers and integration recommendations.

See [`CLAUDE_CODE_PROMPT_SWELL.md`](../CLAUDE_CODE_PROMPT_SWELL.md) for the implementation-specific build prompt that can be given to Claude Code.
