"""Small, public NASA CMR discovery adapter for NISAR GUNW granules.

Discovery is public; reading/downloading protected assets still requires NASA Earthdata
credentials. Results retain collection maturity and product identity to prevent silent mixing.
"""
from __future__ import annotations
import json, re, urllib.parse, urllib.request
from datetime import datetime, timezone

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
COLLECTIONS = (
    ("NISAR_L2_GUNW_V1", "VALIDATED"),
    ("NISAR_L2_GUNW_PROVISIONAL_V1", "PROVISIONAL"),
    ("NISAR_L2_GUNW_BETA_V1", "BETA"),
)
UA = {"User-Agent": "SWELL-Earth-Decision-Twin/1.0", "Accept": "application/json"}


def _data_link(entry):
    for link in entry.get("links", []) or []:
        href = str(link.get("href", ""))
        rel = str(link.get("rel", "")).lower()
        title = str(link.get("title", "")).lower()
        if not href.startswith("https://"):
            continue
        if any(x in rel or x in title for x in ("metadata", "browse", "opendap", "s3 access")):
            continue
        if re.search(r"\.h5(?:$|\?)", href, re.I):
            return href
    return None


def search_nisar_gunw(bbox, start="2025-08-01", end=None, limit=40, timeout=30):
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise ValueError("bbox must be [west,south,east,north].")
    w, s, e, n = [float(x) for x in bbox]
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90) or e-w > 2 or n-s > 2:
        raise ValueError("Use a valid study box no wider than 2 degrees in either direction.")
    if end is None:
        end = datetime.now(timezone.utc).date().isoformat()
    # Validate ISO dates before passing them to CMR.
    from datetime import date
    date.fromisoformat(start); date.fromisoformat(end)
    if start > end:
        raise ValueError("start must be on or before end.")
    limit = max(1, min(100, int(limit)))
    all_rows, totals, errors = [], {}, []
    for short_name, maturity in COLLECTIONS:
        query = {
            "short_name": short_name,
            "bounding_box": ",".join(f"{x:.6f}" for x in (w, s, e, n)),
            "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z",
            "page_size": limit,
            "sort_key[]": "-start_date",
        }
        url = CMR + "?" + urllib.parse.urlencode(query)
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read(8_000_000)
                headers = {k.lower(): v for k, v in response.headers.items()}
            data = json.loads(raw.decode("utf-8"))
            feed = data.get("feed") or {}
            totals[maturity] = int(headers.get("cmr-hits", feed.get("hits", 0)) or 0)
            for entry in feed.get("entry", []) or []:
                name = str(entry.get("producer_granule_id") or entry.get("title") or "")
                dates = re.findall(r"(\d{8})T\d{6}", name)
                maturity_name = maturity
                row = {
                    "id": entry.get("id"),
                    "granule_id": entry.get("producer_granule_id") or entry.get("title"),
                    "short_name": short_name,
                    "maturity": maturity_name,
                    "time_start": entry.get("time_start"),
                    "time_end": entry.get("time_end"),
                    "updated": entry.get("updated"),
                    "orbit_number": entry.get("orbit_number"),
                    "track": entry.get("track_number"),
                    "frame": entry.get("frame_number"),
                    "size_mb": float(entry.get("granule_size") or 0),
                    "hdf5_url": _data_link(entry),
                    "pair_dates_from_name": dates[:4],
                }
                all_rows.append(row)
        except Exception as exc:
            errors.append({"collection": short_name, "error": f"{type(exc).__name__}: {str(exc)[:240]}"})
            totals[maturity] = None
    all_rows.sort(key=lambda r: (r.get("time_end") or "", {"VALIDATED": 0, "PROVISIONAL": 1, "BETA": 2}.get(r["maturity"], 3)))
    return {
        "provider": "NASA Common Metadata Repository (CMR)",
        "product": "NISAR L2 GUNW",
        "bbox_wsen": [w, s, e, n], "start": start, "end": end,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_hits_by_maturity": totals,
        "records": all_rows,
        "errors": errors,
        "discovery_only": True,
        "download_requires_earthdata": True,
        "warning": "Do not combine BETA, PROVISIONAL and VALIDATED products in one time series without a documented reprocessing/compatibility strategy. GUNW is line-of-sight interferometric phase evidence, not direct vertical displacement.",
    }
