# SWELL research and realism audit

**Audit date:** 2026-11-14  
**Scope:** Current `SWELL-pipeline-completion` source archive, its Earth dashboard, Site Twin, NASA archive adapters, and the requested NASA Space Apps 2026 *Dancing with the SARs* use case.

## Executive finding

SWELL should be built as an evidence-first Earth observation and decision-support system with two deliberately separate products:

1. **Earth Decision Studio:** global live context, local evidence, a site-specific physical twin, forecast/scenario work, verification, and stakeholder workspaces.
2. **Worlds:** a separate planetary exploration and data workspace.

A global satellite map is not a global real-time digital twin. Satellite products have different revisit periods, acquisition modes, processing latencies, native resolutions, and coverage. A trustworthy product must show the source, observation time, native resolution, processing level, quality mask, and uncertainty for every layer. Missing coverage must remain missing; it must not be filled with synthetic values and labelled as measured Earth data.

## Findings from the current code

### Earth dashboard

- The bundled `site/data/site.json` is explicitly a synthetic research fixture. The map overlay and derived model outputs are not NISAR observations.
- NASA GIBS is used for global visual context. GIBS serves pre-generated, tiled visualizations of Earth-observation products; it is not a raw-data archive or a live video feed.
- Esri World Imagery is used as close-up visual context. It is not a timestamped live satellite acquisition and must not be presented as such.
- USGS earthquakes are fetched as real event features. NASA FIRMS has a real feed adapter, but it requires the local server's `FIRMS_MAP_KEY` and was previously manual-only.
- The displayed model/ground-motion layer is derived from the bundled site fixture when that fixture is loaded. It must not be described as NISAR merely because the layer label mentions radar.

### Site Twin

- The existing numerical kernel is a **diffusive Manning-flow screening model with a closed outer boundary**. It is not a full 2-D shallow-water solver, a calibrated flood forecast, or a certified hydraulic design model. The browser `hydro.js` path is a per-cell water-balance screen; it is not a routed drainage-network or river model.
- The automatic elevation adapter uses USGS 3DEP. 3DEP is a United States source, not a global DEM. Its mosaic can have varying native resolution and vertical datum; the requested analysis cell size is a resampled grid and must not be confused with source resolution. USGS says 3DEP DEMs are typically NAVD88, but NGVD29 and local datums also occur, especially outside the conterminous U.S.; the raster header is authoritative for each downloaded DEM.
- Previously, terrain requests had no persistent request cache, only one provider attempt, and generic error handling. This made repeated territory loading fragile and hard to diagnose.
- The Site Twin requires real elevation and rainfall input; it must not fabricate a terrain fallback when the provider returns no coverage.

### AI and stakeholder workflows

- The weather adapter is a forecast input, not a SWELL-trained flood model.
- The current evidence assistant is structured/deterministic retrieval. It is not an autonomous research scientist and should not invent citations.
- `decision_engine.research` currently retrieves from seven curated source notes with TF-IDF. `literature_rag.py` chunks a user-supplied local corpus and ranks it with term-frequency/inverse-document-frequency scoring; optional Ollama generation is off unless a model is explicitly configured. `forecast_ensemble.py` runs nine deterministic rainfall/infiltration perturbations; those members are not calibrated probabilities or confidence intervals. `hybrid_calibration.py` trains a site/point-specific model from a user-provided history, not a globally pretrained SWELL model.
- The literature RAG adapter needs a curated, versioned corpus to provide useful source-grounded answers. A language model may explain retrieved evidence but must not be allowed to manufacture measurements, engineering parameters, or approvals.
- Stakeholder files include static reference templates and generated scenario packages. The generated package is decision support, not a professional certification or a construction-ready instruction set.

## NASA and remote-sensing facts that constrain the design

### GIBS: global visual context, not a raw-data pipeline

NASA GIBS publishes pre-generated visualization tiles. Some LANCE near-real-time layers can be available within roughly 3.5 hours of observation, while standard products can be available within about 24 hours; each layer has its own temporal range and native resolution. A close-up view cannot reveal detail finer than the source product's native resolution. SWELL must show the layer's actual date and native resolution, and should switch to a higher-resolution local imagery source only when that source is genuinely available.

Reference: https://nasa-gibs.github.io/gibs-api-docs/available-visualizations/  
Reference: https://nasa-gibs.github.io/gibs-api-docs/access-advanced-topics/

### NISAR: repeat observations, not live video

NISAR has a 12-day exact repeat cycle. Its data are free and open, and acquisition modes and products differ in resolution and availability. This supports time-series surface-change analysis, not minute-by-minute tracking. A SWELL map should show acquisition dates and revisit gaps rather than imply continuous real-time deformation sensing.

Reference: https://science.nasa.gov/mission/nisar/mission-overview/

### OPERA DSWx: a strong flood-observation input

NASA/JPL describes OPERA Dynamic Surface Water eXtent products as pixel-wise water detections from optical or SAR inputs, distributed as analysis-ready GeoTIFFs at 30 m posting. DSWx-S1 and DSWx-HLS are validated product lines. DSWx-NI (NISAR-derived) is listed as under development in the JPL product suite. SWELL should therefore discover and ingest available DSWx-S1/HLS products where coverage exists and must not claim a validated DSWx-NI feed before it is released.

Reference: https://www.jpl.nasa.gov/go/opera/products/dswx-product-suite/


### Global DEM coverage and limitations

Copernicus GLO-30 Public is a 30 m **digital surface model** (buildings and vegetation are included) and does not yet provide every tile globally; GLO-90 is the more complete worldwide surface model at 90 m. Neither should be silently treated as a bare-earth terrain model for precise urban flood hydraulics. OpenTopography provides global DEM APIs including Copernicus and NASADEM, but requires an API key and imposes per-user rate limits; its terms prohibit embedding one user's key in a public multi-user service. A future SWELL global adapter should therefore support local user-owned credentials or public COG tile access, preserve DSM/DTM classification, and refuse engineering-grade use without suitable bare-earth survey data.

Reference: https://registry.opendata.aws/copernicus-dem/  
Reference: https://copernicus-dem-30m.s3.amazonaws.com/readme.html  
Reference: https://opentopography.org/developers/  
Reference: https://www.usgs.gov/faqs/what-projection-horizontal-datum-vertical-datum-and-resolution-a-usgs-digital-elevation-model

### NASA CMR-STAC: preferred discovery contract

NASA CMR supports STAC-style item and asset discovery, including spatial bounding-box filtering. SWELL should standardize collection/granule discovery on CMR-STAC and preserve returned asset links, temporal metadata, checksums, and provider identifiers. The current CMR keyword search remains a useful compatibility path, but is not a complete raster ingestion system.

Reference: https://cmr.earthdata.nasa.gov/stac/docs/index.html  
Reference: https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html

## Research and open-source patterns reviewed

### Current 2026 *Dancing with the SARs* projects

The 2026 challenge asks for an interactive application using NISAR radar observations to track and visualize one or more types of surface change at locations around the world. The event is 14–15 November 2026; as of this audit date, the challenge is still in progress, so there are no 2026 global winners to study yet. Current public repositories are prototypes, not winning solutions.

- `dmanpark/dancing-with-the-sars` describes a flood use case comparing L-band NISAR and C-band Sentinel-1, including water under vegetation and an optical cross-check. The valuable pattern is a focused, falsifiable before/after story with a clear cross-sensor comparison, not a generic dashboard.
  https://github.com/dmanpark/dancing-with-the-sars
- `snon200/Dead-Sea-Alerts` describes an interactive NISAR deformation story tied to nearby infrastructure, while explicitly warning that its exploratory zones are not validated hazard assessments.
  https://github.com/snon200/Dead-Sea-Alerts
- `abilashprabakar27-ctrl/nisar-change-explorer` describes a map-first NISAR application with place search, data availability, NASA GIBS context, and a FastAPI backend. Its README labels several pieces as planned, so it is an architecture reference rather than proof of a complete production pipeline.
  https://github.com/abilashprabakar27-ctrl/nisar-change-explorer

### Flood forecasting and physics-informed AI

- Song et al. (2026), *Physics-Informed, Differentiable Hydrologic Models for Capturing Unseen Extreme Events*, compares differentiable HBV models with LSTM. The study reports better performance for rare extremes in its tested basins and argues that mass balance and storage-dependent flow provide useful structural priors. The transferable lesson is to couple learning to explicit conservation and storage equations, then validate on held-out extreme events and independent basins. It does not justify claiming a trained model for every SWELL location.
  https://doi.org/10.1029/2025WR040414
- Google's public flood-forecasting repository provides a useful global streamflow-model reference. Its published pretrained weights are explicitly trained on the full 1982–2023 historical period without a temporal holdout; the repository warns against using those weights for honest out-of-sample evaluation on that same period. Do not use in-sample metrics as a SWELL accuracy claim. Any warm-start must be re-evaluated with chronological holdouts and independent basins/events.
  https://github.com/google-research/flood-forecasting
- NASA's `cmr-stac` repository is the reference for NASA's STAC interface and should inform a reproducible discovery/asset-manifest layer.
  https://github.com/nasa/cmr-stac
- Deltares' GLOFRIM is a reference for coupling hydrological and hydrodynamic models. It is more relevant to basin/river integration than a single pixel-wise neural network.
  https://github.com/DeltaresProjects/HYD_SIM-glofrim

## Recommended SWELL pipeline

### A. Evidence ingestion (every source has a contract)

1. Search by AOI and time window using NASA CMR-STAC, USGS, NOAA, FIRMS, and the relevant local authority APIs.
2. Store immutable source manifests: provider, collection ID, granule ID, product version, acquisition time, processing time, footprint, CRS, pixel size, units, nodata, quality flags, URL, checksum, and license/attribution.
3. Download only assets needed for the AOI; validate checksums and file signatures before parsing.
4. Normalize raster assets into cloud-optimized GeoTIFFs (COGs) without discarding original assets. Preserve native values, quality masks, and uncertainty bands.
5. Publish map tiles through a tile service (for example TiTiler) rather than rendering entire rasters in the browser.
6. Keep observations, model state, forecasts, and user edits in separate typed layers. A model output must never overwrite an observation.

### B. Earth observation and surface-change pipeline

1. NISAR/OPERA acquisition discovery → granule selection → authenticated download or cloud access.
2. Product preflight: validate product family, processing level, polarization, orbit direction, baseline, CRS, geocoding, coherence, phase units, quality masks, and acquisition times.
3. Interferometric/time-series processing with mission-compatible software (for example ISCE3/OPERA products and MintPy where product formats are supported). Do not treat a single unwrapped interferogram as a validated displacement time series.
4. Reference stable areas and compare with independent GNSS where available; correct atmospheric/topographic artifacts and quantify decorrelation and uncertainty.
5. Produce a displacement layer with LOS geometry and acquisition pairs, then derive vertical/horizontal components only where viewing geometry and independent constraints justify it.
6. For flood mapping, ingest OPERA DSWx-S1/HLS as observed water extent with its classification/quality flags. Compare against optical imagery only where cloud and acquisition timing permit.

### C. Flood and urban-inundation pipeline

1. **Forcing:** gauge/radar rainfall and forecast ensembles; GPM IMERG as broad-scale observation context; soil moisture and antecedent rainfall as initial-state evidence.
2. **Terrain:** 3DEP in the United States; a documented global DEM source elsewhere; hydro-condition the DEM and record vertical datum, resolution, voids, and flow-conditioning operations.
3. **Surface/soil:** land cover and imperviousness, soil hydraulic parameters, roughness, infiltration, drainage network, culverts, levees, channel cross-sections, and surveyed assets where available.
4. **Boundary conditions:** upstream/downstream hydrographs and surveyed stages; explicitly reject a simulation if required boundary data are absent.
5. **Physics solver:** use a validated 1-D/2-D hydrologic-hydrodynamic model for flood depth/velocity (for example LISFLOOD-FP or an appropriately configured HEC-RAS 2D workflow). The current SWELL diffusive screen may remain a fast screening model, but must not be labelled a calibrated flood forecast.
6. **Calibration/validation:** use independent gauges, high-water marks, flood extent maps, and held-out events. Report depth/extent metrics, timing error, water-balance error, and spatial uncertainty.
7. **AI surrogate:** train only on validated solver runs and observations; enforce mass balance and physical bounds; use ensembles/quantiles; validate on temporally held-out extremes and spatially held-out catchments. Fall back to the physics solver or report insufficient evidence when outside the training domain.

### D. Geotechnical and infrastructure pipeline

1. Ingest NISAR/OPERA displacement and coherence, GNSS, soil moisture, precipitation, local soil survey, boreholes, utility records, and building/infrastructure geometry.
2. Separate radar LOS displacement, inferred vertical movement, and modeled future movement; never merge them into a single unqualified “ground truth” field.
3. Use site-specific constitutive/hydro-mechanical models (for example, a Richards-equation soil-water model coupled to poroelastic/geomechanical response) only when soil profiles, hydraulic properties, groundwater levels, and boundary conditions are present.
4. Calibrate against independent GNSS/leveling and field inspections; retain uncertainty and competing explanations.
5. Generate inspection priorities and draft design inputs, not stamped structural designs or certified G-code. Professional approval and authoritative asset data are mandatory before construction use.

### E. Forecast, AI, and RAG

- Keep weather forecast models, river-flow models, flood solvers, ground-motion models, and language models as separate services with explicit I/O contracts.
- Use AI for retrieval, evidence comparison, anomaly triage, uncertainty explanation, and surrogate acceleration only after scientific validation.
- RAG should index official product manuals, peer-reviewed papers, local engineering standards, and the project's own versioned evidence manifests. Every generated claim should cite a retrieved source and distinguish observed, inferred, simulated, and recommended statements.
- Never let a language model invent material properties, costs, pipe locations, building IDs, certification status, or regulatory approvals.

### F. Stakeholder products

Each role receives an in-app action board and a versioned evidence package:

- **Engineer:** observation and model overlays, uncertainty, site investigation plan, editable assumptions, CSV/GeoJSON/PDF drafts.
- **Planner:** neighborhood/parcel-level exposure and zoning/drainage alternatives, with data provenance.
- **Utility:** asset-linked inspection candidates; no invented pipe network when asset data is absent.
- **Emergency manager:** observed hazard extent, forecast window, confidence, affected assets, and human-approved draft alerts.
- **Resident:** plain-language local observations, confidence, and verified protective guidance.
- **Scientist:** source manifests, processing parameters, notebooks, model version, calibration and validation results.

Files must be previewable in the application, editable where appropriate, reproducible, and linked to the scenario/version that generated them. No export should be labelled “certified” unless a competent authority or licensed professional has completed the relevant approval.

## Current release changes

- Cesium ion token can be remembered in the local browser profile and restored on startup. This is intended for a public `assets:read` token restricted to localhost; it is not a secure vault for private credentials.
- Site Twin terrain acquisition now retries transient provider failures, returns readable provider errors, caches successful DEM requests locally for 30 days, and supports an explicit cache bypass. It rejects incomplete terrain rather than filling missing cells with invented values.
- Site Twin requests have a browser timeout and clearer loading/error text.
- NASA archive discovery now exposes OPERA DSWx-S1 and DSWx-HLS collection families. The main Earth imagery now requests each GIBS layer default/latest available date unless the user explicitly chooses a date, rather than hard-coding a two-day-old timestamp.
- Earth dashboard panels are consolidated into a single active bottom workspace; layers are grouped by purpose; the duplicate workflow ribbon is removed.
- When the bundled site is synthetic, the main Earth view now opens in live-context mode and hides the synthetic twin by default. The sample can be explicitly enabled for UI/model demonstration.
- FIRMS detections are requested automatically after the map is zoomed to a regional extent, provided the server has a valid `FIRMS_MAP_KEY`. These are fire detections, not flood detections.
- Stakeholder action plans can be checked off and evidence files previewed in the interface.

## Remaining production gaps (not claimed complete)

1. Full NISAR/OPERA raster download, QA, COG tiling, and time-series processing into a real site-specific `site.json` is not yet a one-click end-to-end pipeline.
2. OPERA DSWx-S1/HLS collection discovery is exposed, but its raster assets are not yet automatically rendered as flood extents in the main Earth map.
3. Global DEM routing is not yet implemented; automatic Site Twin terrain currently uses USGS 3DEP for the United States only. A future Copernicus GLO-30/GLO-90 adapter must label DSM versus DTM and reject missing tiles; it must not claim full 30 m global coverage.
4. FIRMS and USGS event markers are not a global flood hotspot layer. Flood extent must come from actual DSWx products and/or a calibrated hydrodynamic model.
5. The current Site Twin solver is a screening model, not a full shallow-water solver; no calibrated flood depth forecast or engineering certification is produced.
6. There is no fully trained, validated SWELL AI model for global flood or geotechnical forecasting. The architecture must be built and tested against independent observations before it can make that claim.
7. The full role-package workflow still needs real asset inventories, local engineering criteria, and formal approval integration before it can issue construction-ready outputs.
