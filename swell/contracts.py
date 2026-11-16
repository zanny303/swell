"""Action contracts: a recommendation is incomplete until it names what the next observation should show.

A contract is written BEFORE the observation, hashed, and later judged: supported / contradicted / inconclusive.
SWELL recommends and verifies. It does not control the ground and it does not certify structures.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np

from . import fit as F

SAFETY = "Decision support only. Not a structural or safety certification. Needs review by a qualified professional."


def _digest(d: dict) -> str:
    body = {k: v for k, v in d.items() if k not in ("digest", "arrival")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def make(site: dict, zone: dict, forecast: dict, stakeholder: str, action: str, evidence: list[str],
         competing: str, model_version: str, zone_sigma: float | None = None) -> dict:
    """zone = dict(name, cells=[(i, j), ...]). The expectation is the zone-mean forecast and its 90% band."""
    ii, jj = zip(*zone["cells"])
    mu = float(np.nanmean(forecast["mean"][ii, jj]))
    # Zone-mean errors are spatially correlated, so the band does NOT shrink with the number of cells.
    # zone_sigma = spread of zone-mean model errors on earlier passes (supplied by the caller, from training data only).
    band = float(1.645 * zone_sigma) if zone_sigma else float(np.nanmean(forecast["band"][ii, jj]))
    c = dict(id=f"{site['name'][:3].upper()}-{zone['name']}-d{forecast['day']}", source=site["source"],
             stakeholder=stakeholder, zone=zone["name"], n_cells=len(ii), proposed_action=action, evidence=evidence,
             state=f"Model expects {mu:+.1f} mm estimated vertical change (relative to first pass) by day {forecast['day']}",
             competing_explanation=competing,
             expected_observable=dict(day=int(forecast["day"]), mean_mm=mu, band90_mm=band),
             model_version=model_version, safety=SAFETY, approval="PENDING (named human approval required)",
             made_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), arrival="pending")
    c["digest"] = _digest(c)
    return c


def judge(c: dict, site: dict, observed_motion: np.ndarray, zone: dict) -> dict:
    """Arrival check. Raises if the contract was edited after it was made."""
    if _digest(c) != c["digest"]:
        raise ValueError("contract changed after it was made")
    ii, jj = zip(*zone["cells"])
    out = dict(c)
    if float(site["coh"][ii, jj].mean()) < F.MIN_COH:
        out["arrival"] = "inconclusive"; out["arrival_note"] = "coherence too low in this zone"
        return out
    vals = observed_motion[ii, jj]
    if np.isfinite(vals).mean() < 0.5:
        out["arrival"] = "inconclusive"; out["arrival_note"] = "more than half the zone has no valid observation"
        return out
    obs = float(np.nanmean(vals))
    exp = c["expected_observable"]
    out["observed_mm"] = obs
    out["arrival"] = "supported" if abs(obs - exp["mean_mm"]) <= exp["band90_mm"] else "contradicted"
    return out
