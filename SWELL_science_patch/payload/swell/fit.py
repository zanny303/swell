"""Fit the artifact-aware model and its two competitors. Line-of-sight (LOS) change is the measured quantity.

Measurement model, relative to the first pass and to the reference ground:
    y_i(t) = cos(inc_i) * m_i(t) + beta * (1 - paved_i) * [w(t) - w(t0)] + noise

M0  naive      every phase change is ground motion
M1  rain-only  motion follows wetness at once, no artifact
M2  SWELL      artifact learned on OPEN low-clay ground, then lagged clay response (see physics.py)

Three kinds of ground, kept separate on purpose:
  reference  paved, low-clay, high-coherence: defines zero for every pass (never used to fit anything)
  control    open, low-clay: where the moisture artifact is learned (assumed not to swell: tested by `control`)
  clay       everything else that is coherent: where the clay response is fitted
Missing pixels are NaN and are skipped everywhere; they are never treated as "no motion".
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import nnls

from . import physics as ph

CONTROL_LEP = 1.5   # % : cells below this are low-clay
OPEN_PAVED = 0.5    # paved fraction below this counts as open ground
MIN_COH = 0.30


def cosi(site: dict) -> np.ndarray:
    inc = site["inc"] if "inc" in site and np.ndim(site["inc"]) == 2 else np.full(site["lep"].shape, float(site["inc_deg"]))
    return np.cos(np.radians(inc))


def masks(site: dict) -> dict:
    # Missing ancillary pixels are not silently classified as clay or open ground.
    ancillary_ok = np.isfinite(site["lep"]) & np.isfinite(site["paved"])
    ok = (site["coh"] >= MIN_COH) & ancillary_ok
    ref = site["ref"].astype(bool) if "ref" in site else np.zeros_like(ok)
    low = site["lep"] < float(site.get("lep_low", CONTROL_LEP))   # real sites may carry their own threshold (see real_site.py)
    control = low & (site["paved"] < OPEN_PAVED) & ok & ~ref
    clay = ~low & ok & ~ref
    return dict(ok=ok & ~ref, control=control, clay=clay, ref=ref)


def dwet(site: dict) -> np.ndarray:
    return site["w"][site["pass_days"]] - site["w"][site["pass_days"][0]]


def fit_beta(site: dict, passes: np.ndarray) -> tuple[float, float, int]:
    """Artifact strength: regress LOS change on (1 - paved) * wetness change over open low-clay cells."""
    mk = masks(site)["control"]
    x = dwet(site)[passes][:, None] * (1 - site["paved"][mk])[None]
    y = site["los"][passes][:, mk]
    v = np.isfinite(y)
    sxx = float((x[v] ** 2).sum())
    if v.sum() < 30 or sxx < 1e-9:
        return 0.0, float("inf"), int(v.sum())
    beta = float((x[v] * y[v]).sum() / sxx)
    se = float(np.sqrt(np.var(y[v] - beta * x[v]) / sxx))
    return beta, se, int(v.sum())


def artifact(site: dict, beta: float) -> np.ndarray:
    return beta * dwet(site)[:, None, None] * (1 - site["paved"])[None]


def corrected_los(site: dict, beta: float) -> np.ndarray:
    return site["los"] - artifact(site, beta)


def to_vertical(site: dict, los: np.ndarray) -> np.ndarray:
    """LOS -> vertical, ASSUMING no horizontal motion. With one viewing direction this cannot be checked;
    with ascending + descending passes it can (not implemented)."""
    return los / cosi(site)[None]


def fit_clay(site: dict, mcorr: np.ndarray, passes: np.ndarray,
             T_grid=(5, 8, 11, 14, 18, 24, 32), tau_grid=(0, 1, 2, 3, 5, 7)) -> dict:
    mk = masks(site)["clay"]
    lep, pv = site["lep"][mk], site["paved"][mk]
    pd = site["pass_days"]
    y = mcorr[passes][:, mk].ravel()
    v = np.isfinite(y)
    best = None
    for T in T_grid:
        for tau in tau_grid:
            s = ph.unit_response(site["w"], T, tau, s0=site["w"][0])
            ds = s[pd[passes]] - s[pd[0]]
            # Reparameterize: alpha = u+v, alpha*b = v, with u,v >= 0.
            # This enforces alpha >= 0 and 0 <= b <= 1 during optimization,
            # so SSE is evaluated on exactly the parameters used by the twin.
            A = np.stack([(ds[:, None] * lep[None]).ravel(),
                          (ds[:, None] * (lep * (1 - pv))[None]).ravel()], 1)[v]
            if not len(A):
                raise ValueError("No finite clay training observations")
            coef, _ = nnls(A, y[v])
            sse = float(((A @ coef - y[v]) ** 2).sum())
            if best is None or sse < best["sse"]:
                alpha = float(coef.sum())
                best = dict(alpha=alpha, b=float(coef[1] / alpha) if alpha > 1e-9 else 0.0,
                            T=float(T), tau=int(tau), sse=sse, n=int(v.sum()))
    best["rmse_train"] = float(np.sqrt(best["sse"] / max(best["n"], 1)))
    return best


def predict(site: dict, par: dict, w: np.ndarray | None = None, paved: np.ndarray | None = None) -> np.ndarray:
    w = site["w"] if w is None else w
    pv = site["paved"] if paved is None else paved
    m = ph.motion(w, site["lep"], pv, par["alpha"], par["b"], par["T"], par["tau"])
    return m - m[site["pass_days"][0]]


def fit_rain_only(site: dict, passes: np.ndarray) -> float:
    mk = masks(site)["clay"]
    x = dwet(site)[passes][:, None] * site["lep"][mk][None]
    y = to_vertical(site, site["los"])[passes][:, mk]
    v = np.isfinite(y)
    return float((x[v] * y[v]).sum() / max((x[v] ** 2).sum(), 1e-12))


def fit_all(site: dict, n_train: int | None = None) -> dict:
    P = len(site["pass_days"])
    n_train = n_train or int(round(P * 0.65))
    tr, te = np.arange(1, n_train), np.arange(n_train, P)
    beta, beta_se, n_ctrl = fit_beta(site, tr)
    los_corr = corrected_los(site, beta)
    mcorr = to_vertical(site, los_corr)
    par = fit_clay(site, mcorr, tr)
    return dict(beta=beta, beta_se=beta_se, n_control_obs=n_ctrl, par=par, train=tr, test=te, mcorr=mcorr,
                los_corr=los_corr, c_rain=fit_rain_only(site, tr), naive=to_vertical(site, site["los"]),
                naive_los=site["los"])
