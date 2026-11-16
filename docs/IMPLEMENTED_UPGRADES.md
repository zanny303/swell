# Implemented in this SWELL build

## User-facing changes

1. **Earth-first entry point** — `/` now opens the Earth Decision Studio regardless of whether a real site has been connected. The Connections workflow remains accessible as the next step rather than the only landing experience.
2. **Ask SWELL copilot** — new panel launched from the Earth Studio header. It sees the active site, source, synthetic status, role, state, horizon and selected cell. It can:
   - explain a selected cell from the loaded site record;
   - retrieve the deterministic site evidence answer;
   - query the existing research and literature endpoints;
   - display retrieved source links and retrieval status;
   - translate an explicit what-if request into a visible scenario proposal;
   - apply a proposal only after the user clicks “Apply to active twin”.
3. **Scenario shelf** — save up to six scenario branches in this browser with exact painted arrays, model inputs, forcing summary, horizon, role, output metrics and a decision note. Compare only scenarios from the same site/source; load or remove them; export JSON.
4. **Forecast honesty** — the Earth chart no longer draws training RMSE as a future uncertainty band. Text now states that training RMSE is a fit diagnostic, not a calibrated predictive interval. The water-balance screen is labelled uncalibrated and its sensitivity is not represented as probability.
5. **Export metadata** — scenario records now set `uncertainty_mm` to null and add `training_rmse_reference_mm` and an explicit uncertainty note.
6. **Navigation** — the Local Physical Twin's Earth return link now returns to the Earth Decision Studio.
7. **HTML cleanup** — removed a duplicate `id="run"` control from the scenario composer.

## Validation run for this build

The original v2 validation is retained as history. The latest v3 validation is recorded below.

## Tests added

- `tests/test_home_route.py` verifies that `/` serves the Earth Decision Studio and still exposes the Connections workflow.
- `tests/browser_decision_experience.py` exercises the copilot's scenario proposal/apply gate, evidence source display and the scenario shelf save/load flow against a mocked, explicitly synthetic workspace.

The browser test uses a mocked workspace. It proves UI interaction and guardrails, not real NISAR ingestion, a live AI model or scientific validation.

## Still not implemented / blocked

- No real NISAR acquisition is included in the supplied archives. A real site must still be selected, downloaded, processed and independently validated.
- The copilot is evidence-first and deterministic by default. Optional server-side provider adapters support Anthropic, OpenAI, Meta Model API, local Ollama and OpenAI-compatible endpoints. No user's external API key or real provider account was available for a live external credential test in this build environment.
- Scenario shelf storage is local to one browser profile. Authenticated multi-user collaboration, shared approvals, server persistence and audit history remain future work.
- The global/local views are not yet a fully synchronized 3D Tiles digital twin. OSM buildings/Cesium ion are optional provider capabilities; local 3D geometry remains partly conceptual.
- Forecast ensemble calibration, hindcast verification and reliability diagrams remain outstanding.
- The existing water-balance/flood screening model is not a full hydraulic solver; structural/geotechnical design remains outside scope.


## v3 integration, RAG and stakeholder decision room

1. **Provider-neutral AI gateway** — `ai_provider.py` supports Anthropic Messages, OpenAI Chat Completions, Meta Model API Chat Completions, local Ollama and other OpenAI-compatible endpoints. The Connections page uses one generic server-side key field, provider selection, model discovery and an explicit live-generation test.
2. **Correct connection semantics** — saved settings are shown as configured, not connected. A live test is required for a verified status. Changing the provider, key, base URL or model invalidates the previous test. Saved `.env` configuration is reloaded after a server restart.
3. **RAG provenance** — local BM25 lexical retrieval returns evidence IDs, source URL, source filename, SHA-256, word offset and score. This is not vector/embedding search. It works without a generative AI key.
4. **Synthetic data quarantine** — numeric fixture values are excluded from AI prompts and site-specific answers; the no-site stakeholder home does not show synthetic pass counts; research pins and cross-site comparison require real site outputs.
5. **Stakeholder-first home** — the default home is the Stakeholder Decision Room. Before a real site exists, it provides a clear data-connection path, role-specific use cases and the observe → understand → manipulate → decide → verify workflow. Once a real site is loaded, the same panel becomes the live workbench.
6. **Decision ledger and pins** — record stakeholder, decision, rationale, evidence IDs, review status and optional spatial location in a local hash-chained ledger. Real spatial records can be shown as map pins and zoomed to from history. This remains single-user, not a signed approval system.
7. **Research insight pins** — real-site-only Observe-next heuristic pins, Q-learning suggested sequence pins (with held-out simple-rule comparison) and radar-derived moisture-sensitivity pins. Each is labelled as a model/research output, not a direct observation or guarantee.
8. **Cross-site comparison** — upload up to eight other `out/results.json` files. Only real runs with at least one passed validation test, no failed tests and finite physical-signature fields are compared. The result is descriptive similarity, not proof of transferability.

## Latest v3 validation

- `python -m pytest -q`: **104 passed**.
- `node --check` passed for the modified `site/studio.js` and `site/ai-copilot.js`.
- Extracted inline JavaScript from `site/connections.html` passed `node --check`.
- Modified Python modules passed `py_compile`.
- Local HTTP smoke tests passed for `/`, `/connections.html`, `/api/system/health`, `/api/ai/status` and `/api/real-site/status`.
- Synthetic-data guard on `/api/site-twin/cross-site-similarity` correctly returned HTTP 409.
- Headless Chromium navigation was blocked by the sandbox (`ERR_BLOCKED_BY_ADMINISTRATOR`); no visual screenshot was available.
- No real external provider credentials or real NISAR acquisitions were available, so live account connectivity and real-site scientific validity remain to be verified on the user's machine.
