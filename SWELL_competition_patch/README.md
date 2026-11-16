# SWELL competition reliability upgrade

Apply after Scientific Assurance and Polish/Worlds. The installer refuses source conflicts and preserves all existing data, API keys, solvers and old decisions. If you have not yet applied Polish/Worlds, use its own installer first. Stop your server before applying. Work in the project directory and original `.venv`.

```powershell
python .\SWELL_competition_patch\apply_competition_patch.py --project . --check
python .\SWELL_competition_patch\apply_competition_patch.py --project .
python radar_assurance.py
python run_swell.py
```

In a second activated PowerShell: `python record_stakeholder_demo.py --role engineer --assurance --with-worlds`. The default selects the highest absolute change among cells satisfying the 0.50 legacy coherence screen; low quality selections are available only by lowering the diagnostic screen. The recorder selects 0.30 explicitly if needed or requested via row/col. The two modes are not the same as the native-pixel component-aware audit, which is displayed separately.

Exact projected block centers and footprints automatically bind decision selections when the hash and dates of the cached radar audit match the active study. The server rejects review/export when the terrain center is outside the audited block. A center inside is geographic linkage only, not causal linkage or proof that every local terrain cell is inside the radar footprint. Without a matching audit, legacy scenarios remain explicitly approximate and unlinked. The original globe raster is still drawn on the legacy rectangular geographic bounds, so use the Decision Room or radar research observatory for audited coordinates. Do not overwrite the original published radar values. AI remains optional; hypotheses are deterministic unresolved investigations, not probabilities or independently verified causes.

## Optional new numerical experiment

After the recorder creates its new `SWELL-reproducible-decision.zip`, run this against that file:

```powershell
python evaluate_momentum.py "PATH_TO_NEW_RECORDING\SWELL-reproducible-decision.zip" --output momentum-review.json
python competition_replay.py --package "PATH_TO_NEW_RECORDING\SWELL-reproducible-decision.zip" --replay "PATH_TO_NEW_RECORDING\public-replay.html" --momentum momentum-review.json --output competition-replay.html
```

The physical comparison uses the existing momentum solver, an unchanged closed domain, and constant infiltration; it compares max timestep caps 5, 2, 1 s in both alternatives, plus equal-footprint translated drainage and extra infiltration where supported. May be computationally expensive; do not interrupt the server or claim a failed review passed. A passing max-step-cap screen is not spatial grid convergence or field accuracy. The earlier diffusive model and saved outputs are preserved. The demo automatically creates an enhanced public replay without momentum when the matched audit is included. Do not publish secrets or private notes; review attribution and redistribution permission. The replay is static and does not require a backend. Public hosting is your responsibility. Keep the official NASA demo within 7 slides or 30 seconds and meet your event's submission deadline. Do not substitute later code for the submitted version after the cutoff.
