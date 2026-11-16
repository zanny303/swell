# SWELL research: repositories, papers, APIs and integration decisions

**Research date:** 15 November 2026. Links below were checked against current project/research pages where possible. Repository activity, licenses, model weights, dataset versions and API availability can change; re-check before adopting code or weights.

## 1. NISAR: the product semantics SWELL must get right

### Official mission context

- [NASA NISAR Mission Overview](https://science.nasa.gov/mission/nisar/mission-overview/) — NISAR launched 30 July 2025; L-band wavelength 24 cm, S-band 9.4 cm, global land/ice coverage every 12 days with an average ~6-day revisit across ascending/descending passes, and mode-dependent acquisition resolution around 3–10 m. NASA describes the data as free and open. This is acquisition capability, not the native posting of every derived product.
- [NASA NISAR data status](https://science.nasa.gov/mission/nisar/) — provisional L-band data products were announced 20 July 2026; current ASF data-user documentation lists validated, provisional and beta collection names. Always record the actual product maturity for each granule.
- [NISAR Data User Guide — GUNW](https://nisar-docs.asf.alaska.edu/gunw/) — GUNW is a Level-2 geocoded unwrapped interferogram. Unwrapped phase is at 80 m posting; wrapped interferogram is geocoded at 20 m; coherence is available at 20 m and 80 m. The product also contains connected-components and sub-pixel offset layers, an ionospheric phase screen and its uncertainty, and external correction lookup tables. The ionospheric screen is included but not applied to the interferometric data by default; available external corrections are not necessarily removed either.
- [NISAR Data User Guide — GCOV](https://nisar-docs.asf.alaska.edu/gcov/) — GCOV provides calibrated gamma-0 covariance/backscatter, corrected for radiometric and terrain distortions. It supports soil moisture, disturbance and inundation context. It is not a ground-displacement product.
- [NISAR product overview](https://nisar-docs.asf.alaska.edu/products-overview/) — distinguishes GSLC, GOFF, GCOV, GUNW and Level-3 soil moisture. This is the product-selection reference to use in the UI.
- [NISAR phase and coherence guidance](https://nisar-docs.asf.alaska.edu/phase/) — atmospheric effects, especially at L-band, and coherence quality matter to interpretation.
- [NASA JPL OPERA DISP product suite](https://www.jpl.nasa.gov/go/opera/products/disp-product-suite/) — DISP-S1 is the Sentinel-1-derived Level-3 displacement product; DISP-NI is explicitly marked “Coming Soon” on the current product page. Do not claim a released operational DISP-NI feed unless that page changes.
- [NASA JPL OPERA DSWx product suite](https://www.jpl.nasa.gov/go/opera/products/dswx-product-suite/) — the products use a common 30 m structure but JPL states that they are not harmonized across sensors; the current page marks DSWx-NI as under development. Check this before displaying it as an operational layer.

**Engineering consequence:** keep GUNW phase, GCOV backscatter, DSWx water extent, soil-moisture estimates and derived motion as separate data types. The user must see source, maturity, acquisition dates, orbit/direction, polarization, CRS, posting, masks, processing version, correction state and quality. A “radar change” label is not enough.

## 2. Geospatial foundation models and AI

### Best candidates

| Repository / paper | What it is | SWELL use | Critical limitation |
|---|---|---|---|
| [IBM / ESA TerraMind](https://github.com/IBM/terramind) · [ICCV 2025 paper](https://research.ibm.com/publications/terramind-large-scale-generative-multimodality-for-earth-observation) | Any-to-any multimodal EO foundation model; paper describes pretraining across nine geospatial modalities; Apache-2.0 repo | Best research candidate for cross-modal feature generation, missing-modality reasoning experiments and downstream fine-tuning. The repo includes a Sen1Floods11 example. | Not a validated NISAR-L-band ground-motion model. Fine-tune and test against NISAR-specific labels; do not interpret generated modalities as observations. |
| [NASA-IMPACT Prithvi-EO-2.0](https://github.com/NASA-IMPACT/Prithvi-EO-2.0) | NASA/IBM EO foundation model and downstream-task examples | Strong baseline for land-cover, burn-scar, landslide and flood-detection experiments; repository includes a flood-detection fine-tuning config using Sen1Floods11. | Check each config's exact input bands, sensor and preprocessing. A flood-detection example is not proof of NISAR support or deformation inference. |
| [TorchGeo TerraTorch](https://github.com/torchgeo/terratorch) | Apache-2.0 geospatial foundation-model fine-tuning/inference toolkit; supports Prithvi, TerraMind and other backbones | Use as the experiment harness for controlled, reproducible fine-tuning and inference. | It is a toolkit, not a model; third-party model and dataset licenses remain separate. |
| [Clay Foundation Model](https://github.com/Clay-foundation/model) | EO foundation model that encodes imagery, location and time into embeddings | Useful for similarity search, site analogues, anomaly triage and land-cover priors. | Embeddings are not flood/deformation probabilities. A task-specific head and validation are required. |
| [NASA-IMPACT Prithvi-WxC](https://github.com/NASA-IMPACT/Prithvi-WxC) | Weather/climate foundation model, 2.3B parameter pretrained variants and rollout examples | Research candidate for weather/climate representation or downscaling experiments. | High compute; pretraining data/variables and lead-time setup differ from local operational weather. Keep authoritative AIFS/NOAA/ECMWF forecasts as forcing until locally validated. |

### What to do with these models

1. Start with a conventional baseline and the current SWELL physics, not a giant model.
2. Build a NISAR-specific, sensor-aware benchmark: GUNW phase/coherence/quality, GCOV covariance/backscatter, acquisition geometry, weather/soil context and independent references.
3. Compare TerraMind, Prithvi and Clay embeddings as features, not authorities. Use TerraTorch for reproducible fine-tuning.
4. Split by whole site/event and by time. Never randomly split neighboring pixels and call the result geographic generalization.
5. Require independent validation against GNSS, leveling, gauges or field measurements where the target variable supports them.
6. Use LLMs for retrieval, tool selection, explanation and structured proposals. Do not use a vision-language model to hallucinate a displacement value from a rendered map.

### Recent benchmark worth using

- [GEOID-Flood repository](https://github.com/links-ads/geoid-flood) — current README describes 219 flood events across 65 countries, 12,236 1024×1024 tiles, co-registered pre/post Sentinel-1 GRD/RTC, pre-event Sentinel-2 L2A, Copernicus GLO-30 DEM and manually validated classes. The repository is MIT-licensed and includes TerraTorch configs. Its README describes area-of-interest splits so touching AOIs do not leak across train/validation/test. The full dataset is about 329 GB; a held-out evaluation slice is about 10 GB and the small sample is about 1.3 GB, so do not download the entire corpus for a deadline demo. Code is MIT-licensed; the separately distributed dataset is CC BY 4.0 and includes modified Copernicus data with required attribution.
- [GEOID-Flood paper record](https://huggingface.co/papers/2608.02315) — the paper summary describes more than 14,000 tiles. The repository README and paper summary report different counts; pin the dataset release/version before quoting a number in SWELL materials.
- Why it matters: it is a strong 2026 multi-modal flood benchmark and a good way to test Sentinel-1 + optical + DEM fusion. It is not NISAR L-band data. Transfer to NISAR requires explicit sensor-domain evaluation and likely fine-tuning.
- Environment note: GEOID-Flood's README pins `terratorch==1.1` and Python 3.11/3.12, while TerraMind's current repository asks for `terratorch>=1.2.5` and Python 3.11+. Keep these experiments in separate environments/containers until the dependency matrix is reconciled.

## 3. Physics and environmental models

| Repository | Capability | Best SWELL role | Decision |
|---|---|---|---|
| [ANUGA](https://github.com/GeoscienceAustralia/anuga_core) / [community-maintained source](https://github.com/anuga-community/anuga_core) | Python finite-volume shallow-water solver for flood and tsunami hydraulics | Site/area surface-water dynamics where terrain, inflows, friction and boundary conditions are available | Strong open-source candidate for 2D hydraulic flood cases; validate against gauges/high-water marks. Check exact current license and dependency stack before packaging. |
| [EPA SWMM](https://github.com/USEPA/Stormwater-Management-Model) | Dynamic hydrology/hydraulic/water-quality model for stormwater, wastewater and combined sewer networks; public-domain solver | Urban drainage networks, pipes, storage, pumps and controls | Use when the actual network topology and parameters are available. Not a substitute for regional terrain-based flood routing. |
| [Deltares HydroMT](https://github.com/Deltares/hydromt) · [JOSS paper](https://doi.org/10.21105/joss.04897) | Reproducible model building/analysis; plugins include Wflow, SFINCS, FIAT and Delft3D-FM | Data-to-model preparation, repeatable site configuration and model plugin orchestration | Strong architecture fit; model plugins have their own dependencies and calibration needs. MIT license for HydroMT core. |
| [NeuralHydrology](https://github.com/neuralhydrology/neuralhydrology) · [JOSS paper](https://doi.org/10.21105/joss.04050) | Research library for neural rainfall-runoff/streamflow models; BSD-3-Clause | Catchment-scale streamflow forecasts and basin analogues | Not a 2D urban inundation or soil-deformation solver. Needs gauged data and rigorous temporal/spatial holdouts. |
| [OpenGeoSys](https://gitlab.opengeosys.org/ogs/ogs) | Coupled thermo-hydro-mechanical-chemical simulation in porous/fractured media; Modified BSD | Future soil-water-ground deformation and geomechanical coupling where boreholes, stratigraphy, constitutive laws and calibration data exist | The old GitHub mirror explicitly says the project migrated; use the GitLab home, not the stale GitHub repo. High setup/calibration cost. |
| [HydroMT-SFINCS](https://deltares.github.io/hydromt_sfincs/) | HydroMT plugin for fast 2D hydrodynamic flood modelling | Regional flood hazard and scenario modelling | A better future regional flood path than trying to turn the existing reduced-order water-balance screen into a full hydraulic model. |

### 2026 paper: differentiable hydrology and extreme events

- Song et al. (2026), [“Physics-Informed, Differentiable Hydrologic Models for Capturing Unseen Extreme Events,” Water Resources Research 62(2), e2025WR040414](https://doi.org/10.1029/2025WR040414).
- The paper compares LSTM with differentiable HBV variants using temporal extrapolation and spatial tests on CAMELS basins. It reports that process-structured differentiable models can improve some unseen-extreme-event peak predictions, while also discussing trade-offs among extreme-event fit, generalization and internal-variable physical significance.
- SWELL lesson: hybrid physical + learned parameters can be useful, but test on unseen time periods and unseen regions, report failures and protect mass balance. Do not simply add a neural net and label the result “physics-informed”.

### Forecasting caution: pretrained flood weights

- [Google Research Flood Forecasting pretrained-model notes](https://github.com/google-research/flood-forecasting/blob/main/pretrained-models/Pretrained-Models-README.md) explicitly warn that released pretrained weights were trained on the full 1982–2023 historical period without a temporal holdout. Historical performance evaluation on that same period would be leakage/in-sample testing. The notes recommend fine-tuning, spatially held-out basin tests or future-only inference instead.
- This is exactly the kind of model-card warning SWELL should surface in its own UI.

## 4. Geospatial data plane and 3D digital twin

| Repository / standard | Capability | SWELL recommendation |
|---|---|---|
| [TiTiler](https://github.com/developmentseed/titiler) | FastAPI dynamic raster tiling for COG, STAC and Zarr; supports multiple projections and OGC tile services | Put COG/Zarr delivery behind a tile API instead of shipping full rasters into browser memory. |
| [PgSTAC](https://github.com/stac-utils/pgstac) | PostgreSQL schema/functions for high-performance STAC catalogues | Use for persistent, searchable acquisition/product/asset manifests and spatial/temporal queries. |
| [STAC FastAPI + PgSTAC](https://github.com/stac-utils/stac-fastapi-pgstac) | MIT-licensed HTTP STAC API backed by PgSTAC | Good catalogue service for collections/items/assets, filters and transactions. |
| [TiTiler-PgSTAC](https://github.com/stac-utils/titiler-pgstac) | Integration of TiTiler and PgSTAC | A useful pattern for catalogued raster assets and dynamic map tiles. |
| [OGC 3D Tiles](https://github.com/CesiumGS/3d-tiles) | Open specification for streaming large heterogeneous 3D geospatial datasets (photogrammetry, buildings, BIM/CAD, point clouds) | Use 3D Tiles for real city/site content with feature metadata, not a giant monolithic mesh. Cesium can keep global and local camera context coherent. |
| [gsplat](https://github.com/nerfstudio-project/gsplat) · [Nerfstudio](https://github.com/nerfstudio-project/nerfstudio) | Fast Gaussian-splatting rasterization and capture/reconstruction tooling; gsplat is Apache-2.0 | Add local photorealistic site captures when drone/ground imagery exists. Keep splat appearance separate from surveyed engineering geometry. |

### A realistic visualization stack

- **Global:** CesiumJS globe + NASA GIBS/imagery + terrain, with explicit source and date.
- **Regional:** tiled COGs for NISAR/OPERA/soil moisture/DEM, time slider and before/after comparison.
- **Site:** 3D Tiles for buildings/roads/terrain, selectable features with metadata and model linkage.
- **Physical:** Three.js/Cesium local cutaway for soil/water/asset model; conceptual subsurface remains visually distinct until boreholes exist.
- **Photorealistic:** 3D Tiles photogrammetry or Gaussian splats for local captured scenes, with survey/scale metadata. Do not imply a splat is a geotechnical survey.

## 5. Human-centred and decision-support research implications

The most important design pattern is not “dashboard + chat”. It is a **human-in-the-loop decision record** whose state is shared by the map, model and stakeholder workspace.

- One selected place, one active time, one data provenance chain, one model version and one scenario branch should drive all views.
- A person should be able to inspect a result's evidence and uncertainty, edit an intervention, compare alternatives and see the consequences for different roles.
- Decision recommendations must expose trade-offs, who benefits, who carries residual risk, cost assumptions, maintenance and what would falsify the recommendation.
- The system should be able to say “we cannot infer that” and propose the next measurement.
- A local checkbox is not a shared approval. Production collaboration needs authentication, role permissions, server-side persistence, audit history and explicit sign-off.

## 6. A public 2026 project example

- [dmanpark/dancing-with-the-sars](https://github.com/dmanpark/dancing-with-the-sars) is a public project repository whose README describes comparing L-band NISAR and C-band Sentinel-1 for flood mapping under vegetation, with temporal and optical cross-checks. Treat it as an implementation example, not an official NASA product, competition winner or validated scientific benchmark.
- Differentiation opportunity for SWELL: go beyond change visualization into physical intervention, scenario comparison, stakeholder review and follow-up verification. Keep the NISAR product science explicit.

## 7. Recommended integration order

1. **Now:** process one real NISAR GUNW or GCOV study site; expose product metadata and QA; validate the relevant variable independently.
2. **Next:** use TiTiler + COG and STAC/pgSTAC; preserve original HDF5 and provenance; stream rasters to Cesium.
3. **Next:** use TerraTorch to benchmark TerraMind/Prithvi/Clay on a carefully designed NISAR-specific downstream task. Compare to non-foundation baselines.
4. **For water:** use HydroMT to build a reproducible SFINCS or ANUGA setup; use EPA SWMM when urban drainage network data exist.
5. **For soil mechanics:** evaluate OpenGeoSys only after local soil profiles and constitutive parameters are available.
6. **For photorealism:** create one local 3D Tiles/splat capture with proper scale and survey metadata; do not attempt a world-scale photorealistic twin as a first release.
7. **For AI:** keep quantitative tools deterministic; add server-side model orchestration with citations and explicit approval gates.

## 8. Key sources

- NASA Space Apps 2026 event portal: https://www.spaceappschallenge.org/2026/
- NASA NISAR mission: https://science.nasa.gov/mission/nisar/mission-overview/
- NISAR GUNW guide: https://nisar-docs.asf.alaska.edu/gunw/
- NISAR GCOV guide: https://nisar-docs.asf.alaska.edu/gcov/
- NISAR product overview: https://nisar-docs.asf.alaska.edu/products-overview/
- OPERA DISP suite: https://www.jpl.nasa.gov/go/opera/products/disp-product-suite/
- TerraMind paper: https://research.ibm.com/publications/terramind-large-scale-generative-multimodality-for-earth-observation
- TerraMind repo: https://github.com/IBM/terramind
- Prithvi-EO-2.0: https://github.com/NASA-IMPACT/Prithvi-EO-2.0
- TerraTorch: https://github.com/torchgeo/terratorch
- Prithvi-WxC: https://github.com/NASA-IMPACT/Prithvi-WxC
- GEOID-Flood: https://github.com/links-ads/geoid-flood
- Song et al. 2026: https://doi.org/10.1029/2025WR040414
- ANUGA: https://github.com/anuga-community/anuga_core
- EPA SWMM: https://github.com/USEPA/Stormwater-Management-Model
- HydroMT: https://github.com/Deltares/hydromt
- NeuralHydrology: https://github.com/neuralhydrology/neuralhydrology
- OpenGeoSys: https://gitlab.opengeosys.org/ogs/ogs
- TiTiler: https://github.com/developmentseed/titiler
- PgSTAC: https://github.com/stac-utils/pgstac
- STAC FastAPI PgSTAC: https://github.com/stac-utils/stac-fastapi-pgstac
- 3D Tiles: https://github.com/CesiumGS/3d-tiles
- gsplat: https://github.com/nerfstudio-project/gsplat
- Google Flood Forecasting model caveat: https://github.com/google-research/flood-forecasting/blob/main/pretrained-models/Pretrained-Models-README.md
