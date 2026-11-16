"""The pre-registered tests (see PREREGISTRATION.md). Each returns a dict with the numbers and a `passed` flag.
Pass marks live here as constants so they cannot drift from the registration file. Everything is NaN-aware."""
from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr

from . import fit as F
from . import twin as TW

PASS = dict(gps_rms_mm=10.0, shuffle_quantile=0.99, min_rho=0.2, min_rmse_gain=0.10, control_mult=1.5)


def _boot_ci(x: np.ndarray, rng, n=2000, block=5) -> list[float]:
    """Spatial block bootstrap of the mean of a 2-D field (blocks of `block` x `block` cells)."""
    H, W = x.shape
    blocks = [x[i:i + block, j:j + block].ravel() for i in range(0, H, block) for j in range(0, W, block)]
    blocks = [b[np.isfinite(b)] for b in blocks]
    blocks = [b for b in blocks if len(b)]
    if len(blocks) < 4:
        return [float("nan"), float("nan")]
    out = np.empty(n)
    for k in range(n):
        out[k] = np.concatenate([blocks[p] for p in rng.integers(0, len(blocks), len(blocks))]).mean()
    return [float(np.quantile(out, .025)), float(np.quantile(out, .975))]


def _amp(a: np.ndarray) -> np.ndarray:
    """Seasonal range per cell, robust to missing passes and single noisy passes (5th-95th percentile)."""
    return np.nanpercentile(a, 95, axis=0) - np.nanpercentile(a, 5, axis=0)


def t1_gps(site, fr) -> dict:
    if not site.get("gps"):
        return dict(name="T1 GPS referee", passed=None, n=0, stations=0, note="not run: no GPS stations supplied for this site")
    """In the radar's own line of sight: does removing the artifact bring NISAR closer to GPS?
    GPS 'up' is projected into the line of sight with each cell's incidence angle."""
    pd = site["pass_days"]
    c = F.cosi(site)
    e0, e2 = [], []
    for g in site["gps"].values():
        i, j = g["cell"]
        up = np.asarray(g["up_mm"]); gd = np.asarray(g["days"])
        ref = np.array([np.nanmean(up[(gd >= d - 2) & (gd <= d + 2)]) if ((gd >= d - 2) & (gd <= d + 2)).any() else np.nan for d in pd])
        ref = (ref - ref[0]) * c[i, j]
        e0 += list(fr["naive_los"][1:, i, j] - ref[1:]); e2 += list(fr["los_corr"][1:, i, j] - ref[1:])
    e0, e2 = np.array(e0), np.array(e2)
    v = np.isfinite(e0) & np.isfinite(e2)
    if v.sum() < 6:
        return dict(name="T1 GPS referee", passed=None, note="fewer than 6 paired GPS/NISAR values", n=int(v.sum()))
    r0, r2 = float(np.sqrt(np.mean(e0[v] ** 2))), float(np.sqrt(np.mean(e2[v] ** 2)))
    return dict(name="T1 GPS referee", rms_naive_mm=r0, rms_swell_mm=r2, n=int(v.sum()), stations=len(site["gps"]),
                frame="line of sight", passed=bool(r2 < r0 and r2 < PASS["gps_rms_mm"]))


def t2_clay_map(site, fr, rng, n_shuffle=999) -> dict:
    ok = F.masks(site)["ok"]
    amp = _amp(fr["mcorr"])
    ok = ok & np.isfinite(amp)
    rho = float(spearmanr(amp[ok], site["lep"][ok]).statistic)
    H, W = amp.shape
    null = np.empty(n_shuffle)
    for k in range(n_shuffle):                       # toroidal shifts keep the map's spatial structure
        sh = np.roll(site["lep"], (rng.integers(3, H - 3), rng.integers(3, W - 3)), (0, 1))
        null[k] = spearmanr(amp[ok], sh[ok]).statistic
    q = float((null < rho).mean())
    return dict(name="T2 Clay map", spearman=rho, null_quantile=q, n_shuffle=n_shuffle,
                passed=bool(rho >= PASS["min_rho"] and q >= PASS["shuffle_quantile"]))


def t3_forecast(site, fr, rng) -> dict:
    ok = F.masks(site)["clay"]
    rows, e_sw, e_ps, e_rn, e_0, cover, width = [], [], [], [], [], [], []
    dw = F.dwet(site)
    for p in fr["test"]:
        fc = TW.forecast_for_pass(site, fr, int(p))
        obs, persist = fr["mcorr"][p], fr["mcorr"][p - 1]
        rain = fr["c_rain"] * site["lep"] * dw[p]
        e_sw.append((fc["mean"] - obs) ** 2); e_ps.append((persist - obs) ** 2); e_rn.append((rain - obs) ** 2); e_0.append(obs ** 2)
        v = ok & np.isfinite(obs)
        cover.append(float((np.abs(fc["mean"] - obs) <= fc["band"])[v].mean())); width.append(float(fc["band"][v].mean()))
        rows.append(dict(pass_index=int(p), day=fc["day"], rmse_swell=float(np.sqrt(np.nanmean(e_sw[-1][ok]))),
                         rmse_persistence=float(np.sqrt(np.nanmean(e_ps[-1][ok]))),
                         rmse_rain_only=float(np.sqrt(np.nanmean(e_rn[-1][ok]))), coverage90=cover[-1], band_mm=width[-1]))
    def m(e):
        a = np.array(e); n = np.isfinite(a).sum(0)
        return np.where(n > 0, np.nansum(a, 0) / np.maximum(n, 1), np.nan)
    ci = _boot_ci(np.where(ok, m(e_ps) - m(e_sw), np.nan), rng)
    ci0 = _boot_ci(np.where(ok, m(e_0) - m(e_sw), np.nan), rng)
    r_sw = float(np.sqrt(np.nanmean(m(e_sw)[ok])))
    r_best = min(float(np.sqrt(np.nanmean(m(e_ps)[ok]))), float(np.sqrt(np.nanmean(m(e_0)[ok]))))
    big_enough = r_sw <= (1 - PASS["min_rmse_gain"]) * r_best
    return dict(name="T3 Forecast holdout", per_pass=rows, rmse_swell=r_sw, gain_vs_best_baseline=float(1 - r_sw / r_best),
                rmse_persistence=float(np.sqrt(np.nanmean(m(e_ps)[ok]))), rmse_rain_only=float(np.sqrt(np.nanmean(m(e_rn)[ok]))),
                coverage90=float(np.mean(cover)), mean_band_mm=float(np.mean(width)),
                calibration_note="coverage well above 90 % means the bands are wider than they need to be",
                rmse_no_change=float(np.sqrt(np.nanmean(m(e_0)[ok]))),
                mse_gain_vs_persistence_ci95=ci, mse_gain_vs_no_change_ci95=ci0, passed=bool(ci[0] > 0 and ci0[0] > 0 and big_enough))


def t4_spatial(site, rng) -> dict:
    """Fit on the west half, freeze, predict the east half with no refitting."""
    half = site["n"] // 2
    west, east = dict(site), dict(site)
    for k in ("lep", "paved", "coh", "ref", "inc"):
        if k in site and np.ndim(site[k]) == 2:
            west[k], east[k] = site[k][:, :half], site[k][:, half:]
    west["los"], east["los"] = site["los"][:, :, :half], site["los"][:, :, half:]
    fw = F.fit_all(west)
    me = F.to_vertical(east, F.corrected_los(east, fw["beta"]))
    pred = F.predict(east, fw["par"])[east["pass_days"]]
    ok = F.masks(east)["clay"]
    te = fw["test"]
    e_sw, e_0 = np.nanmean((pred[te] - me[te]) ** 2, 0), np.nanmean(me[te] ** 2, 0)
    ci = _boot_ci(np.where(ok, e_0 - e_sw, np.nan), rng)
    return dict(name="T4 Unseen zone", rmse_swell=float(np.sqrt(np.nanmean(e_sw[ok]))),
                rmse_no_change=float(np.sqrt(np.nanmean(e_0[ok]))), mse_gain_ci95=ci, frozen_params=fw["par"],
                frozen_beta=fw["beta"], passed=bool(ci[0] > 0))


def t5_abstain(site, fr) -> dict:
    errs, kept = [], []
    for p in fr["test"]:
        fc = TW.forecast_for_pass(site, fr, int(p))
        errs.append(np.abs(fc["mean"] - fr["mcorr"][p])); kept.append(~fc["unresolved"])
    errs, kept = np.array(errs), np.array(kept)
    v = np.isfinite(errs)
    all_mae = float(errs[v].mean()); kept_mae = float(errs[v & kept].mean()) if (v & kept).any() else float("nan")
    return dict(name="T5 Refusal", mae_all_mm=all_mae, mae_kept_mm=kept_mae, kept_fraction=float(kept.mean()),
                passed=bool(kept_mae < all_mae))


def t6_paved(site, fr, rng) -> dict:
    """On the same clay, does open ground move more than paved ground? Compared within clay-rating bands,
    spatial block bootstrap."""
    mk = F.masks(site)["clay"]
    amp = _amp(fr["mcorr"]) / site["lep"]                                   # mm per % rating
    lo, hi = mk & (site["paved"] < .2), mk & (site["paved"] > .6)
    if lo.sum() < 30 or hi.sum() < 30:
        return dict(name="T6 Paved vs open", passed=None, n_open=int(lo.sum()), n_paved=int(hi.sum()),
                    note="fewer than 30 cells in one class")
    H, W = amp.shape; B = 5
    idx = [(i, j) for i in range(0, H, B) for j in range(0, W, B)]
    diff = np.empty(2000)
    for k in range(2000):
        a, b = [], []
        for q in rng.integers(0, len(idx), len(idx)):
            i, j = idx[q]; sl = (slice(i, i + B), slice(j, j + B))
            a.append(amp[sl][lo[sl]]); b.append(amp[sl][hi[sl]])
        a, b = np.concatenate(a), np.concatenate(b)
        diff[k] = np.nanmean(a) - np.nanmean(b) if len(a) and len(b) else np.nan
    ci = [float(np.nanquantile(diff, .025)), float(np.nanquantile(diff, .975))]
    return dict(name="T6 Paved vs open", open_mm_per_lep=float(np.nanmean(amp[lo])), paved_mm_per_lep=float(np.nanmean(amp[hi])),
                diff_ci95=ci, n_open=int(lo.sum()), n_paved=int(hi.sum()), passed=bool(ci[0] > 0))


def control(site, fr) -> dict:
    """Is the control ground itself stable once the artifact is removed? Noise level comes from the REFERENCE
    ground (paved, low-clay), which is independent of the control cells."""
    mk = F.masks(site)
    if mk["control"].sum() < 20 or mk["ref"].sum() < 5:
        return dict(name="Control ground", passed=None, note="too few control or reference cells",
                    n_control=int(mk["control"].sum()), n_reference=int(mk["ref"].sum()))
    amp_c = float(np.nanmean(_amp(fr["mcorr"])[mk["control"]]))
    amp_naive = float(np.nanmean(_amp(fr["naive"])[mk["control"]]))
    noise = float(np.nanmean(_amp(fr["naive"])[mk["ref"]]))                 # reference cells: range of pure noise
    return dict(name="Control ground", amp_corrected_mm=amp_c, amp_naive_mm=amp_naive, noise_range_mm=noise,
                n_control=int(mk["control"].sum()), n_reference=int(mk["ref"].sum()),
                passed=bool(amp_c <= PASS["control_mult"] * noise))


def run_all(site, fr, seed=0) -> list[dict]:
    rng = np.random.default_rng(seed)
    return [t1_gps(site, fr), t2_clay_map(site, fr, rng), t3_forecast(site, fr, rng), t4_spatial(site, rng),
            t5_abstain(site, fr), t6_paved(site, fr, rng), control(site, fr)]
