# Browser check and navigation pass (14 Nov, afternoon)

Tested in a real headless Chromium against `python run_swell.py`, not static renders.

## Bug fixed
- `site/worlds.js`: `controls.addEventListener(...)` ran before `initGlobe()` created `controls`. The script
  stopped there, so the Worlds page had no globe, dead zoom buttons and empty side panels. `initGlobe()` now runs
  before the controls are wired. One-line move.

## Navigation changes (`site/index.html`, additive `<style id="nav-clarity">` block)
- The ten drawer tabs are grouped under three numbered headings plus "Your own data".
- Zoom buttons are plain + and - under a ZOOM caption.
- The header no longer clips its layer checkboxes at 1280-1920 px wide.

## Verified
- Earth zoom buttons move the camera (107 km -> 69 km -> 101 km).
- Worlds + button enlarges the globe; every Worlds view and world opens with no page errors.
- All ten Earth tabs open with no page errors.

## Not verified here
- NASA imagery, rain, fire and earthquake layers (network blocked in the test environment).
- The Worlds "Mission data" search and uploads against the live NASA archive.
- Phone-size layouts.

## Decision Studio (main page), 14 Nov afternoon

`site/index.html` + `site/studio.js` are now the main app. The earlier page is kept as `site/classic.html`. Other worlds stays a separate page (`site/worlds.html`).

- Steps along the top: Decision Studio, Explore Earth, Investigate, Understand, Simulate, Act, Verify.
- Map (CesiumJS) and 3D cut-away (three.js) show the same per-cell model state.
- Direct manipulation: pick + Water, Drainage or Pave under the map and drag over cells. The twin reruns per cell; map, 3D block, chart, findings and package all update.
- Imagery: NASA GIBS Blue Marble + VIIRS daily + HLS (off by default), Esri World Imagery for close-up detail, and the Natural Earth picture bundled with Cesium as the offline fallback.
- Checked in headless Chromium: no page errors on any step; package zip downloads.
- NOT checked here (network blocked in the build sandbox): NASA GIBS tiles, Esri tiles, USGS feed, place search. GIBS layer names `HLS_S30_Nadir_BRDF_Adjusted_Reflectance` and `SMAP_L4_Analyzed_Surface_Soil_Moisture` need a look on a normal connection; a wrong name only leaves that one layer blank.
- Left out on purpose: dollar figures, building IDs, borehole schedules and CAD files. SWELL has no cost, building or boring data, so showing them would be invented numbers.
