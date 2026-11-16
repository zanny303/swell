"""Independent-holdout verification and split-conformal interval calibration.

Consumes archived, time-stamped forecasts and later observations for one site and one fixed
lead. It does not fit a forecast model and never fabricates history. The reported interval is
empirical calibration from the supplied archive; temporal dependence and regime shifts can
invalidate exchangeability assumptions, so the output is not a safety probability.
"""
from __future__ import annotations
import csv, datetime as dt, io, math, hashlib
import numpy as np

REQUIRED = ("issue_utc", "target_utc", "observed", "forecast")


def _time(value, field):
    try:
        x = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp with timezone.") from exc
    if x.tzinfo is None:
        raise ValueError(f"{field} must include a timezone.")
    return x.astimezone(dt.timezone.utc)


def calibrate(raw: bytes, nominal: float = 0.90):
    if not 0.5 < float(nominal) < 0.99:
        raise ValueError("Nominal interval coverage must be between 0.5 and 0.99.")
    try:
        text = raw.decode("utf-8-sig") if isinstance(raw, (bytes, bytearray)) else str(raw)
        rows = list(csv.DictReader(io.StringIO(text)))
    except Exception as exc:
        raise ValueError("Could not parse forecast archive CSV.") from exc
    if len(rows) < 100 or len(rows) > 50000:
        raise ValueError("Provide 100–50,000 archived forecasts for one site and one fixed lead.")
    if not rows or any(k not in (rows[0] or {}) for k in REQUIRED):
        raise ValueError("CSV must contain issue_utc,target_utc,observed,forecast; optional site_id,lead_hours,model_version,source.")
    issues, targets, observed, forecast = [], [], [], []
    for i, r in enumerate(rows, 1):
        issues.append(_time(r["issue_utc"], f"row {i} issue_utc"))
        targets.append(_time(r["target_utc"], f"row {i} target_utc"))
        try:
            observed.append(float(r["observed"])); forecast.append(float(r["forecast"]))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"row {i} observed and forecast must be numeric.") from exc
    if any(t <= i for i, t in zip(issues, targets)):
        raise ValueError("Every target time must be later than its forecast issue time.")
    if any(a >= b for a, b in zip(issues, issues[1:])):
        raise ValueError("Forecast issue times must be strictly increasing with no duplicates.")
    leads = [(t - i).total_seconds() for i, t in zip(issues, targets)]
    if max(leads) - min(leads) > 1:
        raise ValueError("Use one fixed forecast lead; mixed leads must be calibrated separately.")
    obs, fc = np.asarray(observed, dtype=float), np.asarray(forecast, dtype=float)
    if not np.isfinite(obs).all() or not np.isfinite(fc).all():
        raise ValueError("Missing or non-finite forecast/observation values are not allowed in the calibration archive.")
    if len({str(r.get("site_id", "unspecified")).strip() for r in rows}) != 1:
        raise ValueError("Calibrate one site at a time; do not mix site IDs.")
    if len({str(r.get("model_version", "unspecified")).strip() for r in rows}) != 1:
        raise ValueError("Calibrate one model version at a time.")
    if len({str(r.get("source", "unspecified")).strip() for r in rows}) != 1:
        raise ValueError("Calibrate one forecast source at a time.")

    n = len(rows)
    train_end, cal_end = int(math.floor(.60 * n)), int(math.floor(.80 * n))
    cal_idx = np.arange(train_end, cal_end)
    test_idx = np.arange(cal_end, n)
    if len(cal_idx) < 20 or len(test_idx) < 20:
        raise ValueError("Need at least 20 calibration rows and 20 final holdout rows.")
    residual_cal = np.abs(obs[cal_idx] - fc[cal_idx])
    # Finite-sample split-conformal order statistic; never use the final holdout to tune q.
    rank = min(len(residual_cal), max(1, int(math.ceil((len(residual_cal) + 1) * float(nominal)))))
    q = float(np.sort(residual_cal)[rank - 1])
    err = fc[test_idx] - obs[test_idx]
    covered = np.abs(err) <= q
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    bias = float(np.mean(err))
    raw_bytes = raw if isinstance(raw, (bytes, bytearray)) else text.encode("utf-8")
    return {
        "method": "chronological split-conformal absolute-error interval",
        "nominal_coverage": float(nominal),
        "calibration_quantile_abs_error": q,
        "interval_lower_rule": "forecast - calibration_quantile_abs_error",
        "interval_upper_rule": "forecast + calibration_quantile_abs_error",
        "holdout_empirical_coverage": float(np.mean(covered)),
        "holdout_mean_interval_width": float(2 * q),
        "holdout_mae": mae, "holdout_rmse": rmse, "holdout_bias_forecast_minus_observed": bias,
        "training_archive_rows_excluded_from_calibration": int(train_end),
        "calibration_rows": int(len(cal_idx)), "holdout_rows": int(len(test_idx)),
        "calibration_period_utc": [issues[cal_idx[0]].isoformat(), targets[cal_idx[-1]].isoformat()],
        "holdout_period_utc": [issues[test_idx[0]].isoformat(), targets[test_idx[-1]].isoformat()],
        "forecast_lead_seconds": float(np.mean(leads)),
        "site_id": str(rows[0].get("site_id", "unspecified")),
        "model_version": str(rows[0].get("model_version", "unspecified")),
        "source": str(rows[0].get("source", "unspecified")),
        "archive_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "calibration_status": "empirical holdout evaluation; conditional calibration not established",
        "probability_claim_allowed": False,
        "limitations": [
            "Requires genuine archived forecasts and later independent observations; do not use synthetic fixtures for a scientific claim.",
            "Chronological split reduces leakage but does not remove serial dependence, spatial dependence, regime shift, or event clustering.",
            "Coverage is pooled for this site, model version, source, and fixed lead; it is not a per-pixel probability guarantee.",
            "This module calibrates interval width only. It does not improve the underlying forecast point prediction.",
        ],
    }
