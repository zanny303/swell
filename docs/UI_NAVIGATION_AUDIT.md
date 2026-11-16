# SWELL judge-level visualization and usability audit

## Why the current prototype reads as graphs, not a digital twin

1. **The default deformation layer is a 40x40 synthetic grid stretched over a rectangle.** `app.js` paints each cell into an 8px canvas and displays it as one `SingleTileImageryProvider`. This is a heatmap, not a high-resolution physical twin. Do not blur it into false detail; render georeferenced COG tiles and expose native pixel size and quality masks.
2. **The physical cutaway is a 2D canvas illustration**, not a 3D subsurface model linked to real soil horizons, water table or engineering assets.
3. **Three quick-place buttons only move the camera.** They do not select a location-specific dataset or communicate whether a physical twin exists there.
4. **NASA GIBS is a browse-visualization service with fixed product resolutions.** It cannot provide street/building detail at deep zoom. Use GIBS for global satellite context, a clearly attributed reference basemap for local geography, and NISAR-derived COG tiles only where acquisitions exist.
5. **Layer controls do not verify layer availability.** Current code creates GIBS layers unconditionally; it does not check GetCapabilities, tile failures, latest available date or source freshness.
6. **The click model conflates navigation with analysis.** Users need a search-first flow, region selection, footprints, acquisition coverage, then click-to-inspect cells.
7. **Nine tabs expose internal system architecture rather than a stakeholder journey.** Group into Explore, Investigate, Explain, Simulate, Act, Verify. Keep research and advanced science under an expert workspace.
8. **No visible ingest pipeline status.** Show discovered → queued → downloaded → processed → quality-checked → validated → published, with failures and timestamps.

## Judge-level verdict

Promising scientific concept, but currently a research prototype rather than a convincing real-world digital twin. A judge cannot yet follow one real region from a real NISAR granule through quality-controlled geophysical inference to a field-verifiable stakeholder action. This end-to-end proof is more important than adding more dashboards or AI chat.

## Correct user journey

Earth → search a place → see coverage badge → choose a real acquisition → inspect before/after imagery and quality → compare observed / inferred / forecast / scenario → open 3D terrain + subsurface cross-section → choose stakeholder role → create reviewed action → verify against next observation or field measurement.

Every location needs an explicit state: `validated twin`, `provisional data`, `processing`, `context only`, `no coverage`. Every layer needs source, product, acquisition time, processing time, spatial resolution, maturity and quality.

## Rendering stack

- CesiumJS: globe, camera, terrain, 3D Tiles.
- NASA GIBS WMTS/WMS: global browse imagery, not street-level basemap.
- Attributed reference imagery for local visual geography; mark as reference, not current.
- COGs served through TiTiler/rio-tiler: NISAR rasters and derived products.
- PostGIS: sites, footprints, assets, stakeholder actions and spatial queries.
- STAC: discovery and provenance; object storage for HDF5 and COGs.
- Worker queue: NISAR ingest, reprojection, model inference and publication.
- Three.js/Cesium primitives: subsurface section with terrain, soil horizons, water table and structures. Keep conceptual geometry visibly distinguished from measured geotechnical layers.

## Gates before expanding worldwide

A. One real location with validated NISAR GUNW/GCOV, visible footprint and provenance.
B. Correctly georeferenced COG rendering and quality mask.
C. Independent GNSS/field validation, baselines and held-out dates.
D. 3D section linked to actual local soil/geotechnical context.
E. One complete engineer and planner workflow with exports and verification.
F. Replicate to more cities only after A-C work.
