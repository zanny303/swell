# SWELL Worlds — independent planetary workspace

## Integration boundary

The original Earth dashboard, Earth Decision Studio, physics model, and existing Earth workflows are preserved. The only Earth UI change is a navigation link that opens `worlds.html` as a separate dashboard. Worlds has its own `worlds.js`, styles, planet registry, data-upload workspace, mission catalog search and habitation-screening panel.

## Included in this build

- Independent planetary dashboard for Mars, Moon, Earth, Venus, Europa and Titan.
- Interactive Three.js globe with orbit, zoom, reset, body selection and body-fixed coordinate picking.
- Explicit labels that procedural globe textures are illustrative, not mission-derived terrain or imagery.
- World-specific mission context, environmental reference notes, and official archive/service links.
- Backend proxy to NASA PDS Search API (`https://pds.nasa.gov/api/search/1/products`) using the documented `keywords` and `limit` query parameters.
- Persistent per-world file uploads, up to 500 MB per file, with SHA-256 hashes and upload manifests.
- Supported upload catalog: GeoTIFF/COG, GeoJSON, CSV, NetCDF, HDF5, PDS labels/IMG, LAS/LAZ, GLB/glTF.
- Client-side metadata inspection for GeoTIFF (GeoTIFF.js), GeoJSON and CSV.
- GeoJSON and CSV coordinate features can be overlaid on the selected body's globe after the user assigns a body-fixed longitude/latitude interpretation.
- Upload metadata records body, selected coordinate-reference label, units, observation time and user description.

## Scientific and product limitations

- The globe textures are procedural visual placeholders, not NASA imagery, DEMs or scientific observations.
- The PDS API returns archive metadata, not a universal image tile service. Search results may be empty, incomplete, delayed or unavailable. The dashboard reports the live API response and does not substitute fabricated results.
- PDS API documentation notes that its indexed holdings are not fully populated and that external browser CORS access may require configuration; SWELL uses a local backend proxy.
- Planetary raster uploads are stored and basic GeoTIFF metadata is inspected. This version does not yet reproject arbitrary planetary GeoTIFFs, render raster tiles onto the sphere, or decode all NetCDF/HDF5/PDS/LAS formats. Those require body/instrument-specific adapters and verified coordinate metadata.
- CSV mapping expects explicit longitude/lon and latitude/lat columns and treats them as body-fixed degrees after user selection. It does not infer or convert arbitrary projected coordinates.
- Habitat screening records user assumptions and returns transparent checklist flags only. It is not a physical prediction, site safety certification, landing approval, radiation transport model, thermal simulation, resource reserve estimate or engineering design.
- Earth live monitoring remains in the original SWELL Earth platform. Planetary mission archives are not represented as live weather.
- Environment reference figures are global/contextual approximations and must not be interpreted as point-specific conditions.

## Run

```bash
python run_swell.py
```

Open `http://127.0.0.1:8000/` for the original Earth dashboard or `http://127.0.0.1:8000/worlds.html` for the separate Worlds dashboard.

## Data sources

- NASA PDS Search API: https://nasa-pds.github.io/pds-api/
- PDS Search endpoint: https://pds.nasa.gov/api/search/1/products
- PDS Orbital Data Explorer (ODE): https://ode.rsl.wustl.edu/
- LOLA archive: https://imbrium.mit.edu/
- NASA Trek planetary map portals: https://trek.nasa.gov/
- NASA Celestial Mapping System: https://science.nasa.gov/solar-system/resources/celestial-mapping-system/


## Navigation and globe controls refresh

The Worlds page is organized into task-based workspaces:
- **Explore** — 3D planetary globe, world selector and mission summary.
- **Environment** — environmental context and science-layer explanations.
- **Habitation** — editable mission concept, solar availability, shielding and water-reserve assumptions.
- **Mission data** — NASA PDS catalog search.
- **Data studio** — coordinate reference, units, observation time, dataset description and file upload.

The left column keeps the selected world, body reference and authoritative links visible while users switch workspaces. Only one task workspace is shown at a time.

### Globe navigation
- Drag: orbit / rotate.
- Scroll wheel or trackpad: zoom.
- **+**: zoom in.
- **−**: zoom out.
- **Reset**: restore the default camera distance and target.
- **Pause / Resume**: toggle automatic rotation.
- The percentage readout reports relative camera zoom against the default view.

The globe remains an illustrative procedural body texture until a validated planetary basemap or terrain product is connected. The zoom controls change the 3D camera; they do not increase the underlying scientific image resolution.

### Scope preservation
This refresh changes only `site/worlds.html`, `site/worlds.js` and this documentation. The original Earth application files (`site/index.html`, `site/app.js`, `site/model.js`) are not edited by this navigation update.
