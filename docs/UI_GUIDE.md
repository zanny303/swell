# SWELL interface guide

## Design intent
The interface is organized around one investigation loop:

**Earth → study region → observed change → physical explanation → forecast → scenario → action → verification.**

The 3D globe remains the primary canvas. The analysis drawer is a contextual workspace rather than a separate page, and the time/state dock remains visible while the user changes analysis tabs.

## Global controls
- **World:** Earth or a planetary radar case study. The non-Earth views are contextual research stories; they are not represented as NISAR twins.
- **Study site:** flies to the loaded study-area extent.
- **Global view:** returns to the global camera view.
- **Latitude, longitude:** enter `latitude, longitude` (for example `32.78, -96.80`) to fly to coordinates and place a temporary map pin.
- **Rain / fires / quakes:** toggles NASA GIBS context layers and the public USGS earthquake catalog. These layers are contextual; they are not SWELL deformation observations.
- **Map rail:** zoom and reset camera orientation.
- **Analysis toggle:** hides or restores the evidence drawer to expose the globe.

## Evidence-first copilot and scenario branches

- **Ask SWELL:** opens a copilot that receives the active site, data source, synthetic status, role, active state, forecast horizon and selected cell. It can explain selected-cell values, retrieve curated science sources and prepare a scenario proposal. The model changes only after the user explicitly clicks **Apply to active twin**.
- **Scenario shelf:** saves exact inputs and painted intervention arrays in this browser, compares alternatives only when site/source, model engine/version, horizon, weather forcing, analysis cells and baseline are compatible, restores a saved branch, and exports comparison JSON. It is local to the browser profile; it is not shared stakeholder collaboration or authenticated approval.

## Analysis tabs
- **Evidence:** fitted parameters, validation checks, selected-cell values and a physical cut-away illustration.
- **What-if lab:** natural-language scenario parser and manual controls for rainfall, dry period, wetting reduction and paving assumptions.
- **Stakeholders:** role-specific investigation plans and downloadable review inputs.
- **Structures:** explicitly bounded kinematic screening scenario. It is not a structural analysis or safety classifier.
- **Contracts:** proposed action, expected observable, competing explanation, outcome check and approval state.
- **Earthquakes:** public USGS event details and a generic statistical aftershock-rate illustration, clearly distinguished from SWELL outputs.
- **Your data:** local browser upload for a validated `site.json` and optional daily rainfall CSV. Files are not uploaded by the page.
- **Other worlds:** contextual radar case studies beyond Earth; only Earth is a SWELL/NISAR study site.

## Evidence-state semantics
- **Observed:** the measurement layer in the loaded site file (LOS displacement for the current product workflow).
- **Inferred:** model-estimated motion after the fitted artifact adjustment; hatched cells are unresolved.
- **Forecast:** conditional model trajectory under the displayed baseline assumptions.
- **Scenario:** hypothetical response under user-defined assumptions.

These are separate states. A forecast or scenario must never be styled or described as an observation.

## Source labels
Synthetic fixture data is explicitly labelled **SYNTHETIC DEMO · NOT NASA DATA**. Other uploaded files are labelled **USER-LOADED** with their supplied source string. A source string is not a substitute for product provenance, processing maturity, correction metadata or independent validation.

## Responsive behaviour
Desktop uses a floating analysis drawer with a persistent time dock. Tablet/mobile converts the drawer into a bottom sheet and hides secondary header controls to preserve map visibility. Keyboard Escape closes the analysis drawer. All controls have accessible names and visible focus treatment.


## Research AI tab

The Research AI tab compares M0 no-change, M1 rain-only and M2 SWELL holdout RMSE when those metrics are present in the loaded site file. It also exposes GPS LOS comparison, clay-map association, forecast interval coverage, refusal retained fraction and unresolved zones.

The deterministic site explanation remains in `site/research.js`. The new Ask SWELL copilot also calls the existing `/api/site-twin/research` and `/api/site-twin/literature` retrieval endpoints. Optional local Ollama generation may provide an unverified explanatory draft if configured on the server; retrieval-only mode remains the default. This is not a production Claude/Anthropic agent. The full quantitative test records are embedded into `site/data/site.json` by `python -m swell.validate` so the browser can explain the metrics without reaching into local files.

Synthetic fixtures are always marked as synthetic and must never be presented as real NASA results.
