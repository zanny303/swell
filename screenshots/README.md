# Screenshot provenance

The image files in this folder are retained reference/fixture screenshots from earlier SWELL browser tests. They are not a fresh capture of the current Earth dashboard UI changes in this repair release.

The current Site Twin workflow was re-run in Chromium using `tests/browser_site_twin.py`; it uses a synthetic test DEM fixture and does not verify live USGS or NASA connectivity. A full live Earth-dashboard capture could not be completed in the build environment because browser navigation to the local server was blocked by its browser policy. Please do not treat these older images as proof of live provider coverage.
