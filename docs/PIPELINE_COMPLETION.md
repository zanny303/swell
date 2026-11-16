# SWELL — executable integration pipelines

Build on the connected-site release. Original Earth globe and Worlds renderer are unchanged. New Site Twin controls are collapsed under Verify. No upstream downloads or live model inference were verified in this sandbox. Test data are synthetic fixtures.

## Start here

Use existing `START_SITE_TWIN.txt` and `connect_check.py`. All prior dependencies remain; new modules use the existing NumPy, rasterio, h5py, pyproj and standard library. For authenticated NASA acquisitions install `earthaccess` and configure Earthdata Login locally. Do not place keys into JS, commits or export files.

## NASA challenge-first case: actual paired radar changes

1. Search for NISAR Level-2 GCOV data using the exact active collection from Earthdata Search or the existing product catalog. See https://nisar-docs.asf.alaska.edu/gcov/ and https://asfopensarlab.github.io/NISAR_Cookbook/nisar-data-access/. Select two chronological acquisitions with same L-band relative track, orbit direction, frame, mode, polarization and source. Do not assume maturity; check the collection/provider, release ID, local incidence, calibration, shadow/layover, noise and processing metadata. Beta/unknown output is familiarization only. Download the official files using `nasa_download.py --collection SHORT_NAME --bbox WEST SOUTH EAST NORTH --start YYYY-MM-DD --end YYYY-MM-DD --download` (one bounded selection; inspect before downloading).
2. Execute `python radar_change.py BEFORE.h5 AFTER.h5 --bbox -96.9 32.7 -96.7 32.9 --out radar-review --pol HHHH --maturity provisional` (only declare provisional if documented). Official granule filenames required. The processor reads a bounded AOI window, checks native grid alignment, masks invalid/nonpositive samples and low looks, calculates before/after gamma0 dB and 10 log10(after/before), and retains file hashes. Only matching grids are accepted; independently aligned acquisitions are not yet supported. Geographic bounding box is transformed into the scene CRS; the rectangular projected subset is not an exact clip polygon. Filename checks do not verify local incidence or calibration. It is NOT a flood classification or a deformation inversion. Large file hashing may take time.
3. Import the resulting GeoTIFFs into existing Earth raster upload/overlay workflow. Preserve `radar-change.json` alongside them. Compare with OPERA DSWx and local gauges; permanent water, vegetation, shadow and soil moisture can confuse interpretation. For GUNW use existing `nisar_preflight.py`; phase cannot be interpreted as vertical displacement without corrections and geometry. No arbitrary thresholds are presented as verified flood detections.
4. Site Twin: register real DEM, use historical forcing for the acquisition time, save run, import independent OPERA water class at the same event/hour, evaluate existing IoU workflow. No scientific pass until holdout data support it. Separate radar-change observation from physics forecast.

## Forecast uncertainty

In Site Twin > Verify > Forecast sensitivity ensemble, run nine combinations of rainfall multipliers 0.8/1/1.2 and infiltration multipliers 0.5/1/1.5, using the saved intervention, roughness and outlet. Each is a fresh numerical run. Reports per-member water budgets, peak depth, wet area, cellwise min/max peak and number of members wet at 5 cm. The multipliers are illustrative assumptions, not forecast ensemble probabilities; no distribution or calibrated intervals are claimed. The report enters the existing review ZIP. Budget cap: 24,000 cell-hours. Broader uncertainty including roughness, drainage, DEM error and weather ensembles requires independent calibrated distributions.

## External scientific solver and AI output exchange

`model_products.py` accepts already-computed georeferenced rasters from an independent model. It checks type, units, declared time, content hash, native resolution, grid registration, valid ranges and overlap, and preserves source metadata. No automatic execution/training or skill certification. Types: binary `water_class` (0/1, nearest), `water_probability` (0–1, average), `depth` (m, declared vertical datum identical to site), `los_displacement` (mm, explicit `los_convention` with reference/sign). The source must use a projected metre CRS and site spacing must not be finer than source pixels. All outputs remain unvalidated. Example:

```
python model_products.py SITE_ID predicted-water.tif pipeline/templates/model-product.json
```

Fill the JSON first and compute the actual SHA-256 (`python -c "import hashlib; print(hashlib.sha256(open('predicted-water.tif','rb').read()).hexdigest())"`). Import the returned aligned GeoTIFF into Earth, or compare independent binary observed water using existing Verify only if it genuinely represents independent observations. Never use predictions as ground truth. Use `version` to identify upstream code and weights, and `input_provenance` to document acquisition and preprocessing. For a true independent hydraulic solver use a surveyed drainage network, model boundaries and evaluation protocol (EPA SWMM or Landlab are candidates); export its raster with these metadata. Coupled subsurface mechanics requires surveyed profiles, stress/strain constitutive law and boundary conditions; current profile model is screening only.

## Research and language AI

Use locally obtained, lawfully accessible source text (.txt or .md) and copy `pipeline/templates/literature-corpus.json` into the same directory, filling title, URL and local filename. This pipeline retrieves actual passages by weighted term overlap with source ID, offset and SHA-256. No remote corpus harvesting or model is silently assumed. `python literature_rag.py path/to/corpus.json "How should we validate water extent?" --out answer.json` works without any LLM. Optional: run your own Ollama server and download a model supported by your hardware, then add `--model YOUR_INSTALLED_MODEL`. Model call uses localhost only, no API key, no tool execution, sources treated as untrusted. Output is a draft; ID validation does not establish factual entailment. Set `SWELL_LITERATURE_CORPUS` to corpus path and optionally `SWELL_OLLAMA_MODEL` in your server shell before starting SWELL; use Site Twin > Verify > Research evidence assistant. Avoid sensitive data in a served corpus; use trusted local deployment only. Model inference not tested here. Existing deterministic research assistant is preserved.

## Model selection — what to use, not what to overclaim

- ECMWF AIFS via existing forecast connector: near-term atmospheric forcing. Not a parcel-level flood-depth model.
- NASA/IBM Prithvi-EO 2.0: optical HLS-based segmentation/representation foundation model, https://github.com/NASA-IMPACT/Prithvi-EO-2.0. Follow official TerraTorch dataset preparation and fine-tune/evaluate examples. Optical input requires correct reflectance scale, bands, time, cloud and no-data mask. No direct NISAR substitution. Export georeferenced mask/probabilities through exchange above. Requires model weights, training/validation data and compute; no upstream model execution implemented here.
- NASA/IBM Prithvi-WxC: https://github.com/NASA-IMPACT/Prithvi-WxC, 2.3B-parameter weather/climate foundation model with 6h rollout checkpoint. Requires prescribed MERRA-2/climatology fields and substantial computing; AIFS connector is the practical immediate choice. Not integrated or benchmarked in this release.
- Existing local residual-learning model: chronological real-history input and point forecasts with skill and applicability checks. Do not train on fabricated observations.
- LLM: explanation and source-linked reports, not solver or engineering certifier. Optional local connector above.

## Remaining blocked paths and requirements

| Path | Existing executable step | Required before claiming complete |
| --- | --- | --- |
| Real imagery and high-resolution 3D | Cesium imagery/terrain/building connections and georeferenced DEM/photo registration | Connected browser, provider terms/token, coverage and actual screenshot verification; photorealistic mesh alignment and measured subsurface geometry still not implemented |
| Real radar | Catalog/downloader, GUNW preflight, GCOV change | Real compatible granules, correct maturity, corrections and field validation |
| Physics | Terrain flow, outlet, moisture-profile and exposure calculations, sensitivity | Surveyed geometry, boundary flows, pipe network, calibrated parameter fields and independent validation; full hydraulic/geomechanical upstream solver execution not integrated |
| AI | AIFS adapter, residual fitting/testing, external raster exchange, local optional literature generation | Credentials/service, real training archive, upstream model computation/weights, calibrated holdout scores, independent answer review |
| Design/CAD/CAM | Audited review DXF/GIS, scenario and review evidence | Survey, geometry, material and loads, applicable standards, independent design and CAM verification and licensed review. No construction-ready design or executable G-code generation supplied. |
| Worlds | Existing separate workspace | Real PDS coverage, projection-aware terrain and rendering validation; no planetary physics solver integration added here. |

## Winning approaches researched (2024–2025)

NASA announcements: https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/ and https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-international-space-apps-challenge-announces-2024-global-winners/.
Resonant Exoplanets: ML detection and physical validation, public repo https://github.com/KingTadar12/resonant-planet; exact model architecture not verified. 42 QuakeHeroes: NASA confirms neural network + signal processing; https://github.com/gabrielchayb/42-quake-heroes. SkySense/Twisters: AI-assisted local weather decision tool; exact model unavailable from retrieved winner page. SpaceGenes+: scientific molecular dashboard; architecture not confirmed. 2plant: soil moisture and evapotranspiration; do not infer a named LLM. Gaia+LEO: mixed-integer optimization. NASA has not announced 2026 global winners as of the Nov 14–15 event. The main lesson is narrow scientific problem, applied NASA data, reproducibility, useful decisions and clear demonstration, not copying another team's AI model.
