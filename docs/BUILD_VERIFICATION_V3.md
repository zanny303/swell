# SWELL v3 build verification

Date: 2026-11-15

## Automated checks

- Python test suite: **93 passed**.
- Python syntax compilation: `run_swell.py`, `connections.py`, `ai_provider.py`, `decision_ledger.py`, `literature_rag.py` compile.
- JavaScript syntax: `site/studio.js`, `site/ai-copilot.js`, and inline Connections-page JavaScript pass `node --check`.
- HTTP smoke test: `/api/system/health`, `/api/ai/status`, `/api/real-site/status`, and `/connections.html` returned HTTP 200 from the local server.
- Provider adapters: unit-tested with mocked responses; no real API credentials were used.
- Synthetic evidence protection: unit-tested to ensure numeric fixture fields and selected-cell/scenario context are excluded from generative AI requests.
- Decision ledger: unit-tested with geospatial locations, map-pin metadata, migration-safe schema, and hash verification.\n- Research map insights: code-gated to non-synthetic sites and zones with `status=ok`; pins label outputs as model-derived heuristics rather than observations.
- RAG: local BM25 retrieval smoke-tested against the bundled corpus and returned evidence IDs, source URLs, hashes, offsets and scores.

## Not run

- No live provider account was available for real AI generation.
- No live NASA Earthdata-authenticated NISAR download or real-site build was run.
- No external scientific validation against GNSS/field measurements was run.
- Browser E2E suite was not run because Playwright is not installed in this build environment.

A green unit test suite verifies software behavior under test fixtures. It does not certify a real geophysical model or confirm external account permissions.
