# SWELL connected-site integration release

## Run

From this folder use `python -m pip install -r requirements-site-twin.txt`, `python install_renderers.py`, then `python run_swell.py`. Open http://127.0.0.1:8000/ and select the Earth GPS location and Site Twin. Use **Prepare connected site** to register terrain and request imagery, NASA catalog, hourly AI weather and local conditions independently. A failed DEM blocks the workflow (upload a real georeferenced DEM instead). External imagery is not live video, and available resolution depends on the provider. Check `python connect_check.py --lat 32.7767 --lon -96.797` on your connected machine. Its JSON distinguishes retrieval and failure; it does not establish accuracy.

## What is new

- Existing Earth globe, preview, latest imagery controls, original scientific model, location and Worlds pages unchanged. Site Twin is the working location-conditioned simulation workspace.
- One-action terrain, aligned imagery, NASA catalog, AIFS and location evidence loading. Six-source location snapshot stored server-side under site ID and linked to saved run and export. Not all evidence is co-temporal, and soil/gauge information is not automatically interpreted as model parameter values.
- The prior diffusive conservative flow solver now optionally permits a one-way outlet at a declared grid-edge cell, with a specified exterior stage and matching checked vertical datum. Default remains closed. Outflow is accounted separately in the mass budget. Not bidirectional river hydraulics, sewer routing or full SWE. Existing runs remain readable; version bumped.
- Numerical review replays exactly the saved scenario at 15 s vs original 30 s and reports peak-depth MAE, max difference, wet extent IoU, limiter fraction and mass balance. This is only a timestep sensitivity check, not proof of convergence or field accuracy.
- Surveyed asset CSV analysis: sample model water-surface elevation and compare to surveyed entry elevation with matching datum, report water depth above entry and static pressure. CSV `asset_id,lat,lon,entry_elevation_m,source`. A building's actual structural capacity remains unknown.
- Soil-profile CSV: `top_m,bottom_m,material,theta_initial,theta_scenario,porosity,vertical_strain_per_theta,source`. Calculates layerwise one-dimensional strain × thickness, with positive movement for wetting if supplied coefficient positive; no true coupled geomechanical solution. Requires measured lab coefficients and separately sourced initial/scenario moisture, not inferred from satellite image. Local profile only.
- Register residual ML history for exact site center, fixed lead and declared source. Train with chronological holdout and skill gate; choose the matching hour of a saved run and provide antecedent moisture and provenance. Baseline point physics depth and cumulative rain are taken from saved run, not fabricated. Candidate prediction or abstention, saved with model card. No mass-balance-breaking spatial ML correction. History CSV is specified in prior SITE_TWIN_RELEASE.md. No real training samples bundled.
- Evidence assistant retrieves relevant curated notes from seven linked official/scientific sources with TF-IDF and provides saved simulation evidence. No LLM generation or full literature corpus. All notes are paraphrased; this is not a peer-reviewed inference system.
- Numerical, asset, soil and AI review records and evidence snapshot included in existing role ZIPs with integrity hashes. Still draft DXF/GIS/report outputs. No machine-ready or certified design claims.

## Why some features still require inputs

Real local terrain/imagery and acquisition metadata are external; NASA Earthdata authorization and optional ion access are user-specific. Validated flood predictions require actual event records, known boundary inflow/outflow, surveyed structures and calibrated hydrology, resolution and independent holdout testing. Soil stratigraphy requires real borings and lab testing. Structural design and CNC execution require detailed engineered geometry, materials, loads, codes, qualified signoff and CAM verification. No amount of visual realism can infer these reliably from satellite pixels. See SITE_TWIN_RELEASE.md for NASA setup, datasets and limitations.

## Research sources

- USGS 3DEP bare-earth elevation: https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer
- NASA OPERA water extent (30 m posting, separate optical and SAR products): https://www.jpl.nasa.gov/go/opera/products/dswx-product-suite/
- NOAA National Water Model: https://water.noaa.gov/about/nwm
- Landlab boundary condition guidance: https://landlab.csdms.io/user_guide/overland_flow_user_guide.html
- EPA SWMM: https://github.com/USEPA/Stormwater-Management-Model
- NeuralHydrology: https://github.com/neuralhydrology/neuralhydrology
- NISAR product documentation: https://nisar-docs.asf.alaska.edu/gunw/

These guide the original reduced-order implementations, not claims of integrating full upstream hydraulic or geomechanical solvers.

## Testing

58 pytest tests passed (51 inherited, 7 additional). Browser harness exercises actual UI and backend functions with explicitly synthetic test terrain, including numerical review, research retrieval, drawing interventions, existing 3D surface, export and invalidation. Python attempted actual USGS endpoint in sandbox and DNS failed; no live provider success or real site benchmark is claimed. No browser test of actual device GPS or photorealistic streaming. Read prior release notes for existing functionality and limitations.
