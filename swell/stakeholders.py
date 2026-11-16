"""Stakeholder action plans and the files each can take into their own tools. Same evidence, different decisions.

Wording rules: values are ESTIMATES from an artifact-corrected radar model, never "measured movement".
"Vertical" assumes no horizontal motion. Cells are ~80 m: zones, not buildings. Nothing here prescribes a design.
Every file carries its data source, model version, SHA-256, approval field and the day its outcome is checked.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import numpy as np

from . import contracts as C
from . import fit as F

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
CAP_REQUIRED = ["identifier", "sender", "sent", "status", "msgType", "scope"]
CAP_INFO_REQUIRED = ["category", "event", "urgency", "severity", "certainty"]


def cell_centers(site: dict):
    x0, y0, x1, y1 = site["bbox"]
    n = site["n"]
    return x0 + (np.arange(n) + .5) * (x1 - x0) / n, y1 - (np.arange(n) + .5) * (y1 - y0) / n


def zones(site: dict, k: int = 8) -> list[dict]:
    n = site["n"]
    return [dict(name=f"Z{a}{b}", cells=[(ii, jj) for ii in range(i, min(i + k, n)) for jj in range(j, min(j + k, n))])
            for a, i in enumerate(range(0, n, k)) for b, j in enumerate(range(0, n, k))]


def zone_table(site: dict, fr: dict, drying_mm: np.ndarray, storm_mm: np.ndarray) -> list[dict]:
    """One row per zone: what was estimated, how sure, and what two scenarios add."""
    lon, lat = cell_centers(site)
    amp = np.nanpercentile(fr["mcorr"], 95, 0) - np.nanpercentile(fr["mcorr"], 5, 0)
    unc = np.nanstd(np.diff(fr["mcorr"], axis=0), axis=0) / np.sqrt(2)
    ok = F.masks(site)["ok"]
    x0, y0, x1, y1 = site["bbox"]; n = site["n"]; dx, dy = (x1 - x0) / n, (y1 - y0) / n
    rows = []
    for z in zones(site):
        ii, jj = map(np.array, zip(*z["cells"]))
        good = ok[ii, jj] & np.isfinite(amp[ii, jj])
        box = [round(float(x0 + jj.min() * dx), 5), round(float(y1 - (ii.max() + 1) * dy), 5),
               round(float(x0 + (jj.max() + 1) * dx), 5), round(float(y1 - ii.min() * dy), 5)]
        if good.sum() < max(5, len(ii) // 4):
            rows.append(dict(zone=z["name"], status="UNRESOLVED", bbox=box, valid_cells=int(good.sum()))); continue
        a = amp[ii, jj][good]
        rows.append(dict(zone=z["name"], status="ok", bbox=box, lon=round(float(lon[jj].mean()), 5), lat=round(float(lat[ii].mean()), 5),
                         valid_cells=int(good.sum()),
                         est_seasonal_vertical_mm=round(float(a.mean()), 1),
                         est_within_zone_spread_mm=round(float(np.percentile(a, 90) - np.percentile(a, 10)), 1),
                         uncertainty_mm=round(float(np.nanmean(unc[ii, jj][good])), 1),
                         further_30_dry_days_mm=round(float(np.nanmean(drying_mm[ii, jj][good])), 1),
                         storm_75mm_mm=round(float(np.nanmean(storm_mm[ii, jj][good])), 1),
                         shrink_swell_rating_pct=round(float(site["lep"][ii, jj].mean()), 1),
                         paved_fraction=round(float(site["paved"][ii, jj].mean()), 2),
                         mean_coherence=round(float(site["coh"][ii, jj].mean()), 2)))
    # Heuristic "observe next" priority, not a formal value-of-information calculation.
    # Unresolved zones come first; among resolved zones, combine estimated movement
    # amplitude with uncertainty so large-but-poorly-known areas are revisited.
    for r in rows:
        if r["status"] != "ok":
            r["observe_next_score"] = None
            r["observe_next_reason"] = "UNRESOLVED: another valid acquisition or ground survey needed"
        else:
            r["observe_next_score"] = round(r["est_seasonal_vertical_mm"] * r["uncertainty_mm"], 2)
            r["observe_next_reason"] = "Heuristic movement × uncertainty score; not a formal information-gain estimate"
    return sorted(rows, key=lambda r: (r["status"] == "ok", -(r.get("observe_next_score") or 0)))


def validate_cap(xml_text: str) -> list[str]:
    """Structural check against the CAP 1.2 required elements. Not a full schema validation."""
    root = ET.fromstring(xml_text)
    q = lambda t: f"{{{CAP_NS}}}{t}"
    problems = [] if root.tag == q("alert") else ["root is not cap:alert"]
    problems += [f"missing {t}" for t in CAP_REQUIRED if root.find(q(t)) is None]
    info = root.find(q("info"))
    problems += ["missing info"] if info is None else [f"missing info/{t}" for t in CAP_INFO_REQUIRED if info.find(q(t)) is None]
    if root.findtext(q("scope")) == "Restricted" and root.find(q("restriction")) is None:
        problems.append("scope Restricted needs restriction")
    return problems


def _meta(text: str, site, model_version, check_day) -> dict:
    return dict(sha256=hashlib.sha256(text.encode()).hexdigest(), source=site["source"], model_version=model_version,
                outcome_check_day=int(check_day), approval="PENDING: named human approval required", safety=C.SAFETY,
                meaning="Estimates from an artifact-corrected radar model at ~80 m. 'Vertical' assumes no horizontal motion.")


def build(site: dict, fr: dict, table: list[dict], next_check_day: int, model_version: str) -> dict:
    """Returns {filename: text}."""
    ok_rows = [r for r in table if r["status"] == "ok"]
    files = {}
    M = lambda t: _meta(t, site, model_version, next_check_day)

    # Engineer: inputs for a geotechnical investigation. No foundation type is suggested.
    keys = ["zone", "status", "lon", "lat", "valid_cells", "est_seasonal_vertical_mm", "est_within_zone_spread_mm", "uncertainty_mm",
            "further_30_dry_days_mm", "storm_75mm_mm", "shrink_swell_rating_pct", "paved_fraction", "mean_coherence"]
    buf = io.StringIO(); w = csv.DictWriter(buf, keys); w.writeheader(); [w.writerow({k: r.get(k, "") for k in keys}) for r in table]
    files["engineer_investigation_inputs.csv"] = buf.getvalue()
    files["engineer_investigation_inputs.json"] = json.dumps(dict(meta=M(buf.getvalue()), use=(
        "Where to send a geotechnical investigation first, and what movement range to test for. Confirm with borings, "
        "lab swell tests and a level survey. This file does not suggest a foundation type."), zones=table), indent=1)

    # Planner: zone polygons for GIS, with every number attached
    feats = [dict(type="Feature", geometry=dict(type="Polygon", coordinates=[[[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]], [b[0], b[1]]]]),
                  properties={k: v for k, v in r.items() if k != "bbox"}) for r in table for b in [r["bbox"]]]
    txt = json.dumps(feats)
    files["planner_zones.geojson"] = json.dumps(dict(type="FeatureCollection", meta=M(txt), use=(
        "Overlay on your road, parcel and permit layers. UNRESOLVED zones need another observation, not a decision."), features=feats))

    # Utility: inspection candidates. asset_id is blank until joined with the utility's own pipe inventory.
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["priority", "zone", "west", "south", "east", "north", "asset_id", "task", "evidence", "check_by_day", "approval", "outcome"])
    for k, r in enumerate(ok_rows[:10], 1):
        w.writerow([k, r["zone"], *r["bbox"], "", "Inspect mains, valves and pavement joints in this box",
                    f"est. {r['est_seasonal_vertical_mm']} mm seasonal, spread {r['est_within_zone_spread_mm']} mm, +/-{r['uncertainty_mm']} mm",
                    next_check_day, "PENDING", ""])
    files["utility_inspection_candidates.csv"] = buf.getvalue()

    # Emergency manager: CAP 1.2 draft, structurally checked, never issued by SWELL
    top = ", ".join(r["zone"] for r in ok_rows[:3])
    sent = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    cap = f"""<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="{CAP_NS}">
  <identifier>SWELL-DRAFT-{next_check_day}</identifier>
  <sender>swell-twin@example.invalid</sender>
  <sent>{sent}</sent>
  <status>Draft</status>
  <msgType>Alert</msgType>
  <scope>Restricted</scope>
  <restriction>Draft for human review. Not issued. Approval: PENDING.</restriction>
  <info>
    <category>Geo</category>
    <event>Ground movement inspection priority</event>
    <urgency>Future</urgency>
    <severity>Unknown</severity>
    <certainty>Possible</certainty>
    <headline>Inspection suggested in zones {top} ({site['source'][:40]})</headline>
    <description>Model-estimated seasonal clay movement is highest in these zones. {C.SAFETY}</description>
  </info>
</alert>
"""
    problems = validate_cap(cap)
    if problems:
        raise ValueError(f"CAP draft invalid: {problems}")
    files["emergency_draft_alert.cap.xml"] = cap

    # Farmer / land manager: where wetness-driven movement is largest on open ground. No watering schedule:
    # that needs crop, soil and local agronomy SWELL does not have.
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["zone", "lon", "lat", "paved_fraction", "est_seasonal_vertical_mm", "storm_75mm_mm", "further_30_dry_days_mm", "note"])
    for r in [r for r in ok_rows if r["paved_fraction"] < .3][:15]:
        w.writerow([r["zone"], r["lon"], r["lat"], r["paved_fraction"], r["est_seasonal_vertical_mm"], r["storm_75mm_mm"],
                    r["further_30_dry_days_mm"], "Open ground with large moisture-driven movement: expect cracking when dry. Take to your agronomist."])
    files["land_manager_open_ground.csv"] = buf.getvalue()

    amps = [r["est_seasonal_vertical_mm"] for r in ok_rows]
    files["resident_summary.txt"] = (
        f"SWELL summary  (data: {site['source'][:60]})\n\n"
        f"What we estimated: across this area the ground rose and sank by about {np.mean(amps):.0f} mm over the season.\n"
        f"The most affected zones: about {np.max(amps):.0f} mm. Typical uncertainty: +/-{np.mean([r['uncertainty_mm'] for r in ok_rows]):.0f} mm.\n"
        f"{sum(r['status'] != 'ok' for r in table)} of {len(table)} zones could not be resolved and need another satellite pass.\n\n"
        "What this is: radar measurements from space at about 80 m, corrected for a known moisture effect.\n"
        "What this is not: a statement about your building. It describes neighbourhoods.\n"
        "Why it happens: clay soil shrinks as it dries and swells when it gets wet again.\n"
        "What to do: if you see new cracks or sticking doors, ask a licensed foundation engineer.\n\n" + C.SAFETY + "\n")
    # Scientist / field team: blank, pre-measurement tray experiment log.
    # This is a protocol template, not a claim that an experiment was performed.
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["experiment_id", "tray_id", "treatment", "randomization_block", "soil_source", "soil_classification",
                "dry_mass_kg", "bulk_density_kg_m3", "initial_moisture_pct", "water_added_ml", "elapsed_hours",
                "surface_elevation_mm", "moisture_depth_cm", "moisture_pct", "temperature_c", "load_kg",
                "photo_file", "operator", "deviation_notes"])
    for k in range(1, 13):
        w.writerow(["", f"T{k:02d}", "CONTROL_OR_TREATMENT", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
    files["tray_experiment_log_template.csv"] = buf.getvalue()
    files["observe_next_priority.csv"] = _observe_next_csv(table)

    return files


def _observe_next_csv(table):
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["priority", "zone", "status", "score", "reason", "valid_cells", "estimated_movement_mm", "uncertainty_mm", "west", "south", "east", "north"])
    for rank, r in enumerate(table, 1):
        w.writerow([rank, r["zone"], r["status"], r.get("observe_next_score", ""),
                    r.get("observe_next_reason", ""), r.get("valid_cells", ""),
                    r.get("est_seasonal_vertical_mm", ""), r.get("uncertainty_mm", ""), *r["bbox"]])
    return buf.getvalue()
