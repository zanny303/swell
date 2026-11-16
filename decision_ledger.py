"""Append-only, hash-chained local decision ledger for SWELL stakeholder reviews.

This is a local prototype ledger, not authenticated multi-user governance. The HTTP write
route is restricted to loopback by run_swell.py. Records are never edited/deleted through
this module; corrections are new records.
"""
from __future__ import annotations
import hashlib, json, pathlib, sqlite3, uuid
from datetime import datetime, timezone

STATUSES = {"proposed", "reviewed", "approved_by_user", "rejected", "action_started", "verified"}
GENESIS = "0" * 64


def _db_path(root):
    p = pathlib.Path(root) / "out" / "decision_ledger.sqlite3"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect(root):
    con = sqlite3.connect(_db_path(root), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS decisions (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        id TEXT UNIQUE NOT NULL,
        created_at_utc TEXT NOT NULL,
        actor TEXT NOT NULL,
        role TEXT NOT NULL,
        site_name TEXT NOT NULL,
        site_source TEXT NOT NULL,
        synthetic INTEGER NOT NULL,
        status TEXT NOT NULL,
        decision TEXT NOT NULL,
        rationale TEXT NOT NULL,
        scenario_json TEXT NOT NULL,
        evidence_ids_json TEXT NOT NULL,
        location_json TEXT,
        prev_hash TEXT NOT NULL,
        record_hash TEXT NOT NULL
    )""")
    cols = {r[1] for r in con.execute("PRAGMA table_info(decisions)").fetchall()}
    if "location_json" not in cols:
        con.execute("ALTER TABLE decisions ADD COLUMN location_json TEXT")
    con.commit()
    return con


def _canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _clean_scenario(value):
    if not isinstance(value, dict):
        return {}
    allowed = ("id", "name", "engine", "model_version", "horizon_days", "forcing_key", "changed_cells", "inputs", "metrics", "uncertainty", "selected_cell", "focus")
    out = {k: value[k] for k in allowed if k in value}
    # Deliberately exclude full grid arrays and uploaded files from the audit DB.
    if len(json.dumps(out, default=str)) > 12000:
        raise ValueError("Scenario summary is too large; export the full scenario separately.")
    return out


def append(payload: dict, root) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Decision record must be an object.")
    actor = str(payload.get("actor", "")).strip()[:100]
    role = str(payload.get("role", "stakeholder")).strip()[:40]
    status = str(payload.get("status", "proposed")).strip()
    decision = str(payload.get("decision", "")).strip()[:160]
    rationale = str(payload.get("rationale", "")).strip()[:4000]
    if not actor:
        raise ValueError("Enter the reviewer or stakeholder name/team.")
    if status not in STATUSES:
        raise ValueError("Unsupported decision status.")
    if not decision:
        raise ValueError("Enter the decision or next action.")
    if not rationale:
        raise ValueError("Enter the rationale and evidence considered.")
    evidence = payload.get("evidence_ids", [])
    if not isinstance(evidence, list) or len(evidence) > 50:
        raise ValueError("Evidence IDs must be a list of at most 50 items.")
    evidence = [str(x).strip()[:120] for x in evidence if str(x).strip()][:50]
    scenario = _clean_scenario(payload.get("scenario"))
    location = payload.get("location")
    if location is not None:
        if not isinstance(location, dict):
            raise ValueError("Decision location must be an object.")
        try:
            lat, lon = float(location["lat"]), float(location["lon"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Decision location needs numeric latitude and longitude.")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Decision location is outside valid geographic bounds.")
        location = {"lat": lat, "lon": lon}
        for key in ("row", "col", "zone"):
            if key in payload.get("location", {}):
                location[key] = payload["location"][key]
    site_path = pathlib.Path(root) / "site" / "data" / "site.json"
    if site_path.exists():
        site = json.loads(site_path.read_text(encoding="utf-8"))
        site_name = str(site.get("name", "Unknown site"))[:180]
        site_source = str(site.get("source", "UNSPECIFIED"))[:240]
    else:
        site_name, site_source = "No active site", "UNAVAILABLE"
    synthetic = "SYNTH" in site_source.upper()
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {
        "id": str(uuid.uuid4()), "created_at_utc": created, "actor": actor, "role": role,
        "site_name": site_name, "site_source": site_source, "synthetic": synthetic,
        "status": status, "decision": decision, "rationale": rationale,
        "scenario": scenario, "evidence_ids": evidence,
    }
    if location is not None:
        record["location"] = location
    con = _connect(root)
    try:
        con.execute("BEGIN IMMEDIATE")
        prev = con.execute("SELECT record_hash FROM decisions ORDER BY sequence DESC LIMIT 1").fetchone()
        prev_hash = prev["record_hash"] if prev else GENESIS
        digest = hashlib.sha256((prev_hash + _canonical(record)).encode("utf-8")).hexdigest()
        con.execute("""INSERT INTO decisions
            (id,created_at_utc,actor,role,site_name,site_source,synthetic,status,decision,rationale,scenario_json,evidence_ids_json,location_json,prev_hash,record_hash)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (record["id"], created, actor, role, site_name, site_source, int(synthetic), status, decision, rationale,
             _canonical(scenario), _canonical(evidence), _canonical(location) if location is not None else None, prev_hash, digest))
        con.commit()
        return {**record, "sequence": con.execute("SELECT sequence FROM decisions WHERE id=?", (record["id"],)).fetchone()[0],
                "prev_hash": prev_hash, "record_hash": digest, "ledger": "local_append_only_hash_chain",
                "professional_approval": False}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def list_records(root, site_name=None, limit=50):
    limit = max(1, min(100, int(limit)))
    con = _connect(root)
    try:
        if site_name:
            rows = con.execute("SELECT * FROM decisions WHERE site_name=? ORDER BY sequence DESC LIMIT ?", (str(site_name)[:180], limit)).fetchall()
        else:
            rows = con.execute("SELECT * FROM decisions ORDER BY sequence DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            x = dict(r)
            x["scenario"] = json.loads(x.pop("scenario_json"))
            x["evidence_ids"] = json.loads(x.pop("evidence_ids_json"))
            location_raw = x.pop("location_json", None)
            x["location"] = json.loads(location_raw) if location_raw else None
            x["synthetic"] = bool(x["synthetic"])
            x["professional_approval"] = False
            out.append(x)
        return out
    finally:
        con.close()


def verify(root):
    con = _connect(root)
    try:
        rows = con.execute("SELECT * FROM decisions ORDER BY sequence ASC").fetchall()
        previous = GENESIS
        for row in rows:
            r = dict(row)
            record = {"id": r["id"], "created_at_utc": r["created_at_utc"], "actor": r["actor"], "role": r["role"],
                "site_name": r["site_name"], "site_source": r["site_source"], "synthetic": bool(r["synthetic"]),
                "status": r["status"], "decision": r["decision"], "rationale": r["rationale"],
                "scenario": json.loads(r["scenario_json"]), "evidence_ids": json.loads(r["evidence_ids_json"])}
            if r.get("location_json"):
                record["location"] = json.loads(r["location_json"])
            expected = hashlib.sha256((previous + _canonical(record)).encode("utf-8")).hexdigest()
            if r["prev_hash"] != previous or r["record_hash"] != expected:
                return {"valid": False, "records_checked": int(r["sequence"]), "failed_sequence": int(r["sequence"]), "reason": "Hash-chain mismatch"}
            previous = r["record_hash"]
        return {"valid": True, "records_checked": len(rows), "head_hash": previous, "ledger": "local_append_only_hash_chain",
                "note": "Tamper-evident integrity check, not a digital signature or proof of author identity."}
    finally:
        con.close()
