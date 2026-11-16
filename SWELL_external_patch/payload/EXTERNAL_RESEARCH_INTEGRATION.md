# SWELL: public research and independent-evidence integration

Apply after SWELL Recovery Patch. No replacement of real site, prior model, credentials, or code not on the manifest. Stop the server, use your existing venv, then:

```powershell
python .\SWELL_external_patch\apply_external_patch.py --project .
python -m pip install pyflwdir
python run_swell.py
```

Open Earth → Independent evidence → Retrieve independent GNSS. The connector uses daily final IGS20 solutions from NGL, discovers stations inside the real NISAR AOI, checks actual acquisition dates against provenance, and retrieves up to six overlapping stations. No interpolation. Station positions are shown on the globe and exact-date vertical changes are listed. The GNSS report is keyed by the active site file hash; it augments the AI evidence but does not change the fit or validation scores. If no station or matched date exists, report absence. GNSS must still be screened for monument stability, step discontinuities, horizontal displacement and the common radar reference; point vertical changes cannot be directly treated as radar LOS data. Cite the individual station operator and Blewitt et al. (2018), DOI 10.1029/2018EO104623.

In Independent evidence → Search current literature, use a public scientific query, not personal or confidential information. OpenAlex searches up to eight open-access records and excludes marked retractions/corrections. It returns bibliographic metadata and bounded abstract excerpts where available. It caches the retrieval/hash independently of the model. Ask SWELL a related question afterwards to retrieve relevant cached excerpts alongside curated BM25 sources. No chat questions are automatically transmitted to OpenAlex. Your configured AI provider still receives its usual context, including relevant cached evidence. Abstracts are not full-text peer-review or site validation.

Local terrain twin → Terrain only → Compute terrain flow paths. This directly calls Deltares PyFlwDir `from_dem`, `upstream_area` and `basins`. The resulting map uses the same projected DEM grid as your physical simulator and displays upstream contributing area and basin IDs. Locate a convergence cell, then use the existing drain painting tool to test a hypothetical intervention under identical rainfall. D8 filled-terrain/edge-outlet assumptions and domain clipping mean the map does not locate real pipes or estimate flood depth. The engine does NOT replace or modify the original elevation array or scientific fit.

Record with `python record_recovery_demo.py` in a second terminal. New scenes request actual GNSS, OpenAlex and DEM routing; unavailable services are disclosed in the report. The normal recorder still displays the broader Earth, local twin and Worlds workflows.

## Source and license references
- Deltares PyFlwDir, MIT: https://github.com/Deltares/pyflwdir ; API https://deltares.github.io/pyflwdir/latest/_generated/pyflwdir.from_dem.html ; algorithm Wang & Liu (2006), https://doi.org/10.1080/13658810500433453 . Installed as a separate dependency, not vendored.
- NGL official data portal: https://geodesy.unr.edu/PlugNPlayPortal.php ; holdings https://geodesy.unr.edu/NGLStationPages/DataHoldings.txt ; IGS20 daily archive https://geodesy.unr.edu/gps_timeseries/IGS20/tenv3/IGS20/ .
- OpenAlex API: https://help.openalex.org/api/ ; works attributes https://help.openalex.org/data/works/attributes/ . Keyless availability/rate limits depend on upstream.
- Further work (not implemented): MintPy https://github.com/insarlab/MintPy for network inversion, phase closure on redundant interferograms, reference stability; NASA OPERA displacement and water products for independent radar comparison; ANUGA and EPA SWMM for hydraulic/drainage-network models after gathering surveyed network data.

## Verification limits
117 Python tests passed (five new tests use controlled fixtures/mock provider responses); JavaScript syntax and Python compilation checked. The sandbox could not install PyFlwDir from its configured package index; true external-engine execution and live data calls must be confirmed in your environment. No revised Dallas accuracy claims, no changed scientific pass thresholds, and no generated satellite or GNSS observations.
