# SWELL: a NISAR digital twin for cities on clay

**NASA Space Apps Challenge 2026 · Dancing with the SARs · Dallas, Texas**

When soil gets wet, L-band radar sees its phase shift even if the ground has not moved. The same rain makes clay really swell,
which cracks roads, pipes and foundations. SWELL streams NASA-ISRO NISAR radar, separates the two, models the real clay movement
cell by cell, lets planners, utilities, engineers, emergency managers and residents test decisions by painting changes straight
onto satellite imagery, and grades itself with tests whose pass marks were written before any real data (`PREREGISTRATION.md`).

- **Live copy, no login:** `<your Vercel or GitHub Pages link>`. The real Dallas twin running in your browser.
- **Full app:** this repository, run on your own computer (below).

---

## 1. Two ways to use SWELL

| | Live website (Vercel) | Full app on your computer |
|---|---|---|
| Real NISAR twin of Dallas: map, 3D ground block, time strip | ✓ | ✓ |
| Paint water, drainage, paving, green space; type a storm; before/after | ✓ | ✓ |
| Seven stakeholder roles and their questions | ✓ | ✓ |
| Compare two radar dates (swipe), Verify, correction study, Worlds | ✓ | ✓ |
| Ask the literature (retrieval over 23 sources) | ✓ | ✓ |
| Connections page, build a twin for **any** place from NASA's archive | – | ✓ (free NASA Earthdata login) |
| 3D city: real terrain, buildings, photorealistic city | – | ✓ (free Cesium ion token) |
| Ask SWELL (AI questions about the site), saving decisions | – | ✓ (your own AI key, or local Ollama) |
| **Keys needed** | **None.** Visitors are never asked for one | Your own, stored only in `.env` on your machine |

Keys are never put in the website or in this repository. `.gitignore` keeps `.env` out of git.

## 2. Run the full app (about 10 minutes the first time)

Needs Python 3.11 and git.

**Windows (PowerShell)**
```powershell
git clone https://github.com/<user>/<repo>.git
cd <repo>
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-site-twin.txt
.\.venv\Scripts\python.exe run_swell.py
```
**macOS / Linux**
```bash
git clone https://github.com/<user>/<repo>.git && cd <repo>
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-site-twin.txt
.venv/bin/python run_swell.py
```
Open **http://127.0.0.1:8000/**. The repository already contains the Dallas twin built from NISAR, so the Decision Studio opens on
real data straight away, with no keys.

To build a twin yourself (Dallas again, or any place), open **http://127.0.0.1:8000/connections.html**, enter the keys you want
(section 3), press **Test all connections**, then **Build the real twin**. Or from the command line:
```
python real_site.py --site dallas --yes --install-deps      # or: --bbox WEST SOUTH EAST NORTH --name "My city"
python compare_corrections.py                               # same radar, four processing chains, all scores in Verify
```

## 3. Keys: what each one unlocks, and where to get it (all free)

| Key (Connections page or `.env`) | Unlocks | Get it |
|---|---|---|
| `EARTHDATA_USERNAME` + `EARTHDATA_PASSWORD` (or `EARTHDATA_TOKEN`) | Building a twin from NISAR, plus SMAP, OPERA, HLS, GCOV | https://urs.earthdata.nasa.gov/users/new |
| (same account) approve "NASA GESDISC DATA ARCHIVE" | GPM IMERG rainfall | Earthdata profile → Applications → Authorized Apps |
| `CESIUM_ION_TOKEN` | 3D terrain and buildings; add "Google Photorealistic 3D Tiles" from the ion Asset Depot for the photorealistic city | https://ion.cesium.com/signup |
| `FIRMS_MAP_KEY` | Fire detections as data | https://firms.modaps.eosdis.nasa.gov/api/map_key/ |
| `SWELL_AI_PROVIDER` + `SWELL_AI_API_KEY` (+ `SWELL_AI_MODEL`) | Ask SWELL. Providers: `anthropic`, `openai`, `meta`, `compatible`, or `ollama` (local, no key) | https://console.anthropic.com · https://platform.openai.com/api-keys · https://llama.developer.meta.com · https://ollama.com |

No key is needed for NASA POWER rain, NASA GIBS imagery, USGS earthquakes, ISRIC SoilGrids, ESA WorldCover, or the Nevada
Geodetic Laboratory GPS stations. A copy of the variable names is in `.env.example`.

## 4. How it works

1. **Sense.** NISAR L2 GUNW 12-day pairs are read straight from NASA's archive (only the site window, not whole files), with
   NASA POWER rain, SoilGrids clay and WorldCover paving.
2. **Correct.** NISAR's own ionosphere, troposphere and solid-Earth-tide layers (`swell/corrections.py`), then a reference
   surface through stable ground. Open, low-clay "control" ground teaches how much wet soil shifts the radar; that false signal is removed.
3. **Model.** One clay equation: the ground heads toward a level set by wetness, clay and paving, with a lag (four fitted numbers).
   A physics-informed neural network and a reinforcement-learning crew-order policy are each scored against simpler baselines.
4. **Twin.** A Kalman filter updates each of 3,600 cells at every pass and forecasts with uncertainty. Unreliable cells are refused.
5. **Check.** Seven preregistered tests, including a **GPS referee** (Nevada Geodetic Laboratory stations in the radar line of
   sight). Independent checks: **NISAR GCOV HH/HV brightness** (NISAR's own view of soil wetting), NASA POWER soil wetness, SMAP,
   GPM and Sentinel-1 (OPERA) when reachable. Every forecast is re-checked at the next pass and failures stay on screen.

## 5. Results on real data, stated plainly

Dallas–Fort Worth, 8 provisional NISAR pairs, 5 July to 21 October 2026. Paved ground moving less than open ground passes, as
clay physics predicts. SWELL's wetness index tracks NASA's modelled surface soil wetness (rank correlation 0.64 over 136 days).
The forecast tests do not pass yet: pass-to-pass noise of about 17 mm (most likely atmosphere) is larger than the clay signal in
this short, provisional record. `compare_corrections.py` and the Verify step show every test under four processing chains.
Processing changes made after the first real run are recorded in `PREREGISTRATION.md` and those results are exploratory.

## 6. Make the live copy

```
python build_public_site.py --repo https://github.com/<user>/<repo>
```
This writes `public/`: the Decision Studio with the twin on this computer, read-only, no keys (it refuses to finish if it finds
anything that looks like one). **Vercel:** Add New → Project → import this repository → Deploy (`vercel.json` serves `public/`). Project documentation is in `docs/`.

## 7. Record a walkthrough
```
python run_swell.py                         (leave running)
python record_demo.py                       video + screenshots in demo_out/
python record_demo.py --stills              sharp slide screenshots in deck_stills/
python record_demo.py --short               30-second cut
```

## 8. Tests
```
python -m pytest -q                         110 Python tests (synthetic fixtures only)
node tests/e2e_playwright.js                24 browser checks (needs: npm install playwright)
```

## 9. Scope, data and AI use

- Decision support for planning inspections, not certification. Scenario numbers are model output under the inputs you choose.
  Approval stays with a named person; suggestions need engineer review.
- Synthetic test data exists only for automated tests, is labelled SYNTHETIC, and is never shown as real.
- **Data:** NASA NISAR L2 GUNW and GCOV (ASF DAAC), NASA POWER, NASA GIBS, NASA Earthdata (SMAP, GPM IMERG, OPERA DISP-S1 and
  DSWx, HLS), USGS, Nevada Geodetic Laboratory, ESA WorldCover, ISRIC SoilGrids, Esri World Imagery, Cesium ion (World Terrain,
  OSM Buildings), Google Photorealistic 3D Tiles. NISAR is a joint NASA–ISRO mission.
- **Use of AI:** code, tests and documentation were written with AI assistants (Anthropic Claude, OpenAI ChatGPT) under the
  author's direction; the idea and the challenge choice are the author's. No AI-generated images or video. The Worlds globes are
  procedural illustrations, labelled in the app.

License: see `LICENSE`.
