# SWELL pre-registration

Commit this file **before** running `python -m swell.validate` on real data. The commit time is the proof that
the pass marks came first. Do not edit the marks afterwards; if a test fails, report the failure.

Question: does separating the radar moisture artifact from real clay motion improve agreement with independent
measurements, forecasts of later passes, and the decisions built on them?

Split: the first 65 % of passes are for fitting; the rest are held out. Spatial tests use a shuffled-map null
(toroidal shifts of the soil map) or block bootstrap, never random pixel splits.

| Test | Prediction | Pass mark | If it fails |
|---|---|---|---|
| T1 GPS referee | In the radar line of sight, the artifact-corrected change agrees with GPS better than "phase = motion" | Lower RMS than naive **and** under 10 mm | Show GPS as the limit of trust; no motion claims beyond it |
| T2 Clay map | Seasonal motion is largest where the soil map's shrink-swell rating is highest | Spearman rho of at least 0.2 and above 99 % of shuffled maps | No clay claim; report what the motion does follow |
| T3 Forecast holdout | A model fitted on early passes forecasts later ones | Mean squared error lower than both persistence and "no change since the first pass", 95 % intervals exclude zero, **and** RMSE at least 10 % below the better baseline | "What next" is labelled unproven |
| T4 Unseen zone | Constants fitted on one half of the scene predict the other half, no refitting | Lower error than "no change", 95 % interval excludes zero | Report how the constants differ between halves |
| T5 Refusal | Cells the twin refuses are the ones it would get wrong | Mean error among kept cells lower than among all cells | Drop the refusal claim |
| T6 Paved vs open | On the same clay, open ground moves more than paved ground (motion per unit clay rating, spatial block bootstrap, at least 30 cells per class) | Difference > 0, 95 % interval excludes zero | Drop the paving scenario |
| Control | Open low-clay ground barely moves once the artifact is removed | Seasonal range within 1.5 x the range seen on the reference ground | The control assumption is wrong here: say so, and treat beta as unreliable |
| T7 Transfer (only if a second site is processed) | Constants frozen from the anchor site predict another city | Beats "no change" and a calendar-only baseline | Report the difference in fitted constants |
| Tray experiment | Written at the venue before watering: [prediction, measurement method, what counts as supported] | Direction as predicted | Record "contradicted" |

Action contracts: every contract is written from earlier passes only, hashed, and judged by the next pass as
supported, contradicted or inconclusive. All three counts are reported.

Never written anywhere in the project: "first", "proves", "safe", "NASA-endorsed", "real-time" (use "live,
updated within about 3 days of each pass").

## Ground roles (fixed before real data)

- **Reference ground**: paved, low-clay, high-coherence cells (or a GPS-tied area). Defines zero for every pass. Never used for fitting.
- **Control ground**: open (unpaved) low-clay cells, not in the reference. The moisture artifact is learned here.
- **Clay ground**: all other coherent cells. The clay response is fitted here.

## T1b Cross-sensor referee (added 15 Nov, before any real-data result)

Where OPERA DISP-S1 (Sentinel-1, C-band) covers the site, NISAR motion is compared with it in vertical-equivalent millimetres, on clay
cells, on the dates of NISAR passes, both zeroed on SWELL's reference ground. **Pass mark:** the RMS difference is smaller after
SWELL's soil-moisture correction than before it. Stated assumptions: Sentinel-1 incidence 39 degrees; motion is vertical; C-band is
itself not free of moisture effects, so this is a referee, not ground truth. If the product does not cover the site the test is "not run".

## Change log of pass marks (all before any real-data result)

- 14 Nov, after adversarial synthetic tests: a fixture with **no clay motion at all** still passed T2 and T3 as first
  written. T2 now needs rho of at least 0.2; T3 must also beat "no change since the first pass" by at least 10 % in RMSE (a 0.5 % gain was statistically significant but meaningless). The adversarial
  fixtures (`no_clay`, `control_moves`, `wrong_soil_map`) are kept in the test suite and must fail the right tests.


## Processing change made AFTER the first real-data run (15 Nov 2026, 16:40 local) — stated openly

The first real Dallas run (8 NISAR GUNW pairs, 5 Jul to 21 Oct 2026) gave a training error of 16.7 mm, a negative clay response and
10 of 12 contradicted forecasts. A rehearsal that adds a smooth "atmosphere / orbit" surface to synthetic pairs reproduces exactly
that pattern (19.5 mm, 12 of 12 contradicted). Each pair was only being zeroed on the reference median, a constant.

Change: the reference is generalised from a constant to a smooth surface through the reference cells (or, when those are one small
cluster, a tilt through mostly paved cells), removed from each pair (`swell/ingest.py::_detrend`, switch off with `--no-detrend`).
No pass mark was changed. Because this was decided after seeing real results, every result produced with it is exploratory, not
confirmatory, and is labelled so. Known cost: in the clean synthetic rehearsal the tilt removal lowers the recovered clay response
and three tests that pass without it fail with it, so it can also remove real signal.


## NISAR's own troposphere and tide layers (15 Nov 2026, evening) — a planned step that had not run

The plan and the code before any real data (`swell/ingest.py::OPTIONAL_CORR`) listed NISAR's wet and hydrostatic troposphere and
solid-Earth-tide layers as corrections to apply when present. NASA ships them in every GUNW product and does not apply them to the
phase. They are coarse 3D cubes (height x northing x easting), so the old same-shape check skipped them without a message: the
first Dallas run used none of them. `swell/corrections.py` now reads them at the ground height, interpolates them onto the radar
window and applies them (`--no-troposphere`, `--no-tides` switch them off). The sign is the usual "subtract"; it is reversed only if
adding removes clearly more scene variance, and the numbers are written to out/provenance.json either way.

Rule fixed before the new scores were seen: this chain (variant B in `compare_corrections.py`) is the default from now on, whatever
it scores, because these layers exist for exactly this purpose. `compare_corrections.py` also reports the first-run chain (A), an
exploratory 5 km local-contrast filter (C) and raw (D). All four are shown in Verify. Results from B, C and D are exploratory
for Dallas because the first run had already been seen. No pass mark was changed.


## GPS referee data and NISAR brightness (15 Nov 2026, evening)

T1 (GPS referee) was in the plan from the start and stayed "not run" only because no GPS file was supplied. `swell/gnss.py` now
fetches daily vertical positions for every Nevada Geodetic Laboratory station inside the site box (public, no login) and T1 runs
with its original pass mark. NISAR L2 GCOV brightness (HH and HV) is read as an independent check of soil wetting
(`swell/gcov.py`). It is not used in any fit and adds no test with a pass mark; its correlations are reported as findings only.
