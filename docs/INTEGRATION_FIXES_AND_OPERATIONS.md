# SWELL v3 — connectivity, AI, data provenance and stakeholder workflow

## The key distinction: a connection is not a loaded study

SWELL has two separate states:

1. **Provider connectivity** — a public service or authenticated API responds to a test request.
2. **Study ingestion** — actual data products have been discovered, downloaded/processed, validated and written to `site/data/site.json`.

A green provider check is not proof that the Earth workspace has real site data. The active study remains synthetic until a successful real-site build replaces the fixture. The Earth header now reports this distinction and links to Connections. `/api/system/health` exposes the active site source, acquisition count, job state, AI provider state and the last saved connection test summary.

`ready_for_real_twin` means the required public sources and Earthdata login passed their checks. It does **not** mean a site twin is already built.

## Replacing the synthetic study

1. Open `Connections and real data`.
2. Run **Test all connections** at the actual study coordinates.
3. Read the NASA CMR/NISAR row. If it says no matching granules, this is an AOI/date coverage issue, not a bad key. Choose a region and acquisition window with compatible GUNW products.
4. Click **Find radar passes**. Confirm that the selected GUNW products form a compatible temporal chain and that the data are available for authenticated retrieval.
5. Click **Build the real twin**.
6. Wait for the build log to report `TWIN READY` / successful completion. If it fails, use `out/real_site_log.txt` and `out/real_site_provenance.json`.
7. Reload the Decision Studio. If it was already open during the build, its JavaScript state still holds the old file until the page is reloaded.
8. Confirm the Earth header says `REAL STUDY · N PASSES` and that `/api/system/health` reports `real_site_loaded: true`.

Do not edit the `source` field manually to make a synthetic file look real. The source label is provenance metadata and must reflect the actual processing lineage.

## Provider-neutral AI setup

SWELL Copilot supports one active provider at a time:

| Provider | Base URL | Authentication |
|---|---|---|
| Anthropic Claude | `https://api.anthropic.com` | API key |
| OpenAI | `https://api.openai.com/v1` | API key |
| Meta Model API | `https://api.meta.ai/v1` | Bearer token |
| Ollama local | `http://127.0.0.1:11434/v1` | No key for local server |
| Other compatible endpoint | Provider's `/v1` base URL | Key if required; localhost may be keyless |

In Connections:

1. Choose the provider.
2. Enter the provider API key if required.
3. Save settings.
4. Use **Load available models** to query the provider's model catalogue (if supported).
5. Select a model and save.
6. Use **Test AI generation**. This makes a small live model request; it is separate from the data-source checks.

The AI key is stored server-side in the local `.env` file. It is never sent to browser JavaScript. The server reloads saved `.env` settings when it resolves provider configuration, including after a restart. Switching providers clears the old generic provider key so that an Anthropic key is not accidentally sent to OpenAI/Meta or vice versa. Existing legacy `ANTHROPIC_API_KEY` configuration remains readable when the selected provider is Anthropic.

A provider with a saved key/model is labelled **configured**, not connected. The separate **Test AI generation** action makes a real generation request; only then does the UI report a live generation verification. The test timestamp and provider/model identity are saved without credentials, and an old test does not verify a newly selected model.

### No key required

- Select **Evidence-only** to use local evidence retrieval and deterministic SWELL tools without a generative model.
- Select **Ollama (local)** to use a model running on the same computer; install Ollama, start it, and pull a model first (for example `ollama pull llama3.2`).
- Core Earth data and scientific model operations do not depend on a Claude, OpenAI or Meta key.

### Provider compatibility notes

- Anthropic uses its Messages API.
- OpenAI, Meta Model API and Ollama use the OpenAI-compatible `/chat/completions` route.
- The Meta Model API publishes both `/v1/chat/completions` and `/v1/models`.
- Ollama exposes a local OpenAI-compatible endpoint. It does not need a local API key.
- A custom provider must implement the compatible chat-completions request and response shape. Remote HTTP is rejected; use HTTPS. HTTP is permitted only for localhost services.

## Evidence retrieval and synthetic-data protection

The local literature RAG now uses BM25 lexical retrieval over the curated local corpus. Returned chunks retain:
- evidence ID,
- title and source URL,
- source filename,
- SHA-256 of the source file,
- word offset,
- retrieval score.

This is **lexical BM25 RAG, not vector/embedding retrieval**. It is deterministic and works without an AI key. A configured provider receives the retrieved excerpts plus provenance-labelled active-site evidence and must cite supplied evidence IDs.

When the active `site.json` is marked `SYNTHETIC`:
- numeric grid/cell evidence is not sent to the generative provider;
- selected-cell answers withhold fixture measurements;
- scenario summary numbers are withheld from the Copilot;
- site-specific research analysis is skipped;
- general scientific literature can still be retrieved and discussed;
- stakeholder decision records are restricted to proposed/reviewed rehearsal states and are marked synthetic.

Synthetic fixtures remain in the repository for software tests only. They are not silently converted into observations.

## Stakeholder Decision Room

The default `studio` workspace is now titled **Stakeholder Decision Room**. The map remains the spatial manipulation surface:
- inspect a selected grid cell;
- paint water, drainage, paving or greening interventions;
- compare observed/inferred/forecast/scenario states;
- switch between map, split and physical twin views.

The stakeholder workbench is embedded in the main workspace and connects:
- selected spatial cell and current source label;
- scenario comparison;
- role-specific action plan;
- research retrieval and cited source links;
- a decision form with actor/team, action, rationale and review status;
- append-only hash-chained decision history;
- map pins for recorded decisions with a real spatial location;
- zoom-to-pin from the decision history;
- **Observe-next insight pins** for real-site zones that pass data masks, displaying model-derived seasonal amplitude, spread, uncertainty and a heuristic movement × uncertainty score.
- **Q-learning sequence pins** for the learned zone order, including its held-out comparison against the best simple rule. If the learned policy loses, the UI reports that result rather than hiding it.
- **Radar-derived moisture-sensitivity pins** for the highest fitted per-cell moisture-response coefficients, explicitly labelled as associations rather than direct measurements or causal proof.
- **Cross-site signature matching**: upload up to eight prior `out/results.json` exports; the local endpoint excludes synthetic, failed, incomplete or non-finite studies and ranks eligible sites by standardized physical-signature distance. It does not claim that similar sites are interchangeable.
- The initial no-site screen is now a stakeholder landing room with the role, decision cycle, supported use cases and a direct real-data setup path. It does not display the bundled fixture's pass count, map values or forecast metrics. Synthetic data remains hidden unless the developer explicitly enables the labelled sample.

The ledger is local and single-user in this prototype. It is tamper-evident, not a digital signature, authenticated multi-user governance system, or professional approval workflow.

## Research methods visible in the Decision Room

The codebase contains these methods, but their presence is not evidence that they were run or validated on the active site:

- **PINN**: experimental physics-informed neural network ablation/inverse-model work.
- **Q-learning zone sequencing**: research planner over site-derived rainfall sequences; not proof that a proposed intervention works.
- **Cross-site similarity**: only meaningful with at least two independently validated sites.
- **Nine-member sensitivity ensemble**: deterministic rainfall/infiltration perturbations for the flood twin; not a calibrated probability forecast.

The UI labels these as research/screening methods and states their prerequisites. They must not be described as operational, calibrated or validated unless a reproducible run demonstrates that.

## What is still not completed by this code update

- No user API key was available to us, so no real Anthropic/OpenAI/Meta/Ollama account was called from this development environment. Use the explicit **Test AI generation** action on your machine.
- No real NISAR site was built in this environment. Your Earthdata credentials, selected AOI and available compatible GUNW chain determine whether that can succeed.
- Real NISAR products still need independent geodetic validation (e.g. GNSS/field control) before engineering decisions.
- Building geometry is not a surveyed asset inventory; a 3D map is not automatically a validated infrastructure twin.
- The decision ledger is not multi-user collaboration/authentication.
- BM25 RAG is not semantic vector search; a future upgrade can add a local embedding index, hybrid retrieval and document-level re-ranking.
- Generic OpenAI-compatible providers return grounded text; scenario parsing/application remains in SWELL's deterministic, human-approved workflow. Tool-calling support is not uniform across providers and is not assumed.
- Browser end-to-end automation could not complete in this environment: Chromium navigation was blocked by the sandbox (`ERR_BLOCKED_BY_ADMINISTRATOR`). JavaScript syntax checks, local HTTP API smoke checks and Python tests were run.

## Latest verification

- `python -m pytest -q`: **104 passed**.
- `node --check site/studio.js`, `node --check site/ai-copilot.js`, and an extracted inline-script check for `site/connections.html`: passed.
- Python compile checks for the modified API, provider, RAG, ledger and similarity modules: passed.
- Local HTTP smoke checks for `/`, `/connections.html`, `/api/system/health`, `/api/ai/status` and `/api/real-site/status`: passed.
- Synthetic-data guard on `/api/site-twin/cross-site-similarity`: returned HTTP 409 as intended.
- No real provider key or real NISAR acquisition was available for a live external account test.

## Local commands

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-site-twin.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe run_swell.py
```

Open `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/connections.html`.
