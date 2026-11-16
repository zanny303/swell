"""GNSS referee from the Nevada Geodetic Laboratory (NGL, University of Nevada Reno): free daily GPS positions, no login.

Test T1 in PREREGISTRATION.md compares NISAR with GPS in the radar line of sight. Until now it was "not run" because no GPS
file was supplied. This module finds every NGL station inside the site box, downloads its daily position series (.tenv3),
and writes the vertical component for the radar period. Station positions come from NGL's public station list.

tenv3 columns (NGL README_tenv3.txt): site, YYMMMDD, decimal year, MJD, GPS week, day, reference longitude,
east int, east frac, north int, north frac, up int, up frac, antenna height, sig e, sig n, sig u, corr en, corr eu, corr nu,
latitude, longitude, height. Metres. Up = column 12 + column 13.
"""
from __future__ import annotations

import datetime as dt
import re

LISTS = ["https://geodesy.unr.edu/NGLStationPages/DataHoldings.txt", "https://geodesy.unr.edu/NGLStationPages/llh.out"]
TENV3 = ["https://geodesy.unr.edu/gps_timeseries/IGS20/tenv3/IGS20/{s}.tenv3",
         "https://geodesy.unr.edu/gps_timeseries/tenv3/IGS20/{s}.tenv3",
         "https://geodesy.unr.edu/gps_timeseries/tenv3/IGS14/{s}.tenv3"]
MJD0 = dt.date(1858, 11, 17)
_NUM = re.compile(r"^-?\d+(\.\d+)?$")


def stations(text: str, bbox) -> dict:
    """{name: (lat, lon)} for stations inside bbox = west, south, east, north. Reads either NGL list format."""
    w, s, e, n = bbox; out = {}
    for line in text.splitlines():
        t = line.split()
        if len(t) < 3 or not re.fullmatch(r"[A-Z0-9]{4}", t[0]) or not (_NUM.match(t[1]) and _NUM.match(t[2])):
            continue
        lat, lon = float(t[1]), float(t[2])
        lon = lon - 360 if lon > 180 else lon
        if s <= lat <= n and w <= lon <= e:
            out[t[0]] = (lat, lon)
    return out


def parse_tenv3(text: str) -> list[tuple[dt.date, float]]:
    rows = []
    for line in text.splitlines():
        t = line.split()
        if len(t) < 13 or not _NUM.match(t[3]):
            continue
        try:
            day = MJD0 + dt.timedelta(days=int(float(t[3])))
            rows.append((day, (float(t[11]) + float(t[12])) * 1000.0))
        except ValueError:
            continue
    return rows


def fetch(bbox, epoch0: str, last: str, http, say=print, max_stations: int = 12, min_days: int = 20) -> dict:
    """Returns {station: dict(lat, lon, days, up_mm, source)}; days counted from epoch0. `http(url)` returns text."""
    text, err = None, []
    for u in LISTS:
        try:
            text = http(u); break
        except Exception as ex:
            err.append(f"{u}: {type(ex).__name__}")
    if text is None:
        raise RuntimeError("NGL station list not reachable (" + "; ".join(err) + ")")
    st = stations(text, bbox)
    say(f"gnss    {len(st)} NGL GPS stations inside the box" + (f": {', '.join(sorted(st)[:12])}" if st else ""))
    d0, d1 = dt.date.fromisoformat(epoch0), dt.date.fromisoformat(last)
    out = {}
    for name in sorted(st)[: max_stations * 3]:
        if len(out) >= max_stations:
            break
        rows = None
        for pat in TENV3:
            try:
                rows = parse_tenv3(http(pat.format(s=name)))
                if rows:
                    src = pat.format(s=name); break
            except Exception:
                continue
        if not rows:
            continue
        sel = [(d, u) for d, u in rows if d0 <= d <= d1 + dt.timedelta(days=3)]
        if len(sel) < min_days:
            continue
        lat, lon = st[name]
        out[name] = dict(lat=lat, lon=lon, days=[(d - d0).days for d, _ in sel], up_mm=[round(u, 2) for _, u in sel], source=src)
    say(f"gnss    {len(out)} stations have at least {min_days} daily positions in the radar period" + (f": {', '.join(out)}" if out else ""))
    return out


def to_cells(gps: dict, bbox, n: int) -> dict:
    """Give each station the grid cell it sits in (row 0 = north). Stations outside the covered box are dropped."""
    w, s, e, nn = bbox; out = {}
    for k, v in gps.items():
        if "cell" in v:
            out[k] = v; continue
        if not ("lat" in v and "lon" in v):
            continue
        i = int((nn - v["lat"]) / (nn - s) * n); j = int((v["lon"] - w) / (e - w) * n)
        if 0 <= i < n and 0 <= j < n:
            out[k] = dict(v, cell=[i, j])
    return out
