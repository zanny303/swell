# SWELL data pipeline

Separates rapidly refreshed **context** from scientific **measurement** products.

```bash
python -m pip install -r requirements-api.txt
python pipeline/harvest_context.py --bbox -97.8,32.3,-96.2,33.3 --out data/live
python pipeline/nisar_catalog.py --bbox -97.8,32.3,-96.2,33.3 --product GUNW --maturity VALIDATED --out data/nisar
```

- GIBS: browse imagery/context only.
- USGS ComCat: earthquake observations, not prediction.
- FIRMS: thermal anomaly detections; needs free `FIRMS_MAP_KEY`.
- NISAR GUNW: geocoded unwrapped interferogram for LOS displacement.
- NISAR GCOV: calibrated backscatter for inundation, disturbance, moisture and crop applications.
- NISAR SME2: soil-moisture product; maturity/availability must be checked.

NISAR search uses ASF `asf_search`. Granule download/streaming requires NASA Earthdata Login. Store credentials in `~/.netrc`, never in source or browser JS.

After discovery: select compatible orbit/track/polarization pairs; download; inspect HDF5, maturity, quality masks, geolocation and corrections; pair acquisitions without bridging temporal gaps; reproject ancillary data explicitly; create georeferenced COGs; run competing hypotheses and independent GNSS holdout validation; publish only valid pixels. Preserve source files and provenance.
