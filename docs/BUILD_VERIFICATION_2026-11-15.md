# Build verification — 2026-11-15

## Code changes in this release

- Corrected the optional Claude provider default model from the unverified `claude-sonnet-5-5` identifier to Anthropic's currently listed active `claude-sonnet-5` model ID.
- Changed the default Anthropic API version header to the stable `2023-06-01`; model availability must still be confirmed against the account's live `/v1/models` response.
- Updated the Connections UI default and setup hint to match.
- Added provider-configuration tests proving deterministic fallback, optional key behavior and no key exposure in status output.
- Added live API, NASA Earthdata/NISAR, terrain/weather, acceptance and scientific validation runbook.
- Added a current model card and three-minute demonstration script.
- Expanded the Claude Code handoff prompt with the new release requirements.

## Verification performed

- `PYTHONPATH=. pytest -q`: **84 passed**.
- `node tests/test_hydro.cjs`: **passed**, 12 hydrology invariants plus AI-forcing conservation/intervention checks.
- `python -m compileall -q .`: **passed**.
- `node --check` on key frontend scripts: **passed**.
- `SWELL_LOCAL_HARNESS=1 python tests/browser_earth_preview.py`: **passed** (historical bundled Earth texture, zoom, coordinate picking/navigation).
- `python tests/browser_live_offline.py`: **passed** (Earth UI, offline provider status, coordinate controls, Connections dialog).
- Local HTTP smoke test: `/` and `/connections.html` returned HTTP 200.
- Updated ZIP integrity check: **passed**.

## Not verified in this environment

- No Anthropic key was supplied; real Claude API request/tool-use is not tested.
- No NASA Earthdata token was supplied; authenticated NISAR download is not tested.
- Network sandbox did not establish live third-party provider access; do not infer provider health from the offline browser tests.
- No genuine NISAR study area was downloaded, processed and independently validated in this build session.
- No production hosting, TLS, user authentication, multi-user authorization, persistent deployment database, or operational security review was performed.

The 84 tests and browser checks demonstrate software regression behavior with local fixtures/mocks. They do not validate environmental model skill or make the application operationally certified.
