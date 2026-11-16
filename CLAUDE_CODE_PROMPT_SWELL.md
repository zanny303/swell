# Claude Code build prompt — SWELL Earth-to-Action Decision Twin

Copy this entire prompt into Claude Code with the **updated SWELL project folder** open. Give Claude permission to inspect and edit the repository, run tests and create files. Do not ask it to start a new project.

---

## ROLE AND MISSION

You are the lead product architect, geospatial systems engineer, remote-sensing scientist, hydrologist/geotechnical systems engineer, human-computer interaction designer and technical submission lead for SWELL.

Your job is to **finish and materially improve the existing SWELL codebase**, not write another generic proposal or redesign it from scratch.

SWELL must become an Earth-to-Action Decision Twin. A person should be able to:

1. Explore a real place on Earth.
2. Discover what real satellite, weather, soil, terrain, water and infrastructure evidence exists there.
3. Inspect what was observed, what was derived, what was inferred and what remains unknown.
4. Ask an evidence-grounded AI copilot to explain the selected place, pixel, asset or model result.
5. Directly manipulate physical interventions and scenario parameters on the map.
6. Run the correct scientific model and compare multiple futures against the same baseline.
7. Understand uncertainty, trade-offs and who is affected.
8. Move into a stakeholder-specific decision workflow, record human review and identify what must be measured next.
9. Return to a later satellite or field observation and verify whether the decision worked.

This is not a dashboard with an AI chatbot beside it. The map, evidence, models, AI, scenarios, stakeholders and decision record must all operate on the same underlying site and scenario state.

## FIRST: UNDERSTAND THE ACTUAL REPOSITORY

Before changing code:

1. Read `README.md`, `docs/SWELL_GAP_ANALYSIS_AND_BUILD_BLUEPRINT_2026.md`, `docs/RESEARCH_REPOSITORIES_AND_PAPERS_2026.md`, `docs/AI_ARCHITECTURE.md`, `docs/RESEARCH_AND_REALISM_AUDIT.md` and this prompt.
2. Inspect the actual project tree. Start with these existing modules:
   - `run_swell.py`
   - `site/index.html`, `site/studio.js`, `site/model.js`, `site/research.js`
   - `site/ai-copilot.js`, `site/scenario-shelf.js`, `site/decision-experience.css`
   - `site/site-twin.html`, `site/site-twin.js`
   - `site/live.html`, `site/live.js`, `site/worlds.html`, `site/worlds.js`
   - `real_site.py`, `nisar_preflight.py`, `radar_change.py`, `science_observations.py`, `earth_services.py`, `connections.py`
   - `site_twin.py`, `decision_engine.py`, `forecast_ensemble.py`, `location_services.py`, `geo_services.py`
   - `swell/`, `literature_rag.py`, `literature/`, `tests/`
3. Run the full existing test suite and browser harnesses before edits. Record the baseline.
4. Inspect `site/data/site.json` and every data asset. If the source says `SYNTHETIC`, it is a software fixture only. Do not call it a real NISAR observation or use it as a real-site case study.
5. Build a feature inventory with columns: feature, exact files/endpoints, working state, test evidence, external dependency/key, limitation, next action.
6. Do not assume a service is live because an adapter exists. Exercise the actual request and record response/error/status.

The three source archives contained a synthetic fixture and no processed real NISAR HDF5/GeoTIFF study site. This is a known blocker for a truthful NASA-data demo. Your first deliverable must make this limitation visible and provide a reproducible path to ingest one real site.

## NON-NEGOTIABLE SCIENTIFIC AND PRODUCT RULES

### 1. Preserve the existing science

- Do not delete or rewrite the existing SWELL shrink–swell model, validation contracts, moisture-artifact correction, decision engine or scientific tests.
- Extend the current architecture in small, testable increments.
- Do not replace working functionality with mock cards or static sample numbers.
- Keep the separate Worlds workspace. Earth is the primary experience; Worlds remains a distinct destination.

### 2. Never mix observation and simulation

Every raster, chart line, value and visual object must have one explicit state:

- `observed`
- `derived`
- `inferred`
- `forecast`
- `scenario`
- `verified`
- `unavailable`

Never paint a model result as an observation. Never use synthetic data without a visible synthetic/demo label. Never silently interpolate missing or low-quality pixels into apparent certainty.

### 3. NISAR product semantics must be exact

Use the current official [NISAR Data User Guide](https://nisar-docs.asf.alaska.edu/):

- **GUNW** is the L2 geocoded unwrapped interferogram used for surface displacement analysis. Current GUNW production is co-polarized HH or VV, nearest-neighbor 12-day, Frequency A. Its unwrapped phase is in radians at 80 m posting; wrapped interferogram is geocoded at 20 m; coherence is provided at 20 m and 80 m; connected-components, sub-pixel offsets, ionospheric phase screen and its uncertainty are also available. The ionospheric screen is included but is not automatically applied to the phase; external phase correction lookup tables are not necessarily applied either.
- **GCOV** is calibrated gamma-0 covariance/backscatter with radiometric/terrain correction. Depending on acquisition mode it has 10/20/80 m spacing. It is useful for backscatter/soil moisture/inundation context, not displacement.
- **OPERA DSWx** products share a 30 m structure but JPL states that the products are not harmonized across sensors. DSWx-NI is currently marked under development; DISP-NI is currently marked coming soon. Check the product pages at implementation time.
- Keep GUNW, GCOV, DSWx, soil moisture and derived displacement separate in code, API, UI and exports.
- Do not equate the 3–10 m mode-dependent acquisition resolution with the posting of a derived product. Display native posting and effective resolution for every layer.
- Record collection short name and maturity (`VALIDATED`, `PROVISIONAL`, `BETA`) for every acquisition. Do not silently upgrade product maturity.
- A phase value in radians is not vertical displacement in millimetres. Implement and unit-test phase-to-LOS conversion, wavelength, sign convention, incidence/look geometry, reference strategy, masks, unwrapping/connected components and atmospheric/ionospheric correction state. If you infer vertical motion from LOS, show the assumption and do not imply that horizontal motion was measured away.
- Use independent GNSS/leveling/field reference where possible. If none exists, label the result provisional/unvalidated.
- OPERA currently lists DISP-NI as coming soon and DSWx-NI as under development in the relevant product documentation. Verify current release status at build time. Do not fabricate an operational product feed.

### 4. Forecast uncertainty must be honest

- Training RMSE is a fit diagnostic, not a calibrated future prediction interval.
- Parameter sensitivity is not a probability distribution.
- A single deterministic AIFS run is not an ensemble forecast.
- Every forecast must show issue time, valid time, lead, forcing source, model version, calibration status and known missing inputs. If issue time is unavailable from the current connector, show `issue time unavailable`.
- Only draw probability bands when ensemble or residual distributions have been calibrated on independent holdouts and coverage is reported.
- Add temporal and spatial holdouts, event/site-level splits, hindcast replay and forecast-vs-observation scoring.

### 5. The AI cannot invent science or silently act

- No provider key in browser JavaScript, HTML, localStorage or downloadable client config.
- AI responses must retrieve from active site manifest, selected cell, source records, model run, validation data and curated scientific references.
- Quantitative claims must include evidence IDs, units, time, state type, model version and limitations.
- If evidence is missing, the AI must say so and identify the next measurement that would reduce uncertainty.
- AI may call read-only evidence tools and deterministic simulation tools. It may propose a scenario as structured JSON, but it cannot apply it until a human explicitly confirms.
- Never let an LLM generate numeric model outputs, approve interventions, certify structural safety or invent a data source.
- If Claude/Anthropic or another LLM is configured, invoke it only server-side using an environment secret. Keep the existing deterministic/RAG fallback functional when no model key/service is available.

### 6. 3D must be beautiful and truthful

- Keep Cesium as the main global/local geographic experience unless there is a compelling tested reason to change it.
- Use Cesium terrain/3D Tiles/OSM buildings or an approved photorealistic provider where configured and licensed.
- Distinguish photorealistic appearance, OSM building extrusions, surveyed asset geometry, simulation geometry and conceptual subsurface.
- Gaussian splats are appearance reconstructions unless survey/control points establish metric accuracy. Do not use them as engineering meshes by default.
- No made-up buildings, pipe networks, foundations, soil horizons or groundwater levels.
- A conceptual subsurface cutaway must say it is conceptual until real borehole/soil-profile data exist.

## PRODUCT EXPERIENCE TO BUILD

### A. Earth-first home and continuous navigation

- `/` must open the Earth Decision Studio, not a setup page that strands a first-time user.
- Keep `connections.html` accessible from the map as the real-data onboarding path.
- Maintain a shared context object: site, bounding box, selected date/acquisition, role, selected cell/asset, active layer, scenario ID and model version.
- Global → region → site → cell/asset navigation must preserve that context.
- Make data coverage, source freshness, product maturity and unavailable layers visible without requiring a user to understand the code.

### B. Evidence workspace

- Every layer must expose source, acquisition/issue time, valid time, resolution/posting, CRS, units, product type, maturity, processing version, QA and limitations.
- Add linked before/after, phase/coherence, backscatter, quality mask, soil moisture/weather and independent reference views.
- Add a provenance drawer and a simple/technical detail toggle.
- Selecting a cell or asset must update the copilot context, chart, model panel and export.

### C. Direct physical manipulation

- The user must be able to select cells, draw polygons/lines, paint a zone and place parametric interventions.
- Support interventions that the current model actually understands: rainfall forcing, drainage/wetting reduction, paved fraction, vegetation/green space and any additional validated parameter you implement.
- Each intervention must have geometry, parameter, unit, magnitude, duration, provenance and a visible assumption.
- Do not create a UI control that changes no model output. Every control must connect to a deterministic solver parameter or be labelled as a future concept.
- Keep baseline and observations immutable. Editing affects only the scenario branch.

### D. Scenario lab

- Save at least three alternatives with exact model inputs, edited geometry, forcing, model version, source manifest, outputs, uncertainty status and human note.
- Compare alternatives against the same baseline and same horizon; block comparisons across incompatible sites/data/model versions unless explicitly normalized.
- Provide timeline scrub, baseline-vs-scenario, scenario-vs-scenario, zone/asset impacts and sensitivity/tornado analysis.
- Add export/import of scenario packages and a reproducible decision brief.
- Local browser storage is a demo fallback only. Production stakeholder collaboration requires server-side persistence, authentication, permissions and audit logs.

### E. Evidence-first AI copilot

The copilot must know:
- current site and acquisition;
- selected cell/asset and coordinates;
- active layer and date;
- stakeholder role;
- active scenario and model version;
- source/quality/uncertainty status.

It must support:
- “Explain this place/cell/asset.”
- “What changed and what evidence supports it?”
- “What is uncertain or missing?”
- “Compare these hypotheses.”
- “What measurement would reduce uncertainty most?”
- “What if I change rainfall/drainage/paving/vegetation?”
- “Prepare a stakeholder decision brief.”

Implement structured tool contracts, not free-form prompt magic. Example tools:

- `get_site_context(site_id, time_id)`
- `get_selected_cell(site_id, row, col, time_id)`
- `get_product_manifest(site_id, product_id)`
- `get_quality_report(run_id)`
- `retrieve_science_sources(query, site_context)`
- `run_swell_scenario(site_id, scenario_inputs)`
- `run_hydrology_scenario(site_id, scenario_inputs)`
- `compare_scenarios(scenario_ids)`
- `create_decision_draft(scenario_id, stakeholder_role)`

The AI must not have `approve_decision`, `delete_evidence` or any unconfirmed write tool.

### F. Stakeholder decision room

Create one shared site/science state with role-specific tasks:

- **Scientist:** inspect acquisition, phase/coherence, correction, reference and validation.
- **Engineer:** inspect motion/quality, assets and survey gaps; prepare an investigation plan, not a structural certificate.
- **Planner:** compare interventions, cost inputs, equity, maintenance and zone impacts.
- **Utility:** select assets and assign inspection/repair tasks.
- **Emergency manager:** view official alerts/observations and conservative no-go statements.
- **Resident/community:** plain-language site story, uncertainty, questions and transparent review status.
- **Field team:** GPS/photo/soil/gauge observation capture and later verification.

An approval must record authenticated actor, role, timestamp, version, note and evidence. If authentication is not implemented, label it `local draft review`, not shared approval.

## TECHNICAL INTEGRATION PLAN

### Geospatial data plane

Design toward:

- STAC for collection/item/asset metadata;
- PgSTAC + PostGIS for catalogue, geometry, site, asset and scenario records;
- original HDF5 retention + immutable hashes;
- COG for raster display, Zarr for large multidimensional/time series;
- TiTiler for dynamic raster tiles;
- Cesium/3D Tiles for 3D context;
- background workers for processing and long model runs.

Do not introduce the entire stack in one commit. Add the minimum useful layer, test it, then migrate incrementally. Keep the existing server working during the transition.

### Models to evaluate, not blindly install

- [TerraMind](https://github.com/IBM/terramind) + [TerraTorch](https://github.com/torchgeo/terratorch): multimodal EO representation/fine-tuning; evaluate on NISAR-specific data.
- [Prithvi-EO-2.0](https://github.com/NASA-IMPACT/Prithvi-EO-2.0): downstream EO baseline; inspect the exact sensor/band config.
- [Clay](https://github.com/Clay-foundation/model): embeddings for similarity/anomaly context; not a classifier without a task head.
- [Prithvi-WxC](https://github.com/NASA-IMPACT/Prithvi-WxC): weather/climate research candidate; not an automatic local operational forecast replacement.
- [GEOID-Flood](https://github.com/links-ads/geoid-flood): 2026 Sentinel-1/2/DEM flood benchmark; not NISAR data.
- [ANUGA](https://github.com/anuga-community/anuga_core): 2D shallow-water flood solver.
- [EPA SWMM](https://github.com/USEPA/Stormwater-Management-Model): urban drainage network solver.
- [HydroMT](https://github.com/Deltares/hydromt): reproducible model setup and plugins, including SFINCS.
- [OpenGeoSys](https://gitlab.opengeosys.org/ogs/ogs): coupled hydro-mechanical modeling; use only with real local profiles/parameters.
- [NeuralHydrology](https://github.com/neuralhydrology/neuralhydrology): basin-scale streamflow forecasting, not 2D site inundation.
- [TiTiler](https://github.com/developmentseed/titiler), [PgSTAC](https://github.com/stac-utils/pgstac), [STAC FastAPI PgSTAC](https://github.com/stac-utils/stac-fastapi-pgstac): geospatial data serving/catalogue.
- [3D Tiles](https://github.com/CesiumGS/3d-tiles), [gsplat](https://github.com/nerfstudio-project/gsplat): streaming city/site geometry and photogrammetric/splat appearance.

Check the current license, dependencies, model weights, dataset terms, hardware and model card before integrating any repository. GEOID-Flood currently pins TerraTorch 1.1 while TerraMind asks for TerraTorch 1.2.5 or newer; keep those research environments separate until reconciled. GEOID-Flood's full corpus is roughly 329 GB, so use a documented subset/held-out slice rather than downloading everything. Do not pull every repository into the runtime. Prototype one model at a time behind a clean adapter.

## IMPLEMENTATION ORDER — DO THE WORK, DO NOT STOP AT A PLAN

### Phase 0: Baseline and preservation

- Run all tests and record current result.
- Add regression tests for root route, synthetic-data labeling, product maturity and no-data behavior.
- Preserve Worlds and existing Earth/Local Twin functions.

### Phase 1: Real NISAR proof (highest scientific priority)

- Select one accessible site with actual NISAR L-band data.
- Use ASF/Earthdata/CMR/earthaccess discovery; capture granule/product IDs and maturity.
- Download one GUNW pair or appropriate GCOV time pair, preserving original HDF5 and checksum.
- Extract required datasets with correct polarization, orbit, dates, geocoding and metadata.
- Validate CRS, geotransform, no-data, connected components, coherence and correction state.
- Convert display-ready layers to COG with a provenance manifest.
- Process the data using a documented, unit-tested algorithm.
- If independent GNSS/leveling is unavailable, label the inferred motion as unvalidated; do not invent ground truth.
- Add a one-command reproduction script and a real-data smoke test that is skipped cleanly without credentials/network.

### Phase 2: One Earth workspace

- Make root `/` the Earth Decision Studio.
- Keep the connection wizard accessible inside the workspace.
- Connect global globe, local Site Twin and selected cell/asset context.
- Add coverage/maturity/provenance/uncertainty display.
- Keep the map as the main working canvas, not a background behind card grids.

### Phase 3: Copilot and scenario branches

- Extend the evidence-first copilot with selected-cell and site context.
- Add optional server-side LLM provider only if configured; deterministic fallback remains.
- Add typed tools and schema validation.
- Add 3+ scenario branches, same-baseline compare, save/restore/export, and human review notes.
- Require explicit confirmation for all model-changing actions.

### Phase 4: Forecast and model rigor

- Add ensemble/uncertainty and hindcast verification.
- Show issue/valid time and missing data.
- Add temporal and spatial holdouts; report calibration, coverage and error by region/event.
- Keep SWELL ground-motion and flood/urban drainage models separate.
- Integrate one physical solver only after its input data and calibration are available.

### Phase 5: Immersive local digital twin

- Use real terrain and building/asset geometry with provenance.
- Add 3D Tiles and optional local photogrammetry/3DGS.
- Keep surveyed geometry and visual geometry separate.
- Add real soil profiles/underground assets only from measured/imported data.
- Make interventions editable in the map and directly connected to the solver.

### Phase 6: Stakeholder and verification loop

- Add authenticated multi-user roles, comments, action assignments, approval records and audit history.
- Add mobile/offline field observations.
- Define success criteria before an action.
- Compare subsequent satellite/field evidence against the prior forecast and record whether the action worked.

## REQUIRED ACCEPTANCE TESTS

Do not call the build complete until the following tests pass or an explicit blocker is documented:

1. `/` opens the Earth Decision Studio; `connections.html` remains reachable.
2. Synthetic fixture is visibly labelled in every map, chart, AI response, export and demo mode.
3. No synthetic fixture is included in a real-data claim or submission screenshot without a synthetic label.
4. GUNW and GCOV appear as distinct product types with distinct units/metadata.
5. GUNW phase conversion is unit-tested and uses correct wavelength, sign convention and LOS geometry; low-coherence/invalid components remain masked.
6. Product maturity, acquisition date, orbit/direction, posting, CRS and correction state are displayed.
7. Training RMSE is never drawn or labelled as a calibrated predictive interval.
8. Forecasts show issue time/valid time or clearly say unavailable.
9. Scenario edits never mutate observed data; they update only the scenario branch.
10. Natural-language scenario proposals are shown before applying; clicking Apply is required.
11. At least three alternatives can be saved and compared on the same site/baseline; incompatible versions are blocked or clearly normalized.
12. Copilot quantitative claims cite active evidence/model records; it abstains when evidence is missing.
13. A selected cell updates map, chart, copilot context and export consistently.
14. Role-specific decision drafts show evidence, assumptions, uncertainty, owner, action and verification criteria.
15. No local checkbox is represented as authenticated multi-user approval.
16. All existing Python and browser tests still pass; new features have browser/unit tests.
17. No provider API keys appear in client bundles, browser storage, source control or exported packages.
18. A fresh install/run guide works from a clean environment.

## REQUIRED DELIVERABLES

Implement the changes, then produce:

1. Updated working application source.
2. Full passing test report and any skipped live-provider tests with reason.
3. `SWELL_REAL_DATA_RUNBOOK.md` with exact data access, product selection, processing, QA and reproduction steps.
4. `SWELL_MODEL_CARD.md` with intended use, prohibited use, assumptions, validation, error, uncertainty and known failure modes.
5. `SWELL_SUBMISSION_BRIEF.md` with problem, innovation, NASA/NISAR relevance, evidence, demo story, impact, limitations and next steps.
6. A 2–3 minute demo script and exact screen sequence.
7. Screenshots from a real browser session (not fabricated UI mocks).
8. A final file inventory and explicit list of features that are implemented, partial, blocked or future.
9. A ZIP of the updated project, with no secrets, raw user credentials or unlicensed third-party datasets.

## WORKING STYLE

- Implement, run, inspect, correct, and re-run. Do not just describe what you would do.
- Keep commits/patches small and explain the reason for each architectural change.
- Prefer the existing stack and existing working APIs. Add dependencies only when they solve a demonstrated need.
- Do not hide an unavailable provider or model behind a fake success state.
- Do not claim “real-time”, “hyperrealistic”, “AI-powered”, “NASA-validated”, “engineering-grade” or “digital twin” unless the exact capability is working and its data/validation basis is shown.
- If a required real dataset, key, calibration or external service is unavailable, build the correct connection point and report the blocker. Do not manufacture a replacement dataset.
- Optimize for scientific credibility, usability, and a coherent decision experience—not feature count.

**Start now by running the repository audit and tests, then implement Phase 1 and the highest-value Phase 2–3 items. Do not stop after writing a plan.**

## ADDITIONAL RELEASE REQUIREMENTS (2026-11-15)

- Read `docs/LIVE_TESTING_AND_API_SETUP.md`, `docs/SWELL_MODEL_CARD.md` and `docs/SWELL_DEMO_SCRIPT.md` before further changes.
- The Claude API default is `claude-sonnet-5` and the stable API version header is `2023-06-01`. Do not revert to `claude-sonnet-5-5` or an unverified API version. Before changing a model ID, check the provider's live `/v1/models` response and official deprecation documentation.
- Add tests for provider configuration without requiring a real key. Live provider tests must be opt-in and skipped with an explicit reason when credentials are absent.
- Verify both deterministic fallback and the actual Claude tool loop with a real key before claiming live AI is connected. The Copilot must never claim that a draft proposal was applied or a model was run unless the deterministic SWELL backend confirms it.
- Create a reproducible live-site manifest that records AOI, source product IDs, maturity, timestamps, checksums, CRS, units, model version and processing parameters. Keep secrets and raw credentials out of the manifest.
- Do not describe a local HTTP server or a static browser preview as production deployment. Production needs TLS, authentication, authorization, CSRF protection, rate limits, durable database/storage, secret management, backups, monitoring and a documented threat model.


---

## V3 implementation state — preserve these changes

The current codebase includes a provider-neutral AI gateway in `ai_provider.py`. Preserve its support for Anthropic Messages, OpenAI Chat Completions, Meta Model API, local Ollama and compatible endpoints. The Connections UI has one provider/key/base URL/model field set, model discovery, and an explicit live generation test. Never reintroduce a Claude-only route or send API keys to the browser.

`/api/system/health` and the Earth header distinguish a provider connection check from a real study actually loaded. `connections.run()` persists only redacted connection summaries; it must not store credential values. NASA CMR zero-granule coverage is a no-data/AOI issue, not a bad API key. Do not report `ready_for_real_twin` as a loaded site.

The AI evidence gateway must continue excluding numeric site evidence, selected-cell values and scenario numbers whenever `site/data/site.json` is marked `SYNTHETIC`. Keep synthetic data for automated tests only. Never modify source labels to simulate a successful real-data build.

The local literature retriever is BM25 lexical RAG with source URL, source-file SHA-256, word offset and evidence ID. Do not call it vector/embedding RAG unless an embedding index is actually implemented.

The default workspace is Stakeholder Decision Room. The stakeholder workbench is embedded in the main Earth workspace and includes selected-cell context, direct intervention actions, role-specific plans, cited research retrieval, a decision ledger and real-site decision pins. The ledger is local single-user and tamper-evident, not authenticated multi-user governance.

Research cards for PINN, Q-learning zone sequencing, cross-site similarity and deterministic sensitivity ensembles are explicitly labelled research/screening methods. Do not promote them to operational algorithms or calibrated predictions without a reproducible real-site run and validation.

Before making further changes:
1. Run `python -m pytest -q`.
2. Run `node --check` on all changed browser scripts.
3. Test `/api/system/health`, `/api/ai/status`, `/api/ai/models`, and `/api/real-site/status`.
4. Test each provider adapter with mocked HTTP responses and, on the user's machine, the explicit Test AI generation action.
5. Verify the real-site build writes a non-synthetic `site/data/site.json` from actual acquisitions and that the Earth workspace reloads it.
6. Do not claim a real NISAR demonstration, live provider test, GNSS validation, multi-user collaboration or photorealistic asset twin unless actually verified.
