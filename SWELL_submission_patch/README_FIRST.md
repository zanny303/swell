# SWELL — final submission reliability update

Apply only after Competition Reliability and Polish/Worlds. Stop the local server, keep .venv, extract ZIP into project, and run:

```
python .\SWELL_submission_patch\apply_submission_patch.py --project . --check
python .\SWELL_submission_patch\apply_submission_patch.py --project .
python radar_assurance.py
python run_swell.py
```

New optional landing: `http://127.0.0.1:8000/welcome.html` (root unchanged). Earth Studio now retrieves a matching audited projected display; map picks use its nearest-display-pixel lookup, and selected coordinates and outlines use actual projected block corners. It does not recalculate the source phase or clay model. If the audit is missing, legacy approximate map remains available and labelled. Not every old geographic-context tool has been reworked; use the Decision Room for binding. Existing NISAR cache, previous exports, solver source, AI providers and credentials are untouched.

Decision Room: select an eligible audited observation, open the full-width investigation section, click Find independent observations. CMR queries use the selected radar block bbox and pair's date interval. Each product family yields bounded catalog metadata, not scientific measurements; opening assets and controlling geometry, reference, product quality and timing is still necessary. USGS daily discharge returns available real measurement records near the block, not depth within it. Provider failure is explicitly shown. The enriched ZIP includes the matched selected-cell evidence inventory if retrieved. New code uses only stdlib plus existing numpy/pyproj.

In second terminal:
```
python record_stakeholder_demo.py --role engineer --assurance --independent-comparison --with-worlds
python evaluate_momentum.py --output momentum-review.json
```
The last command selects the newest reproducible ZIP by modification time; prints which one. Adaptive results require the correct location, 5/2/1 s maximum timestep caps, spatial and water balance checks, and remain conditional. Review actual steps and minimum dt. Do not treat cap screening as grid convergence or flood validation. If the new archive is missing, do not present old run as corrected site. Run explicit archive path to avoid ambiguity.

```
$latest = Get-ChildItem -Directory -Filter "demo_stakeholder_*" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python competition_replay.py --package "$($latest.FullName)\SWELL-reproducible-decision.zip" --replay "$($latest.FullName)\public-replay.html" --momentum momentum-review.json --output competition-replay.html
python record_recovery_demo.py --planetary-terrain
```

Recorder now gets an audited cell and navigates directly to Site Twin. If an Earth choice is unavailable it explicitly reports the highest-coherence audited cell used instead. Photorealistic mode is preferred; `--with-osm` retains diagnostic recording of the known preview defect. Map transition reset is implemented but not live-verified. PDS class-search 400/404 fallback requires explicit target and product class metadata in generic results. A second provider failure remains an error, not fake records; native DEM access remains unverified.

## Testing
140 Python tests passed on retained source snapshot, including CMR and USGS fixtures and strict PDS fallback tests. JS syntax passed. Real archived Dallas audited centers 3600/3600 correctly map to their row/column in the 480-display lookup (not a test of field accuracy). No fresh authenticated NISAR, no live external browser/3D or newly corrected-site terrain array available in this environment. No independent empirical validation, new case, or user-study results claimed. Existing adaptive numerical results refer to old geographically unlinked terrain.

## Sources
- NASA CMR API: https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html
- OPERA DISP: https://www.jpl.nasa.gov/go/opera/products/disp-product-suite/
- OPERA DSWx: https://www.jpl.nasa.gov/go/opera/products/dswx-product-suite/
- USGS Water Data API: https://api.waterdata.usgs.gov/docs/ogcapi/
- PDS Registry search: https://nasa-pds.github.io/pds-api/guides/search/endpoints.html
- NISAR GUNW documentation: https://nisar-docs.asf.alaska.edu/gunw/

## Eligibility
Preserve the version submitted before the applicable event deadline. Only make further competition changes before the deadline or with explicit event authorization. Do not publish credentials, proprietary imagery/tiles or any data that you do not have permission to redistribute. See the project's attribution and AI assistance disclosure; adapt accurately to team contributions.
