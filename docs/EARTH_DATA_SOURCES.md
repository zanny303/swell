# Earth imagery and public context feeds

## NASA GIBS satellite imagery

The Earth base layer now uses NASA GIBS WMS:
`https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi`

Selectable true-colour layers:
- `MODIS_Terra_CorrectedReflectance_TrueColor`
- `MODIS_Aqua_CorrectedReflectance_TrueColor`
- `VIIRS_SNPP_CorrectedReflectance_TrueColor`

GIBS provides pre-generated visualization layers through OGC WMS/WMTS/TMS services. The client requests the date two days before the current UTC date to reduce requests for imagery that has not yet been ingested. This is a daily satellite composite, not a live video stream. Resolution and temporal availability vary by product. NASA notes some NRT visualization products are generated within 3.5 hours, but that is not a guarantee for every layer.

Other contextual layers:
- `IMERG_Precipitation_Rate` (precipitation visualization)
- `VIIRS_SNPP_Thermal_Anomalies_375m_All` (thermal anomaly visualization)
- `MODIS_Terra_Cloud_Top_Pressure` (cloud context; availability should be checked in GIBS capabilities)

## USGS earthquake feed

The app requests:
`https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson`

The feed is refreshed every 60 seconds by the browser. It represents the public M2.5+ event catalog for the past day, not a prediction feed.

## Esri reference imagery

Optional zoom-in basemap:
`https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`

This is labelled as reference imagery and must not be interpreted as a current observation or NASA data.

## SWELL deformation twin

The study overlay is read from `site/data/site.json`. The included file is explicitly synthetic. It is not a live NISAR feed. NISAR raw GUNW/GCOV acquisition discovery, download, processing, geocoding, quality control, independent GNSS validation and global operational coverage remain separate integration work.

## NASA acknowledgment

“We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS).”

Official documentation:
- https://nasa-gibs.github.io/gibs-api-docs/
- https://nasa-gibs.github.io/gibs-api-docs/access-basics/
- https://nasa-gibs.github.io/gibs-api-docs/available-visualizations/
- https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
