# SWELL model card — current development build

## System purpose

SWELL is a geospatial evidence and scenario workspace for exploring environmental observations, running reduced-order site models, comparing interventions and preparing human-reviewed decisions.

## Intended uses

- Exploratory analysis of terrain, rainfall, satellite-derived layers and site evidence.
- Scenario comparison using explicitly declared model inputs.
- Preliminary flood/water screening and soil-moisture/shrink–swell research workflows.
- Evidence organization and preparation of stakeholder investigation plans.

## Prohibited / unsupported uses

- Emergency warnings, evacuation decisions or operational flood control.
- Structural safety certification, foundation design, engineering sign-off or regulatory compliance determinations.
- Claiming that a synthetic fixture represents a real place or a real NISAR acquisition.
- Treating backscatter change as displacement, NISAR phase as vertical displacement, or visual 3D geometry as surveyed asset geometry.
- Treating a deterministic forecast or parameter-sensitivity experiment as a probability distribution.

## Model components and status

| Component | Current status | Key limitations |
|---|---|---|
| Shrink–swell / soil response | Reduced-order scientific model | Depends on site parameters and moisture inputs; not a coupled geomechanics solver |
| Surface-water screening | Reduced-order numerical solver | Not a full 2D shallow-water solver, sewer model or calibrated hydraulic design model |
| Forecast ensemble utilities | Experimental support | Requires genuine ensemble or archived forecast inputs; no universal calibrated forecast is bundled |
| Forecast interval calibration | Chronological split-conformal utility | Empirical site/source/lead calibration only; serial dependence and regime shift remain concerns |
| NISAR ingestion | Product discovery/preflight and selected processing workflows | Product maturity, quality, phase convention, masks, geometry and independent reference must be checked per acquisition |
| Copilot | Optional server-side Claude + deterministic evidence fallback | AI can misread context; tool outputs and citations require human review |
| 3D twin | Cesium/terrain and selected site geometry | Not a complete city-scale asset twin; underground geometry and asset attributes require surveyed data |

## Data provenance labels

Every user-facing quantity should be classified as observed, derived, inferred, forecast, scenario, verified or unavailable. Synthetic fixtures must be explicitly labelled synthetic/demo and must not enter a real-world evidence claim.

## Evaluation requirements

- Unit and integration tests for contracts, units, masks, numerical stability and mass balance.
- Temporal and spatial holdouts; event/site splits to avoid leakage.
- Hindcast replay against later observations and operational baselines.
- Independent GNSS, leveling, gauges, field surveys or other suitable references where applicable.
- Report MAE, RMSE, bias, coverage, interval width, spatial overlap and mass balance as relevant, with data periods and sample sizes.
- Record input hashes, model version, configuration, forcing source, issue/valid times and processing history.

## Known limitations

The bundled site fixture is synthetic. No bundled independent real-site benchmark establishes predictive accuracy. Provider connectivity is dependent on user credentials, network, data availability, terms and service status. A successful API call proves connectivity, not scientific validity. Model output is decision support for expert review, not a substitute for professional judgment.
