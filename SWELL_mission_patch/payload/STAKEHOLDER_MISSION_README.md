# SWELL — Guided stakeholder mission

This additive update targets usability and scientific defensibility rather than claiming an improved clay model. It uses the existing real study and physical terrain solver. The root URL now opens the guided room if a real NISAR study with ingestion provenance is available. `/index.html` and `/earth` still open the original Earth Studio; the previous local twin, AI, and Worlds remain intact. The patch does not overwrite the user's data or previous scientific results.

## Install in your active Windows venv

Stop the running server with Ctrl+C. From the folder containing run_swell.py:

```powershell
Expand-Archive "$HOME\Downloads\SWELL_Stakeholder_Mission_Patch.zip" -DestinationPath . -Force
python .\SWELL_mission_patch\apply_mission_patch.py --project . --check
python .\SWELL_mission_patch\apply_mission_patch.py --project .
python -m pip install pyflwdir playwright pillow python-pptx
python -m playwright install chromium
python run_swell.py
```

The safe installer checks prerequisites and uses small anchored insertions rather than replacing entire files with potentially older versions. If a merge anchor is missing, stop and share the error. It keeps backups under `out/mission_patch_backups`. Do not rerun the synthetic validation pipeline. This assumes the prior Science, Recovery and Research Integration patches are installed.

Open `http://127.0.0.1:8000/decision-mission.html` (or the home URL). Select a role and eligible radar cell, load local terrain, optionally retrieve GNSS and imagery, compute flow paths, paint a real-terrain intervention, run the same storm twice, check sensitivity, choose a draft next action, and export the evidence package. No new external key required. Your configured AI is optional; it receives exact saved-run metrics and cached research. If it fails the physical workflow still works, without a fabricated provider answer.

## Recorder and slides

In another terminal inside the same project and existing venv:

```powershell
python record_stakeholder_demo.py --role planner
```

To specify a selected eligible regional cell and optionally independently chosen local center, use `--row 32 --col 30` (only if eligible) and `--lat ... --lon ...`. The default is the eligible cell with largest absolute referenced LOS change, not the highest risk. The recorder requires a real dataset and stops if the core result/review/export fails. Optional provider failures are logged. The raw walkthrough can exceed 30 seconds; it is supplemental. Seven screenshots and a verified decision ZIP are saved under a new timestamped `demo_stakeholder_*` directory. The old recorder remains unchanged. Extra Worlds footage is optional (`--with-worlds`); it is not part of the main seven scenes.

```powershell
python make_stakeholder_deck.py --team "YOUR TEAM NAME" --members "MEMBER ONE, MEMBER TWO"
```

The slide builder uses only the actual local screenshots and numerical records from the verified exported package. It creates exactly seven slides including the title. Edit team information, review all slides, include disclosures and actual references in the submission, and export to PDF from PowerPoint if desired. Use the deck as the official demo; publish with a publicly accessible link. Do not submit the longer raw recording as the official demo.

## Scientific change

- Provenance-gated real observation view; no synthetic fallback. Latest pair referenced LOS with unobserved/reference/low-coherence pixels withheld. Pair-specific coherence used only if cached NPZ shape, dates, bbox and LOS values match the current study; otherwise the study-average coherence proxy is identified. Regional center is approximate.
- The local terrain solver retains its existing conditional assumptions. Same forcing, domain and boundary for both arms; common depth scale; explicit edit footprint. Four paired cases: original 30 seconds, both arms at 15 seconds, baseline and edited infiltration varied -20% and +20%. The range is deterministic sensitivity, **not** a calibrated confidence interval. Numerical mass balance checks conservation, not field accuracy. The solver is closed-boundary surface-ponding screening with idealized sinks. No network topology, design approval, or observed flood depth is implied.
- Role-specific questions and concrete actions with server-derived measurements from saved calculations. The package includes the real-site provenance identifiers, saved run ID, paired review, draft field actions, GeoTIFFs, GIS/CAD review files and a hash manifest. Changing inputs invalidates results; cached numerical checks can be reused for another stakeholder only when the exact run and evidence binding match.
- GNSS evidence is independent vertical point information, not a projected, co-referenced LOS validation. The unresolved clay model and all original validation results remain available. Ground-motion calibration, GNSS projection/referencing, prospective flood observations, spatial convergence and measured drainage capacity remain genuinely outstanding.

## Verification

The code was tested against the reconstructed latest Research Integration build, not the user's private current installation. 122 Python tests passed (includes controlled geospatial fixtures and mocks). An offline Chromium DOM harness using real backend solver calls on a controlled fixture reached comparison, paired review, decision and downloaded ZIP with no page errors. Direct local HTTP browser navigation in this sandbox was administratively blocked. Live NASA, USGS, NGL, Meta, and PyFlwDir still require the user's environment. The patch contains no new real dataset or secrets. No synthetic screenshot or fabricated scientific result is used by the production recorder or slide builder.
