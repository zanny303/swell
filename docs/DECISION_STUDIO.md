# SWELL Decision Studio

## What it does

Decision Studio takes the currently loaded study, selected map cell, scenario assumptions and role selection, then creates a role-specific interpretation and editable draft deliverables.

### Workspaces

- **Civil / geotechnical engineer:** investigation brief, borehole planning schedule (CSV), conceptual DXF layout in a local ENU frame, conceptual SVG subsurface section, model JSON and time-series CSV.
- **City planner / resilience office:** municipal options memo (Markdown), economic sensitivity CSV based on user-entered assumptions, location context GeoJSON, report HTML and model JSON.
- **Water utility:** draft inspection work-order template and spatial context.
- **Emergency manager:** preparedness checklist (not an alert or forecast).
- **Farmer / land manager:** land-management assessment.
- **Resident:** plain-language location explainer.
- **Research scientist:** reproducibility record and time-series export.

## Scientific integrity

The default `site/data/site.json` is a synthetic test fixture. The interface labels this explicitly. The browser scenario uses the existing `SwellModel.scenario` moisture-response model; it does not solve groundwater flow, full poromechanics, foundation response or city-scale hazard probability. Groundwater rise is recorded as a context-only assumption and is not coupled to the current equation.

The economic calculator uses editable assumptions for asset counts, asset values, intervention budgets and annual disruption losses. It does not estimate intervention effectiveness, avoided losses or audited benefit-cost ratios. It reports simple sensitivity arithmetic only.

The DXF and SVG are conceptual planning artifacts. The DXF uses a local East-North-Up coordinate frame with an origin noted in the drawing. It is not survey set-out geometry, a stamped design or a construction deliverable. No G-code is generated: G-code is machine-control code and is not an appropriate substitute for geotechnical or civil engineering design.

## How to use

1. Run `python run_swell.py`.
2. Open the app and select a map cell within the loaded study footprint.
3. Open **Decision studio**.
4. Select a stakeholder role.
5. Adjust rainfall, drainage and horizon assumptions; groundwater rise is context-only.
6. For the planner or engineer, edit the corresponding planning/investigation assumptions.
7. Run the scenario.
8. Download each report, CSV, GeoJSON, DXF, SVG or JSON deliverable.

If a point is outside the loaded physical study footprint, site-specific simulation and deliverables are disabled rather than extrapolated.

## Production requirements

Before operational use, replace the synthetic fixture with a real acquisition and derived geospatial data pipeline. Required gates include NISAR provenance and maturity, correct georeferencing, quality masks, native resolution display, independent GNSS/field validation, local soil/geotechnical records, verified infrastructure inventories, model calibration and professional review.
