"""Sister cities: compare sites by how their ground behaves, not where they are.

A site's signature = (gain per unit clay rating, relaxation time, delay, artifact strength, artifact share).
Only sites that PASSED their tests should be compared; `sisters` enforces that.
"""
from __future__ import annotations

import numpy as np

from . import fit as F

KEYS = ("gain_per_lep", "T", "tau", "beta", "artifact_share")


def signature(site: dict, fr: dict) -> dict:
    ok = F.masks(site)["ok"]
    from .stats import _amp
    naive, corr = np.nanmean(_amp(fr["naive"])[ok]), np.nanmean(_amp(fr["mcorr"])[ok])
    return dict(gain_per_lep=float(fr["par"]["alpha"]), T=float(fr["par"]["T"]), tau=float(fr["par"]["tau"]),
                beta=float(fr["beta"]), artifact_share=float(max(naive - corr, 0) / max(naive, 1e-9)))


def eligible(result: dict) -> tuple[bool, str]:
    """Require a real, validated run with at least one passed test and no failed tests."""
    if not isinstance(result, dict):
        return False, "result is not an object"
    if "SYNTH" in str(result.get("source", "")).upper():
        return False, "synthetic fixture"
    tests = result.get("tests")
    if not isinstance(tests, list) or not tests:
        return False, "missing validation tests"
    if any(not isinstance(t, dict) or t.get("passed") is False for t in tests):
        return False, "one or more validation tests failed"
    if not any(t.get("passed") is True for t in tests):
        return False, "no validation test has passed"
    signature = result.get("signature")
    if not isinstance(signature, dict):
        return False, "missing physical signature"
    for key in KEYS:
        try:
            value = float(signature[key])
        except (KeyError, TypeError, ValueError):
            return False, f"missing numeric signature field: {key}"
        if not np.isfinite(value):
            return False, f"non-finite signature field: {key}"
    return True, "eligible"


def sisters(results: dict[str, dict]) -> dict[str, list]:
    """Rank real validated sites by standardized physical-signature distance.

    This is a descriptive similarity screen, not proof of causal equivalence or
    transferability. Every site must have at least one passed validation test and
    no failed validation tests.
    """
    ok = {k: v for k, v in results.items() if eligible(v)[0]}
    if len(ok) < 2:
        return {}
    names = list(ok)
    X = np.array([[ok[n]["signature"][k] for k in KEYS] for n in names], dtype=float)
    Z = (X - X.mean(0)) / np.where(X.std(0) > 0, X.std(0), 1)
    D = np.sqrt(((Z[:, None] - Z[None]) ** 2).sum(-1))
    return {n: [dict(site=names[j], distance=float(D[i, j])) for j in np.argsort(D[i]) if j != i] for i, n in enumerate(names)}
