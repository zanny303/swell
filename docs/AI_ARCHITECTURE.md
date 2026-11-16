# SWELL research and AI architecture

## Current implementation

SWELL separates scientific computation, evidence retrieval and optional language-model generation. The scientific engine does not depend on an AI provider.

### Evidence and research

- The active study evidence is read from `site/data/site.json`, including source label, acquisition count, site metadata, validation tests and (when a real site is active) selected-cell values.
- The curated local corpus is retrieved with deterministic BM25 lexical ranking in `literature_rag.py`.
- Each retrieved chunk carries an evidence ID, source title/URL, local filename, source-file SHA-256, word offset and retrieval score.
- This is lexical RAG, not embedding/vector search. It works without an API key and can be used in evidence-only mode.
- An optional local Ollama model can produce an explanatory draft from retrieved sources. It remains explicitly unverified unless its citations are checked.

### Provider-neutral generation

`ai_provider.py` is a server-side provider gateway. It supports:

- Anthropic Claude through the Messages API.
- OpenAI through Chat Completions.
- Meta Model API through its OpenAI-compatible Chat Completions endpoint.
- Local Ollama through its OpenAI-compatible endpoint.
- Other OpenAI-compatible endpoints, including local endpoints that do not require a key.

Only one provider is selected at a time. API keys are stored in the local `.env` file and never sent to browser JavaScript. The server reloads saved configuration after restart. The Connections page can retrieve the provider's available model catalogue where supported.

A saved key/model means **configured**, not connected. The separate **Test AI generation** action makes an actual generation request. The UI reports live verification only after that test succeeds and stores only provider/model/timestamp metadata—not the key.

### Synthetic-data protection

The bundled `site/data/site.json` is a synthetic software fixture. When its source label is synthetic:

- numeric site/cell values and scenario metrics are removed from the provider prompt;
- selected-cell quantitative answers are withheld;
- site-specific research analysis is skipped;
- general curated literature can still be retrieved;
- the default stakeholder home shows no synthetic acquisition count or site metrics;
- insight pins and cross-site similarity are disabled;
- decision records are limited to proposed/reviewed rehearsal states.

A real site must be discovered, downloaded, processed and validated before site-specific claims are enabled. Passing API checks does not load a study.

## Ask SWELL behavior

The Earth Decision Studio copilot (`site/ai-copilot.js`) reads the active workspace contract from `site/studio.js`.

When a provider is configured and live-tested, it sends the user question, safe workspace context, active site evidence and retrieved BM25 excerpts to the selected server-side model. The model is instructed to distinguish observations, derived products, inferences, forecasts, scenarios and recommendations; cite retrieved evidence IDs; state uncertainty; and abstain when evidence is missing.

Without a configured provider, the copilot uses deterministic site-evidence answers and local BM25 retrieval. A local Ollama explanation is optional and labelled unverified.

Natural-language scenario requests are parsed by SWELL's deterministic scenario parser. The parsed inputs are shown as a proposal. The user must explicitly apply the scenario before the deterministic model is recomputed. A language model does not run the physical simulation or approve an action.

## Scientific methods shown in the Stakeholder Decision Room

- **PINN ablation:** the real-site validation pipeline compares physics-fit, network-only and physics-informed held-out error. The UI reports the actual result, including when the physics-informed model does not improve fit.
- **Q-learning zone sequencing:** the real-site pipeline evaluates a learned zone order against simple rules on held-out rainfall sequences. The UI reports the best simple rule and whether the learned policy beat it.
- **Observe-next heuristic:** real-site zones are ranked using modelled movement amplitude × uncertainty. This is a screening heuristic, not formal value-of-information analysis.
- **Radar-derived moisture susceptibility:** high fitted per-cell response coefficients can be shown as map pins. They are associations, not direct observations or proof of causation.
- **Cross-site physical-signature matching:** user-uploaded prior `out/results.json` exports are compared only when each site has at least one passed validation test and no failed tests. The standardized distance is descriptive; it does not prove transferability.
- **Flood sensitivity ensemble:** nine deterministic rainfall/infiltration perturbations belong to the separate flood Site Twin. They are not a calibrated probability distribution.

The map pins are generated only from real-site outputs. Synthetic fixture outputs are never presented as operational research findings.

## Why not put provider keys in the browser?

Never place provider API keys in `site/app.js`, HTML, browser storage or static assets. Browser code calls local server endpoints; server-side adapters attach credentials to outbound provider requests. Local key writes are restricted to the loopback server and the `.env` file is excluded from version control.

## Remaining production work

1. Add a versioned embedding index and hybrid retrieval/reranking alongside BM25, with a reproducible corpus manifest.
2. Add provider-specific tool calling only after implementing strict per-tool schemas, permission boundaries, timeouts and audit logging. The current generic gateway does not assume every provider supports the same tool-call contract.
3. Build an authenticated multi-user stakeholder ledger with named approvals, role permissions, signatures, review assignments and audit exports. The current hash-chained ledger is local and single-user.
4. Persist immutable acquisition manifests, processing versions, model runs, validation records and evidence snapshots.
5. Add an explicit site archive and governed cross-site registry instead of relying only on user-uploaded result exports.
6. Benchmark models with temporal holdouts, whole-region spatial holdouts and external-site transfer using frozen parameters. Report LOS RMSE/MAE/bias, interval coverage and width, calibration by coherence/land cover, false-alert/missed-event rates, abstention coverage-risk, physical constraint violations and independent GNSS agreement.
7. Validate real NISAR products against independent geodetic/field evidence before operational engineering use.

## Non-negotiable answer contract

The AI may explain and propose. It may not fabricate an observation, silently change the physical model, certify structural safety, approve a decision, or turn a training RMSE/sensitivity range into a probability interval. If evidence is absent, stale, low-quality, contradictory or outside the validation domain, SWELL must say so.
