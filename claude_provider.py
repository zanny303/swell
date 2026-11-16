"""Optional server-side Claude copilot for SWELL.

The browser never receives ANTHROPIC_API_KEY. Claude gets a compact, provenance-labelled
site context and a small set of read-only/proposal-only tools. No tool can mutate a model,
approve a decision, or issue a field action.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import urllib.error
import urllib.request
from datetime import datetime, timezone

APP = pathlib.Path(__file__).resolve().parent
API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_API_VERSION = "2023-06-01"
MAX_TURNS = 3

SYSTEM = """You are SWELL Copilot, an evidence-grounded Earth-science decision assistant.

You help people understand the active site, distinguish observations from inferences and
scenarios, compare explanations, identify missing measurements, and prepare reviewable
interventions. You are not an engineering certifier or emergency authority.

NON-NEGOTIABLE RULES
- Use only facts in the supplied site context and tool results. If a fact is absent, say so.
- Distinguish observed, derived, inferred, forecast, scenario, and unavailable values.
- Never call a synthetic fixture a real satellite observation or real-site forecast.
- NISAR GUNW phase is not itself vertical displacement. Any vertical component is an
  inference and depends on geometry, reference choice, corrections, and assumptions.
- Training RMSE is a fit diagnostic, not a calibrated predictive interval. Sensitivity
  members are not probabilities. Never invent confidence percentages.
- Cite evidence IDs in square brackets, e.g. [SITE-METADATA], [CELL-r-c-p], [T1-GPS].
  If no evidence ID supports a quantitative claim, do not make the claim.
- When important evidence is missing, explain what is missing and the next measurement
  that would reduce uncertainty.
- You may use propose_scenario to create a DRAFT parameter proposal. It does not run the
  model and does not apply changes. Clearly state that a human must review and apply it.
- Never claim you changed the map, ran a simulation, approved an intervention, or verified
  a real-world outcome. Only the deterministic SWELL application can do those actions.
- Be concise, explicit about limitations, and useful to engineers, planners, utilities,
  scientists, field teams, and residents. Explain technical terms when needed."""


def configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def status() -> dict:
    return {
        "provider": "anthropic" if configured() else "deterministic",
        "configured": configured(),
        "model": os.environ.get("SWELL_CLAUDE_MODEL", DEFAULT_MODEL),
        "key_present": configured(),
        "api_version": os.environ.get("ANTHROPIC_API_VERSION", DEFAULT_API_VERSION),
        "server_side_key": True,
        "warning": None if configured() else "Claude is not connected. SWELL remains in deterministic evidence-retrieval mode.",
    }


def _finite(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _grid_value(site: dict, field: str, pass_index: int, row: int, col: int):
    arr = site.get(field)
    try:
        v = arr[pass_index][row][col] if field in ("observed_los", "inferred_motion", "inferred_sd", "artifact") else arr[row][col]
        return _finite(v)
    except (IndexError, TypeError):
        return None


def site_evidence(root: pathlib.Path, context: dict | None = None) -> dict:
    path = pathlib.Path(root) / "site" / "data" / "site.json"
    if not path.exists():
        return {"evidence_id": "SITE-METADATA", "available": False, "reason": "No site/data/site.json is loaded."}
    site = json.loads(path.read_text(encoding="utf-8"))
    source = str(site.get("source", "UNSPECIFIED"))
    synthetic = "SYNTH" in source.upper()
    tests = []
    for t in site.get("tests", [])[:20]:
        if not isinstance(t, dict):
            continue
        row = {k: t.get(k) for k in ("name", "passed", "n", "stations", "frame", "rms_naive_mm", "rms_swell_mm", "rmse_no_change", "rmse_rain_only", "rmse_swell", "coverage90", "mean_band_mm", "gain_vs_best_baseline") if k in t}
        tests.append(row)
    evidence = {
        "evidence_id": "SITE-METADATA",
        "available": True,
        "site": site.get("name"),
        "source_label": source,
        "synthetic_fixture": synthetic,
        "bbox_wsen": site.get("bbox"),
        "grid_shape": [site.get("n"), site.get("n")],
        "pass_count": len(site.get("pass_days", [])),
        "pass_days": site.get("pass_days", [])[:100],
        "incidence_angle_mean_deg": _finite(site.get("inc_deg")),
        "model_parameters": {k: _finite(v) for k, v in (site.get("params") or {}).items() if k in ("alpha", "b", "T", "tau", "rmse_train")},
        "validation_tests": tests,
        "unresolved_zone_count": sum(1 for z in site.get("zones", []) if z.get("status") != "ok"),
        "zone_count": len(site.get("zones", [])),
        "warnings": [
            "The source label controls whether this is real data or a synthetic software fixture.",
            "The inferred vertical-motion layer assumes negligible horizontal motion and is not direct vertical measurement.",
            "Training fit error and deterministic sensitivity are not calibrated forecast uncertainty.",
        ],
        "site_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    ctx = context if isinstance(context, dict) else {}
    cell = ctx.get("selected_cell") if isinstance(ctx.get("selected_cell"), dict) else None
    if cell:
        try:
            row, col = int(cell.get("row")), int(cell.get("col"))
            p = int(ctx.get("pass_index", len(site.get("observed_los", [])) - 1))
        except (TypeError, ValueError):
            row = col = p = -1
        n = int(site.get("n") or 0)
        if 0 <= row < n and 0 <= col < n and 0 <= p < len(site.get("observed_los", [])):
            w, s, e, north = site.get("bbox", [None] * 4)
            unresolved = bool((site.get("unresolved") or [[1] * n for _ in range(n)])[row][col])
            evidence["selected_cell"] = {
                "evidence_id": f"CELL-{row}-{col}-{p}",
                "row": row, "col": col, "pass_index": p,
                "latitude": north - (row + 0.5) * (north - s) / n,
                "longitude": w + (col + 0.5) * (e - w) / n,
                "unresolved": unresolved,
                "observed_los_mm": _grid_value(site, "observed_los", p, row, col),
                "inferred_vertical_mm": None if unresolved else _grid_value(site, "inferred_motion", p, row, col),
                "inferred_sd_mm": None if unresolved else _grid_value(site, "inferred_sd", p, row, col),
                "moisture_artifact_estimate_mm": _grid_value(site, "artifact", p, row, col),
                "coherence": _grid_value(site, "coh", p, row, col),
                "clay_proxy_pct": _grid_value(site, "lep", p, row, col),
                "paved_fraction": _grid_value(site, "paved", p, row, col),
            }
    return evidence


def _tool_definitions():
    return [
        {"name": "get_site_evidence", "description": "Read the active SWELL site metadata and validation evidence. Read-only.", "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
        {"name": "get_selected_cell_evidence", "description": "Read the active site evidence for one selected grid cell and acquisition pass. Read-only. Use only row, col, and pass_index from the user interface context.", "input_schema": {"type": "object", "properties": {"row": {"type": "integer", "minimum": 0}, "col": {"type": "integer", "minimum": 0}, "pass_index": {"type": "integer", "minimum": 0}}, "required": ["row", "col", "pass_index"], "additionalProperties": False}},
        {"name": "search_curated_research", "description": "Search SWELL's curated local science corpus. Returns source passages and URLs; it does not verify their applicability to this site.", "input_schema": {"type": "object", "properties": {"query": {"type": "string", "minLength": 3, "maxLength": 300}}, "required": ["query"], "additionalProperties": False}},
        {"name": "propose_scenario", "description": "Create a validated scenario proposal for a human to review. This tool does not apply inputs and does not run a model.", "input_schema": {"type": "object", "properties": {"rain_mm": {"type": "number", "minimum": 0, "maximum": 250}, "rain_days": {"type": "integer", "minimum": 1, "maximum": 14}, "dry_days": {"type": "integer", "minimum": 0, "maximum": 30}, "wetting_reduction": {"type": "number", "minimum": 0, "maximum": 0.8}, "paved_delta": {"type": "number", "minimum": 0, "maximum": 0.6}, "horizon_days": {"type": "integer", "minimum": 10, "maximum": 90}, "rationale": {"type": "string", "maxLength": 600}}, "required": ["rain_mm", "rain_days", "dry_days", "wetting_reduction", "paved_delta", "horizon_days", "rationale"], "additionalProperties": False}},
    ]


def _execute_tool(name: str, args: dict, root: pathlib.Path, context: dict | None):
    if name == "get_site_evidence":
        return site_evidence(root, context)
    if name == "get_selected_cell_evidence":
        cell_ctx = dict(context or {})
        cell_ctx["selected_cell"] = {"row": args.get("row"), "col": args.get("col")}
        cell_ctx["pass_index"] = args.get("pass_index")
        evidence = site_evidence(root, cell_ctx)
        if "selected_cell" not in evidence:
            return {"available": False, "reason": "Cell/pass is outside the loaded site or has no acquisition data."}
        return evidence["selected_cell"]
    if name == "search_curated_research":
        import literature_rag
        corpus = os.environ.get("SWELL_LITERATURE_CORPUS") or str(pathlib.Path(root) / "literature" / "corpus.json")
        sources = literature_rag.retrieve(args["query"], corpus)
        return {"evidence_id": "CURATED-RESEARCH", "sources": sources[:6], "status": "retrieved" if sources else "no_match"}
    if name == "propose_scenario":
        proposal = {
            "rainMm": float(args["rain_mm"]), "rainDays": int(args["rain_days"]),
            "dryDays": int(args["dry_days"]), "reduction": float(args["wetting_reduction"]),
            "pavedDelta": float(args["paved_delta"]), "horizon": int(args["horizon_days"]),
        }
        canonical = json.dumps(proposal, sort_keys=True, separators=(",", ":"))
        return {"evidence_id": "SCENARIO-PROPOSAL", "proposal_id": hashlib.sha256(canonical.encode()).hexdigest()[:16],
                "proposal": proposal, "rationale": str(args["rationale"])[:600], "status": "proposal_only",
                "requires_human_review": True, "model_run_started": False, "model_inputs_changed": False}
    raise ValueError("Tool is not permitted")


def ask(question: str, root: pathlib.Path, context: dict | None = None) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Claude is not configured. Add ANTHROPIC_API_KEY in Connections.")
    question = str(question or "").strip()
    if not question or len(question) > 1200:
        raise ValueError("Question must contain 1–1,200 characters.")
    model = os.environ.get("SWELL_CLAUDE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    api_version = os.environ.get("ANTHROPIC_API_VERSION", DEFAULT_API_VERSION).strip() or DEFAULT_API_VERSION
    ctx = context if isinstance(context, dict) else {}
    safe_ctx = {
        "role": str(ctx.get("role", "stakeholder"))[:40],
        "active_state": str(ctx.get("active_state", "unknown"))[:30],
        "horizon_days": _finite(ctx.get("horizon_days")),
        "pass_index": int(ctx.get("pass_index", 0)) if str(ctx.get("pass_index", "0")).lstrip("-").isdigit() else 0,
        "selected_cell": ({"row": int(ctx["selected_cell"]["row"]), "col": int(ctx["selected_cell"]["col"])}
                          if isinstance(ctx.get("selected_cell"), dict) and str(ctx["selected_cell"].get("row", "")).isdigit() and str(ctx["selected_cell"].get("col", "")).isdigit() else None),
        "scenario_summary": ctx.get("scenario_summary") if isinstance(ctx.get("scenario_summary"), dict) else None,
    }
    user_text = "ACTIVE SWELL WORKSPACE CONTEXT (client summary; site facts must be verified with tools):\n" + json.dumps(safe_ctx, ensure_ascii=False) + "\n\nUSER QUESTION:\n" + question
    messages = [{"role": "user", "content": user_text}]
    sources: list[dict] = []
    tool_events: list[dict] = []
    proposal = None
    usage = {"input_tokens": None, "output_tokens": None}
    last_text = ""

    for turn in range(MAX_TURNS):
        body = {"model": model, "max_tokens": 1500, "system": SYSTEM,
                "tools": _tool_definitions(), "messages": messages}
        req = urllib.request.Request(API_URL, data=json.dumps(body).encode("utf-8"), method="POST",
            headers={"content-type": "application/json", "x-api-key": key,
                     "anthropic-version": api_version, "user-agent": "SWELL/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=65) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read(1600).decode("utf-8", "replace")
            if exc.code in (401, 403):
                raise RuntimeError("Anthropic rejected the API key or its permissions. Recheck the key in Connections.") from exc
            if exc.code == 429:
                raise RuntimeError("Anthropic rate limit reached. Wait briefly and try again.") from exc
            raise RuntimeError(f"Anthropic API returned HTTP {exc.code}: {detail[:500]}") from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            raise RuntimeError(f"Could not reach Anthropic API: {exc}") from exc
        usage = payload.get("usage", usage)
        blocks = payload.get("content", [])
        text_parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        if text_parts:
            last_text = "\n".join(text_parts).strip()
        tool_calls = [b for b in blocks if b.get("type") == "tool_use"]
        if not tool_calls:
            break
        messages.append({"role": "assistant", "content": blocks})
        results = []
        for call in tool_calls:
            name, args = call.get("name"), call.get("input") or {}
            try:
                result = _execute_tool(name, args, pathlib.Path(root), safe_ctx)
                tool_events.append({"tool": name, "status": "ok"})
                if name == "search_curated_research":
                    for source in result.get("sources", []):
                        if isinstance(source, dict):
                            sources.append({"title": source.get("title", "Curated source"), "url": source.get("url"), "note": source.get("text", "")[:500]})
                if name == "propose_scenario" and result.get("status") == "proposal_only":
                    proposal = result
                content = json.dumps(result, ensure_ascii=False, default=str)
                is_error = False
            except Exception as exc:
                tool_events.append({"tool": str(name), "status": "error"})
                content = json.dumps({"error": str(exc)[:400]}, ensure_ascii=False)
                is_error = True
            results.append({"type": "tool_result", "tool_use_id": call.get("id"), "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": results})
    if not last_text:
        last_text = "I retrieved the requested evidence but could not produce a complete explanation. Please retry or inspect the source records directly."
    # Deduplicate source links and never return API credentials or raw request payloads.
    unique = []
    seen = set()
    for s in sources:
        k = s.get("url") or s.get("title")
        if k not in seen:
            seen.add(k); unique.append(s)
    return {"provider": "anthropic", "model": model, "answer": last_text,
            "sources": unique[:8], "proposal": proposal, "tool_events": tool_events,
            "usage": {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")},
            "warning": "Claude is an explanatory assistant, not a scientific validator. Quantitative results remain those of the cited site data and deterministic SWELL models."}
