# SWELL Worlds navigation refresh

## User-facing changes
- Split the previous all-in-one Worlds screen into five task-focused views.
- Persistent left rail for world selection, body reference and authoritative links.
- Dedicated **Explore**, **Environment**, **Habitation**, **Mission data** and **Data studio** tabs.
- Only the selected workspace is visible, reducing simultaneous panels and scrolling.
- Explicit **+ / − / Reset** camera zoom controls.
- Relative zoom percentage updates from camera changes, including mouse-wheel zoom.
- Existing drag-to-orbit, scroll-to-zoom and rotation pause/resume are retained.
- Responsive mobile layout stacks the world selector and workspace controls.

## Preserved
- Original Earth dashboard, application logic and physical model.
- Existing Worlds body registry, NASA PDS connector, upload API, file handling and planetary reference metadata.
- Existing world-specific source links and mission-context copy.

## Validation
- `node --check site/worlds.js` passes.
- `node --check site/app.js` passes.
- `node --check site/model.js` passes.
- Worlds HTML IDs are unique.
- Required view containers and zoom controls are present.
- Existing Python test suite result is recorded separately in the build response.

## Scientific limitation
The zoom controls alter the camera view, not the native resolution of the procedural globe texture. The existing caveat remains: globe textures are illustrative until a validated planetary basemap or terrain product is connected.
