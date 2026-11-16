# SWELL scientific assurance upgrade

This is an additive update for the working Stakeholder Mission Edition. It does **not** reprocess or replace your Dallas dataset, overwrite `.env`, delete saved runs, change any previous test thresholds, replace the working physical solver, replace Meta AI, or remove Earth Studio or Worlds. The original two recorders still work; the stakeholder recorder gains an optional `--assurance` argument.

## Windows PowerShell — install

Stop the server with Ctrl+C in the server terminal. Stay in the activated `.venv` in `SWELL-final\swell`:

```powershell
Expand-Archive "$HOME\Downloads\SWELL_Scientific_Assurance_Patch.zip" -DestinationPath . -Force
python .\SWELL_assurance_patch\apply_assurance_patch.py --project . --check
python .\SWELL_assurance_patch\apply_assurance_patch.py --project .
```

The installer refuses to replace conflicting add-on files or ambiguous source anchors. It checks all changes before writing anything, creates backups of altered files under `out/assurance_patch_backups/`, uses atomic file replacement and restores previously written files if an installation write fails. Do not force a conflicting patch. Existing source modifications outside the identified anchors are preserved. The included source snapshot passed 131 tests; the exact Windows source tree may differ.

## Real-study scientific audit (optional, important)

```powershell
python radar_assurance.py
python science_assurance.py --benchmarks
```

`radar_assurance.py` reads the original named cached HDF5 files from `data/dallas/gunw` (or `--gunw-dir PATH`) and checks their projected coordinate vectors and CRS. It checks the active NPZ against the browser dataset, the recorded granule order and the legacy geographic bounding box. It calculates exact block centers for the trimmed projected grid, component-aware raw phase using common coherence/phase support, threshold sensitivity, reference-subset sensitivity, and matched-support sensitivity to the legacy ionospheric correction sign. It does not publish new LOS values. The audit may refuse if original granules, provenance, or layout are missing or inconsistent. Stored subset files commonly omit full viewing geometry and coarse atmosphere/tide LUTs; no fabricated corrections or LOS validation are generated. Future ingestion rejects an equal-shape but differently registered crop.

```powershell
python gnss_assurance.py
python explore_assurance.py --worlds
```

The GNSS utility uses previously discovered NGL stations to retrieve full IGS20 east, north and up daily components on the actual radar dates. Optional `--geometry geometry.json` projects exact-date changes at a station and a reference station using explicitly supplied, independently verified ENU unit vectors and positive-toward-sensor convention. Required JSON fields: `station`, `reference`, `station_vector`, `reference_vector`, `dates` (two ISO dates), `geometry_source`, `sign_convention` (exactly `positive toward sensor`). No assumed viewing direction, stability or T1 pass is inserted. Retrieve GNSS in the original Decision Room first. The Worlds utility inventories configured NASA layers, cached mosaic hashes, image dimensions and the missing per-tile provenance; it does not turn imagery into elevation or infer planetary terrain properties. For a second research site, `python explore_assurance.py --bbox WEST SOUTH EAST NORTH` performs a read-only NASA catalog search and writes a candidate chain to a separate output; this is not a processed case study.

## Start and use the updated app

```powershell
python run_swell.py
```

Visit http://127.0.0.1:8000/decision-mission.html and hard-refresh. Complete the normal saved comparison and sensitivity review. Open **Advanced independent science review** beneath Method, assumptions and results. This panel provides:

- Saved signed peak-depth difference map, percent storage reduction, capacity utilization and local area affected.
- Both alternatives rerun at 30/15/10/5 seconds, wet-mask intersection-over-union, peak and spatial depth RMSE, limiter diagnostics, predeclared intended-use screening gates and a same-capacity relocated-footprint control. The output distinguishes water accounting from spatial convergence. It is not an optimized design or calibrated probability.
- Optional separate existing adaptive momentum solver comparison; disagreement is shown, not averaged. Closed boundary, constant infiltration, and a bounded domain required. Not an external ANUGA validation.
- Reproducible ZIP with exact float64 processed elevation (`.npy` and georeferenced GeoTIFF), exact scenario, standalone diffusive solver, environment identifiers, current evidence and current decision only, optional saved advanced review/cross-solver/structured AI checks, and manifest hashes. Original export still works. Local package may contain source/provenance and stakeholder notes; inspect before public sharing. It does not include original full granules or provider credentials.
- Exact cached radar geometry and a button to insert the audited block center into the local terrain inputs, after the CLI audit. Existing published radar values do not change. Load terrain again after changing coordinates.
- Server-calculated run-bound facts and an optional selected-provider structured numeric extraction test. Reject numbers, units and evidence IDs that do not match saved facts. This does not certify ordinary generated prose, research interpretation or recommendations.

The **Radar research** navigation link opens the new actual acquisition timeline (`science-observatory.html`): cumulative or consecutive LOS, selected-cell graph, and raw phase only when the granule audit is available. Browser verifies the active data hash before drawing. Radar grid cells are not building-scale observations.

## Record everything, without touching the old recordings

Keep server running; in a second activated terminal:

```powershell
python record_stakeholder_demo.py --role engineer --assurance --with-worlds
python record_recovery_demo.py
```

The stakeholder recorder keeps its original seven screenshots, adds advanced review screenshots, verifies the enriched ZIP, and generates `public-replay.html` using the matched active radar timeline. It returns a failure exit code if requested assurance does not complete. Cross-solver/checked AI are manual optional tests. The full recovery recorder remains unchanged. Normal commands without `--assurance` still run the original workflow. The expanded raw walkthrough is supplementary; official NASA demo is <=30 s or <=7 slides.

## Public replay

The separate `SWELL_Public_Replay.html` is built directly from the supplied real Dallas stakeholder archive and has no access to the server or external keys. It shows real saved metrics, local water-depth maps and hour slider, signed difference map, documented GNSS summaries, case table and role action. It does not contain the entire regional radar time series because the original uploaded archive did not include it. To produce a full timeline replay from your local active study, run the recorder with `--assurance` or use:

```powershell
python build_public_replay.py --package "PATH\TO\SWELL-reproducible-decision.zip" --include-active-radar --output public_replay\index.html
```

Review the static output before publishing, then host just `index.html` on any static web host such as GitHub Pages. Test the HTTPS link in a private window. No public deployment is performed by this patch. Replay intentionally omits free-text private notes, AI prompts/responses, restricted third-party imagery, passwords, cookies and full server code. It is a saved-data viewer, not a live solver.

## Independent numerical tests and remaining scientific gates

- 131 full Python regression tests passed in the retained source tree (controlled fixtures/mocks). A controlled offline Chromium run completed the prior and enriched exports without JS page errors; separate real exported-data replay content and controls passed a Chromium test with no page errors. Direct URL navigation in this sandbox is restricted; live Windows recording and the source granules still need local tests.
- Flat uniform rainfall analytical budget and dry sloped zero-forcing tests passed for all four timesteps. A Ritter analytical dry-bed dam-break test of the existing momentum **flux core** decreased mean absolute depth error from 0.013854905 m at 2 m to 0.009752562 m at 1 m, with zero mass residual in both. These are analytical tests, not independent field validation or complete EA/ANUGA benchmark testing.
- Still not established: full correction LUT interpolation and physical sign/wavelength validation; independent GNSS LOS co-reference and stable monument assessment; cycle closure (the current nearest-neighbor chain has no redundant edges); empirical flood event validation; surveyed open boundary or physically justified larger domain; DEM-supported grid convergence; optimal siting or equivalent cost; second real processed location; true planetary elevation/illumination analysis; real stakeholder usability testing; publicly hosted judge link. None of these is marked complete. Existing clay-model calibration remains unresolved.
- The new exact geometry and raw phase tools have unit tests but have not been executed against your actual raw Dallas granules. The upgraded physical review has not been run against your actual cached elevation in this environment. Live provider checks must use your own configured credentials. No change to original pass marks.

Research basis: ASF NISAR GUNW product documentation https://nisar-docs.asf.alaska.edu/gunw/ ; NGL station and IGS20 solutions https://geodesy.unr.edu/PlugNPlayPortal.php ; MintPy https://github.com/insarlab/MintPy ; Environment Agency hydraulic benchmarks https://www.gov.uk/flood-and-coastal-erosion-risk-management-research-reports/2d-benchmarking-evaluating-the-latest-generation-of-the-hydraulic-models-for-fcrm ; NASA Trek https://trek.nasa.gov/ . External engines are not claimed as newly integrated where no adapter was tested.
