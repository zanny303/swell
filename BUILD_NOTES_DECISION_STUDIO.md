# SWELL build notes — Decision Studio

Implemented in this update:
- New Decision Studio navigation tab.
- Role-specific outputs for engineer, city planner, utility, emergency manager, land manager, resident and scientist.
- Scenario controls connected to the existing SwellModel moisture-response scenario function.
- Selected Cesium map coordinates/grid cell synchronize into Decision Studio.
- Outside-footprint locations are blocked from site-specific physical simulation.
- Dynamic HTML, JSON, CSV, GeoJSON, DXF, SVG and Markdown deliverables.
- Engineer investigation schedule and conceptual local-ENU DXF/SVG.
- Planner economic sensitivity from editable user assumptions, with no inferred avoided-loss benefit.
- Three.js interactive conceptual subsurface scene with orbit/zoom and visibility controls.
- Optional TiTiler COG raster overlay input on the Cesium globe.
- COG publication script that checks CRS and geotransform before generating COG output.
- TiTiler + PostGIS local service scaffold.

Verification:
- Node syntax checks pass for app.js, model.js and research.js.
- Python syntax compilation passes for pipeline scripts.
- Existing pytest suite: 19 passed.
- HTML audit: no duplicate IDs; all required Decision Studio controls are present.

Not implemented / not claimed:
- No real NISAR granule has been downloaded or processed in this build.
- The included site dataset remains synthetic.
- The Three.js geology is conceptual, not site-specific borehole geology.
- Groundwater rise is a recorded scenario assumption only; it is not coupled to the current model equation.
- CAD outputs are conceptual investigation-planning drawings, not stamped design or survey set-out.
- Planner economics are editable assumption-based sensitivity, not an audited cost-benefit analysis.
- No G-code is generated because machine-control code is not an appropriate civil/geotechnical design deliverable.
