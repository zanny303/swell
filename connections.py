"""One place for every outside connection SWELL uses: test them all, and store the three optional keys.

    python connections.py                 test every service and print a table (also writes connection-status.json)
    python connections.py --setup         type your Earthdata login / FIRMS key / Cesium token once (hidden input)
    python connections.py --lat 21.15 --lon 79.09     test at another place

The same checks power the Connections page in the app (site/connections.html).
Keys live only in the local file `.env` next to this script. They are never printed, logged or sent to the browser.
A green tick means the service answered sensibly just now. It does not mean the science is validated.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent
ENV = ROOT / ".env"
KEYS = {  # name -> (label, pattern, help)
    "EARTHDATA_USERNAME": ("NASA Earthdata username", r"[A-Za-z0-9_.\-]{3,60}", "Free account at urs.earthdata.nasa.gov"),
    "EARTHDATA_PASSWORD": ("NASA Earthdata password", r"[^\r\n]{6,200}", "Used only to read NISAR and other NASA files"),
    "EARTHDATA_TOKEN": ("NASA Earthdata token (instead of username + password)", r"[A-Za-z0-9_.\-]{20,4000}", "Optional alternative: Generate Token on your Earthdata profile"),
    "FIRMS_MAP_KEY": ("NASA FIRMS map key", r"[A-Za-z0-9_\-]{8,100}", "Optional. Fire detections as data, not only as a picture"),
    "CESIUM_ION_TOKEN": ("Cesium ion token", r"[A-Za-z0-9_.\-]{20,4000}", "Optional. 3D terrain and building shapes"),
    "ANTHROPIC_API_KEY": ("Anthropic API key", r"sk-ant-[A-Za-z0-9_\-]{20,300}", "Optional. Server-side Claude Copilot; never sent to the browser"),
    "SWELL_CLAUDE_MODEL": ("Claude model ID", r"claude-[a-z0-9-]{5,80}", "Legacy Claude model setting"),
    "SWELL_AI_PROVIDER": ("AI provider", r"(?:none|anthropic|openai|meta|ollama|compatible)", "Provider selected for SWELL Copilot"),
    "SWELL_AI_API_KEY": ("AI API key", r"[^\r\n]{4,500}", "Optional server-side key for the selected provider"),
    "SWELL_AI_BASE_URL": ("AI API base URL", r"https?://[A-Za-z0-9._:/-]{1,240}", "Provider endpoint; HTTPS required except localhost Ollama"),
    "SWELL_AI_MODEL": ("AI model ID", r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,120}", "Model identifier from the selected provider"),
}
UA = {"User-Agent": "SWELL-SpaceApps/1.0 (connection check)"}


def load_env():
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", line)
            if m and m.group(1) not in os.environ:
                os.environ[m.group(1)] = m.group(2).strip().strip('"').strip("'")


def save_keys(values: dict) -> list[str]:
    """Validate and write keys to .env. Empty string removes a key. Returns the names that changed."""
    cur = {}
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", line)
            if m: cur[m.group(1)] = m.group(2)
    changed = []
    for k, v in values.items():
        if k not in KEYS:
            raise ValueError(f"unknown key {k}")
        v = str(v).strip()
        if v == "":
            if k in cur: cur.pop(k); os.environ.pop(k, None); changed.append(k)
            continue
        if not re.fullmatch(KEYS[k][1], v):
            raise ValueError(f"{KEYS[k][0]}: that does not look right (check for spaces or missing characters)")
        cur[k] = v; os.environ[k] = v; changed.append(k)
    ENV.write_text("# SWELL local keys. Never commit or share this file.\n" + "".join(f"{k}={v}\n" for k, v in cur.items()))
    try: os.chmod(ENV, 0o600)
    except OSError: pass
    gi = ROOT / ".gitignore"
    if not gi.exists() or ".env" not in gi.read_text().split():
        with gi.open("a") as f: f.write("\n.env\n")
    if any(k in changed for k in ("SWELL_AI_PROVIDER", "SWELL_AI_API_KEY", "SWELL_AI_BASE_URL", "SWELL_AI_MODEL", "ANTHROPIC_API_KEY", "SWELL_CLAUDE_MODEL")):
        # A key/model change invalidates any previously green AI connectivity check.
        report_path = ROOT / "out" / "connection_status.json"
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            for row in report.get("results", []):
                if row.get("id") == "ai_provider":
                    row["status"] = "not_tested"
                    row["detail"] = "Provider settings changed; run Test AI generation to verify the selected model."
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        except (OSError, ValueError):
            pass
        # A successful test belongs to the exact key/provider/model configuration.
        # Remove it whenever any of those settings are saved again.
        try:
            (ROOT / "out" / "ai_provider_test.json").unlink(missing_ok=True)
        except OSError:
            pass
    return changed


def key_state() -> dict:
    load_env()
    return {k: bool(os.environ.get(k)) for k in KEYS}


def _get(url, headers=None, timeout=20, data=None, limit=400_000):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})}, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limit), dict(r.headers)


def _json(url, **kw):
    return json.loads(_get(url, **kw)[0])


# ---------------------------------------------------------------- the checks. Each returns a short plain sentence, or raises.
def c_gibs(lat, lon):
    d = (dt.date.today() - dt.timedelta(days=2)).isoformat()
    q = urllib.parse.urlencode(dict(SERVICE="WMS", REQUEST="GetMap", VERSION="1.1.1", LAYERS="VIIRS_SNPP_CorrectedReflectance_TrueColor", SRS="EPSG:4326",
                                    BBOX=f"{lon - 1},{lat - 1},{lon + 1},{lat + 1}", WIDTH=64, HEIGHT=64, FORMAT="image/jpeg", TIME=d))
    b, h = _get("https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?" + q)
    if not h.get("Content-Type", "").startswith("image"): raise RuntimeError("answered, but not with an image: " + b[:120].decode("utf-8", "replace"))
    return f"satellite picture for {d} received"


def c_esri(lat, lon):
    b, h = _get("https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/0/0/0")
    if not h.get("Content-Type", "").startswith("image"): raise RuntimeError("no image returned")
    return "close-up imagery tile received"


def c_quakes(lat, lon):
    return f"{len(_json('https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson')['features'])} earthquakes of M 2.5+ in the past day"


def c_eonet(lat, lon):
    return f"{len(_json('https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=50')['events'])} open natural events listed"


class NoDataError(RuntimeError):
    """The upstream catalogue is reachable but has no matching records for this AOI."""


class NotTestedError(RuntimeError):
    """Settings exist but a live generation check has not yet been completed."""


def c_nisar(lat, lon):
    box = f"{lon - .25},{lat - .2},{lon + .25},{lat + .2}"; out = []; counts = []
    for sn, label in (("NISAR_L2_GUNW_V1", "validated"), ("NISAR_L2_GUNW_PROVISIONAL_V1", "provisional"), ("NISAR_L2_GUNW_BETA_V1", "beta")):
        _, h = _get("https://cmr.earthdata.nasa.gov/search/granules.json?" + urllib.parse.urlencode(dict(short_name=sn, bounding_box=box, page_size=1)))
        raw = h.get("CMR-Hits", h.get("cmr-hits", "?"))
        try: counts.append(int(raw))
        except (TypeError, ValueError): counts.append(None)
        out.append(f"{raw} {label}")
    if counts and all(v == 0 for v in counts):
        raise NoDataError("NASA CMR is reachable, but no NISAR GUNW granules match this test box. This is no coverage, not an API-key failure; preview a different AOI/date.")
    return "NASA CMR reachable; matching NISAR GUNW catalogue counts: " + ", ".join(out)


def c_power(lat, lon):
    a, b = (dt.date.today() - dt.timedelta(days=12)), (dt.date.today() - dt.timedelta(days=5))
    d = _json("https://power.larc.nasa.gov/api/temporal/daily/point?" + urllib.parse.urlencode(dict(parameters="PRECTOTCORR", community="AG", longitude=lon, latitude=lat,
              start=a.strftime("%Y%m%d"), end=b.strftime("%Y%m%d"), format="JSON")), timeout=40)["properties"]["parameter"]["PRECTOTCORR"]
    v = [x for x in d.values() if x >= 0]
    return f"{sum(v):.1f} mm of rain in the week to {b.isoformat()}"


def c_soilgrids(lat, lon):
    from pyproj import Transformer
    x, y = Transformer.from_crs("EPSG:4326", "+proj=igh +lat_0=0 +lon_0=0 +datum=WGS84 +units=m +no_defs", always_xy=True).transform(lon, lat)
    crs = "http://www.opengis.net/def/crs/EPSG/0/152160"
    b, _ = _get("https://maps.isric.org/mapserv?map=/map/clay.map&SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage&COVERAGEID=clay_30-60cm_mean&FORMAT=GEOTIFF_INT16"
                f"&SUBSET=X({x - 1500:.0f},{x + 1500:.0f})&SUBSET=Y({y - 1500:.0f},{y + 1500:.0f})&SUBSETTINGCRS={crs}&OUTPUTCRS={crs}", timeout=40)
    if b[:2] not in (b"II", b"MM"): raise RuntimeError("no GeoTIFF returned: " + b[:120].decode("utf-8", "replace"))
    return "clay-content map window received"


def c_worldcover(lat, lon):
    import math
    la, lo = int(math.floor(lat / 3) * 3), int(math.floor(lon / 3) * 3)
    tile = f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}"
    b, _ = _get(f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif", headers={"Range": "bytes=0-15"}, limit=16)
    if b[:2] not in (b"II", b"MM"): raise RuntimeError("land-cover tile not found for " + tile)
    return f"land-cover tile {tile} reachable"


def c_aifs(lat, lon):
    d = _json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(dict(latitude=lat, longitude=lon, daily="precipitation_sum", timezone="GMT", forecast_days=7)))
    return f"{sum(x or 0 for x in d['daily']['precipitation_sum']):.1f} mm of rain forecast for the next 7 days"


def c_glofas(lat, lon):
    d = _json("https://flood-api.open-meteo.com/v1/flood?" + urllib.parse.urlencode(dict(latitude=lat, longitude=lon, daily="river_discharge", forecast_days=3)))
    return f"river discharge forecast received ({len(d['daily']['time'])} days)"


def c_noaa(lat, lon):
    try: d = _json(f"https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}", headers={"Accept": "application/geo+json"})
    except urllib.error.HTTPError as e:
        if e.code in (400, 404): return "reachable; this place is outside NOAA's coverage (United States only)"
        raise
    return f"{len(d.get('features', []))} active weather alerts here"


def c_water(lat, lon):
    try: d = _json("https://waterservices.usgs.gov/nwis/iv/?" + urllib.parse.urlencode(dict(format="json", bBox=f"{lon - .2:.3f},{lat - .2:.3f},{lon + .2:.3f},{lat + .2:.3f}", parameterCd="00065", siteStatus="active")), limit=3_000_000)
    except urllib.error.HTTPError as e:
        if e.code in (400, 404): return "reachable; no US river gauges near this place"
        raise
    return f"{len(d['value']['timeSeries'])} river gauges reporting nearby"


def c_sda(lat, lon):
    body = urllib.parse.urlencode(dict(query="SELECT TOP 1 mukey FROM mapunit", format="JSON")).encode()
    d = json.loads(_get("https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest", data=body, timeout=30)[0])
    if not d.get("Table"): raise RuntimeError("no rows returned")
    return "soil survey database answered (United States only)"


def c_3dep(lat, lon):
    d = _json("https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer?f=json")
    return "terrain service answered" + (f": {d.get('name')}" if d.get("name") else "") + " (United States only)"


def c_earthdata(lat, lon):
    tok, u, p = os.environ.get("EARTHDATA_TOKEN"), os.environ.get("EARTHDATA_USERNAME"), os.environ.get("EARTHDATA_PASSWORD")
    netrc = any((pathlib.Path.home() / f).exists() for f in (".netrc", "_netrc"))
    if not tok and not (u and p):
        if netrc: return "a login file (.netrc) exists on this computer; it will be used"
        raise LookupError("not set. Needed to read NISAR radar files")
    try:
        if tok: _get("https://cmr.earthdata.nasa.gov/search/collections.json?page_size=1", headers={"Authorization": "Bearer " + tok})
        else: _get("https://urs.earthdata.nasa.gov/api/users/tokens", headers={"Authorization": "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()})
    except urllib.error.HTTPError as e:
        if e.code in (401, 403): raise RuntimeError("NASA rejected this login. Re-enter it")
        raise
    return "login accepted by NASA"


def c_firms(lat, lon):
    k = os.environ.get("FIRMS_MAP_KEY")
    if not k: raise LookupError("not set. Optional: fire detections as data")
    b, _ = _get(f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{urllib.parse.quote(k)}/VIIRS_SNPP_NRT/{lon - 1:.2f},{lat - 1:.2f},{lon + 1:.2f},{lat + 1:.2f}/1", timeout=40)
    t = b.decode("utf-8", "replace")
    if "latitude" not in t.splitlines()[0].lower(): raise RuntimeError("key not accepted: " + t[:100])
    return f"key accepted; {max(0, len(t.splitlines()) - 1)} fire detections within about 100 km in the past day"


def c_cesium(lat, lon):
    k = os.environ.get("CESIUM_ION_TOKEN")
    if not k: raise LookupError("not set. Optional: 3D terrain and building shapes")
    try: _get("https://api.cesium.com/v1/assets?limit=1", headers={"Authorization": "Bearer " + k})
    except urllib.error.HTTPError as e:
        if e.code == 401: raise RuntimeError("token rejected")
        if e.code == 403: return "token valid (restricted scope, which is what you want)"
        raise
    return "token accepted"


def c_ai_provider(lat, lon):
    import ai_provider
    state = ai_provider.status()
    if not state.get("configured"):
        raise LookupError("not configured. Optional: choose Anthropic, OpenAI, Meta Model API, Ollama or an OpenAI-compatible provider")
    test = state.get("last_test")
    if not test or not test.get("ok"):
        raise NotTestedError(f"{state['provider']} / {state['model']}: settings are saved; click Test AI generation to verify the provider.")
    return f"{state['provider']} / {state['model']}: live generation verified at {test.get('tested_at_utc', 'unknown time')}"


def c_anthropic(lat, lon):
    k = os.environ.get("ANTHROPIC_API_KEY")
    if not k: raise LookupError("not set. Optional: server-side Claude Copilot")
    try:
        d = _json("https://api.anthropic.com/v1/models?limit=1", headers={"x-api-key": k, "anthropic-version": os.environ.get("ANTHROPIC_API_VERSION", "2023-06-01")}, timeout=20)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403): raise RuntimeError("Anthropic rejected this API key or its permissions")
        raise
    models = d.get("data") or []
    return "API key accepted; model catalogue reachable" + (f" ({len(models)} model record returned)" if models else "")


def c_packages(lat, lon):
    import importlib.util, sys
    need = ["numpy", "scipy", "h5py", "rasterio", "pyproj", "earthaccess", "matplotlib"]
    miss = [m for m in need if importlib.util.find_spec(m) is None]
    if miss:
        raise RuntimeError("missing: " + ", ".join(miss) + ". They are installed automatically when you press Find radar passes or Build. By hand: "
                           + sys.executable + " -m pip install " + " ".join(miss))
    return "all " + str(len(need)) + " packages the build needs are installed"


CHECKS = [  # id, name, group, what SWELL uses it for, function
    ("packages", "Python packages on this computer", "core", "Reading radar files and maps", c_packages),
    ("nisar", "NASA NISAR radar catalog", "core", "The ground-motion twin: which radar passes exist", c_nisar),
    ("earthdata", "NASA Earthdata login", "account", "Reading the NISAR files themselves", c_earthdata),
    ("power", "NASA POWER rainfall", "core", "Rain record that drives soil wetness", c_power),
    ("soilgrids", "ISRIC SoilGrids clay", "core", "Where the clay is", c_soilgrids),
    ("worldcover", "ESA WorldCover land cover", "core", "How much of each cell is paved", c_worldcover),
    ("gibs", "NASA GIBS satellite imagery", "map", "The Earth you see", c_gibs),
    ("esri", "Esri World Imagery", "map", "Close-up detail when zoomed in", c_esri),
    ("quakes", "USGS earthquakes", "map", "Live earthquake layer", c_quakes),
    ("eonet", "NASA EONET events", "map", "Open natural events on the globe", c_eonet),
    ("aifs", "Open-Meteo forecast", "context", "Rain forecast for scenarios", c_aifs),
    ("glofas", "GloFAS river forecast", "context", "Flood site twin", c_glofas),
    ("noaa", "NOAA weather alerts", "context", "Official warnings (US)", c_noaa),
    ("water", "USGS river gauges", "context", "Flood site twin (US)", c_water),
    ("sda", "USDA soil survey", "context", "Soil detail at a point (US)", c_sda),
    ("3dep", "USGS 3DEP terrain", "context", "Flood site twin terrain (US)", c_3dep),
    ("firms", "NASA FIRMS fire data", "account", "Fire detections as data", c_firms),
    ("cesium", "Cesium ion", "account", "3D terrain and buildings", c_cesium),
    ("ai_provider", "SWELL AI provider", "account", "Live generative AI test (optional; provider-neutral)", c_ai_provider),
]


def run(lat=32.7767, lon=-96.7970, only=None) -> dict:
    load_env()

    def one(c):
        cid, name, group, use, fn = c; t = time.time()
        try: st, msg = "ok", fn(lat, lon)
        except LookupError as e: st, msg = "needs_key", str(e)
        except NoDataError as e: st, msg = "no_data", str(e)
        except NotTestedError as e: st, msg = "not_tested", str(e)
        except Exception as e:
            st, msg = "failed", f"{type(e).__name__}: {str(e)[:220]}"
            if isinstance(e, (urllib.error.URLError, TimeoutError)) and not isinstance(e, urllib.error.HTTPError):
                msg = "No answer from this server. Check your internet connection, VPN or firewall, then test again."
            for k in KEYS:                                                   # never echo a secret back, even inside an error
                v = os.environ.get(k)
                if v and v in msg: msg = msg.replace(v, "•••")
        return dict(id=cid, name=name, group=group, use=use, status=st, detail=msg, ms=int(1000 * (time.time() - t)))
    todo = [c for c in CHECKS if not only or c[0] in only]
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(one, todo))
    core_ok = all(r["status"] == "ok" for r in rows if r["group"] == "core")
    login_ok = next((r["status"] == "ok" for r in rows if r["id"] == "earthdata"), False)
    result = dict(checked_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), lat=lat, lon=lon, results=rows, keys_set=key_state(),
                  ready_for_real_twin=bool(core_ok and login_ok),
                  next_step=("Core public sources and Earthdata are reachable. This does NOT mean a study is loaded. Step 2: find compatible radar passes; step 3: build the real twin." if core_ok and login_ok else
                             "Public data services are reachable. Add your free NASA Earthdata login to download authenticated NISAR files." if core_ok else
                             "A required public data source failed or has no coverage. Read each row; a reachable catalogue with zero granules means choose another AOI/date, not change your key."),
                  note="A tick means the service answered just now. It is not scientific validation.")
    # Persist provider checks and boolean key-presence flags only; credential values are never stored here.
    try:
        out = ROOT / "out"; out.mkdir(exist_ok=True)
        (out / "connection_status.json").write_text(json.dumps(result, indent=2))
    except OSError:
        pass
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, default=32.7767); ap.add_argument("--lon", type=float, default=-96.7970); ap.add_argument("--setup", action="store_true")
    a = ap.parse_args()
    if a.setup:
        import getpass
        print("Press Enter to skip any line. Input is hidden and saved only to .env in this folder.")
        vals = {}
        for k, (label, _, hint) in KEYS.items():
            if k == "EARTHDATA_TOKEN" and vals.get("EARTHDATA_USERNAME"): continue
            v = (input if k == "EARTHDATA_USERNAME" else getpass.getpass)(f"{label} ({hint}): ").strip()
            if v: vals[k] = v
        print("Saved:", ", ".join(save_keys(vals)) or "nothing")
    out = run(a.lat, a.lon)
    mark = dict(ok="OK  ", failed="FAIL", needs_key="KEY ")
    for r in out["results"]:
        print(f"{mark[r['status']]} {r['name']:<30} {r['detail']}")
    print("\n" + out["next_step"])
    (ROOT / "connection-status.json").write_text(json.dumps(out, indent=1))
    print("Saved connection-status.json (contains no keys).")


if __name__ == "__main__":
    main()
