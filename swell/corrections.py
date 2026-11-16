"""Phase corrections that NISAR ships inside every GUNW product but does not apply to the unwrapped phase.

The ASF NISAR GUNW guide: the product carries "geocoded lookup tables for external phase corrections" (solid Earth tides,
hydrostatic and wet troposphere) and "these phase corrections, when available, are not removed from the interferometric
data". The ionosphere screen is a full-resolution layer next to the phase and was already applied by swell.ingest. The
troposphere and tide layers are coarse 3D cubes (height x northing x easting) under /science/LSAR/GUNW/metadata/radarGrid.
Until this module, swell.ingest only applied a correction when it had the same shape as the phase, so the cubes were
silently skipped. This module finds them by name, takes the layer at the ground height, interpolates it onto the radar
window, and reports how much of the pass-to-pass variance it removes.

Nothing here invents a value: a layer that is missing, empty or all zero is reported as "not available" and skipped.
"""
from __future__ import annotations

import numpy as np

RADAR_GRID = "/science/LSAR/GUNW/metadata/radarGrid"
TROPO_COMBINED = ("combinedTroposphericPhaseScreen",)
TROPO_WET = ("wetTroposphericPhaseScreen",)
TROPO_DRY = ("hydrostaticTroposphericPhaseScreen", "dryTroposphericPhaseScreen")
TIDE = ("slantRangeSolidEarthTidesPhase", "solidEarthTidesPhase")
COORD = ("xCoordinates", "yCoordinates", "heightAboveEllipsoid", "projection")


def _names(f):
    out = []
    f.visititems(lambda k, o: out.append("/" + k) if hasattr(o, "shape") else None)
    return out


def cube_paths(names) -> list[str]:
    """Every dataset worth copying from the radar grid: the correction cubes and their coordinates."""
    want = TROPO_COMBINED + TROPO_WET + TROPO_DRY + TIDE + COORD
    return [k for k in names if "/radarGrid/" in k and k.rsplit("/", 1)[-1] in want]


def _find(names, leaves):
    for leaf in leaves:
        hit = [k for k in names if "/radarGrid/" in k and k.endswith("/" + leaf)]
        if hit:
            return hit[0]
    return None


def plan(names) -> dict:
    """Which layers to apply. Troposphere: the combined screen if present, otherwise wet + hydrostatic."""
    p = {}
    comb = _find(names, TROPO_COMBINED)
    if comb:
        p["troposphere"] = [comb]
    else:
        parts = [x for x in (_find(names, TROPO_WET), _find(names, TROPO_DRY)) if x]
        if parts:
            p["troposphere"] = parts
    tide = _find(names, TIDE)
    if tide:
        p["solid_earth_tide"] = [tide]
    return p


def _layer_at_height(cube, heights, h):
    """A cube is (height, y, x) in the NISAR spec. Axes are matched by length so a different order still works."""
    cube = np.asarray(cube, float)
    if cube.ndim == 2:
        return cube
    if cube.ndim != 3:
        raise ValueError(f"unexpected correction layer with {cube.ndim} dimensions")
    hz = np.asarray(heights, float).ravel() if heights is not None else None
    ax = 0
    if hz is not None and len(hz) in cube.shape:
        ax = cube.shape.index(len(hz))
    cube = np.moveaxis(cube, ax, 0)
    if hz is None or len(hz) != cube.shape[0]:
        return cube[0]
    order = np.argsort(hz); hz = hz[order]; cube = cube[order]
    h = float(np.clip(h, hz[0], hz[-1])); k = int(np.clip(np.searchsorted(hz, h) - 1, 0, len(hz) - 2))
    t = (h - hz[k]) / max(1e-9, hz[k + 1] - hz[k])
    return (1 - t) * cube[k] + t * cube[k + 1]


def _interp2(layer, cy, cx, y, x):
    """Bilinear interpolation of a coarse (y, x) layer onto the radar window coordinates (same projection)."""
    from scipy.interpolate import RegularGridInterpolator
    cy = np.asarray(cy, float).ravel(); cx = np.asarray(cx, float).ravel(); layer = np.asarray(layer, float)
    if layer.shape != (len(cy), len(cx)) and layer.shape == (len(cx), len(cy)):
        layer = layer.T
    if cy[0] > cy[-1]:
        cy, layer = cy[::-1], layer[::-1]
    if cx[0] > cx[-1]:
        cx, layer = cx[::-1], layer[:, ::-1]
    fn = RegularGridInterpolator((cy, cx), layer, bounds_error=False, fill_value=None)
    yy, xx = np.meshgrid(np.asarray(y, float), np.asarray(x, float), indexing="ij")
    return fn(np.stack([yy.ravel(), xx.ravel()], 1)).reshape(yy.shape)


def screens(f, x, y, ground_height_m: float = 150.0) -> tuple[dict, dict]:
    """Return ({kind: radians on the (y, x) window}, {kind: note}). Only layers with usable values are returned."""
    names = _names(f); p = plan(names); out, notes = {}, {}
    cx = _find(names, ("xCoordinates",)); cy = _find(names, ("yCoordinates",)); ch = _find(names, ("heightAboveEllipsoid",))
    if not p:
        return out, {"troposphere": "not in this file", "solid_earth_tide": "not in this file"}
    if not (cx and cy):
        return out, {k: "radar-grid coordinates missing, layer not used" for k in p}
    for kind, paths in p.items():
        try:
            tot = None
            for path in paths:
                lay = _layer_at_height(f[path][...], f[ch][...] if ch else None, ground_height_m)
                lay = _interp2(lay, f[cy][...], f[cx][...], y, x)
                tot = lay if tot is None else tot + lay
            if tot is None or not np.isfinite(tot).any() or np.nanmax(np.abs(tot)) == 0:
                notes[kind] = "present but empty or all zero, not used"; continue
            fin = np.isfinite(tot)
            if fin.mean() < 0.5:
                notes[kind] = f"only {fin.mean():.0%} of the window has values, not used"; continue
            if not fin.all():                                                 # fill gaps (fill values at the cube edge) from the nearest valid value
                from scipy.ndimage import distance_transform_edt
                idx = distance_transform_edt(~fin, return_distances=False, return_indices=True); tot = tot[tuple(idx)]
            if float(np.std(tot)) > 50.0:                                     # > 50 rad spread (about 1 m): not a troposphere screen
                notes[kind] = f"implausible spread {float(np.std(tot)):.0f} rad, not used"; continue
            out[kind] = tot; notes[kind] = " + ".join(pp.rsplit("/", 1)[-1] for pp in paths) + f" at {ground_height_m:.0f} m"
        except Exception as ex:                                               # a malformed layer must never stop the build
            notes[kind] = f"could not be read ({type(ex).__name__}: {str(ex)[:80]}), not used"
    return out, notes


def spread(a, ok=None) -> float:
    v = np.asarray(a, float)
    m = np.isfinite(v) if ok is None else (np.isfinite(v) & ok)
    if m.sum() < 30:
        return float("nan")
    v = v[m]; return float(np.sqrt(np.mean((v - np.median(v)) ** 2)))


def choose_sign(phases, screens_list, cohs=None) -> tuple[int, dict]:
    """The spec does not state the sign. Subtracting is the usual convention; it is kept unless adding the layer
    removes clearly more scene variance over all pairs. If neither removes variance the layer is not applied (sign 0).
    The numbers are returned so the choice is on record."""
    before = after_sub = after_add = 0.0; n = 0
    for k, (ph, sc) in enumerate(zip(phases, screens_list)):
        if sc is None:
            continue
        ok = None if cohs is None else (np.nan_to_num(cohs[k]) >= 0.3)
        b, s_, a_ = spread(ph, ok), spread(ph - sc, ok), spread(ph + sc, ok)
        if np.isfinite([b, s_, a_]).all():
            before += b * b; after_sub += s_ * s_; after_add += a_ * a_; n += 1
    if n == 0:
        return -1, dict(pairs=0)
    sign = +1 if after_add < 0.8 * after_sub else -1
    rms = lambda q: float(np.sqrt(q / n))
    if min(after_sub, after_add) >= 0.98 * before:                           # quality gate: a correction that adds variance is not applied
        return 0, dict(pairs=n, rms_before_rad=rms(before), rms_after_subtract_rad=rms(after_sub), rms_after_add_rad=rms(after_add),
                       applied="not applied (did not reduce scene variance)", variance_removed_pct=0.0)
    return sign, dict(pairs=n, rms_before_rad=rms(before), rms_after_subtract_rad=rms(after_sub), rms_after_add_rad=rms(after_add),
                      applied="added" if sign > 0 else "subtracted",
                      variance_removed_pct=round(100 * (1 - (after_add if sign > 0 else after_sub) / max(before, 1e-12)), 1))


def highpass(d_mm, coh, sigma_cells: float):
    """Remove the smooth part of one pair (NaN-aware Gaussian). Keeps cell-to-cell differences: clay against its
    neighbours. Removes any movement smoother than about 2 x sigma, real or atmospheric. Exploratory option only."""
    from scipy.ndimage import gaussian_filter
    v = np.asarray(d_mm, float); m = np.isfinite(v).astype(float)
    num = gaussian_filter(np.nan_to_num(v), sigma_cells, mode="nearest"); den = gaussian_filter(m, sigma_cells, mode="nearest")
    with np.errstate(all="ignore"):
        smooth = num / den
    return v - smooth
