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

## Post-result revision (science-0.2, 2026-11-15)
Thresholds unchanged. Constrained least squares, training-only PINN collocation, equal-support benchmarks, and a separate zero-future-rain rolling LOS hindcast were added after observing Dallas results. This is retrospective model development; the old Dallas holdout is no longer a fresh independent test for the revision. No operational clearance without new data and independent field verification.
