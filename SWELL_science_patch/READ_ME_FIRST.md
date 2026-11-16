# SWELL science-0.2 — targeted patch for SWELL-final-v2

This is an overlay, not a fresh app. Do not delete or replace your working SWELL installation. No `.env`, raw satellite files, `out/dallas.npz`, provenance, current `site/data/site.json`, UI layout, visual assets, API providers or Worlds are replaced. Science caveats, validation panel and decision-status controls are updated; all visual/scenario functionality remains.

## Run (existing Windows PowerShell, inside the folder with run_swell.py)

1. Stop the old server using Ctrl+C. Extract this ZIP into the existing SWELL project; it creates a `SWELL_science_patch` directory.
2. Run `python .\SWELL_science_patch\apply_science_patch.py --project .` (or use `.venv\Scripts\python.exe` instead of `python` throughout if that is your running interpreter). The patch checks source hashes and backs up originals. A mismatch means your local code differs: don't force overwrite; provide the listed source files for a safe merge.
3. Confirm `Get-ChildItem out\*.npz` lists your cached Dallas dataset. Run `python revalidate_science.py --site out/dallas.npz --publish`. This stages all results, verifies the site identity, backs up the old scientific outputs, then publishes. No NASA redownload or API key is required. Do not run `python -m swell.validate` by itself (synthetic default).
4. Read the new terminal result and the report path. If it fails, keep the prior real site; report the traceback. Never change tests just to make them green.
5. Start `python run_swell.py`; open http://127.0.0.1:8000/ (Ctrl+F5). Verify → Research displays revised PINN and rolling LOS benchmark. Use Connections → Add the other satellites again if available to refresh ancillary comparisons. You can use `python real_site.py --site dallas --extras-only` with the server stopped instead (network/login required).
6. In a second terminal in this folder, run `python record_science_demo.py`. If necessary: `python -m pip install playwright` and `python -m playwright install chromium`. Outputs in `demo_science_out/`: real capture WebM, screenshots, and report. Raw video length depends on rendering/network; the seven-slide PDF is the seven-slide demo deliverable. Do not select --demo for the real submission.

## What was corrected

- Constrained least squares uses alpha=u+v, b=v/(u+v), u,v≥0. Error now describes the actually used equation, not an unconstrained fit followed by clipping. A boundary alpha=0 says the mechanism is not identified; not that the Earth is stationary.
- PINN physics collocation stops at the last training date. The ablation uses common finite held-out cell-pass support. The closed-form comparator still uses realized rainfall, and is explicitly a conditional hindcast.
- T3 uses common finite support for the compared methods; its threshold is unchanged. Added rolling, fixed-fit, dry-assumption LOS hindcast against previous-pass persistence with no realized future rain. It inherits archive-wide quality masks/preprocessing; not prospective validation.
- Missing observation sentinel -9999 is no longer exported or interpreted as a measurement. Old files are decoded in the studio and AI evidence.
- Historical contracts/bands are nominal, not calibrated probabilities. The UI and AI distinguish experimental results. Decision logging supports proposals/reviews/rejections; consequential statuses require independent scientific clearance. Scenario simulation is preserved.
- Reports distinguish total scenario differences (weather plus edits) from same-storm intervention comparisons. The previous numbers are not empirical benefits.

## Honest scientific status

109 software tests passed in this environment; the staged complete pipeline also ran successfully on the labelled SYNTHETIC test fixture. Real Dallas NPZ and provenance were not included in the uploaded source ZIP; no revised Dallas metric has been computed here, and no fresh external data download or live browser recording was run. These are post-result methodological fixes, not a new preregistered experiment. The updated test criteria are not relaxed. Existing red tests may remain red. Independently validate phase sign, geometry, reference stability, soil mineralogy/linear extensibility, and new observations; OPERA DISP-S1 cross-sensor agreement is supporting evidence, not GNSS truth. Official sources: https://nisar-docs.asf.alaska.edu/products-overview/ and https://www.jpl.nasa.gov/go/opera/products/disp-product-suite/.

## 7-scene narration

1. **Observe:** We loaded eight NISAR interferometric pairs over Dallas–Fort Worth, nine radar dates. Show the time strip and real-source metadata. Radar LOS is not direct vertical displacement.
2. **Understand:** One radar signal, competing mechanisms: soil moisture changes radar phase, and expansive clay can physically move. Show raw / corrected / conceptual subsurface and the hypothesis.
3. **Simulate:** Type 120 mm over four days; paint paving or green space. The linked map and chart recompute conditional model outputs.
4. **Compare:** Show Before/after sensitivity, then Planner → Paving or drainage (same storm). Different forcing is not isolated intervention effect.
5. **Decide:** Engineer inspection, utility leak, resident explanation, emergency storm, planner alternatives. Say “inspection hypotheses,” not certified safety or predicted damage.
6. **Experience:** Photorealistic city geometry, regional model overlay, not building-level measurements. Preserve credits. If tiles fail use analysis map / existing recorded screenshots.
7. **Verify:** Show persistence, closed-form, NN, PINN and the new rolling LOS audit. Read actual revised numbers from terminal or page, including failures. Request GNSS/OPERA and another independent NISAR pass, then export a proposed inspection decision.

Close: “SWELL doesn't turn uncertainty into confidence. It turns evidence into a decision we can test.”

For submission: preserve the real derived site file, provenance, results, contracts, and permitted derived NPZ; exclude all keys and local private credentials. Include public source attribution and disclose Claude and ChatGPT assistance. The provided slides use only supplied actual screenshots/recording frames, labeled archived pre-revision; replace metrics/screenshots only with genuinely rerun results.
