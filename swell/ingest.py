"""Real-data ingest: NISAR GUNW -> out/<site>.npz in the format swell.validate reads.

*** NOT YET RUN ON REAL FILES. *** It was written from the ASF NISAR product guide without network access to
NASA. Run step 1 and step 2 first and fix dataset paths if `inspect` shows different names.

  1. python -m swell.ingest search  --site dallas
  2. python -m swell.ingest inspect --file <one downloaded GUNW .h5>      (lists every dataset path)
  3. python -m swell.ingest build   --site dallas --gunw-dir data/dallas --rain rain.csv --lep lep.tif --paved paved.tif --gps gps.json

Needs: pip install asf_search earthaccess h5py rasterio pyproj ; an Earthdata login in ~/.netrc
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib

import numpy as np

from . import physics as ph

SITES = {  # bbox = west, south, east, north. Add a city = add a line.
    "dallas": dict(name="Dallas-Fort Worth, USA", bbox=[-97.05, 32.60, -96.55, 33.00]),
    "toulouse": dict(name="Toulouse, France", bbox=[1.25, 43.45, 1.65, 43.75]),
    "nagpur": dict(name="Nagpur, India", bbox=[78.95, 21.00, 79.25, 21.30]),
}
# Expected GUNW layout (frequency A, HH). Verify with `inspect`.
G = "/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/"
PATHS = dict(phase=G + "unwrappedPhase", coh=G + "coherenceMagnitude", cc=G + "connectedComponents",
             iono=G + "ionospherePhaseScreen", x=G + "xCoordinates", y=G + "yCoordinates", epsg=G + "projection")


def search(site: str):
    import asf_search as asf
    w, s, e, n = SITES[site]["bbox"]
    wkt = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"
    res = asf.search(dataset="NISAR", processingLevel="GUNW", intersectsWith=wkt, start="2026-06-17")
    rows = sorted((r.properties.get("pathNumber"), r.properties.get("startTime"), r.properties.get("fileName"),
                   r.properties.get("url")) for r in res)
    by_track = {}
    for t, *rest in rows:
        by_track.setdefault(t, []).append(rest)
    for t, v in by_track.items():
        print(f"track {t}: {len(v)} GUNW pairs, {v[0][0]} .. {v[-1][0]}")
    pathlib.Path("out").mkdir(exist_ok=True)
    json.dump(by_track, open(f"out/{site}_inventory.json", "w"), indent=1, default=str)
    print(f"GO if one track has >= 8 pairs. Inventory saved to out/{site}_inventory.json")


def inspect(file: str):
    import h5py
    with h5py.File(file, "r") as f:
        f.visititems(lambda name, obj: print(name, getattr(obj, "shape", "")) if hasattr(obj, "shape") else None)


def _crop(f, bbox):
    from pyproj import Transformer
    x, y = f[PATHS["x"]][:], f[PATHS["y"]][:]
    epsg = int(np.array(f[PATHS["epsg"]]))
    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    (x0, x1), (y0, y1) = tr.transform([bbox[0], bbox[2]], [bbox[1], bbox[3]])
    j = np.where((x >= min(x0, x1)) & (x <= max(x0, x1)))[0]
    i = np.where((y >= min(y0, y1)) & (y <= max(y0, y1)))[0]
    if len(i) < 8 or len(j) < 8:
        raise ValueError("this radar frame does not cover the site box (no overlap between the frame grid and the box). Pick another track/frame or move the box.")
    return slice(i.min(), i.max() + 1), slice(j.min(), j.max() + 1)


def _detrend(d, coh, order=2, min_coh=0.35, fit_on=None):
    """Remove the smooth scene-wide surface from one interferogram (orbit error, ionosphere and long-wavelength troposphere).

    A smooth surface is fitted with a robust (Huber-type) weight and subtracted. When `fit_on` is given it is fitted only on
    ground that should not move (paved or low-clay cells), so clay swelling across the site is not mistaken for atmosphere. Standard InSAR practice ("deramping"). Cost, stated in provenance: any real ground motion that is itself
    smooth across the whole site is removed too. SWELL keeps the local, cell-to-cell differences, which is what clay movement
    between neighbouring ground and what strains structures. Returns (detrended, rms of the removed surface in mm)."""
    n = d.shape[0]; yy, xx = np.mgrid[0:n, 0:n]; x = xx / (n - 1) * 2 - 1; y = yy / (n - 1) * 2 - 1
    cols = [np.ones_like(x), x, y] + ([x * x, x * y, y * y] if order >= 2 else [])
    A = np.stack([c.ravel() for c in cols], 1); v = d.ravel(); ok = np.isfinite(v) & (np.nan_to_num(coh).ravel() >= min_coh)
    if fit_on is not None and (ok & fit_on.ravel()).sum() >= 25:
        ok = ok & fit_on.ravel()                                          # learn the surface only where the ground should not move
    if ok.sum() < 60:
        ok = np.isfinite(v)
    if ok.sum() < 60:
        return d, 0.0
    w = np.ones(int(ok.sum())); coef = np.zeros(A.shape[1])
    for _ in range(5):
        coef = np.linalg.lstsq(A[ok] * w[:, None], v[ok] * w, rcond=None)[0]
        r = v[ok] - A[ok] @ coef; sc = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-9
        w = 1.0 / np.maximum(1.0, np.abs(r) / (2.0 * sc))
    surf = (A @ coef).reshape(d.shape)
    return d - surf, float(np.sqrt(np.mean((surf - surf.mean()) ** 2)))


def _regrid(a, n):
    """Block-average to an n x n grid, ignoring NaN. A block with under 30 % valid pixels stays NaN."""
    H, W = a.shape
    a = a[: H // n * n, : W // n * n].reshape(n, H // n, n, W // n)
    frac = np.isfinite(a).mean(axis=(1, 3))
    with np.errstate(all="ignore"):
        out = np.nanmean(a, axis=(1, 3))
    return np.where(frac >= 0.3, out, np.nan)


def _warp_to_grid(path, epsg, x, y, resampling="average"):
    """Reproject any raster onto the radar crop grid (explicit CRS + transform: no assumed alignment)."""
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject
    dx, dy = float(abs(x[1] - x[0])), float(abs(y[1] - y[0]))
    dst = np.full((len(y), len(x)), np.nan, dtype="float32")
    with rasterio.open(path) as src:
        if src.crs is None:
            raise ValueError(f"{path} has no CRS: cannot align it to the radar grid")
        reproject(rasterio.band(src, 1), dst, src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
                  dst_transform=from_origin(x.min() - dx / 2, y.max() + dy / 2, dx, dy), dst_crs=f"EPSG:{epsg}",
                  dst_nodata=np.nan, resampling=getattr(Resampling, resampling))
        info = dict(file=str(path), crs=str(src.crs), res=[float(v) for v in src.res])
    cover = float(np.isfinite(dst).mean())
    if cover < 0.9:
        raise ValueError(f"{path} covers only {cover:.0%} of the site box: check extent and CRS")
    info["coverage"] = cover
    return (dst if y[0] > y[-1] else dst[::-1]), info


OPTIONAL_CORR = dict(  # external phase corrections supplied with GUNW but NOT pre-applied. Names to verify with `inspect`.
    troposphere_wet="wetTroposphericPhaseScreen", troposphere_hydrostatic="hydrostaticTroposphericPhaseScreen",
    solid_earth_tide="solidEarthTidesPhase")


def build(site: str, gunw_dir: str, rain_csv: str, lep_tif: str, paved_tif: str, gps_json: str | None, n: int = 60,
          start_date: str | None = None, lep_low: float = 1.5, clay_layer: str = "shrink-swell rating (LEP, %)", detrend: int = 2,
          troposphere: bool = True, tides: bool = True, ground_height_m: float = 150.0, highpass_km: float = 0.0):
    """LOS time series on an n x n grid, with missing data kept missing.

    Reference ground  = paved (>0.8), low-clay, coherent cells, or the cell of the GPS station named "REFERENCE" in gps.json.
    Control ground    = open low-clay cells (chosen later by swell.fit.masks). The two never overlap.
    """
    import h5py
    from datetime import datetime
    bbox = SITES[site]["bbox"]
    files = sorted(glob.glob(f"{gunw_dir}/*.h5"))
    if not files:
        raise SystemExit(f"no .h5 files in {gunw_dir}")
    # --start-date drops pairs that begin earlier, e.g. to start the series after the 27 Jul - 10 Aug data gap
    pairs, dates, ids, budget = [], [], [], []
    grid = None
    from . import corrections as CR
    raw = []
    for fn in files:
        applied = ["ionosphere"]
        with h5py.File(fn, "r") as f:
            si, sj = _crop(f, bbox)
            x, y = f[PATHS["x"]][sj], f[PATHS["y"]][si]
            epsg = int(np.array(f[PATHS["epsg"]]))
            ph_ = f[PATHS["phase"]][si, sj].astype(float)
            if PATHS["iono"] in f and f[PATHS["iono"]].shape == f[PATHS["phase"]].shape:
                ph_ -= f[PATHS["iono"]][si, sj].astype(float)
            else:
                applied.remove("ionosphere")
            scr, notes = CR.screens(f, x, y, ground_height_m) if (troposphere or tides) else ({}, {})
            use = [k for k in scr if (k == "troposphere" and troposphere) or (k == "solid_earth_tide" and tides)]
            screen = sum(scr[k] for k in use) if use else None
            coh = f[PATHS["coh"]][si, sj].astype(float)
            cc = f[PATHS["cc"]][si, sj]
            ph_[(cc <= 0) | ~np.isfinite(ph_)] = np.nan                  # not unwrapped -> missing
            try:
                inc_ds = [k for k in _all_datasets(f) if k.endswith("incidenceAngle")]
                inc_val = float(np.nanmean(f[inc_ds[0]][...])) if inc_ds else float("nan")
            except Exception:
                inc_val = float("nan")
            try:
                t0 = f["/science/LSAR/identification/referenceZeroDopplerStartTime"][()].decode()[:10]
                t1 = f["/science/LSAR/identification/secondaryZeroDopplerStartTime"][()].decode()[:10]
            except Exception:                                             # fall back to the dates in the official file name
                import re
                tk = re.findall(r"(\d{8})T\d{6}", pathlib.Path(fn).name)
                if len(tk) < 3:
                    raise ValueError(f"{fn}: cannot read the pair dates from the file or its name")
                t0, t1 = (f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in (tk[0], tk[2]))
        if len(y) > 1 and y[0] < y[-1]:                                  # keep row 0 = north, column 0 = west, whatever order the file uses
            ph_, coh, y = ph_[::-1], coh[::-1], y[::-1]
            screen = None if screen is None else screen[::-1]
        if len(x) > 1 and x[0] > x[-1]:
            ph_, coh, x = ph_[:, ::-1], coh[:, ::-1], x[::-1]
            screen = None if screen is None else screen[:, ::-1]
        if start_date and t0 < start_date:
            continue
        if grid is None:
            grid = dict(x=x, y=y, epsg=epsg, shape=ph_.shape)
        elif ph_.shape != grid["shape"]:
            raise ValueError(f"{fn}: crop shape {ph_.shape} differs from first file {grid['shape']} (different frame?)")
        raw.append(dict(ph=ph_, coh=coh, screen=screen, use=use))
        dates.append((t0, t1)); ids.append(pathlib.Path(fn).name)
        budget.append(dict(granule=ids[-1], pair=[t0, t1], applied=applied, nisar_layers=notes,
                           not_applied=[k for k in ("troposphere", "solid_earth_tide") if k not in use] + ["squint/unwrapping residuals"],
                           scene_surface_removed_rms_mm=0.0,
                           incidence_deg=inc_val))
    corr_summary = dict(requested=dict(troposphere=troposphere, solid_earth_tide=tides, ground_height_m=ground_height_m), pairs_with_layers=0)
    if any(r["screen"] is not None for r in raw):
        sign, stats = CR.choose_sign([r["ph"] for r in raw], [r["screen"] for r in raw], [r["coh"] for r in raw])
        corr_summary.update(stats); corr_summary["pairs_with_layers"] = sum(r["screen"] is not None for r in raw) if sign != 0 else 0
        for r, bud in zip(raw, budget):
            if r["screen"] is not None and sign != 0:
                r["ph"] = r["ph"] + sign * r["screen"]; bud["applied"] += [k + " (NISAR layer)" for k in r["use"]]
        print(f"NISAR correction layers ({', '.join(sorted({k for r in raw for k in r['use']}))}): {stats['applied']}, "
              f"scene variance removed {stats['variance_removed_pct']} % over {stats['pairs']} pairs")
    else:
        print("NISAR troposphere / tide layers: not found in these files (or switched off). Run real_site.py again to fetch them.")
    for r in raw:
        pairs.append((ph.phase_to_los_mm(_regrid(r["ph"], n)), _regrid(r["coh"], n)))
    del raw
    lep_full, lep_info = _warp_to_grid(lep_tif, grid["epsg"], grid["x"], grid["y"])
    pv_full, pv_info = _warp_to_grid(paved_tif, grid["epsg"], grid["x"], grid["y"])
    lep, paved = _regrid(lep_full, n), _regrid(pv_full, n)
    paved = paved / 100.0 if np.nanmax(paved) > 1 else paved
    coh_pairs = np.array([c for _, c in pairs])
    coh = np.nanmin(coh_pairs, axis=0)                                    # worst pair governs a cell's trust
    gps = json.load(open(gps_json)) if gps_json else {}
    if "REFERENCE" in gps:
        i, j = gps["REFERENCE"]["cell"]
        ref = np.zeros((n, n), bool); ref[max(i - 1, 0):i + 2, max(j - 1, 0):j + 2] = True
        ref_kind = "3x3 cells around GPS station REFERENCE"
    else:
        ref = (paved > 0.8) & (lep < lep_low) & (coh > 0.5)
        ref_kind = f"paved (>0.8), low-clay (<{lep_low:.1f}), coherent (>0.5) cells"
        if ref.sum() < 5:                                                 # real cities: little paved ground is also low-clay
            ref = (paved > np.nanquantile(paved, 0.9)) & (paved > 0.5) & (coh > 0.5)
            ref_kind = "most-paved 10 % of cells, coherent (>0.5). WEAKER: clay may lie under this pavement"
    if ref.sum() < 5:
        raise SystemExit(f"only {int(ref.sum())} reference cells ({ref_kind}). Name a GPS station REFERENCE in gps.json, or widen the site box.")
    stable_n = int(ref.sum()); surface_order = 0
    if detrend:
        # The reference ground is assumed not to move. Until now each pair was zeroed on its median (a constant). Atmosphere and orbit
        # error are not constant across a city, so the reference is generalised to a smooth surface through the same reference cells.
        ii, jj = np.nonzero(ref); spread = min(np.ptp(ii), np.ptp(jj)) / max(1, n - 1)
        surface_order = detrend if (stable_n >= 150 and spread >= 0.6) else 1 if (stable_n >= 30 and spread >= 0.3) else 0
        fit_cells = ref
        if not surface_order:                                             # reference cells are one small cluster: fall back to a tilt (plane) through mostly paved ground
            pv_ok = (paved > 0.6) & np.isfinite(paved); pi, pj = np.nonzero(pv_ok)
            if pv_ok.sum() >= 60 and min(np.ptp(pi), np.ptp(pj)) / max(1, n - 1) >= 0.5:
                fit_cells, surface_order, stable_n = pv_ok, 1, int(pv_ok.sum())
        if surface_order:
            for k, (d_mm, c_n) in enumerate(pairs):
                d2, removed = _detrend(d_mm, c_n, order=surface_order, min_coh=0.0, fit_on=fit_cells)
                pairs[k] = (d2, c_n); budget[k]["scene_surface_removed_rms_mm"] = round(removed, 2)
    hp_note = "none"
    if highpass_km and highpass_km > 0:                                 # exploratory: keep only cell-to-cell differences
        cell_km = abs(float(grid["x"][1] - grid["x"][0])) * (grid["shape"][1] // n) / 1000.0
        sig = max(0.5, highpass_km / max(cell_km, 1e-6))
        for k, (d_mm, c_n) in enumerate(pairs):
            pairs[k] = (CR.highpass(d_mm, c_n, sig), c_n)
        hp_note = f"Gaussian high-pass, sigma {highpass_km:g} km ({sig:.1f} cells). EXPLORATORY: removes any movement smoother than this, real or not"
    epoch0 = datetime.fromisoformat(dates[0][0])
    pass_dates = [dates[0][0]] + [d[1] for d in dates]
    breaks = [i + 1 for i, (a, b) in enumerate(zip(dates[:-1], dates[1:])) if a[1] != b[0]]
    los = [np.zeros((n, n))]
    for k, (d, _) in enumerate(pairs):
        d = d - np.nanmedian(d[ref])                                      # zero on the reference ground, per pair
        nxt = los[-1] + d                                                 # NaN propagates: a broken chain stays unknown
        if k in breaks:
            nxt = np.full((n, n), np.nan)
            print(f"WARNING: no interferogram spans {dates[k - 1][1]} -> {dates[k][0]}. Passes after it are disconnected "
                  "from the ones before. Process the two halves as separate series, or add a spanning pair.")
        los.append(nxt)
    los = np.array(los)
    pass_days = np.array([(datetime.fromisoformat(d) - epoch0).days for d in pass_dates])
    rain = np.loadtxt(rain_csv, delimiter=",", skiprows=1, usecols=1)
    if len(rain) <= pass_days.max():
        raise SystemExit(f"rain.csv has {len(rain)} days but the last pass is day {pass_days.max()}")
    incidence_values = np.asarray([b["incidence_deg"] for b in budget], dtype=float)
    if not np.isfinite(incidence_values).any():
        raise ValueError("No usable incidenceAngle metadata was found in the selected GUNW files. SWELL will not assume a default 37° incidence angle; inspect the HDF5 product layout and supply the actual geometry.")
    inc = float(np.nanmean(incidence_values))
    if not 0.0 < inc < 90.0:
        raise ValueError(f"Invalid mean incidence angle {inc}; check the NISAR metadata before converting LOS to vertical motion.")
    from pyproj import Transformer as _T                                  # the box the radar window really covers (the frame may clip the requested box)
    _gx, _gy = np.asarray(grid["x"], float), np.asarray(grid["y"], float)
    _lon, _lat = _T.from_crs(grid["epsg"], 4326, always_xy=True).transform([_gx.min(), _gx.max(), _gx.min(), _gx.max()], [_gy.min(), _gy.min(), _gy.max(), _gy.max()])
    requested = list(bbox); bbox = [float(min(_lon)), float(min(_lat)), float(max(_lon)), float(max(_lat))]
    covered = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / max(1e-12, (requested[2] - requested[0]) * (requested[3] - requested[1]))
    if covered < 0.9:
        print(f"NOTE: the radar frame covers about {covered:.0%} of the requested box. The site is the covered part: {[round(v, 3) for v in bbox]}")
    if gps:                                                               # stations given by latitude / longitude (NGL) get their cell now
        from .gnss import to_cells
        gps = to_cells({k: v for k, v in gps.items() if k != "REFERENCE"}, bbox, n)
    out = dict(source="NASA NISAR GUNW (" + str(len(ids)) + " pairs, see out/provenance.json)", name=SITES[site]["name"], n=n,
               days=len(rain), rain=rain, w=ph.wetness(rain), lep=lep,
               paved=paved, pass_days=pass_days, los=los, coh=np.nan_to_num(coh, nan=0.0),
               coh_pairs=coh_pairs, inc_deg=inc, ref=ref, lep_low=lep_low, bbox=np.array(bbox), gps=json.dumps({k: v for k, v in gps.items() if k != "REFERENCE"}))
    pathlib.Path("out").mkdir(exist_ok=True)
    np.savez_compressed(f"out/{site}.npz", **out)
    print("scene-wide surface removed per pair (rms mm): " + ", ".join(f"{b['scene_surface_removed_rms_mm']:.1f}" for b in budget))
    json.dump(dict(site=site, bbox=bbox, requested_bbox=requested, scene_surface_filter=(f"per pair, a smooth surface (polynomial order {surface_order}) through {stable_n} reference (or mostly paved) cells is removed: atmosphere and orbit error. Any real motion of the reference ground is removed with it" if detrend and surface_order else "none (too few or too clustered reference cells): pairs are zeroed on the reference median only"), clay_layer=clay_layer, low_clay_threshold=lep_low, nisar_corrections=corr_summary, high_pass=hp_note, grid_epsg=grid["epsg"], pass_dates=pass_dates, chain_breaks=breaks, reference=ref_kind,
                   reference_cells=int(ref.sum()), valid_fraction_per_pass=[float(np.isfinite(l).mean()) for l in los],
                   rasters=[lep_info, pv_info], correction_budget=budget,
                   incidence_note="one mean incidence angle used; per-pixel angles are a TODO" if True else ""),
              open("out/provenance.json", "w"), indent=1)
    print(f"wrote out/{site}.npz ({len(pass_days)} passes, {int(ref.sum())} reference cells, "
          f"{np.isfinite(los).mean():.0%} valid). Next: python -m swell.validate --site out/{site}.npz")


def _all_datasets(f):
    names = []
    f.visititems(lambda name, obj: names.append("/" + name) if hasattr(obj, "shape") else None)
    return names


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("search"); a.add_argument("--site", required=True)
    a = sub.add_parser("inspect"); a.add_argument("--file", required=True)
    a = sub.add_parser("build"); a.add_argument("--site", required=True); a.add_argument("--gunw-dir", required=True)
    a.add_argument("--rain", required=True); a.add_argument("--lep", required=True); a.add_argument("--paved", required=True)
    a.add_argument("--gps", default=None); a.add_argument("--start-date", default=None)
    v = ap.parse_args()
    if v.cmd == "search": search(v.site)
    elif v.cmd == "inspect": inspect(v.file)
    else: build(v.site, v.gunw_dir, v.rain, v.lep, v.paved, v.gps, start_date=v.start_date)
