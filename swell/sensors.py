"""Other satellites as evidence for (or against) the NISAR twin. Every source is optional: it either adds a finding or
reports "not run" with the reason. Nothing here can stop or alter the twin itself.

    GPM IMERG (daily, late run)      measured rain            -> does the rain record that drives the twin agree with it?
    SMAP L3 enhanced (9 km)          measured soil moisture   -> does SWELL's wetness index follow real soil moisture?
    OPERA DISP-S1 (Sentinel-1, 30 m) C-band ground motion     -> independent referee: is NISAR closer to it after the correction?
    HLS Landsat 30 m                 vegetation (NDVI)        -> is the false radar signal larger where vegetation is denser?
    OPERA DSWx-HLS                   open water               -> which cells are water, where radar motion means nothing?

Each reader takes an open HDF5 / GeoTIFF and returns numbers for the site window, so it can be tested offline with small
files in the real layouts. File layouts follow the products' public documentation; they have not yet been exercised
against the live archives, which is why every step is wrapped and logged.
"""
from __future__ import annotations

import datetime as dt
import re

import numpy as np

S1_INCIDENCE_DEG = 39.0     # mid-swath Sentinel-1 IW value, used only to compare vertical-equivalent motion. Stated assumption.


# ------------------------------------------------------------------ pure readers (offline-testable)
def imerg_window(f, bbox) -> float:
    """Mean daily rain (mm) over the box from a GPM IMERG daily file (variable `precipitation`, dims time, lon, lat)."""
    w, s, e, n = bbox; lon, lat = np.asarray(f["lon"]), np.asarray(f["lat"])
    j = np.flatnonzero((lon >= w - .05) & (lon <= e + .05)); i = np.flatnonzero((lat >= s - .05) & (lat <= n + .05))
    if not len(i) or not len(j): raise ValueError("box outside the IMERG grid")
    d = f["precipitation"]; a = np.asarray(d[0, j[0]:j[-1] + 1, i[0]:i[-1] + 1] if d.ndim == 3 else d[j[0]:j[-1] + 1, i[0]:i[-1] + 1], float)
    a[a < 0] = np.nan
    return float(np.nanmean(a))


def smap_window(f, bbox) -> float:
    """Mean volumetric soil moisture (m3/m3) over the box from SMAP SPL3SMP_E, morning and evening passes combined."""
    w, s, e, n = bbox; vals = []
    for grp, suf in (("Soil_Moisture_Retrieval_Data_AM", ""), ("Soil_Moisture_Retrieval_Data_PM", "_pm")):
        if grp not in f: continue
        g = f[grp]; lat = np.asarray(g["latitude" + suf], float); lon = np.asarray(g["longitude" + suf], float)
        lat[lat < -90] = np.nan; lon[lon < -180] = np.nan
        with np.errstate(all="ignore"):
            rl, cl = np.nanmax(lat, 1), np.nanmax(lon, 0)                 # global EASE-Grid 2: latitude by row, longitude by column
        i = np.flatnonzero((rl >= s - .1) & (rl <= n + .1)); j = np.flatnonzero((cl >= w - .1) & (cl <= e + .1))
        if not len(i) or not len(j): continue
        a = np.asarray(g["soil_moisture" + suf][i[0]:i[-1] + 1, j[0]:j[-1] + 1], float); a[(a < 0) | (a > 1)] = np.nan
        if np.isfinite(a).any(): vals.append(float(np.nanmean(a)))
    if not vals: raise ValueError("no valid SMAP retrieval over the box on this day")
    return float(np.mean(vals))


def disp_dates(name: str):
    m = re.search(r"_(\d{8})T\d{6}Z_(\d{8})T\d{6}Z_", name)
    if not m: return None
    iso = lambda d: f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return iso(m.group(1)), iso(m.group(2))


def disp_window(f, bbox, n: int) -> np.ndarray:
    """OPERA DISP-S1 line-of-sight displacement (mm, positive toward the satellite) on an n x n lat/lon grid over the box."""
    from pyproj import CRS, Transformer
    x, y = np.asarray(f["x"], float), np.asarray(f["y"], float)
    wkt = f["spatial_ref"].attrs.get("crs_wkt") or f["spatial_ref"].attrs.get("spatial_ref")
    crs = CRS.from_wkt(wkt.decode() if isinstance(wkt, bytes) else wkt)
    w, s, e, nn = bbox; tr = Transformer.from_crs(4326, crs, always_xy=True)
    lon = w + (np.arange(n) + .5) * (e - w) / n; lat = nn - (np.arange(n) + .5) * (nn - s) / n
    X, Y = tr.transform(*np.meshgrid(lon, lat)); xe, ye = tr.transform([w, e, w, e], [s, s, nn, nn])
    j = np.flatnonzero((x >= min(xe)) & (x <= max(xe))); i = np.flatnonzero((y >= min(ye)) & (y <= max(ye)))
    if len(i) < 2 or len(j) < 2: raise ValueError("box outside this Sentinel-1 frame")
    si, sj = slice(i.min(), i.max() + 1), slice(j.min(), j.max() + 1)
    d = np.asarray(f["displacement"][..., si, sj], float).reshape(si.stop - si.start, sj.stop - sj.start) * 1000.0
    if "recommended_mask" in f:
        d[np.asarray(f["recommended_mask"][..., si, sj]).reshape(d.shape) != 1] = np.nan
    xs, ys = x[sj], y[si]; dx, dy = abs(xs[1] - xs[0]), abs(ys[1] - ys[0]); cell = (e - w) / n * 111_320 * np.cos(np.radians((s + nn) / 2))
    r = max(1, int(cell / (2 * dx)))                                       # average the 30 m pixels that fall in each SWELL cell
    cj = np.clip(np.round((X - xs[0]) / (xs[1] - xs[0])).astype(int), 0, len(xs) - 1); ci = np.clip(np.round((Y - ys[0]) / (ys[1] - ys[0])).astype(int), 0, len(ys) - 1)
    out = np.full((n, n), np.nan)
    for a in range(n):
        for b in range(n):
            blk = d[max(ci[a, b] - r, 0):ci[a, b] + r + 1, max(cj[a, b] - r, 0):cj[a, b] + r + 1]
            if np.isfinite(blk).mean() >= 0.3: out[a, b] = np.nanmean(blk)
    return out


def chain_disp(items: list[tuple[str, str, np.ndarray]]) -> dict:
    """items: (reference date, secondary date, displacement since the reference). Returns cumulative maps by date.
    The reference date jumps every few acquisitions; each file is added to the cumulative map of its own reference date."""
    cum = {}
    for ref, sec, d in sorted(items, key=lambda t: (t[1], t[0])):
        if not cum: cum[ref] = np.zeros_like(d)
        if ref not in cum:
            prev = [k for k in cum if k <= ref]
            if not prev: continue
            cum[ref] = cum[max(prev)]                                      # nearest earlier date stands in for a missing link
        cum[sec] = cum[ref] + d
    return cum


def cross_sensor(web: dict, cum: dict, epoch0: str) -> dict:
    """Is NISAR closer to Sentinel-1 after SWELL's correction? Vertical-equivalent, same reference ground, same dates."""
    n = web["n"]; pd = np.array(web["pass_days"]); ref = np.array(web["reference"], bool); inc = np.radians(web["inc_deg"])
    days = np.array([(dt.date.fromisoformat(k) - dt.date.fromisoformat(epoch0)).days for k in sorted(cum)]); maps = np.array([cum[k] for k in sorted(cum)])
    keep = (pd >= days.min()) & (pd <= days.max())
    if keep.sum() < 3: return dict(status="not run", reason=f"only {int(keep.sum())} NISAR passes fall inside the Sentinel-1 record")
    s1 = np.empty((len(pd), n, n))
    for a in range(n):
        for b in range(n):
            v = np.isfinite(maps[:, a, b]); s1[:, a, b] = np.interp(pd, days[v], maps[v, a, b]) if v.sum() >= 3 else np.nan
    s1 = s1 / np.cos(np.radians(S1_INCIDENCE_DEG))
    if ref.any(): s1 = s1 - np.nanmedian(s1[:, ref], axis=1)[:, None, None]
    k0 = int(np.flatnonzero(keep)[0]); s1 = s1 - s1[k0]
    arr = lambda key: np.array([[[np.nan if v is None else v for v in r] for r in m] for m in web[key]], float)
    naive = arr("observed_los") / np.cos(inc); swell = arr("inferred_motion"); naive, swell = naive - naive[k0], swell - swell[k0]
    clay = ~ref & ~np.array(web["control"], bool) & ~(np.array(web["unresolved"]) == 1)
    sel = keep[:, None, None] & clay[None] & np.isfinite(s1) & np.isfinite(naive) & np.isfinite(swell); sel[k0] = False
    if sel.sum() < 100: return dict(status="not run", reason="too few cells where both radars are valid")
    r0 = float(np.sqrt(np.mean((naive[sel] - s1[sel]) ** 2))); r1 = float(np.sqrt(np.mean((swell[sel] - s1[sel]) ** 2)))
    return dict(status="ok", name="T1b Cross-sensor referee (Sentinel-1)", rms_naive_mm=r0, rms_swell_mm=r1, n=int(sel.sum()), passes=int(keep.sum()) - 1,
                passed=bool(r1 < r0), frame="vertical-equivalent; Sentinel-1 incidence assumed 39 deg; both zeroed on SWELL's reference ground",
                finding=f"Against Sentinel-1, NISAR differs by {r0:.1f} mm before the soil-moisture correction and {r1:.1f} mm after ({sel.sum()} cell-dates).")


# ------------------------------------------------------------------ online fetchers (window reads; need Earthdata login)
def _open(fs, url):
    try: return fs.open(url, cache_type="background", block_size=8 * 2 ** 20)
    except Exception: return fs.open(url, block_size=8 * 2 ** 20)


def _h5_links(g):
    return [u for u in g.data_links() if re.search(r"\.(h5|nc4?|HDF5)$", u)]


def _granule_date(g) -> str:
    return str(g["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"])[:10]


def series(ea, fs, short_name, version, bbox, start, end, reader, say, cap=120, label=""):
    """Daily series over the box from one-file-per-day products. Returns {date: value}."""
    import h5py
    kw = dict(short_name=short_name, temporal=(start, end), count=2000)
    if version: kw["version"] = version
    gr = sorted(ea.search_data(**kw), key=_granule_date)
    say(f"{label:7s} {short_name}: {len(gr)} daily files found" + (f", reading the latest {cap}" if len(gr) > cap else ""))
    out, fails = {}, 0
    for k, g in enumerate(gr[-cap:], 1):
        links = _h5_links(g)
        if not links: continue
        try:
            with _open(fs, links[0]) as fo, h5py.File(fo, "r") as f:
                out[_granule_date(g)] = reader(f, bbox)
        except Exception as ex:
            fails += 1
            if fails == 1: say(f"{label:7s} first failure: {type(ex).__name__}: {str(ex)[:200]}")
            if fails >= 8 and len(out) == 0: raise RuntimeError(f"{short_name}: the first {fails} files could not be read ({type(ex).__name__}: {str(ex)[:150]})")
        if k % 20 == 0: say(f"{label:7s} {k} files read")
    return out


def disp_s1(ea, fs, bbox, n, start, end, say, cap=36):
    import h5py
    gr = ea.search_data(short_name="OPERA_L3_DISP-S1_V1", bounding_box=tuple(bbox), temporal=(start, end), count=2000)
    by = {}
    for g in gr:
        links = _h5_links(g)
        if not links: continue
        name = links[0].rsplit("/", 1)[1]; d = disp_dates(name); fr = re.search(r"_(F\d+)_", name)
        if d and fr: by.setdefault(fr.group(1), {})[d] = links[0]            # newest listing wins for a repeated pair
    if not by: raise RuntimeError("no Sentinel-1 displacement products over this box (coverage is North America)")
    frame = max(by, key=lambda k: len(by[k])); pairs = sorted(by[frame].items(), key=lambda t: t[0][1])[-cap:]
    say(f"sentinel OPERA DISP-S1: frame {frame}, {len(by[frame])} dates, reading {len(pairs)}")
    items = []
    for k, ((ref, sec), url) in enumerate(pairs, 1):
        try:
            with _open(fs, url) as fo, h5py.File(fo, "r") as f:
                items.append((ref, sec, disp_window(f, bbox, n)))
        except Exception as ex:
            if not items and k >= 4: raise RuntimeError(f"DISP-S1 files could not be read ({type(ex).__name__}: {str(ex)[:150]})")
        if k % 10 == 0: say(f"sentinel {k} files read")
    return chain_disp(items), frame


def _cog_to_grid(ea, url, bbox, n, resampling="average"):
    """Read a whole (small) cloud GeoTIFF band and warp it onto the n x n lat/lon grid. Returns float array with NaN nodata."""
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject
    w, s, e, nn = bbox; dst = np.full((n, n), np.nan, "float32")
    with ea.open([url])[0] as fo, MemoryFile(fo.read()) as mem, mem.open() as src:
        a = src.read(1).astype("float32"); nod = src.nodata
        if nod is not None: a[a == nod] = np.nan
        reproject(a, dst, src_transform=src.transform, src_crs=src.crs, src_nodata=np.nan, dst_transform=from_origin(w, nn, (e - w) / n, (nn - s) / n),
                  dst_crs="EPSG:4326", dst_nodata=np.nan, resampling=getattr(Resampling, resampling))
    return dst


def landsat_ndvi(ea, bbox, n, end, say):
    start = (dt.date.fromisoformat(end) - dt.timedelta(days=75)).isoformat()
    gr = ea.search_data(short_name="HLSL30", bounding_box=tuple(bbox), temporal=(start, end), cloud_cover=(0, 15), count=40)
    if not gr: raise RuntimeError("no Landsat scene under 15 % cloud in the last 75 days")
    gr = sorted(gr, key=_granule_date, reverse=True); acc, used = [], []
    for g in gr[:6]:
        L = g.data_links(); red = next((u for u in L if u.endswith("B04.tif")), None); nir = next((u for u in L if u.endswith("B05.tif")), None)
        if not red or not nir: continue
        r, q = _cog_to_grid(ea, red, bbox, n), _cog_to_grid(ea, nir, bbox, n)
        r[r <= -9000] = np.nan; q[q <= -9000] = np.nan
        with np.errstate(all="ignore"): nd = (q - r) / (q + r)
        nd[(nd < -1) | (nd > 1)] = np.nan
        if np.isfinite(nd).mean() > 0.05: acc.append(nd); used.append(_granule_date(g))
        if acc and np.isfinite(np.nanmean(acc, 0)).mean() > 0.9: break
    if not acc: raise RuntimeError("Landsat scenes found but none covered the box with clear pixels")
    with np.errstate(all="ignore"): nd = np.nanmean(acc, 0)
    say(f"landsat HLS Landsat 30 m: NDVI from {len(acc)} scene(s) {used}, covers {np.isfinite(nd).mean():.0%} of the box")
    return nd, used


def opera_water(ea, bbox, n, end, say):
    start = (dt.date.fromisoformat(end) - dt.timedelta(days=45)).isoformat()
    gr = sorted(ea.search_data(short_name="OPERA_L3_DSWX-HLS_V1", bounding_box=tuple(bbox), temporal=(start, end), count=60), key=_granule_date, reverse=True)
    if not gr: raise RuntimeError("no OPERA surface-water product over this box in the last 45 days")
    acc, used = [], []
    for g in gr[:6]:
        u = next((x for x in g.data_links() if x.endswith("_B01_WTR.tif")), None)
        if not u: continue
        import rasterio  # noqa: F401  (ensures a clear error if missing)
        a = _cog_to_grid(ea, u, bbox, n, "nearest"); wat = np.where(np.isin(a, (1, 2)), 1.0, np.where(a == 0, 0.0, np.nan))   # 1 open water, 2 partial; 0 not water
        if np.isfinite(wat).mean() > 0.05: acc.append(wat); used.append(_granule_date(g))
    if not acc: raise RuntimeError("water products found but none covered the box with clear pixels")
    with np.errstate(all="ignore"): wf = np.nanmax(acc, 0)
    say(f"water   OPERA DSWx-HLS: {int(np.nansum(wf))} of {n * n} cells had open water in {len(acc)} recent scene(s)")
    return wf, used


def run_all(web: dict, bbox, epoch0: str, last: str, power_rain: list, login, say, track=None) -> dict:
    """Runs every sensor, never raises. Returns the `sensors` block and (if it ran) the cross-sensor test row."""
    from scipy.stats import spearmanr
    out, test = {}, None; n = web["n"]; day = lambda k: (dt.date.fromisoformat(k) - dt.date.fromisoformat(epoch0)).days

    def step(key, name, fn):
        try: out[key] = dict(name=name, status="ok", **fn())
        except Exception as ex:
            out[key] = dict(name=name, status="not run", reason=f"{type(ex).__name__}: {str(ex)[:220]}"); say(f"{key:8s} not run: {out[key]['reason']}")
    try:
        ea = login(); fs = ea.get_fsspec_https_session()
    except Exception as ex:
        return dict(all=dict(name="Other satellites", status="not run", reason=str(ex)[:200])), None

    def gpm():
        d = series(ea, fs, "GPM_3IMERGDL", "07", bbox, epoch0, last, imerg_window, say, 120, "gpm")
        ks = [k for k in d if 0 <= day(k) < len(power_rain)]; a = np.array([d[k] for k in ks]); b = np.array([power_rain[day(k)] for k in ks])
        if len(ks) < 15: raise RuntimeError(f"only {len(ks)} days read")
        r = float(np.corrcoef(a, b)[0, 1])
        return dict(days=len(ks), total_mm=float(a.sum()), driver_total_mm=float(b.sum()), correlation=r, series={k: round(d[k], 2) for k in ks},
                    finding=f"GPM measured {a.sum():.0f} mm over {len(ks)} days; the rain record driving the twin has {b.sum():.0f} mm (daily correlation {r:.2f}).")

    def smap():
        d = series(ea, fs, "SPL3SMP_E", "006", bbox, epoch0, last, smap_window, say, 90, "smap")
        ks = [k for k in d if 0 <= day(k) < len(web["wetness"])]
        if len(ks) < 15: raise RuntimeError(f"only {len(ks)} days with a valid retrieval")
        a = np.array([d[k] for k in ks]); b = np.array([web["wetness"][day(k)] for k in ks]); rho = float(spearmanr(a, b).statistic)
        return dict(days=len(ks), spearman=rho, mean_m3m3=float(a.mean()), series={k: round(d[k], 3) for k in ks},
                    finding=f"SMAP soil moisture and SWELL's wetness index move together with rank correlation {rho:.2f} over {len(ks)} days. SMAP was not used in the fit.")

    def s1():
        nonlocal test
        start = (dt.date.fromisoformat(epoch0) - dt.timedelta(days=40)).isoformat()
        cum, frame = disp_s1(ea, fs, bbox, n, start, last, say); res = cross_sensor(web, cum, epoch0)
        if res["status"] != "ok": raise RuntimeError(res["reason"])
        test = {k: res[k] for k in ("name", "rms_naive_mm", "rms_swell_mm", "n", "passes", "passed", "frame")}
        return dict(frame=frame, dates=len(cum), **{k: res[k] for k in ("rms_naive_mm", "rms_swell_mm", "n", "passed", "finding")})

    def ndvi():
        nd, used = landsat_ndvi(ea, bbox, n, last, say); k = len(web["artifact"]) - 1
        art = np.array([[np.nan if v is None else abs(v) for v in r] for r in web["artifact"][k]], float); pv = np.array(web["paved"])
        v = np.isfinite(nd) & np.isfinite(art) & (pv < 0.5); rho = float(spearmanr(nd[v], art[v]).statistic) if v.sum() > 30 else float("nan")
        return dict(scenes=used, grid=[[None if not np.isfinite(x) else round(float(x), 3) for x in r] for r in nd], artifact_vs_ndvi=rho,
                    finding=(f"On open ground the false radar signal and Landsat greenness have rank correlation {rho:.2f} ({int(v.sum())} cells)." if np.isfinite(rho) else "Vegetation map made; too few open cells to compare with the false signal."))

    def water():
        wf, used = opera_water(ea, bbox, n, last, say); un = np.array(web["unresolved"]) == 1; wet = np.nan_to_num(wf) > 0
        return dict(scenes=used, grid=[[None if not np.isfinite(x) else int(x) for x in r] for r in wf], water_cells=int(wet.sum()), unresolved_that_are_water=int((wet & un).sum()),
                    finding=f"{int(wet.sum())} cells held open water recently; {int((wet & un).sum())} of the {int(un.sum())} cells the twin refuses are water.")
    def gcov_():
        from . import gcov
        return gcov.run(ea, fs, web, web.get("bbox", bbox), epoch0, last, say, track=track)
    for key, name, fn in (("gcov", "NISAR radar brightness, HH and HV (GCOV)", gcov_), ("gpm", "GPM IMERG rainfall", gpm), ("smap", "SMAP soil moisture", smap), ("sentinel1", "Sentinel-1 ground motion (OPERA DISP-S1)", s1),
                          ("landsat", "Landsat vegetation (HLS)", ndvi), ("water", "Open water (OPERA DSWx)", water)):
        say(f"{key:8s} starting"); step(key, name, fn)
    return out, test
