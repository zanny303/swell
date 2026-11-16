"""The twin: a per-cell Kalman filter around the clay dynamics, plus forecasts, scenarios and refusal.

State per cell: m (vertical motion, mm, relative to first pass) with variance P.
  predict (daily):  m <- m + (G * w(t - tau) - m_abs) / T          P <- (1 - 1/T)^2 P + q
  update (a pass):  z = (y - beta (1 - paved) dw) / cos(inc), variance r(coherence); skipped where y is missing
                    K = P / (P + r);  m <- m + K (z - m);  P <- (1 - K) P
"""
from __future__ import annotations

import numpy as np

from . import fit as F
from . import physics as ph

Z90 = 1.645


def obs_var(coh: np.ndarray, base_mm: float = 2.5) -> np.ndarray:
    """Observation variance grows as coherence falls (Cramer-Rao-like shape), floor at base_mm^2."""
    c = np.clip(coh, 0.05, 0.99)
    return (base_mm ** 2) * (1 - c ** 2) / (2 * c ** 2) * 4 + base_mm ** 2 * 0.25


def run(site: dict, fitres: dict, upto_pass: int | None = None, q: float = 0.05, w: np.ndarray | None = None,
        horizon_days: int = 0) -> dict:
    """Assimilate passes [1..upto_pass]; then free-run to the end of the wetness series (+ nothing else).
    Returns daily mean and variance. Passes after `upto_pass` are NOT used: they are what forecasts are scored on."""
    par, beta = fitres["par"], fitres["beta"]
    w = site["w"] if w is None else w
    days = len(w)
    pd = site["pass_days"]
    upto = len(pd) - 1 if upto_pass is None else upto_pass
    G = ph.gain(site["lep"], site["paved"], par["alpha"], par["b"])
    s = ph.unit_response(w, par["T"], par["tau"], s0=w[0])
    model = G[None] * (s - s[pd[0]])[:, None, None]             # open-loop model, relative to first pass
    r = obs_var(site["coh"])
    e = np.zeros_like(site["lep"])                               # filter state = model + e
    P = np.zeros_like(e)
    mean = np.zeros((days,) + e.shape)
    var = np.zeros_like(mean)
    decay = 1 - 1 / par["T"]
    pass_at = {int(d): i for i, d in enumerate(pd)}
    for t in range(int(pd[0]), days):
        if t > pd[0]:
            e = decay * e                                         # errors relax like the clay does
            P = decay ** 2 * P + q
        i = pass_at.get(t)
        if i is not None and 1 <= i <= upto:
            z = fitres["mcorr"][i]
            K = np.where(np.isfinite(z), P / (P + r), 0.0)          # no observation -> no update (never "zero motion")
            e = e + K * (np.nan_to_num(z) - (model[t] + e))
            P = (1 - K) * P
        mean[t], var[t] = model[t] + e, P
    return dict(mean=mean, var=var, model=model, upto=upto)


def forecast_for_pass(site: dict, fitres: dict, target_pass: int) -> dict:
    """Forecast pass `target_pass` using only passes before it. Returns mean, 90% band half-width, refusal mask."""
    tw = run(site, fitres, upto_pass=target_pass - 1)
    d = int(site["pass_days"][target_pass])
    mu = tw["mean"][d]
    sd = np.sqrt(tw["var"][d] + obs_var(site["coh"]))            # predictive sd for the observation
    return dict(day=d, mean=mu, band=Z90 * sd, unresolved=refuse(site, mu, np.sqrt(tw["var"][d])))


def refuse(site: dict, mean: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """'Unresolved: observe again' where coherence is low or the 90% interval spans zero."""
    return (site["coh"] < F.MIN_COH) | (np.abs(mean) < Z90 * sd) | F.masks(site)["ref"]


def scenario(site: dict, fitres: dict, extra_rain_mm: float = 0.0, rain_days: int = 3, drought_days: int = 0,
             wetting_reduction: float = 0.0, paved_delta: float = 0.0, horizon: int = 30) -> dict:
    """User scenario, run with the same equations. Returns baseline vs scenario motion over `horizon` days ahead.
    Baseline future = no rain (a declared assumption, shown on screen)."""
    par = fitres["par"]
    n_past = len(site["rain"])
    base_rain = np.concatenate([site["rain"], np.zeros(horizon)])
    scen_rain = base_rain.copy()
    start = n_past + drought_days
    if extra_rain_mm > 0 and start < len(scen_rain):
        scen_rain[start:start + rain_days] += extra_rain_mm / rain_days
    scen_rain[n_past:] *= (1.0 - wetting_reduction)              # reduction applies to future wetting only
    pv = np.clip(site["paved"] + paved_delta, 0, 1)
    w0, w1 = ph.wetness(base_rain), ph.wetness(scen_rain)
    m0 = ph.motion(w0, site["lep"], site["paved"], par["alpha"], par["b"], par["T"], par["tau"])
    m1 = ph.motion(w1, site["lep"], pv, par["alpha"], par["b"], par["T"], par["tau"])
    now = len(site["rain"]) - 1
    return dict(days_ahead=np.arange(1, horizon + 1), baseline=m0[now + 1:] - m0[now], scenario=m1[now + 1:] - m1[now],
                assumptions=dict(extra_rain_mm=extra_rain_mm, rain_days=rain_days, drought_days=drought_days,
                                 wetting_reduction=wetting_reduction, paved_delta=paved_delta,
                                 baseline_future="no further rain"))


def horizon_maps(site: dict, fitres: dict, horizon: int = 30) -> dict:
    """Per-cell estimated vertical change from today after `horizon` days: (a) with no rain, (b) with a 75 mm storm
    in the first two days. Both are model outputs under stated assumptions."""
    dry = scenario(site, fitres, horizon=horizon)["baseline"][-1]
    storm = scenario(site, fitres, extra_rain_mm=75, rain_days=2, horizon=horizon)["scenario"][-1]
    return dict(drying=dry, storm=storm, storm_effect=storm - dry)
