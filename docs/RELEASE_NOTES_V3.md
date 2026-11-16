# SWELL v3 release notes

Date: 15 November 2026

## What changed

### Provider connectivity
- One provider-neutral AI settings flow supports Anthropic Claude, OpenAI, Meta Model API, local Ollama and other OpenAI-compatible endpoints.
- The browser uses one generic provider-key field. Keys are stored in the local `.env` file and are not returned to the browser.
- Provider model discovery is available where the endpoint supports it.
- A saved key/model is shown as **configured**, not connected. A separate live generation test verifies the selected provider/model.
- Changing provider credentials or model invalidates the prior live test. Saved `.env` settings are reloaded after server restart.
- Error responses redact saved credentials.

### Evidence and RAG
- The local research corpus uses deterministic BM25 lexical retrieval.
- Returned passages retain evidence IDs, URLs, source filenames, source-file SHA-256 hashes, word offsets and retrieval scores.
- Evidence-only mode works without a generative AI key.
- Synthetic fixture measurements and scenario metrics are withheld from provider prompts and site-specific answers.

### Stakeholder-first experience
- The Stakeholder Decision Room is the default home.
- Before a real site is loaded, the home screen explains the stakeholder workflow and directs the user to connect data without displaying synthetic pass counts or metrics.
- After a real site is loaded, the same workspace connects map selection, intervention painting, scenario comparisons, role-specific plans, research retrieval, decision records and map pins.
- The local hash-chained decision ledger records actor/team, decision, rationale, evidence IDs, review status and optional map location.
- Real-site insight pins include observation-priority heuristics, Q-learning sequence suggestions and radar-derived moisture-sensitivity estimates. These are labelled as model/research outputs, not observations or guarantees.
- Cross-site signature matching accepts up to eight prior `out/results.json` exports and compares only real, validation-eligible sites.

## Verification

- Python test suite: **104 passed**.
- All 22 `site/*.js` files passed `node --check`.
- The inline script in `site/connections.html` passed `node --check`.
- Modified Python modules passed `py_compile`.
- Local HTTP smoke tests passed for `/`, `/connections.html`, `/api/system/health`, `/api/ai/status` and `/api/real-site/status`.
- The cross-site similarity endpoint correctly rejected the synthetic fixture with HTTP 409.

## What still needs to be verified on the user's machine

- Enter and test a real provider API key. No user's provider credentials were available during this build.
- Authenticate with NASA Earthdata, find compatible NISAR GUNW acquisitions for the chosen area and build the real site twin. No real NISAR site was built in this environment.
- Reload the browser after a successful site build and confirm the header says `REAL STUDY`.
- Headless Chromium navigation was blocked by this environment (`ERR_BLOCKED_BY_ADMINISTRATOR`), so a full visual browser review could not be completed here.
- BM25 is lexical RAG, not vector/embedding retrieval. The local decision ledger is single-user, not authenticated multi-user governance.
- Research methods and map pins require real site outputs and remain subject to independent geodetic/field validation before operational decisions.
