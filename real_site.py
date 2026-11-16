"""Build the SWELL clay twin for a real place from real data. One command, no synthetic inputs.

    python real_site.py --site dallas --check        # 1 minute: what real data exists? nothing large is downloaded
    python real_site.py --site dallas                # downloads NISAR pairs (asks first), builds and validates the twin
    python real_site.py --bbox -97.05 32.60 -96.55 33.00 --name "My place"

What it fetches
    radar      NASA NISAR L2 GUNW pairs from the Alaska Satellite Facility   (needs your free Earthdata login)
    rain       NASA POWER daily precipitation at the site centre             (no login)
    clay       ISRIC SoilGrids clay content, 30-60 cm, 250 m                 (no login)
    paving     ESA WorldCover 2021 built-up class, 10 m                      (no login)
Then it runs swell.ingest.build and swell.validate, which write site/data/site.json. Restart run_swell.py and the
Decision Studio opens on the real site.

Honest limits, printed again in out/provenance.json
    - The clay layer is clay CONTENT, not a shrink-swell rating. "Low-clay" ground is the lowest quarter of the site.
    - No GPS is fetched, so test T1 (GPS referee) is reported as "not run".
    - Nothing here was run against the live servers when it was written. Every step prints what it got; if a step
      fails, send the file out/real_site_log.txt and it can be fixed from that.
Credentials: Earthdata login is read from ~/.netrc, or EARTHDATA_USERNAME / EARTHDATA_PASSWORD, or EARTHDATA_TOKEN
(also from a local .env file). They are never printed or written anywhere.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys
import traceback
import urllib.parse
import urllib.request

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "out"
LOG = []


def say(*a):
    line = " ".join(str(x) for x in a); print(line, flush=True); LOG.append(line)


def load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", line)
            if m and m.group(1) not in os.environ:
                os.environ[m.group(1)] = m.group(2).strip().strip('"').strip("'")


def http(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "SWELL-SpaceApps/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------------------------------------------------------------- radar: find a chain of NISAR GUNW pairs
def pair_dates(name: str):
    """Reference and secondary acquisition dates from an official NISAR GUNW file name."""
    tk = re.findall(r"(\d{8})T\d{6}", name)
    if len(tk) < 3:
        return None
    iso = lambda d: f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return iso(tk[0]), iso(tk[2])


def choose_chain(rows: list[dict], max_pairs: int) -> list[dict]:
    """Return the best consecutive GUNW chain without crossing processing maturity.

    VALIDATED, PROVISIONAL and BETA are separate scientific processing streams. A time series
    must not silently splice them together. Prefer the longest chain; on ties prefer the more
    mature collection, then the most recent end date.
    """
    if int(max_pairs) < 1:
        raise ValueError("max_pairs must be at least 1")
    groups = {}
    for row in rows:
        d = pair_dates(row["name"])
        if not d or not str(row.get("url", "")).endswith(".h5"):
            continue
        r = dict(row, ref=d[0], sec=d[1], span=(dt.date.fromisoformat(d[1]) - dt.date.fromisoformat(d[0])).days)
        if r["span"] > 0:
            maturity = str(r.get("maturity", "unknown")).lower()
            groups.setdefault((r.get("track"), r.get("frame"), maturity), []).append(r)
    best, best_score = [], None
    maturity_rank = {"validated": 0, "provisional": 1, "beta": 2, "unknown": 3}
    for key, group in groups.items():
        by_ref = {}
        for r in sorted(group, key=lambda x: (x["ref"], x["span"], str(x.get("updated", "")), x["name"])):
            cur = by_ref.get(r["ref"])
            # Shortest temporal baseline first; if equal, prefer latest processing timestamp/name.
            if cur is None or r["span"] < cur["span"] or (r["span"] == cur["span"] and
                    (str(r.get("updated", "")), r["name"]) > (str(cur.get("updated", "")), cur["name"])):
                by_ref[r["ref"]] = r
        seq = [by_ref[k] for k in sorted(by_ref)]
        chain = [seq[-1]] if seq else []
        for r in reversed(seq[:-1]):
            if r["sec"] == chain[0]["ref"]:
                chain.insert(0, r)
            else:
                break
        chain = chain[-int(max_pairs):]
        if not chain:
            continue
        cover = min(float(r.get("cover", 0.5)) for r in chain)             # a frame that only clips the box is worth less than one that spans it
        score = (cover >= 0.99, len(chain) >= 4, round(cover, 1), len(chain), -maturity_rank.get(key[2], 3), chain[-1]["sec"])
        if best_score is None or score > best_score:
            best, best_score = chain, score
    return best


SHORT_NAMES = [("NISAR_L2_GUNW_V1", "validated", 0), ("NISAR_L2_GUNW_PROVISIONAL_V1", "provisional", 1), ("NISAR_L2_GUNW_BETA_V1", "beta", 2)]
NAME_RE = re.compile(r"NISAR_L2_[A-Z]{2}_GUNW_(\d+)_(\d+)_([AD])_(\d+)_")


def _row(name, url, size, maturity="unknown", rank=3, track=None, frame=None):
    m = NAME_RE.match(name)
    return dict(name=name, url=url, bytes=int(size or 0), maturity=maturity, rank=rank,
                track=track if track is not None else (m.group(2) + m.group(3) if m else None), frame=frame if frame is not None else (m.group(4) if m else None))


def _cover(granule, bbox) -> float:
    """Share of the site box (4 corners, 4 edge mid-points, centre) inside the granule footprint. 0.5 if the footprint is unknown."""
    try:
        polys = granule["umm"]["SpatialExtent"]["HorizontalSpatialDomain"]["Geometry"]["GPolygons"]
        w, s, e, n = bbox; pts = [(x, y) for x in (w, (w + e) / 2, e) for y in (s, (s + n) / 2, n)]; hit = 0
        for px, py in pts:
            inside = False
            for g in polys:
                ring = [(float(q["Longitude"]), float(q["Latitude"])) for q in g["Boundary"]["Points"]]; c = False
                for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                    if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1) + x1: c = not c
                inside = inside or c
            hit += inside
        return hit / len(pts)
    except Exception:
        return 0.5


def search_nisar(bbox):
    """Catalog search needs no login. Short names are the ones in the ASF NISAR documentation."""
    rows, errors = [], []
    try:
        import earthaccess
        for sn, maturity, rank in SHORT_NAMES:
            try:
                res = earthaccess.search_data(short_name=sn, bounding_box=tuple(bbox), temporal=("2025-08-01", dt.date.today().isoformat()), count=600)
            except Exception as ex:
                errors.append(f"{sn}: {type(ex).__name__}: {str(ex)[:120]}"); continue
            for r in res:
                url = next((u for u in r.data_links() if str(u).endswith(".h5")), None)
                if url:
                    try: size = float(r.size()) * 1e6
                    except Exception: size = 0
                    row = _row(pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name, url, size, maturity, rank)
                    row["short_name"] = sn; row["cover"] = _cover(r, bbox)
                    row["updated"] = str(getattr(r, "updated", "") or "")
                    rows.append(row)
            say(f"radar   {sn}: {len(res)} products over this box")
    except ImportError:
        errors.append("earthaccess is not installed (python -m pip install earthaccess)")
    if not rows:                                                           # last resort: NASA's public catalog, no extra packages
        try:
            for sn, maturity, rank in SHORT_NAMES:
                q = urllib.parse.urlencode(dict(short_name=sn, bounding_box=",".join(str(v) for v in bbox), temporal="2025-08-01T00:00:00Z,", page_size=600))
                for g in json.loads(http("https://cmr.earthdata.nasa.gov/search/granules.json?" + q))["feed"]["entry"]:
                    url = next((l["href"] for l in g.get("links", []) if str(l.get("href", "")).startswith("https") and str(l["href"]).endswith(".h5")), None)
                    if url:
                        row = _row(pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name, url,
                                   float(g.get("granule_size") or 0) * 1e6, maturity, rank)
                        row["updated"] = g.get("updated", "")
                        row["short_name"] = sn
                        rows.append(row)
            errors.clear()
        except Exception as ex:
            errors.append(f"NASA CMR: {type(ex).__name__}: {str(ex)[:120]}")
    if not rows and errors:
        raise RuntimeError("radar catalog search failed: " + " | ".join(errors))
    return rows


def login():
    """Earthdata login without ever hanging a background job on a hidden prompt."""
    import earthaccess
    env = os.environ.get("EARTHDATA_TOKEN") or (os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD"))
    netrc = any((pathlib.Path.home() / f).exists() for f in (".netrc", "_netrc"))
    if env: auth = earthaccess.login(strategy="environment")
    elif netrc: auth = earthaccess.login(strategy="netrc")
    elif sys.stdin and sys.stdin.isatty(): auth = earthaccess.login(persist=True)
    else: raise RuntimeError("Earthdata login is not set. Open the Connections page (or run: python connections.py --setup) and enter it.")
    if not getattr(auth, "authenticated", False):
        raise RuntimeError("Earthdata login was rejected. Check the username and password on the Connections page.")
    return earthaccess


def stream_subset(chain, bbox, folder: pathlib.Path):
    """Read only the site window from each radar file over HTTPS and save it as a small local file with the same layout.
    Avoids downloading whole products. Method from the ASF NISAR earthaccess guide (fsspec HTTPS session)."""
    import h5py
    from swell import ingest
    ea = login(); fs = ea.get_fsspec_https_session(); folder.mkdir(parents=True, exist_ok=True); layout = None
    for k, r in enumerate(chain, 1):
        dst = folder / r["name"]
        if dst.exists():
            continue
        try: fobj = fs.open(r["url"], cache_type="background", block_size=16 * 2 ** 20)
        except Exception: fobj = fs.open(r["url"], block_size=16 * 2 ** 20)
        with fobj, h5py.File(fobj, "r") as f:
            if layout is None:
                layout = layout_of(f); ingest.PATHS.update(layout)
            si, sj = ingest._crop(f, bbox); P = ingest.PATHS; shape = f[P["phase"]].shape; tmp = dst.with_suffix(".part")
            if k == 1: say(f"radar   layout: {P['phase']}  full grid {shape}, site window {si.stop - si.start} x {sj.stop - sj.start} pixels")
            with h5py.File(tmp, "w") as o:
                for key in ("phase", "coh", "cc", "iono"):
                    if P[key] in f and f[P[key]].shape == shape:
                        o.create_dataset(P[key], data=f[P[key]][si, sj], compression="gzip")
                o[P["x"]] = f[P["x"]][sj]; o[P["y"]] = f[P["y"]][si]; o[P["epsg"]] = int(np.array(f[P["epsg"]]))
                for t in ("referenceZeroDopplerStartTime", "secondaryZeroDopplerStartTime"):
                    q = "/science/LSAR/identification/" + t
                    if q in f: o[q] = f[q][()]
                try:
                    inc = [n_ for n_ in _names(f) if n_.endswith("incidenceAngle")]
                    val = float(np.nanmean(f[inc[0]][...])) if inc else float("nan")
                    if not np.isfinite(val):                                   # fall back to the line-of-sight unit vector, if the product carries it
                        los = [n_ for n_ in _names(f) if n_.endswith("losUnitVectorZ")]
                        if los: val = float(np.degrees(np.arccos(np.clip(np.nanmean(np.abs(f[los[0]][...])), 0, 1))))
                    if np.isfinite(val): o["/science/LSAR/GUNW/metadata/radarGrid/incidenceAngle"] = np.array([val])
                    elif k == 1: say("radar   WARNING: no incidence angle found in the file. Datasets with 'ncidence' or 'los': " + "; ".join(n_ for n_ in _names(f) if "ncidence" in n_ or "los" in n_.lower())[:600])
                except Exception as ex:
                    if k == 1: say(f"radar   WARNING: incidence angle could not be read ({type(ex).__name__}: {str(ex)[:120]})")
                _copy_cubes(f, o)
            tmp.replace(dst)
        say(f"radar   {k}/{len(chain)} window read online: {r['ref']} -> {r['sec']}  ({dst.stat().st_size / 1e6:.1f} MB kept)")
    return layout


def _copy_cubes(f, o) -> int:
    """Copy NISAR's troposphere / solid-Earth-tide correction cubes and their coordinates (small, coarse grids)."""
    from swell import corrections as CR
    n = 0
    for k in CR.cube_paths(_names(f)):
        if k in o:
            continue
        try:
            o.create_dataset(k, data=f[k][...]); n += 1
        except Exception:
            pass
    o.attrs["swell_cubes_checked"] = 1
    return n


def augment_cubes(chain, folder: pathlib.Path) -> int:
    """Site windows saved by an earlier SWELL version lack the correction cubes. Fetch only those (a few MB at most)."""
    import h5py
    todo = []
    for r in chain:
        p = folder / r["name"]
        if p.exists():
            with h5py.File(p, "r") as h:
                if not h.attrs.get("swell_cubes_checked"):
                    todo.append((r, p))
    if not todo:
        return 0
    say(f"radar   fetching NISAR troposphere / tide correction layers for {len(todo)} saved pair(s) (small, read online)")
    ea = login(); fs = ea.get_fsspec_https_session(); got = 0
    for r, p in todo:
        try:
            with fs.open(r["url"], block_size=4 * 2 ** 20) as fobj, h5py.File(fobj, "r") as f, h5py.File(p, "a") as o:
                got += _copy_cubes(f, o)
        except Exception as ex:
            say(f"radar   correction layers for {r['name'][:60]}... not read ({type(ex).__name__}: {str(ex)[:120]})")
    say(f"radar   correction layers copied: {got} datasets")
    return got


def download(chain, folder: pathlib.Path):
    earthaccess = login()
    folder.mkdir(parents=True, exist_ok=True)
    todo = [r["url"] for r in chain if not (folder / r["name"]).exists()]
    if todo:
        earthaccess.download(todo, str(folder))
    missing = [r["name"] for r in chain if not (folder / r["name"]).exists()]
    if missing:
        raise RuntimeError(f"{len(missing)} radar files did not download: {missing[:2]}")


def detect_layout(h5file: pathlib.Path) -> dict:
    """Find the unwrapped-phase group in a real file instead of trusting a path written from the product guide."""
    import h5py
    with h5py.File(h5file, "r") as f:
        return layout_of(f)


def _names(f):
    names = []
    f.visititems(lambda k, o: names.append("/" + k) if hasattr(o, "shape") else None)
    return names


def layout_of(f) -> dict:
    names = _names(f)
    ph = [k for k in names if "/unwrappedInterferogram/" in k and k.endswith("/unwrappedPhase")]
    ph.sort(key=lambda k: (("frequencyA" not in k), ("/HH/" not in k), k))
    if not ph:
        raise RuntimeError("no unwrappedPhase dataset in this file. Datasets containing 'GUNW': "
                           + "; ".join(k for k in names if "GUNW" in k)[:1500])
    grp = ph[0].rsplit("/", 1)[0]; parent = grp.rsplit("/", 1)[0]

    def find(leaf):
        for k in (f"{grp}/{leaf}", f"{parent}/{leaf}"):
            if k in names:
                return k
        hit = [k for k in names if k.endswith("/" + leaf) and "frequencyA" in k]
        return hit[0] if hit else f"{grp}/{leaf}"
    return dict(phase=ph[0], coh=find("coherenceMagnitude"), cc=find("connectedComponents"), iono=find("ionospherePhaseScreen"),
                x=find("xCoordinates"), y=find("yCoordinates"), epsg=find("projection"))


# ---------------------------------------------------------------- rain, clay, paving
def fetch_rain(bbox, start: str, path: pathlib.Path, need_days: int):
    """Fetch a contiguous daily rainfall history; never convert missing observations to zero.

    NASA POWER can publish recent days late. The caller may trim the radar chain to the last
    acquisition supported by this rainfall record. Internal gaps fail closed because zero-fill
    would bias the soil-wetness state and subsequent motion inference.
    """
    lon, lat = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    end = dt.date.today()
    url = ("https://power.larc.nasa.gov/api/temporal/daily/point?" + urllib.parse.urlencode(dict(
        parameters="PRECTOTCORR,GWETTOP", community="AG", longitude=round(lon, 4), latitude=round(lat, 4),
        start=start.replace("-", ""), end=end.strftime("%Y%m%d"), format="JSON")))
    par = json.loads(http(url))["properties"]["parameter"]
    d, gw = par["PRECTOTCORR"], par.get("GWETTOP", {})
    first = dt.date.fromisoformat(start)
    expected = [(first + dt.timedelta(days=i)).strftime("%Y%m%d") for i in range((end - first).days + 1)]
    raw = [float(d.get(k, -999)) for k in expected]
    # Drop only the trailing not-yet-published segment. Preserve all earlier missingness as an error.
    while raw and raw[-1] < 0:
        raw.pop(); expected.pop()
    gaps = [k for k, v in zip(expected, raw) if v < 0]
    if gaps:
        dates = [f"{k[:4]}-{k[4:6]}-{k[6:]}" for k in gaps[:8]]
        raise RuntimeError("NASA POWER rainfall has internal missing days; no zero-fill was applied. Missing: " + ", ".join(dates))
    vals = [max(0.0, v) for v in raw]
    if not vals:
        raise RuntimeError("NASA POWER returned no contiguous rainfall observations for this site/date range.")
    available_through = f"{expected[-1][:4]}-{expected[-1][4:6]}-{expected[-1][6:]}"
    path.write_text("date,rain_mm\n" + "\n".join(f"{k[:4]}-{k[4:6]}-{k[6:]},{v:.2f}" for k, v in zip(expected, vals)) + "\n")
    covered = len(vals) > int(need_days)
    say(f"rain    NASA POWER: {len(vals)} contiguous days from {start} through {available_through}, total {sum(vals):.0f} mm"
        + ("; all requested radar dates covered" if covered else f"; latest requested radar date not covered yet (needs day {need_days}, available through day {len(vals)-1})"))
    return dict(source="NASA POWER PRECTOTCORR (daily, point at site centre)", url=url, days=len(vals),
                missing_set_to_zero=0, padded_days=0, available_through=available_through,
                coverage_complete=covered, nasa_surface_wetness=[float(gw.get(k, -999)) for k in expected])


IGH = "+proj=igh +lat_0=0 +lon_0=0 +datum=WGS84 +units=m +no_defs"     # SoilGrids' Interrupted Goode Homolosine


def fetch_clay(bbox, path: pathlib.Path):
    import rasterio
    from pyproj import Transformer
    from rasterio.crs import CRS
    w, s, e, n = bbox; m = 0.05
    xs, ys = Transformer.from_crs("EPSG:4326", IGH, always_xy=True).transform([w - m, e + m, w - m, e + m], [s - m, s - m, n + m, n + m])
    crs = "http://www.opengis.net/def/crs/EPSG/0/152160"
    url = ("https://maps.isric.org/mapserv?map=/map/clay.map&SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage"
           f"&COVERAGEID=clay_30-60cm_mean&FORMAT=GEOTIFF_INT16&SUBSET=X({min(xs):.0f},{max(xs):.0f})&SUBSET=Y({min(ys):.0f},{max(ys):.0f})"
           f"&SUBSETTINGCRS={crs}&OUTPUTCRS={crs}")
    raw = path.with_suffix(".raw.tif")
    try:
        data = http(url, 180)
        if data[:2] not in (b"II", b"MM"):
            raise RuntimeError("SoilGrids WCS did not return a GeoTIFF: " + data[:200].decode("utf-8", "replace"))
        raw.write_bytes(data)
    except Exception as ex:                                               # second route: the same layer as a cloud raster on files.isric.org
        say(f"clay    SoilGrids map service did not answer ({type(ex).__name__}); trying the cloud raster")
        from rasterio.windows import from_bounds
        url = "https://files.isric.org/soilgrids/latest/data/clay/clay_30-60cm_mean.vrt"
        with rasterio.open("/vsicurl/" + url) as src:
            win = from_bounds(min(xs), min(ys), max(xs), max(ys), src.transform).round_offsets().round_lengths(); a0 = src.read(1, window=win)
            with rasterio.open(raw, "w", driver="GTiff", height=a0.shape[0], width=a0.shape[1], count=1, dtype=a0.dtype, transform=src.window_transform(win), nodata=src.nodata) as dst0:
                dst0.write(a0, 1)
    with rasterio.open(raw) as src:
        a = src.read(1).astype("float32"); prof = src.profile
        a[(a <= 0) | (a == (src.nodata if src.nodata is not None else -32768))] = np.nan
    a = a / 10.0                                                          # SoilGrids stores g/kg; /10 = percent
    if not np.isfinite(a).any():
        raise RuntimeError("SoilGrids returned no valid clay values for this box")
    filled = float(np.isnan(a).mean()); a = np.where(np.isfinite(a), a, np.nanmedian(a))
    prof.update(dtype="float32", nodata=None, count=1, compress="deflate", crs=CRS.from_proj4(IGH))
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(a, 1)
    low = float(np.quantile(a, 0.25))
    say(f"clay    SoilGrids 30-60 cm: {np.min(a):.0f}-{np.max(a):.0f} % clay, lowest quarter is below {low:.1f} %"
        + (f", {filled:.0%} masked pixels filled with the site median" if filled else ""))
    return dict(source="ISRIC SoilGrids 2.0 clay content 30-60 cm (percent)", url=url, low_clay_threshold=low, masked_filled_fraction=filled), low


def fetch_paved(bbox, path: pathlib.Path):
    import math
    import rasterio
    from rasterio.merge import merge
    from rasterio.windows import from_bounds
    w, s, e, n = bbox; parts = []; urls = []
    for lat0 in range(int(math.floor(s / 3) * 3), int(math.floor((n - 1e-9) / 3) * 3) + 1, 3):
        for lon0 in range(int(math.floor(w / 3) * 3), int(math.floor((e - 1e-9) / 3) * 3) + 1, 3):
            tile = f"{'N' if lat0 >= 0 else 'S'}{abs(lat0):02d}{'E' if lon0 >= 0 else 'W'}{abs(lon0):03d}"
            url = f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
            urls.append(url)
            with rasterio.open("/vsicurl/" + url) as src:
                b = (max(w - .02, src.bounds.left), max(s - .02, src.bounds.bottom), min(e + .02, src.bounds.right), min(n + .02, src.bounds.top))
                win = from_bounds(*b, src.transform).round_offsets().round_lengths()
                a = (src.read(1, window=win) == 50).astype("float32")     # class 50 = built-up
                tmp = path.with_name(f"paved_{tile}.tif")
                prof = dict(driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype="float32", crs=src.crs,
                            transform=src.window_transform(win), compress="deflate")
                with rasterio.open(tmp, "w", **prof) as dst:
                    dst.write(a, 1)
                parts.append(tmp)
    if len(parts) == 1:
        parts[0].replace(path)
    else:
        srcs = [rasterio.open(p) for p in parts]; mosaic, tr = merge(srcs)
        prof = srcs[0].profile; prof.update(height=mosaic.shape[1], width=mosaic.shape[2], transform=tr)
        [x.close() for x in srcs]
        with rasterio.open(path, "w", **prof) as dst:
            dst.write(mosaic[0], 1)
    with rasterio.open(path) as src:
        frac = float(src.read(1).mean())
    say(f"paving  ESA WorldCover 2021: {frac:.0%} of the box is built-up")
    return dict(source="ESA WorldCover 2021 v200, class 50 built-up, as a 0/1 mask averaged to each cell", urls=urls, built_up_fraction=frac)


# ---------------------------------------------------------------- run
def extras(bbox, epoch0, last):
    """Other satellites as evidence. Adds `sensors` (and the Sentinel-1 referee test) to site/data/site.json. Never raises."""
    try:
        from swell import sensors
        sj = ROOT / "site" / "data" / "site.json"; web = json.loads(sj.read_text())
        if "SYNTH" in str(web.get("source", "")).upper():
            say("extras  skipped: no real site is loaded"); return
        say("extras  NISAR radar brightness (HH/HV), then other satellites: GPM rain, SMAP soil moisture, Sentinel-1 motion, Landsat vegetation, open water (each may take minutes)")
        try: track = json.loads((OUT / "real_site_provenance.json").read_text())["steps"]["radar"]["pairs"][0].get("track")
        except Exception: track = None
        out, test = sensors.run_all(web, bbox, epoch0, last, web["rain"], login, say, track=track)
        web["sensors"] = out; web["tests"] = [t for t in web["tests"] if not str(t.get("name", "")).startswith("T1b")] + ([test] if test else [])
        sj.write_text(json.dumps(web)); (OUT / "sensors.json").write_text(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("grid", "series")} for k, v in out.items()}, indent=1))
        for k, v in out.items():
            say(f"extras  {v['name']}: " + (v.get("finding") or v.get("reason") or v["status"]))
    except Exception as ex:
        say(f"extras  stopped ({type(ex).__name__}: {str(ex)[:300]}). The twin itself is unaffected."); LOG.append(traceback.format_exc())


NEEDED = [("numpy", "numpy"), ("scipy", "scipy"), ("h5py", "h5py"), ("rasterio", "rasterio"), ("pyproj", "pyproj"), ("earthaccess", "earthaccess"), ("matplotlib", "matplotlib")]


def missing_packages() -> list[str]:
    import importlib.util
    return [pip for mod, pip in NEEDED if importlib.util.find_spec(mod) is None]


def install_packages(pkgs) -> bool:
    import subprocess
    say("setup   installing: " + " ".join(pkgs) + "  (one time, can take a few minutes)")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *pkgs], capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines()[-6:]:
        say("setup   " + line[:200])
    return r.returncode == 0


def main(argv=None):
    from swell import ingest
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", help="one of: " + ", ".join(ingest.SITES)); ap.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    ap.add_argument("--name"); ap.add_argument("--max-pairs", type=int, default=8); ap.add_argument("--grid", type=int, default=60)
    ap.add_argument("--download", action="store_true", help="download whole radar files instead of reading only the site window online")
    ap.add_argument("--no-extras", action="store_true", help="skip GPM, SMAP, Sentinel-1, Landsat and water")
    ap.add_argument("--extras-only", action="store_true", help="re-run only the other satellites on the site already built")
    ap.add_argument("--no-detrend", action="store_true", help="do not remove the smooth scene-wide surface from each radar pair")
    ap.add_argument("--no-troposphere", action="store_true", help="do not apply NISAR's own troposphere layers (they ship in the file but are not applied to the phase)")
    ap.add_argument("--no-tides", action="store_true", help="do not apply NISAR's solid-Earth-tide layer")
    ap.add_argument("--ground-height", type=float, default=150.0, help="ground height above the ellipsoid in metres, used to read the troposphere cube (Dallas about 150)")
    ap.add_argument("--highpass-km", type=float, default=0.0, help="EXPLORATORY: keep only differences between neighbouring ground, removing anything smoother than this many km")
    ap.add_argument("--no-gnss", action="store_true", help="do not fetch GPS stations from the Nevada Geodetic Laboratory (the GPS referee test then stays 'not run')")
    ap.add_argument("--install-deps", action="store_true", help="install any missing Python packages first")
    ap.add_argument("--check", action="store_true", help="only report what real data exists"); ap.add_argument("--yes", action="store_true", help="do not ask before downloading")
    a = ap.parse_args(argv)
    if not a.site and not a.bbox:
        ap.error("give --site or --bbox")
    key = a.site or re.sub(r"[^a-z0-9]+", "_", (a.name or "site").lower()).strip("_") or "site"
    if a.bbox:
        ingest.SITES[key] = dict(name=a.name or key, bbox=list(a.bbox))
    if key not in ingest.SITES:
        ap.error(f"unknown site {key}")
    LOG.clear(); miss = missing_packages()
    if miss and a.install_deps:
        install_packages(miss); miss = missing_packages()
    if miss:
        say("STOPPED: these Python packages are missing from the environment that runs SWELL: " + ", ".join(miss))
        say("Fix:  " + sys.executable + " -m pip install " + " ".join(miss) + "    (or press 'Install missing packages' on the Connections page), then run again.")
        OUT.mkdir(exist_ok=True); (OUT / "real_site_log.txt").write_text("\n".join(LOG) + "\n"); return 3
    bbox = ingest.SITES[key]["bbox"]; load_env(); OUT.mkdir(exist_ok=True); work = ROOT / "data" / key; work.mkdir(parents=True, exist_ok=True)
    prov = dict(site=key, name=ingest.SITES[key]["name"], bbox=bbox, grid=a.grid, started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), steps={})
    ok = True
    if a.extras_only:
        try:
            old = json.loads((OUT / "real_site_provenance.json").read_text()); pairs = old["steps"]["radar"]["pairs"]; prov = old
            extras(old["bbox"], pairs[0]["ref"], pairs[-1]["sec"]); return 0
        except Exception as ex:
            say(f"FAILED: build the twin first ({type(ex).__name__}: {str(ex)[:200]})"); return 2
        finally:
            (OUT / "real_site_provenance.json").write_text(json.dumps(prov, indent=1, default=str)); (OUT / "real_site_log.txt").write_text("\n".join(LOG) + "\n")
    try:
        say(f"SWELL real site: {ingest.SITES[key]['name']}  box {bbox}")
        rows = search_nisar(bbox); chain = choose_chain(rows, a.max_pairs)
        say(f"radar   catalog: {len(rows)} NISAR ground-motion (GUNW) products over this box")
        if not chain:
            sample = [r["name"] for r in rows[:5]]
            raise RuntimeError("no usable chain of pairs. First file names returned: " + json.dumps(sample))
        gb = sum(r["bytes"] for r in chain) / 1e9
        say(f"radar   chosen: track {chain[0]['track']}, frame {chain[0]['frame']}, {len(chain)} consecutive pairs, "
            f"{chain[0]['ref']} to {chain[-1]['sec']}" + (f", about {gb:.1f} GB" if gb else ", size not listed"))
        for r in chain:
            say(f"          {r['ref']} -> {r['sec']}  {r['name']}")
        need = (dt.date.fromisoformat(chain[-1]["sec"]) - dt.date.fromisoformat(chain[0]["ref"])).days
        try:
            rain_meta = fetch_rain(bbox, chain[0]["ref"], work / "rain.csv", need)
            prov["steps"]["rain"] = rain_meta
            available = dt.date.fromisoformat(rain_meta["available_through"])
            covered_chain = [r for r in chain if dt.date.fromisoformat(r["sec"]) <= available]
            if not covered_chain:
                raise RuntimeError(f"Rainfall data are available only through {available}; no NISAR pair is covered. Wait for NASA POWER publication or choose an earlier study window.")
            if len(covered_chain) < len(chain):
                say(f"radar   trimming {len(chain)-len(covered_chain)} latest pair(s): rainfall is only available through {available}; no zero-filled rainfall is permitted")
                chain = covered_chain
            need = (dt.date.fromisoformat(chain[-1]["sec"]) - dt.date.fromisoformat(chain[0]["ref"])).days
            if rain_meta["days"] <= need:
                raise RuntimeError("Contiguous rainfall record does not cover the retained radar chain.")
        except Exception as ex:
            ok = False; say(f"rain    FAILED: {type(ex).__name__}: {str(ex)[:400]}"); LOG.append(traceback.format_exc())
        # Record final, homogeneous collection chain after the rainfall coverage gate.
        prov["steps"]["radar"] = dict(source="NASA NISAR L2 GUNW via ASF/CMR", catalog_count=len(rows),
            selected_maturity=chain[0].get("maturity", "unknown"), selected_short_name=chain[0].get("short_name"),
            pairs=[dict(name=r["name"], ref=r["ref"], sec=r["sec"], url=r["url"], maturity=r.get("maturity", "unknown"),
                        short_name=r.get("short_name"), track=r.get("track"), frame=r.get("frame"), bytes=r.get("bytes", 0), updated=r.get("updated")) for r in chain])
        for label, fn in (("clay", lambda: fetch_clay(bbox, work / "clay.tif")), ("paving", lambda: fetch_paved(bbox, work / "paved.tif"))):
            try:
                res = fn(); prov["steps"][label] = res[0] if isinstance(res, tuple) else res
                if label == "clay": prov["lep_low"] = res[1]
            except Exception as ex:
                ok = False; say(f"{label:7s} FAILED: {type(ex).__name__}: {str(ex)[:400]}"); LOG.append(traceback.format_exc())
        gps_path = None
        if not a.no_gnss and not a.check:
            try:
                from swell import gnss
                g = gnss.fetch(bbox, chain[0]["ref"], chain[-1]["sec"], lambda u: http(u, timeout=60).decode("utf-8", "replace"), say)
                if g:
                    gps_path = work / "gps.json"; gps_path.write_text(json.dumps(g))
                prov["steps"]["gnss"] = dict(source="Nevada Geodetic Laboratory (UNR) daily IGS20 positions, vertical", stations=sorted(g))
            except Exception as ex:
                say(f"gnss    not used ({type(ex).__name__}: {str(ex)[:200]}). The GPS referee test stays 'not run'.")
        if len(chain) < 4:
            say(f"NOTE    only {len(chain)} pairs: the twin can be built but the forecast test needs more passes.")
        if a.check:
            say("CHECK ONLY: nothing large was downloaded. Run again without --check to build the twin." if ok else "CHECK ONLY: fix the FAILED steps above first.")
            return 0 if ok else 2
        if not ok:
            raise RuntimeError("one of rain / clay / paving failed (see above). The twin is not built from partial inputs.")
        gdir = work / "gunw"; layout = None
        if not a.download:
            try:
                say(f"radar   reading the site window from {len(chain)} files online (no full download)")
                layout = stream_subset(chain, bbox, gdir)
            except Exception as ex:
                say(f"radar   online window read failed ({type(ex).__name__}: {str(ex)[:300]})"); LOG.append(traceback.format_exc())
                if not a.yes and not (sys.stdin and sys.stdin.isatty()):
                    raise RuntimeError("online read failed and full download was not approved. Run again with --download --yes" + (f" (about {gb:.1f} GB)" if gb else ""))
        if layout is None and not all((gdir / r["name"]).exists() for r in chain):
            if not a.yes and input(f"Download {len(chain)} whole radar files" + (f" (about {gb:.1f} GB)" if gb else "") + f" into {gdir}? [y/N] ").strip().lower() != "y":
                say("Stopped before downloading."); return 1
            download(chain, gdir)
        keep = {r["name"] for r in chain}
        for f in gdir.glob("*.h5"):                                       # only this chain is used
            if f.name not in keep:
                f.rename(f.with_suffix(".h5.unused"))
        if not (a.no_troposphere and a.no_tides):
            try: augment_cubes(chain, gdir)
            except Exception as ex: say(f"radar   correction layers skipped ({type(ex).__name__}: {str(ex)[:200]})")
        layout = detect_layout(gdir / chain[0]["name"]); ingest.PATHS.update(layout); prov["steps"]["radar"]["hdf5_layout"] = layout
        say("radar   layout found in the file: " + layout["phase"])
        ingest.build(key, str(gdir), str(work / "rain.csv"), str(work / "clay.tif"), str(work / "paved.tif"), str(gps_path) if gps_path else None, n=a.grid,
                     lep_low=prov["lep_low"], clay_layer="SoilGrids clay content 30-60 cm (%), not a shrink-swell rating", detrend=0 if a.no_detrend else 2,
                     troposphere=not a.no_troposphere, tides=not a.no_tides, ground_height_m=a.ground_height, highpass_km=a.highpass_km)
        try:
            pv = json.loads((OUT / "provenance.json").read_text()); prov["steps"]["radar"]["nisar_corrections"] = pv.get("nisar_corrections")
            nc = pv.get("nisar_corrections") or {}
            if nc.get("pairs_with_layers"):
                say(f"radar   NISAR troposphere/tide layers {nc.get('applied')} on {nc['pairs_with_layers']} pairs: scene variance removed {nc.get('variance_removed_pct')} %")
            else:
                say("radar   NISAR troposphere/tide layers were not found in these products; pairs keep the reference-surface correction only")
        except Exception:
            pass
        from swell import validate
        validate.main(["--site", str(OUT / f"{key}.npz")])
        try:                                                              # independent check: SWELL wetness index vs NASA modelled surface soil wetness
            from scipy.stats import spearmanr
            gw = np.array(prov["steps"].get("rain", {}).get("nasa_surface_wetness") or [])
            sj = ROOT / "site" / "data" / "site.json"; web = json.loads(sj.read_text()); w = np.array(web["wetness"][:len(gw)]); gw = gw[:len(w)]; okk = gw >= 0
            if okk.sum() >= 20:
                rho = float(spearmanr(w[okk], gw[okk]).statistic)
                web["wetness_check"] = dict(spearman=rho, days=int(okk.sum()), source="NASA POWER GWETTOP (MERRA-2 / GEOS surface soil wetness), not used in the fit")
                sj.write_text(json.dumps(web)); say(f"check   wetness index vs NASA surface soil wetness: rank correlation {rho:.2f} over {int(okk.sum())} days")
        except Exception as ex:
            say(f"check   wetness comparison skipped ({type(ex).__name__})")
        say("TWIN READY: the real site is written. Other satellites are added next; you can already open the Decision Studio.")
        if not a.no_extras:
            extras(bbox, chain[0]["ref"], chain[-1]["sec"])
        say(f"DONE    real site written to site/data/site.json. Restart: python run_swell.py  then open http://127.0.0.1:8000/")
        return 0
    except SystemExit as ex:
        say(f"STOPPED: {ex}"); return 2
    except Exception as ex:
        say(f"FAILED: {type(ex).__name__}: {str(ex)[:1500]}"); LOG.append(traceback.format_exc()); return 2
    finally:
        prov["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        (OUT / "real_site_provenance.json").write_text(json.dumps(prov, indent=1, default=str))
        (OUT / "real_site_log.txt").write_text("\n".join(LOG) + "\n")
        print("Log saved to out/real_site_log.txt (no credentials in it).")


if __name__ == "__main__":
    sys.exit(main())
