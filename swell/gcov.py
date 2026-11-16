"""NISAR radar brightness (L2 GCOV, HH and HV polarizations): the same satellite's own view of soil wetting.

Why: L-band backscatter rises when soil gets wetter (higher dielectric constant). HH responds mostly to the soil surface,
HV mostly to vegetation volume. So GCOV gives SWELL an independent NISAR observable of the very wetting that creates the
false signal in the phase. It is not used in the fit; it is a check and a change-detection map.

Layout (ASF NISAR cookbook): /science/LSAR/GCOV/grids/frequencyA/{HHHH,HVHV,xCoordinates,yCoordinates,projection},
values are real-valued backscatter covariance terms (linear power). The reader discovers the group by name.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import re
import urllib.parse

import numpy as np

SHORT_NAMES = [("NISAR_L2_GCOV_V1", "validated", 0), ("NISAR_L2_GCOV_PROVISIONAL_V1", "provisional", 1), ("NISAR_L2_GCOV_BETA_V1", "beta", 2)]
NAME_RE = re.compile(r"NISAR_L2_[A-Z]{2}_GCOV_\d+_(\d+)_([AD])_(\d+)_")
DATE_RE = re.compile(r"_(\d{8})T\d{6}")


def _names(f):
    out = []
    f.visititems(lambda k, o: out.append("/" + k) if hasattr(o, "shape") else None)
    return out


def layout(f) -> dict:
    names = _names(f)
    hh = sorted([k for k in names if k.endswith("/HHHH") and "GCOV" in k], key=lambda k: ("frequencyA" not in k, k))
    vv = sorted([k for k in names if k.endswith("/VVVV") and "GCOV" in k], key=lambda k: ("frequencyA" not in k, k))
    co = (hh or vv)
    if not co:
        raise RuntimeError("no HHHH or VVVV backscatter layer in this GCOV file")
    grp = co[0].rsplit("/", 1)[0]
    cross = [k for k in names if k.startswith(grp + "/") and k.rsplit("/", 1)[-1] in ("HVHV", "VHVH")]
    find = lambda leaf: next((k for k in names if k == f"{grp}/{leaf}"), None)
    return dict(co=co[0], cross=cross[0] if cross else None, x=find("xCoordinates"), y=find("yCoordinates"), epsg=find("projection"),
                co_pol=co[0].rsplit("/", 1)[-1][:2], cross_pol=cross[0].rsplit("/", 1)[-1][:2] if cross else None)


def _block(a, n):
    H, W = a.shape
    if H < n or W < n:
        raise ValueError("site window smaller than the grid")
    a = a[: H // n * n, : W // n * n].reshape(n, H // n, n, W // n)
    frac = np.isfinite(a).mean(axis=(1, 3))
    with np.errstate(all="ignore"):
        m = np.nanmean(a, axis=(1, 3))
    return np.where(frac >= 0.3, m, np.nan)


def window(f, bbox, n: int) -> dict:
    """Mean backscatter per grid cell (linear power), row 0 = north, column 0 = west."""
    from pyproj import Transformer
    L = layout(f); x = f[L["x"]][:]; y = f[L["y"]][:]; epsg = int(np.array(f[L["epsg"]]))
    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    (x0, x1), (y0, y1) = tr.transform([bbox[0], bbox[2]], [bbox[1], bbox[3]])
    j = np.where((x >= min(x0, x1)) & (x <= max(x0, x1)))[0]; i = np.where((y >= min(y0, y1)) & (y <= max(y0, y1)))[0]
    if len(i) < n or len(j) < n:
        raise ValueError("this GCOV frame does not cover the site box")
    si, sj = slice(i.min(), i.max() + 1), slice(j.min(), j.max() + 1)
    out = {}
    for key in ("co", "cross"):
        if not L[key]:
            continue
        a = f[L[key]][si, sj].astype("f4")
        a[~np.isfinite(a) | (a <= 0)] = np.nan
        if y[si][0] < y[si][-1]:
            a = a[::-1]
        if x[sj][0] > x[sj][-1]:
            a = a[:, ::-1]
        out[key] = _block(a, n)
    out["pols"] = (L["co_pol"], L["cross_pol"])
    return out


def db(a):
    with np.errstate(all="ignore"):
        return 10 * np.log10(a)


def find_granules(ea, bbox, start: str, end: str, track=None) -> list[dict]:
    rows = []
    for sn, maturity, rank in SHORT_NAMES:
        try:
            res = ea.search_data(short_name=sn, bounding_box=tuple(bbox), temporal=(start, end), count=400)
        except Exception:
            continue
        for r in res:
            url = next((u for u in r.data_links() if str(u).endswith(".h5")), None)
            if not url:
                continue
            name = pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name
            m = NAME_RE.search(name); d = DATE_RE.search(name)
            if not d:
                continue
            rows.append(dict(name=name, url=url, rank=rank, maturity=maturity, date=f"{d.group(1)[:4]}-{d.group(1)[4:6]}-{d.group(1)[6:]}",
                             track=int(m.group(1)) if m else None, direction=m.group(2) if m else None))
    if track is not None and any(r["track"] == track for r in rows):
        rows = [r for r in rows if r["track"] == track]                     # same geometry as the phase pairs
    best = {}
    for r in sorted(rows, key=lambda r: r["rank"]):
        best.setdefault(r["date"], r)
    return [best[k] for k in sorted(best)]


def summarise(web: dict, epoch0: str, grids: list[tuple[str, dict]]) -> dict:
    """Change maps relative to the first date, and a check against the wetness index on open ground."""
    from scipy.stats import spearmanr
    dates = [d for d, _ in grids]; days = [(dt.date.fromisoformat(d) - dt.date.fromisoformat(epoch0)).days for d in dates]
    co = np.array([db(g["co"]) for _, g in grids]); cr = np.array([db(g["cross"]) if "cross" in g else np.full(co[0].shape, np.nan) for _, g in grids])
    dco = co - co[0]; dcr = cr - cr[0]
    pv = np.array(web["paved"], float); openg = np.isfinite(pv) & (pv < 0.3)
    w = np.array(web["wetness"], float)
    ser = [float(np.nanmedian(c[openg])) if openg.any() else float("nan") for c in co]
    wi = [float(w[min(max(d, 0), len(w) - 1)]) for d in days]
    ok = np.isfinite(ser)
    rho = float(spearmanr(np.array(ser)[ok], np.array(wi)[ok]).statistic) if ok.sum() >= 5 else float("nan")
    # does the phase artifact SWELL removed line up with the brightness change on the same ground?
    art_rho = float("nan")
    try:
        pdays = list(web["pass_days"]); art = web["artifact"]; a_s, b_s = [], []
        for k, d in enumerate(days):
            if d in pdays:
                p = pdays.index(d); A = np.array([[np.nan if v is None else v for v in r] for r in art[p]], float)
                m = openg & np.isfinite(A) & np.isfinite(dco[k])
                if m.sum() > 30:
                    a_s.append(float(np.nanmedian(A[m]))); b_s.append(float(np.nanmedian(dco[k][m])))
        if len(a_s) >= 5:
            art_rho = float(spearmanr(a_s, b_s).statistic)
    except Exception:
        pass
    r1 = lambda a: [[None if not np.isfinite(v) else round(float(v), 2) for v in row] for row in a]
    pol_co, pol_cr = grids[0][1]["pols"]
    finding = (f"NISAR {pol_co} brightness over open ground and SWELL's wetness index have rank correlation {rho:.2f} over {int(ok.sum())} dates"
               if np.isfinite(rho) else f"NISAR {pol_co} brightness maps made for {len(dates)} dates; too few dates for a correlation")
    if np.isfinite(art_rho):
        finding += f"; the phase artifact SWELL removed and the brightness change agree with rank correlation {art_rho:.2f}"
    return dict(dates=dates, days=days, pols=[pol_co, pol_cr], open_ground_db=[round(v, 2) for v in ser],
                wetness_vs_brightness=rho, artifact_vs_brightness=art_rho,
                d_co_db=[r1(a) for a in dco], d_cross_db=[r1(a) for a in dcr], finding=finding + ". GCOV is not used in the fit.")


def run(ea, fs, web: dict, bbox, epoch0: str, last: str, say, track=None, cap: int = 12) -> dict:
    import h5py
    start = (dt.date.fromisoformat(epoch0) - dt.timedelta(days=2)).isoformat(); end = (dt.date.fromisoformat(last) + dt.timedelta(days=2)).isoformat()
    gr = find_granules(ea, bbox, start, end, track)
    say(f"gcov    {len(gr)} NISAR GCOV dates over the box" + (f" (track {track})" if track is not None else "") + (f", reading {cap}" if len(gr) > cap else ""))
    if len(gr) < 2:
        raise RuntimeError("fewer than 2 NISAR GCOV dates over this box")
    grids, fails = [], 0
    for k, g in enumerate(gr[:cap], 1):
        try:
            try: fo = fs.open(g["url"], cache_type="background", block_size=8 * 2 ** 20)
            except Exception: fo = fs.open(g["url"], block_size=8 * 2 ** 20)
            with fo, h5py.File(fo, "r") as f:
                grids.append((g["date"], window(f, bbox, web["n"])))
            say(f"gcov    {k}/{min(cap, len(gr))} {g['date']} read")
        except Exception as ex:
            fails += 1; say(f"gcov    {g['date']} not read ({type(ex).__name__}: {str(ex)[:150]})")
            if fails >= 4 and not grids:
                raise
    if len(grids) < 2:
        raise RuntimeError("fewer than 2 GCOV dates could be read")
    return summarise(web, epoch0, grids)
