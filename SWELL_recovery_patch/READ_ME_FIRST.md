# SWELL recovery patch — observation, local water, AI and Worlds

Apply only to the last science-patched SWELL tree. The installer checks every changed source and refuses mismatches; it does not change downloaded NISAR, .env, cached data or site.json. Stop the server first.

```powershell
Expand-Archive "$HOME\Downloads\SWELL_Recovery_Patch.zip" -DestinationPath .
python .\SWELL_recovery_patch\apply_recovery_patch.py --project .
python -m pip install pillow playwright
python run_swell.py
```

Ctrl+F5 in browser. Open Water & inspection. Select a radar zone, inspect actual referenced LOS change, try a same-storm capture assumption, then open the local DEM twin. The water accounting does not estimate clay displacement or flood depth. Actual USGS/Copernicus elevation and a separate hydraulic solver are used in the local twin, subject to availability. No new observations are manufactured.

In Connections save your existing Meta provider and model and test live generation. Ask in Copilot. The retry is bounded and uses the same provider. No secret is needed in the recording script.

In a second terminal with the same venv, run:
```powershell
python -m playwright install chromium
python record_recovery_demo.py
```
Output: demo_recovery_out, including video, screenshots and honest diagnostics. The raw recording is longer than a short submission video. Benchmarks remain in Verify, not in the main recording. The recorder declines synthetic Earth studies. NASA Trek fetch failures are labelled as unavailable, not replaced by fake archive images.

Read-only scientific diagnostic (optional):
```powershell
python inspect_real_science.py --site out/dallas.npz
```
This compares training fits under alternative artifact assumptions and reports coverage, independent GPS count and an input hash. It does not publish any new outputs. Do not rerun the unqualified synthetic pipeline.

## Scientific follow-up
- NISAR GUNW documentation: https://nisar-docs.asf.alaska.edu/gunw/ — use actual geometry, quality flags, atmospheric correction layers and reference conventions; preserve the acquisition chain.
- MintPy: https://github.com/insarlab/MintPy — mature time-series processing, network quality control, reference sensitivity. Requires a compatible NISAR reader and test of conventions; not integrated here.
- OPERA: https://github.com/opera-adt — compare suitable Sentinel-1 displacement products after aligning temporal support, reference and LOS geometry; independent field GNSS remains necessary. Not connected by this patch.
- ANUGA: https://github.com/GeoscienceAustralia/anuga_core — validated numerical methods and mesh-based shallow-water workflows for a higher-fidelity hydraulic model; requires appropriate DEM, boundaries and validation. Not integrated.
- EPA SWMM: https://github.com/USEPA/Stormwater-Management-Model — drainage network modeling when real pipe and inlet data become available. Not integrated.
- NASA Trek: https://trek.nasa.gov/ — official archive mosaics, not live planetary terrain.

Tests: 112 Python tests on local fixtures, JavaScript syntax and evidence-screen conservation tests passed. Actual Dallas re-fit, external API responses, and end-to-end live browser recording were not verified in this environment.
