# SWELL live testing and API connection runbook

This runbook separates a local software smoke test from an actual connected-data test and from scientific validation. Passing one does not imply the next.

## 0. Safety and scope

- Start with a copy of the project and never put API keys in browser JavaScript, HTML, screenshots, source control, or a public ZIP.
- Use a dedicated low-privilege API key, provider spending limits, and a server-side secret store. Rotate any key that has ever been pasted into chat, a document, or a repository.
- The bundled `site/data/site.json` is a synthetic fixture. Do not use its outputs as real-world evidence or submission results.
- Do not use SWELL for emergency response, structural certification, or operational control. Human expert review remains mandatory.

## 1. Local reproducible test

From the project root:

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-site-twin.txt
PYTHONPATH=. python -m pytest -q
python run_swell.py
```

Open `http://127.0.0.1:8000/`. Confirm Earth Decision Studio loads, then visit `/worlds.html`, `/site-twin.html` and `/connections.html`. Record browser console errors and the test output. Use `PYTHONPATH=.` when running pytest from a checkout where the repository root is not automatically inserted into `sys.path`.

## 2. Claude API

1. Create an API key in the Anthropic Console. Claude consumer subscriptions and API billing are separate; a Claude.ai subscription is not an API key or API credit.
2. In SWELL open Connections and enter the key in the Claude field. The app stores it in the server-side connection configuration; keep that configuration out of source control and public archives. Prefer a managed secret store in production.
3. Leave the model field at the default `claude-sonnet-5` unless the provider account's `/v1/models` endpoint confirms another model ID is enabled for that key.
4. Run the connection check. Confirm provider status is connected and the model-list/API test succeeds.
5. In Copilot ask: `What is the source label of the active site? Is it synthetic? Cite the evidence ID.` With the bundled fixture, the answer must explicitly say synthetic and cite site metadata. Ask it to propose an intervention; verify that it creates a proposal only and does not silently apply it.
6. Test invalid key, revoked key, timeout, and rate-limit behavior. Confirm the UI returns a useful error and deterministic evidence mode remains available.

The default Anthropic API version header is the stable `2023-06-01`. Model identifiers change over time; check Anthropic's active model list before pinning or upgrading. Never infer availability from a marketing model name.

## 3. NASA Earthdata / NISAR

1. Create/verify a free NASA Earthdata Login at https://urs.earthdata.nasa.gov/ and accept any required data-provider application agreements.
2. Prefer an Earthdata bearer token over storing a reusable account password. Configure it only in the server-side secret/configuration interface. Do not commit `.netrc`, token files, or credentials.
3. Open Connections and test Earthdata authentication. A successful login proves authentication only; it does not prove that a suitable NISAR product exists for the selected AOI.
4. Search ASF DAAC / Vertex for the study AOI and time range. Check the exact product short name, maturity (VALIDATED/PROVISIONAL/BETA), acquisition times, track/frame, orbit direction, frequency, polarization, product version, QA masks and spatial overlap.
5. Download two compatible products only if the selected analysis requires a pair. GUNW is an interferometric phase/displacement product; GCOV is calibrated covariance/backscatter. Do not treat GCOV intensity change as displacement.
6. Keep original HDF5 files, metadata, checksums and processing logs. Process only the geographic subset needed. Record native posting and effective resolution separately.
7. Verify georeferencing, units, masks, phase conventions, incidence/look geometry, correction state, reference strategy and connected components before interpreting a deformation signal.
8. Compare any deformation interpretation with independent GNSS, leveling, field survey or another defensible reference. If no independent reference exists, label it provisional and unvalidated.

Official starting points:
- NISAR data access: https://hyp3-docs.asf.alaska.edu/nisar-docs/access-overview/
- Earthaccess workflow: https://nisar-docs.asf.alaska.edu/earthaccess/
- ASF NISAR Cookbook: https://asfopensarlab.github.io/NISAR_Cookbook/nisar-data-access/
- ASF search / Vertex: https://search.asf.alaska.edu/
- NASA Earthdata Search: https://search.earthdata.nasa.gov/

## 4. Terrain, weather and imagery

- USGS 3DEP: test the ImageServer/coverage request for the exact AOI, inspect spatial reference, vertical datum, units, NoData, pixel size and returned raster bounds. A successful HTTP response is not proof of correct datum or adequate resolution.
- NASA GIBS: confirm selected layer, date/time, projection, tile coverage and attribution. Imagery tiles are not a calibrated analytical raster unless the product specification says so.
- Weather/AIFS: record provider, model/run issue time, valid time, lead, units and missing fields. A single deterministic forecast is not an ensemble and must not be displayed with probabilistic confidence bands.
- Check all layers align spatially and temporally. A site snapshot can contain asynchronous sources; display timestamps per source.

## 5. Live-site acceptance test

For one chosen study site, complete and archive this checklist:

- [ ] Exact AOI polygon and CRS stored.
- [ ] At least one real terrain raster downloaded; vertical datum and units recorded.
- [ ] Real satellite acquisitions found; source collection, IDs, maturity, timestamps and checksums stored.
- [ ] Source data successfully read and quality masks inspected.
- [ ] Every displayed layer labelled observed / derived / inferred / forecast / scenario / verified / unavailable.
- [ ] No synthetic fixture is mixed into the live-site evidence set.
- [ ] Baseline model input manifest, parameters, software version and output hashes saved.
- [ ] Intervention scenario saved as a separate immutable version; baseline remains unchanged.
- [ ] Same model and forcing used for baseline/scenario comparison unless differences are explicitly disclosed.
- [ ] Mass-balance and numerical stability diagnostics pass their stated thresholds.
- [ ] Independent event or field observations withheld from calibration used for evaluation.
- [ ] Forecast skill compared to persistence and relevant operational baseline; temporal leakage checked.
- [ ] Stakeholder report lists evidence, assumptions, uncertainties, trade-offs and required human sign-off.
- [ ] A second user can reproduce the analysis from the manifest and archived inputs.

## 6. Scientific forecast validation

Do not enable a calibrated uncertainty display until there are genuine archived forecast/observation pairs for the same site, forecast source, model version and fixed lead. Use chronological calibration and a later untouched holdout; report coverage, interval width, MAE, RMSE, bias and archive hash. Evaluate by event and season where possible. Serial dependence, spatial dependence and regime shifts can invalidate simple conformal exchangeability assumptions. This is not a per-pixel safety probability.

## 7. What a successful live test does and does not prove

- API status `ok`: provider authentication/connectivity works at test time.
- Data download success: the file was retrieved, not scientifically validated.
- Product parsing success: file structure was read, not that its interpretation is correct.
- Synthetic browser regression: UI and code paths work with fixtures, not with real observations.
- Numerical sensitivity check: solution changes little under that specific perturbation, not that the model matches reality.
- Independent holdout skill: measured predictive performance for the tested site, period, lead and regime, not universal accuracy.

## 8. Suggested first real pilot

Pick a site with (a) a documented environmental/infrastructure decision, (b) overlapping NISAR acquisitions of a compatible product, (c) quality-controlled terrain and rainfall, (d) a known event or independent field reference, and (e) a stakeholder who can review the result. Do not select a site solely because it is visually dramatic. Confirm product availability in ASF before committing to the demo narrative.
