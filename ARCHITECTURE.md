# SWELL architecture (one page)

One question drives everything: **did the ground move, or did the radar only see the soil get wet?**

```
 NASA / partner data            SWELL pipeline (Python, swell/)                      Decision Studio (site/)
 ───────────────────            ───────────────────────────────                      ───────────────────────
 NISAR L2 GUNW  ─────────┐
 rain record (GPM/gauge) ├─► ingest.py ─► fit.py ──────────► twin.py ─► validate.py ─► data/site.json ─► index.html
 soil survey clay rating │   (to a grid)  1 learn artifact   Kalman     tests T1–T7     │                 map + 3D twin
 paved fraction          │                  on control ground filter,    contracts       │                 paint / type / sliders
 GPS (referee only) ─────┘                2 fit clay equation refusal    stakeholders    │                 Cause & effect  (causal.js)
                                          pinn.py: physics-informed      paper           │                 Research        (causal.js)
                                          network + ablation                             └─► data/stakeholder/* ─► role packages (zip)
 literature/ (summaries + links) ─────────────────────────────────────► data/literature.json ─► evidence under every causal link
```

## The cause-and-effect model (what affects what)

| Link | Equation | Where the number comes from | Checked by |
|---|---|---|---|
| rain → soil wetness | `A(t)=0.9·A(t−1)+rain`, `w=A/(A+40)` | stated assumption | forecast holdout T3 |
| wetness → false radar signal | `artifact = β·(1−paved)·Δw` | β learned on open low-clay control ground | GPS referee T1, control test |
| wetness, clay, paving → resting level | `G·w`, `G = α·clay·(1−b·paved)` | α, b fitted on training passes | clay map T2, paved vs open T6 |
| resting level → ground movement | `m(t+1)=m(t)+(G·w(t−τ)−m(t))/T` | T, τ fitted; T also estimated by `pinn.py` | T3, unseen zone T4 |
| movement + artifact → what the radar sees | `LOS = cos(inc)·m + artifact` | geometry | T1 |
| movement → structure tilt (upper bound) | `|m| / edge distance` | user input | not a design check |

The browser recomputes this chain for the selected cell on every change (painted cells, typed request, sliders, the
"Change a cause" buttons), so the graph, the map, the 3D block, the chart and the downloaded package always agree.

## Pages

- `/` Decision Studio (home): Explore → Investigate → Understand → Simulate → Act → Verify, plus bottom tabs
  Scenario · Timeline · Findings · Deliverables · **Cause & effect** · **Research**.
- More ▾: Earth observatory (`live.html`), Flood site twin (`site-twin.html`), Other worlds, classic, offline.

## What is real and what is not, today

- Real code paths, tested: every equation above, the tests, the network ablation, package export.
- The app shows no synthetic data. The synthetic fixture in `site/data/site.json` exists only so the tests can check the equations against a known answer; the pages hide it and `/` opens the real-feed Earth view until a real site is built.
- Real site: `python real_site.py --site dallas` fetches NISAR GUNW (ASF), rain (NASA POWER), clay (SoilGrids) and paving (ESA WorldCover), then builds and validates. Rehearsed offline end to end with files in the real formats; not yet run against the live servers.
- Known model limits: movement is fully recoverable (Welch et al. 2024 measured about a tenth that is permanent); one wetness
  series per scene; "vertical" assumes no sideways motion; α and T are only partly separable on a short record.

## Added 15 Nov

- `connections.py` + `site/connections.html`: one page tests all 17 services, stores the three optional keys in `.env`, finds real radar passes and builds the twin (`real_site.py`, window-only online reads).
- `swell/rl.py`: Q-learning for crew order inside the twin, scored against simple rules on held-out rain. Finding kept in the report: one-way drying of swollen clay increases movement, so the action is moisture stabilisation; and a simple clay-gain ranking is usually as good as the learned policy.
- `site/usecases.js`: "My decisions" tab. Each role gets three or four questions that run the twin and answer from the site's numbers. Also a switch to view the satellite-derived inputs (paving, clay, radar quality) that the Pave tool edits.
- `real_site.py` also fetches NASA POWER surface soil wetness and reports its rank correlation with SWELL's wetness index (not used in the fit).
- Not done: OPERA water, GPM IMERG granules, SMAP and Landsat as processed datasets. Rain is NASA POWER; SMAP is a map layer only.

## Added 15 Nov, midday: other satellites as evidence

`swell/sensors.py`, run automatically after the twin is built (`real_site.py`), each one optional and logged:
GPM IMERG rain (checks the rain driver), SMAP soil moisture (checks the wetness index), OPERA DISP-S1 Sentinel-1 motion
(test T1b: is NISAR closer to it after the correction?), HLS Landsat NDVI (false signal vs vegetation), OPERA DSWx open water
(explains refused cells). `swell/validate.py` also writes a radar-derived moisture susceptibility map and its agreement with the soil map.
All readers are tested offline on files in the documented layouts; none has yet been run against the live archives.
