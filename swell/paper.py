"""Write the paper from results.json. No number in the paper is typed by hand."""
from __future__ import annotations

import pathlib


def _t(tests, prefix):
    return next(t for t in tests if t["name"].startswith(prefix))


def _g(t, k, f=".2f"):
    v = t.get(k)
    if isinstance(v, (list, tuple)):
        return " to ".join(format(x, f) for x in v)
    return format(v, f) if isinstance(v, (int, float)) and v == v else "n/a"


def _pf(t):
    return "not run" if t["passed"] is None else ("PASS" if t["passed"] else "FAIL")


def write_paper(r: dict, path: pathlib.Path):
    T = r["tests"]
    t1, t2, t3, t4, t5, t6, tc = (_t(T, p) for p in ("T1", "T2", "T3", "T4", "T5", "T6", "Control"))
    syn = r["source"] == "SYNTHETIC"
    banner = ("> **These numbers come from the SYNTHETIC test fixture, not NASA data.** They show only that the code "
              "recovers parameters it was given. Rerun `python -m swell.validate --site out/<site>.npz` on real NISAR "
              "data and this file is rewritten.\n\n") if syn else ""
    p = r["params"]
    truth = ""
    if syn:
        s = r["synthetic_truth"]
        truth = (f"\nFixture check: recovered alpha {p['alpha']:.2f} (true {s['alpha']}), b {p['b']:.2f} ({s['b']}), "
                 f"T {p['T']:.0f} d ({s['T']:.0f}), tau {p['tau']} d ({s['tau']}), beta {r['beta_mm_per_wetness']:.2f} ({s['beta']}).\n")
    c = r["contracts"]
    adv = ""
    if r.get("adversarial"):
        lines = "".join(f"| {k} | {', '.join(v['expected_to_fail'])} | {', '.join(v['failed']) or 'none'} | {'yes' if v['caught'] else 'NO'} |\n" for k, v in r["adversarial"].items())
        adv = ("**Adversarial fixtures.** Each breaks one assumption on purpose; the named tests must fail.\n\n"
               "| Broken assumption | Tests that must fail | Tests that failed | Caught |\n|---|---|---|---|\n" + lines + "\n")
    md = f"""# Artifact-Aware Physical Inference for a Decision-Centred SAR Digital Twin: An Expansive-Clay Case Study with NISAR

*NASA Space Apps Challenge 2026, Dancing with the SARs. Team: [names]. Code commit `{r['commit'] or 'uncommitted'}`, model `{r['model_version']}`. Data source for this build of the paper: **{r['source']}**, site: {r['site']}.*

{banner}## Abstract

Radar interferometry measures phase, not ground motion. At NISAR's L-band wavelength, a change in soil moisture shifts the phase even when the ground does not move, and on expansive clay the same rain also makes the ground really swell. A twin that reads every phase change as motion will therefore rank the wrong places for inspection. We test whether separating the two, using low-clay ground as an in-scene reference, improves agreement with GPS, forecasts of later passes, and the decisions built on them. On this dataset the artifact-corrected line-of-sight change differs from GPS by {_g(t1,'rms_swell_mm','.1f')} mm RMS against {_g(t1,'rms_naive_mm','.1f')} mm for the naive reading; held-out forecast error is {_g(t3,'rmse_swell','.1f')} mm against {_g(t3,'rmse_persistence','.1f')} mm for persistence and {_g(t3,'rmse_no_change','.1f')} mm for no change. All pass marks were fixed before any result (PREREGISTRATION.md), and failures are reported in Section 5.

## 1 Introduction

Expansive clays shrink as they dry and swell as they wet, damaging foundations, roads and buried pipes. GPS on Texas expansive clay has recorded 6-16 cm of drought-summer subsidence that largely recovers in autumn (Welch et al., 2024), and radar time series have been used to map clay shrink-swell hazard in France (Le Corvec, 2026). NISAR, a NASA-ISRO L-band mission with a 12-day repeat, now provides open interferograms (GUNW) and calibrated backscatter (GCOV) over all land.

Two things make this harder than "map the motion". First, soil moisture changes the radar phase directly; NISAR's own science team has documented this bias. Second, a recommendation is only useful if someone can check later whether it was right. We therefore ask three questions: (Q1) can the moisture artifact be separated from real clay motion with data available in the scene; (Q2) does the separated model forecast later passes better than simple baselines; (Q3) can each recommendation carry an expected observation that the next pass confirms or contradicts?

We do not claim to have invented Earth digital twins (see Destination Earth, NASA's Earth System Digital Twin programme) or to certify any structure. The contribution is a small, testable loop: observation, competing explanations, uncertainty with refusal, bounded scenario, human-approved action, re-observation.

## 2 Data

| Data | Use |
|---|---|
| NISAR L2 GUNW (12-day pairs, 80 m): unwrapped phase, coherence, ionosphere screen, troposphere tables | Line-of-sight change |
| NISAR L2 GCOV (HH, HV) | Wetness cross-check |
| NASA GPM IMERG daily rain; NASA SMAP soil moisture | Wetness forcing |
| Soil map (USDA SSURGO linear extensibility in the US; SoilGrids elsewhere) | Clay rating; control ground |
| Impervious-surface map | Paved fraction |
| GPS daily positions (Nevada Geodetic Laboratory) | Independent referee |

This build used {r['n_passes']} passes (days {r['pass_days'][0]}-{r['pass_days'][-1]}); passes {r['train_passes'][0]}-{r['train_passes'][-1]} were used for fitting and passes {r['test_passes'][0]}-{r['test_passes'][-1]} were held out. For real data, list every granule id, its collection (PROVISIONAL or VALIDATED) and the retrieval date in `out/provenance.json`; the provisional and validated collections overlap on 21-23 October 2026 and must be checked for an offset there.

## 3 Method

**Phase to distance.** d = -(lambda / 4 pi) phi with lambda = 238.4 mm, after subtracting the ionosphere screen and troposphere correction, masking coherence below 0.30, and referencing to a stable area.

**Wetness.** A daily rain index A(t) = 0.9 A(t-1) + P(t), mapped to w = A / (A + 40 mm).

**Three kinds of ground, kept separate.** *Reference* ground (paved, low-clay, high-coherence, or GPS-tied) defines zero for each pass and is never used for fitting. *Control* ground (open, low-clay, outside the reference) is where the moisture artifact is learned. *Clay* ground is everything else that is coherent. Referencing to the same ground the artifact is learned on would cancel the artifact before it could be measured.

**Measurement model.** Line-of-sight (LOS) change is the measured quantity. For cell i at pass t, relative to the first pass and to the reference ground:

    y_i(t) = cos(inc_i) m_i(t) + beta (1 - paved_i) [w(t) - w(t0)] + noise

Vertical motion m is obtained by dividing by cos(inc_i) with each cell's own incidence angle. This assumes no horizontal motion, which one viewing direction cannot test. Missing pixels stay missing: they are skipped in every fit and never update the twin.

**Artifact.** On control ground real swelling is assumed negligible (tested below), so beta is the regression slope of y on (1 - paved) times wetness change there. Fitted: beta = {r['beta_mm_per_wetness']:.2f} +/- {r['beta_se']:.2f} mm per unit wetness. This single term stands in for the soil-moisture phase effect only. Residual ionosphere, troposphere, solid-Earth tide, squint and unwrapping errors are separate; `out/provenance.json` lists which corrections were actually applied.

**Clay dynamics.** m_i(t+1) = m_i(t) + (G_i w(t - tau) - m_i(t)) / T, with G_i = alpha LEP_i (1 - b paved_i). T and tau are chosen on a grid; alpha and b by least squares on training passes only. Fitted: alpha = {p['alpha']:.2f} mm per % rating, b = {p['b']:.2f}, T = {p['T']:.0f} days, tau = {p['tau']} days (training RMSE {p['rmse_train']:.2f} mm).
{truth}
**Twin.** A per-cell Kalman filter carries the model forward daily and corrects it at each pass with variance set by coherence. A forecast for a pass uses only earlier passes. A cell is marked *unresolved* when coherence is low or its 90 % interval spans zero.

**Competing models.** M0: phase is motion. M1: motion follows wetness at once, no artifact. M2: this method.

**Action contracts.** Each recommendation stores its evidence, the competing explanation, the expected zone-mean motion at the next pass with a 90 % band, and a SHA-256 digest. The next pass marks it supported, contradicted or inconclusive.

## 4 Results

| Test | Measure | Result | Verdict |
|---|---|---|---|
| T1 GPS referee | RMS vs GPS in line of sight, naive / SWELL (mm), n = {_g(t1,'n','d')} | {_g(t1,'rms_naive_mm')} / {_g(t1,'rms_swell_mm')} | {_pf(t1)} |
| T2 Clay map | Spearman rho; share of shuffled maps beaten | {_g(t2,'spearman')}; {_g(t2,'null_quantile','.1%')} | {_pf(t2)} |
| T3 Forecast holdout | RMSE SWELL / persistence / no change / rain-only (mm) | {_g(t3,'rmse_swell')} / {_g(t3,'rmse_persistence')} / {_g(t3,'rmse_no_change')} / {_g(t3,'rmse_rain_only')} | {_pf(t3)} |
| T3 calibration | 90 % band: coverage; mean half-width (mm) | {_g(t3,'coverage90','.0%')}; {_g(t3,'mean_band_mm')} | reported |
| T4 Unseen zone | RMSE frozen model / no change (mm) | {_g(t4,'rmse_swell')} / {_g(t4,'rmse_no_change')} | {_pf(t4)} |
| T5 Refusal | Mean abs error, all / kept cells (mm); share kept | {_g(t5,'mae_all_mm')} / {_g(t5,'mae_kept_mm')}; {_g(t5,'kept_fraction','.0%')} | {_pf(t5)} |
| T6 Paved vs open | Open minus paved, mm per % rating, 95 % block-bootstrap interval; cells open / paved | {_g(t6,'diff_ci95')}; {_g(t6,'n_open','d')} / {_g(t6,'n_paved','d')} | {_pf(t6)} |
| Control ground | Seasonal range naive / corrected (mm); range on reference ground | {_g(tc,'amp_naive_mm')} / {_g(tc,'amp_corrected_mm')}; {_g(tc,'noise_range_mm')} | {_pf(tc)} |

Coverage above 90 % means the bands are wider than needed; coverage and width are reported together so neither can be gamed.

{adv}Figures: `out/figures/fig1_maps.png` (naive vs corrected seasonal range, and the soil map), `fig2_gps.png` (GPS referee), `fig3_forecast.png` (forecast error per held-out pass).

**Action contracts.** {c['n']} contracts were written before their target pass: {c['tally']['supported']} supported, {c['tally']['contradicted']} contradicted, {c['tally']['inconclusive']} inconclusive. The band on each contract is 1.645 times the spread of zone-mean forecast errors on training passes ({c['zone_sigma_mm']:.2f} mm), combined with the model's estimate of how far the reference ground itself moved, so about one in ten should be contradicted even when the model is right. More than that points to a bias, most likely an unstable reference.

**Scenario example.** A 75 mm storm over two days gives a modelled mean change of {r['scenarios']['storm_75mm_day30_mean_mm']:.1f} mm after 30 days; with wetting assumed 35 % lower, {r['scenarios']['storm_with_35pct_less_wetting_mean_mm']:.1f} mm. These are model outputs under stated assumptions, not observations.

## 5 Failures and limits

- Any test marked FAIL above is a result, and is discussed here before submission: [write one paragraph per failed test].
- The control-ground assumption (no real swelling on open low-clay soil) is the method's weakest point: if those soils move, beta absorbs real motion. The Control test checks it against the reference ground.
- The wetness index is one series per scene from rain alone. NISAR backscatter (GCOV) and SMAP are not yet used, so spatial differences in wetting are missed.
- One artifact coefficient per scene ignores land cover; the vertical moisture profile, which matters at L-band, is not modelled.
- Vertical values assume no horizontal motion. Ascending plus descending passes would test this; only one direction is used.
- Cells are 80 m: the results describe neighbourhoods, never single buildings.
- With one season of mostly provisional NISAR data, "seasonal" means "this season".
- Scenario outputs are bounded what-ifs from a reduced model. They are not engineering designs.

## 6 The physical loop at desk scale

[Fill in from the tray experiment: the prediction written before watering, the measurement, and whether it was supported, contradicted or inconclusive. This validates the observe-predict-intervene-measure loop only, not field-scale behaviour.]

## 7 Generality

Only the dynamics and the forcing are clay-specific. The same measurement model, filter, refusal rule and contract protocol could take a water-table forcing (peat), accumulated thaw (permafrost) or groundwater head (aquifer compaction). None of those was tested here.

## 8 Reproducibility and data availability

`python -m swell.validate --site out/<site>.npz` regenerates `out/results.json`, the figures and this paper. Pass marks are in `PREREGISTRATION.md`, committed before results. Code: [repository URL], MIT licence. Derived maps and the benchmark package: [Zenodo DOI].

## 9 Use of AI

[State which AI tools were used and for what: literature search, critique, code drafting, text editing. State how outputs were checked. AI did not produce any measurement or result in this paper.]

## References

- Welch, J. et al. (2024). Drought-induced subsidence on expansive soils in Texas. *Geophysical Research Letters*. [verify full citation]
- Le Corvec, N. (2026). InSAR mapping of clay shrink-swell. EGU General Assembly 2026, EGU26-21004.
- NISAR Project (JPL). Closure-phase bias briefing; NISAR GUNW product specification; ASF NISAR Data User Guide.
- Le Moigne, J. (2025). NASA Earth System Digital Twins. AMS 2025.
- Reasenberg, P. & Jones, L. (1989). Earthquake hazard after a mainshock in California. *Science*.
- [Add after reading them yourself: Zheng & Fattahi (2026); the 2025 Senegal expansive-clay study.]
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md)
