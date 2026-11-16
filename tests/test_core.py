"""Run: python -m pytest -q   (uses SYNTHETIC fixtures only)"""
import json, os, pathlib, subprocess, warnings
import numpy as np
from swell import synthetic, fit as F, twin as TW, contracts as C, stats as ST, physics as ph, stakeholders as S

warnings.simplefilter("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[1]
ENV = dict(os.environ, NO_COLOR="1", FORCE_COLOR="0")


def node(js):
    out = subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True, env=ENV).stdout
    return out.strip()


def setup_module(m):
    m.site = synthetic.make(); m.fr = F.fit_all(m.site)


def test_recovers_fixture_parameters():
    p, t = fr["par"], synthetic.TRUE
    assert abs(p["alpha"] - t["alpha"]) / t["alpha"] < 0.15 and abs(p["T"] - t["T"]) <= 4 and p["tau"] == t["tau"]
    assert abs(fr["beta"] - t["beta"]) / t["beta"] < 0.2


def test_reference_and_control_never_overlap():
    mk = F.masks(site)
    assert mk["ref"].sum() >= 5 and mk["control"].sum() >= 20 and not (mk["ref"] & mk["control"]).any() and not (mk["ref"] & mk["clay"]).any()


def test_missing_data_stays_missing():
    assert np.isnan(site["los"]).any()
    assert np.isnan(fr["mcorr"])[np.isnan(site["los"])].all()          # never turned into zero motion
    p = int(fr["test"][0]); a = TW.forecast_for_pass(site, fr, p)["mean"]
    assert np.isfinite(a).all()                                          # the twin still carries a state there


def test_artifact_removal_beats_naive_against_truth():
    pd = site["pass_days"]; truth = site["truth_motion"][pd] - site["truth_motion"][pd[0]]
    ok = F.masks(site)["ok"]
    assert np.sqrt(np.nanmean(((fr["mcorr"] - truth) ** 2)[:, ok])) < np.sqrt(np.nanmean(((fr["naive"] - truth) ** 2)[:, ok]))


def test_forecast_never_sees_its_target():
    p = int(fr["test"][0]); a = TW.forecast_for_pass(site, fr, p)["mean"].copy()
    f2 = dict(fr); f2["mcorr"] = fr["mcorr"].copy(); f2["mcorr"][p:] += 999.0
    assert np.allclose(a, TW.forecast_for_pass(site, f2, p)["mean"])


def test_adversarial_fixtures_fail_the_right_tests():
    must = dict(no_clay=["T2", "T3", "T4"], control_moves=["Control"], wrong_soil_map=["T2"])
    for adv, names in must.items():
        s = synthetic.make(adversarial=adv)
        got = {t["name"].split()[0]: t["passed"] for t in ST.run_all(s, F.fit_all(s))}
        assert all(got[n] is False for n in names), (adv, got)


def test_contract_tamper_detected_and_judged():
    z = S.zones(site)[7]; p = int(fr["test"][0]); fc = TW.forecast_for_pass(site, fr, p)
    c = C.make(site, z, fc, "engineer", "inspect", ["x"], "artifact", "v", zone_sigma=1.0)
    assert len(c["digest"]) == 64
    assert C.judge(c, site, fr["mcorr"][p], z)["arrival"] in ("supported", "contradicted")
    assert C.judge(c, site, fr["mcorr"][p] + 500, z)["arrival"] == "contradicted"
    assert C.judge(c, site, np.full_like(fr["mcorr"][p], np.nan), z)["arrival"] == "inconclusive"
    c["expected_observable"]["mean_mm"] += 1
    try: C.judge(c, site, fr["mcorr"][p], z); assert False
    except ValueError: pass


def test_scenarios_move_the_right_way():
    wet = TW.scenario(site, fr, extra_rain_mm=80)["scenario"][-1].mean()
    dry = TW.scenario(site, fr)["scenario"][-1].mean()
    drained = TW.scenario(site, fr, extra_rain_mm=80, wetting_reduction=.5)["scenario"][-1].mean()
    assert wet > drained > dry


def test_stakeholder_files():
    hz = TW.horizon_maps(site, fr); table = S.zone_table(site, fr, hz["drying"], hz["storm"])
    files = S.build(site, fr, table, 156, "v")
    assert S.validate_cap(files["emergency_draft_alert.cap.xml"]) == []
    assert "foundation" not in files["engineer_investigation_inputs.csv"].lower()
    gj = json.loads(files["planner_zones.geojson"]); assert gj["features"][0]["geometry"]["type"] == "Polygon"
    assert len(json.loads(files["engineer_investigation_inputs.json"])["meta"]["sha256"]) == 64
    assert any(r["status"] == "UNRESOLVED" for r in table)


def test_browser_model_matches_python():
    web = json.load(open(ROOT / "site/data/site.json"))
    out = float(node("const M=require('./site/model.js');const S=require('./site/data/site.json');"
                     "console.log(M.scenario(S,{rainMm:80,rainDays:3,cells:[[20,20]],horizon:30}).scen[29])"))
    f2 = dict(fr); f2["par"] = dict(fr["par"], **{k: web["params"][k] for k in ("alpha", "b", "T", "tau")})
    py = TW.scenario(site, f2, extra_rain_mm=80, rain_days=3)["scenario"][-1][20, 20]
    assert abs(out - py) < 0.35      # web data are rounded to 0.1 mm / 0.1 %


def test_typed_request_parser():
    o = json.loads(node("const M=require('./site/model.js');console.log(JSON.stringify(M.parseRequest("
                        "'120 mm of rain over 4 days after 3 weeks of drought, with drainage cutting wetting by 40%').settings))"))
    assert (o["rainMm"], o["rainDays"], o["dryDays"], o["reduction"]) == (120, 4, 21, 0.4)
    assert json.loads(node("const M=require('./site/model.js');console.log(JSON.stringify(M.parseRequest('hello')))"))["ignored"]


def test_aftershock_rate_decays():
    r = ph.reasenberg_jones_rate(np.array([1., 10., 100.]), 7.0)
    assert r[0] > r[1] > r[2] > 0


def test_structure_screen_is_explicit_upper_bound_and_scales():
    from swell import structures
    a = structures.screen(20, "Post-tensioned slab", edge_m=1.5, structure_span_m=10)
    b = structures.screen(20, "Post-tensioned slab", edge_m=1.5, structure_span_m=10, edge_reduction=.5)
    assert abs(a["upper_bound_angular_distortion"] - (20/1500)) < 1e-12
    assert abs(b["edge_movement_mm"] - 10) < 1e-12
    assert a["status"] == "SCREENING_SCENARIO_NOT_STRUCTURAL_ANALYSIS"
    assert structures.screen(20, "Flexible pavement (road)")["building_guide"] is None

def test_missing_ancillary_pixels_are_not_assigned_to_clay_or_control():
    import numpy as np
    s = synthetic.make()
    s["lep"] = s["lep"].copy(); s["lep"][0, 0] = np.nan
    s["paved"] = s["paved"].copy(); s["paved"][0, 1] = np.nan
    m = F.masks(s)
    assert not m["ok"][0, 0] and not m["ok"][0, 1]
    assert not m["clay"][0, 0] and not m["control"][0, 1]


def test_structure_screen_browser_and_python_match():
    from swell import structures
    py = structures.screen(20, "Post-tensioned slab", edge_m=1.5, structure_span_m=10, edge_reduction=.25)
    js = json.loads(node("const M=require('./site/model.js');console.log(JSON.stringify(M.structureScreen(20,'Post-tensioned slab',10,1.5,.25)))"))
    assert abs(js["distortion"] - py["upper_bound_angular_distortion"]) < 1e-12
    assert abs(js["edgeMovementMm"] - py["edge_movement_mm"]) < 1e-12


def test_frontend_contract_and_syntax():
    import re
    html = (ROOT / "site/classic.html").read_text()  # the earlier page, kept as the classic view
    js = (ROOT / "site/app.js").read_text()
    ids = set(re.findall(r'id="([^"]+)"', html))
    refs = set(re.findall(r'\$\("([^"]+)"\)', js))
    assert not (refs - ids), f"Missing HTML elements: {sorted(refs - ids)}"
    assert all(x in ids for x in ["globe", "drawer", "bottom", "coordinateSearch", "metricPasses", "tab-structures"])
    subprocess.run(["node", "--check", "site/app.js"], cwd=ROOT, check=True)
    subprocess.run(["node", "--check", "site/model.js"], cwd=ROOT, check=True)


def test_dataset_source_label_does_not_claim_all_user_data_are_nisar():
    js = (ROOT / "site/app.js").read_text()
    assert 'USER-LOADED · ${sourceName}' in js
    assert '"NASA NISAR"' not in js


def test_research_copilot_uses_loaded_validation_evidence_and_labels_synthetic():
    js = """const fs=require('fs'); const R=require('./site/research.js');
    const s=JSON.parse(fs.readFileSync('./site/data/site.json','utf8'));
    const r=R.report(s), a=R.answer(s,'How does the forecast compare with baselines?');
    console.log(JSON.stringify({synthetic:r.synthetic,candidates:r.candidates.length,best:r.best.id,
      answer:a.body,limitations:a.limitations,evidence:a.evidence}));"""
    got = json.loads(node(js))
    assert got["synthetic"] is True
    assert got["candidates"] == 3
    assert got["best"] == "M2"
    assert "SYNTHETIC FIXTURE" in got["limitations"][0]
    assert "T3 Forecast holdout" in got["evidence"]

def test_research_copilot_does_not_claim_missing_gnss_data():
    js = """const R=require('./site/research.js');
    const s={source:'USER DATA',name:'Test',pass_days:[0],zones:[],tests:[]};
    console.log(JSON.stringify(R.answer(s,'What does GPS validation show?')));"""
    got = json.loads(node(js))
    assert "does not contain usable T1 GPS" in got["body"]


def test_decision_studio_page():
    import re
    subprocess.run(["node", "--check", "site/studio.js"], cwd=ROOT, check=True)
    # Decision Studio (main page): the ids studio.js needs that are not created by its own templates
    studio = (ROOT / "site/index.html").read_text()
    sids = set(re.findall(r'id="([^"]+)"', studio))
    assert all(x in sids for x in ["globe", "twin", "mini", "right", "steps", "tools", "passes", "chart", "findings", "gen", "ask", "run", "role", "day"])


def test_pinn_gradients_and_ablation():
    """Analytic gradients match finite differences, and the ablation reports all four numbers."""
    import numpy as np
    from swell import pinn, synthetic, fit as F
    rng = np.random.default_rng(0); p = pinn._init(rng); raw = np.array([.3, -.2, 2.0]); N = 12
    b = dict(Xk=rng.random((N, 3)), X0=rng.random((N, 3)), y=rng.normal(0, 5, N), Xa=rng.random((N, 3)), Xb=rng.random((N, 3)),
             lep=rng.random(N) * 6, pv=rng.random(N), wlag=rng.random(N))
    L, g, graw, *_ = pinn.loss_and_grad(p, raw, b, 5.0, 4.0)
    for key, idx in (("W1", (1, 2)), ("W2", (3, 4)), ("W3", (5, 0)), ("b2", (2,))):
        old = p[key][idx]; p[key][idx] = old + 1e-5; Lp = pinn.loss_and_grad(p, raw, b, 5.0, 4.0)[0]
        p[key][idx] = old - 1e-5; Lm = pinn.loss_and_grad(p, raw, b, 5.0, 4.0)[0]; p[key][idx] = old
        assert abs((Lp - Lm) / 2e-5 - g[key][idx]) < 1e-4 * max(1, abs(g[key][idx]))
    for k in range(3):
        r2 = raw.copy(); r2[k] += 1e-5; Lp = pinn.loss_and_grad(p, r2, b, 5.0, 4.0)[0]; r2[k] -= 2e-5; Lm = pinn.loss_and_grad(p, r2, b, 5.0, 4.0)[0]
        assert abs((Lp - Lm) / 2e-5 - graw[k]) < 1e-4 * max(1, abs(graw[k]))
    site = synthetic.make(seed=3); fr = F.fit_all(site); out = pinn.run(site, fr, steps=200)
    assert set(out["heldout_rmse_mm"]) == {"no_change", "physics_fit", "network_only", "physics_informed"}
    assert all(np.isfinite(v) for v in out["heldout_rmse_mm"].values()) and 0 < out["discovered"]["b"] < 1


def test_cause_effect_view_and_literature():
    import json as _json
    subprocess.run(["node", "--check", "site/causal.js"], cwd=ROOT, check=True)
    lit = _json.loads((ROOT / "site/data/literature.json").read_text())["sources"]
    assert len(lit) >= 15 and all(s["url"].startswith("http") and s["text"] for s in lit)
    assert any("soil moisture" in s["title"].lower() for s in lit)
    web = _json.loads((ROOT / "site/data/site.json").read_text())
    assert set(web["pinn"]["heldout_rmse_mm"]) == {"no_change", "physics_fit", "network_only", "physics_informed"}
    assert "causal.js" in (ROOT / "site/index.html").read_text()


def test_real_site_chain_and_layout(tmp_path):
    """Pair choice from official file names, and layout detection on a file that is NOT laid out as ingest.py assumes."""
    import sys, h5py, numpy as np
    sys.path.insert(0, str(ROOT)); import real_site as R
    nm = lambda a, b, v="001": f"NISAR_L2_PR_GUNW_005_034_A_071_006_4000_SH_{a}T000000_{a}T000030_{b}T000000_{b}T000030_X05010_N_F_J_{v}.h5"
    rows = [dict(name=nm(a, b), url="https://x/" + nm(a, b), bytes=1, track=34, frame=71) for a, b in
            [("20260812", "20260824"), ("20260824", "20260905"), ("20260905", "20260917"), ("20260812", "20260905")]]
    rows += [dict(name=nm("20260905", "20260917", "002"), url="https://x/" + nm("20260905", "20260917", "002"), bytes=1, track=34, frame=71),
             dict(name=nm("20260601", "20260613"), url="https://x/" + nm("20260601", "20260613"), bytes=1, track=34, frame=71)]
    chain = R.choose_chain(rows, 8)
    assert [(r["ref"], r["sec"]) for r in chain] == [("2026-08-12", "2026-08-24"), ("2026-08-24", "2026-09-05"), ("2026-09-05", "2026-09-17")]
    assert chain[-1]["name"].endswith("_002.h5")           # newest processing wins; the 24-day pair and the disconnected June pair are dropped
    f = tmp_path / "g.h5"
    with h5py.File(f, "w") as h:
        g = h.create_group("/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram"); v = g.create_group("VV")
        v["unwrappedPhase"] = np.zeros((4, 4)); v["coherenceMagnitude"] = np.ones((4, 4)); v["connectedComponents"] = np.ones((4, 4))
        g["xCoordinates"] = np.arange(4.0); g["yCoordinates"] = np.arange(4.0); g["projection"] = 32614
    lay = R.detect_layout(f)
    assert lay["phase"].endswith("/VV/unwrappedPhase") and lay["x"].endswith("unwrappedInterferogram/xCoordinates")


def test_connections_keys_are_validated_and_never_echoed(tmp_path, monkeypatch):
    import sys, os, pytest
    sys.path.insert(0, str(ROOT)); import connections as C
    monkeypatch.setattr(C, "ENV", tmp_path / ".env"); monkeypatch.setattr(C, "ROOT", tmp_path)
    for k in C.KEYS: monkeypatch.delenv(k, raising=False)
    with pytest.raises(ValueError): C.save_keys({"NOT_A_KEY": "x"})
    with pytest.raises(ValueError): C.save_keys({"FIRMS_MAP_KEY": "has space"})
    assert C.save_keys({"EARTHDATA_USERNAME": "zed_user", "EARTHDATA_PASSWORD": "s3cret-pass!"}) == ["EARTHDATA_USERNAME", "EARTHDATA_PASSWORD"]
    assert "s3cret-pass!" in (tmp_path / ".env").read_text() and ".env" in (tmp_path / ".gitignore").read_text()
    assert C.key_state()["EARTHDATA_PASSWORD"] is True and "s3cret" not in json.dumps(C.key_state())
    def boom(lat, lon): raise RuntimeError("server said: bad password s3cret-pass! for zed_user")
    monkeypatch.setattr(C, "CHECKS", [("earthdata", "x", "account", "y", boom), ("firms", "f", "account", "y", C.c_firms)])
    out = C.run(); txt = json.dumps(out)
    assert "s3cret-pass!" not in txt and out["results"][0]["status"] == "failed" and out["results"][1]["status"] == "needs_key"
    assert out["ready_for_real_twin"] is False
    C.save_keys({"EARTHDATA_PASSWORD": ""}); assert "EARTHDATA_PASSWORD" not in (tmp_path / ".env").read_text()


def test_rl_reports_all_policies_and_is_honest():
    from swell import rl, synthetic, fit as F
    site = synthetic.make(seed=5); fr = F.fit_all(site); out = rl.run(site, fr, episodes=150, eval_n=30)
    e = out["exposure"]
    assert set(e) == {"no action", "random order", "largest movement first", "largest clay gain first", "learned policy"}
    assert len(out["suggested_order"]) == 5 and len(set(out["suggested_order"])) == 5
    rules = min(v for k, v in e.items() if k not in ("learned policy", "no action"))
    assert out["learned_beats_rules"] == ((rules - e["learned policy"]) / rules > 0.01)      # the claim follows the numbers
    subprocess.run(["node", "--check", "site/usecases.js"], cwd=ROOT, check=True)


def test_other_satellite_readers_offline(tmp_path):
    """Files in the documented layouts of GPM IMERG, SMAP L3 and OPERA DISP-S1; and the cross-sensor referee on a known answer."""
    import h5py, numpy as np
    from pyproj import CRS, Transformer
    from swell import sensors as SN
    bbox = [-97.05, 32.60, -96.55, 33.00]
    with h5py.File(tmp_path / "imerg.nc4", "w") as f:
        f["lon"] = np.arange(-179.95, 180, 0.1); f["lat"] = np.arange(-89.95, 90, 0.1); a = np.full((1, 3600, 1800), 2.0, "f4"); a[0, 825:840, 1220:1236] = 12.0; a[0, 0, 0] = -9999.9
        f["precipitation"] = a
    with h5py.File(tmp_path / "imerg.nc4", "r") as f: assert 11.9 < SN.imerg_window(f, bbox) <= 12.0
    with h5py.File(tmp_path / "smap.h5", "w") as f:
        lat = np.linspace(85, -85, 400); lon = np.linspace(-180, 180, 900); LA, LO = np.meshgrid(lat, lon, indexing="ij")
        for grp, suf, val in (("Soil_Moisture_Retrieval_Data_AM", "", 0.30), ("Soil_Moisture_Retrieval_Data_PM", "_pm", 0.20)):
            g = f.create_group(grp); sm = np.full(LA.shape, -9999.0); m = (LA > 32.4) & (LA < 33.2) & (LO > -97.3) & (LO < -96.3); sm[m] = val
            la, lo = LA.copy(), LO.copy(); la[::7, ::5] = -9999.0; lo[::7, ::5] = -9999.0
            g["latitude" + suf] = la; g["longitude" + suf] = lo; g["soil_moisture" + suf] = sm
    with h5py.File(tmp_path / "smap.h5", "r") as f: assert abs(SN.smap_window(f, bbox) - 0.25) < 1e-6
    assert SN.disp_dates("OPERA_L3_DISP-S1_IW_F40286_VV_20160701T005555Z_20160818T005558Z_v1.0_20250724T212204Z.nc") == ("2016-07-01", "2016-08-18")
    crs = CRS.from_epsg(32614); tr = Transformer.from_crs(4326, crs, always_xy=True); (x0, x1), (y0, y1) = tr.transform([-97.2, -96.4], [32.5, 33.1])
    x = np.arange(x0, x1, 300.0); y = np.arange(y1, y0, -300.0)
    with h5py.File(tmp_path / "disp.nc", "w") as f:
        f["x"] = x; f["y"] = y; f["displacement"] = np.full((1, len(y), len(x)), 0.004); mk = np.ones((1, len(y), len(x)), "u1"); mk[0, :5] = 0; f["recommended_mask"] = mk
        f.create_dataset("spatial_ref", data=0).attrs["crs_wkt"] = crs.to_wkt()
    with h5py.File(tmp_path / "disp.nc", "r") as f: d = SN.disp_window(f, bbox, 10)
    assert d.shape == (10, 10) and np.nanmax(np.abs(d - 4.0)) < 1e-6
    one = np.ones((2, 2)); cum = SN.chain_disp([("2026-01-01", "2026-01-13", one), ("2026-01-01", "2026-01-25", 2 * one), ("2026-01-25", "2026-02-06", one)])
    assert cum["2026-02-06"][0, 0] == 3.0 and cum["2026-01-13"][0, 0] == 1.0      # reference date jumps on 25 Jan
    # referee: Sentinel-1 built from the true motion must be closer to the corrected NISAR than to the raw NISAR
    web = json.loads((ROOT / "site/data/site.json").read_text()); n = web["n"]; inc = np.radians(web["inc_deg"])
    inf = np.array([[[np.nan if v is None else v for v in r] for r in m] for m in web["inferred_motion"]], float)
    s1 = np.nan_to_num(inf) * np.cos(np.radians(SN.S1_INCIDENCE_DEG)); import datetime as dt
    cum = {(dt.date(2026, 8, 1) + dt.timedelta(int(d))).isoformat(): s1[k] for k, d in enumerate(web["pass_days"])}
    res = SN.cross_sensor(web, cum, "2026-08-01")
    assert res["status"] == "ok" and res["passed"] and res["rms_swell_mm"] < 0.5 < res["rms_naive_mm"]


def test_site_json_is_strict_json():
    """A real site can have cells with no soil or land-cover value. The file the browser loads must still be valid JSON."""
    txt = (ROOT / "site/data/site.json").read_text()
    json.loads(txt, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(f"non-finite number {c} in site.json")))


def test_planner_and_e2e_scripts_parse():
    for f in ("site/planner.js", "tests/e2e_playwright.js"):
        subprocess.run(["node", "--check", f], cwd=ROOT, check=True)
    html = (ROOT / "site/index.html").read_text()
    assert 'data-tool="green"' in html and "planner.js" in html


def test_focus_pass_and_dependency_preflight(monkeypatch):
    import sys
    subprocess.run(["node", "--check", "site/focus.js"], cwd=ROOT, check=True)
    assert "focus.js" in (ROOT / "site/index.html").read_text()
    sys.path.insert(0, str(ROOT)); import real_site as R
    monkeypatch.setattr(R, "missing_packages", lambda: ["rasterio", "pyproj"])
    monkeypatch.setattr(R, "OUT", ROOT / "out")
    assert R.main(["--site", "dallas", "--check"]) == 3           # stops with the exact pip command instead of failing mid-build
    assert "pip install rasterio pyproj" in (ROOT / "out/real_site_log.txt").read_text()
    (ROOT / "out/real_site_log.txt").unlink()
    cover = R._cover({"umm": {"SpatialExtent": {"HorizontalSpatialDomain": {"Geometry": {"GPolygons": [{"Boundary": {"Points": [
        {"Longitude": -98, "Latitude": 32}, {"Longitude": -96, "Latitude": 32}, {"Longitude": -96, "Latitude": 34}, {"Longitude": -98, "Latitude": 34}]}}]}}}}}, [-97.05, 32.6, -96.55, 33.0])
    assert cover == 1.0 and R._cover({}, [0, 0, 1, 1]) == 0.5


# ---------------------------------------------------------------- NISAR correction layers (troposphere / tides)
def _cube_file(tmp_path, with_layers=True, zero=False):
    import h5py
    from swell import corrections as CR
    p = tmp_path / "g.h5"; cx = np.arange(0, 20000, 2000.0); cy = np.arange(0, 20000, 2000.0)
    base = np.add.outer(cy / 1e4, cx / 1e4)                     # smooth ramp in radians
    with h5py.File(p, "w") as f:
        R_ = CR.RADAR_GRID + "/"
        f[R_ + "xCoordinates"] = cx; f[R_ + "yCoordinates"] = cy; f[R_ + "heightAboveEllipsoid"] = np.array([0.0, 100.0, 300.0])
        if with_layers:
            lay = np.zeros_like(base) if zero else base
            f[R_ + "wetTroposphericPhaseScreen"] = np.stack([lay * 2, lay, lay * 0]).astype("f4")
            f[R_ + "hydrostaticTroposphericPhaseScreen"] = np.stack([lay, lay, lay]).astype("f4")
    return p, base


def test_corrections_read_cube_at_height(tmp_path):
    import h5py
    from swell import corrections as CR
    p, base = _cube_file(tmp_path)
    x = np.arange(1000, 17000, 500.0); y = np.arange(1000, 17000, 500.0)
    with h5py.File(p, "r") as f:
        scr, notes = CR.screens(f, x, y, ground_height_m=100.0)
    assert "troposphere" in scr and "wet" in notes["troposphere"]
    want = 2 * np.add.outer(y / 1e4, x / 1e4)                   # wet at 100 m = base, hydrostatic = base
    assert np.allclose(scr["troposphere"], want, atol=1e-5)


def test_corrections_missing_or_empty_layers_are_not_invented(tmp_path):
    import h5py
    from swell import corrections as CR
    x = y = np.arange(1000, 9000, 1000.0)
    p, _ = _cube_file(tmp_path, with_layers=False)
    with h5py.File(p, "r") as f:
        scr, notes = CR.screens(f, x, y)
    assert scr == {} and "not in this file" in notes["troposphere"]
    (tmp_path / "z").mkdir(); p2, _ = _cube_file(tmp_path / "z", zero=True)
    with h5py.File(p2, "r") as f:
        scr, notes = CR.screens(f, x, y)
    assert scr == {} and "empty" in notes["troposphere"]


def test_corrections_sign_check_and_highpass():
    from swell import corrections as CR
    rg = np.random.default_rng(0); scr = [rg.normal(0, 1, (40, 40)) for _ in range(4)]
    ph_ = [s + rg.normal(0, .1, s.shape) for s in scr]
    sign, st = CR.choose_sign(ph_, scr)
    assert sign == -1 and st["variance_removed_pct"] > 90
    sign2, st2 = CR.choose_sign([-p for p in ph_], scr)
    assert sign2 == +1 and st2["applied"] == "added"
    yy, xx = np.mgrid[0:40, 0:40]; ramp = xx * 0.5; bump = np.zeros((40, 40)); bump[18:22, 18:22] = 5
    hp = CR.highpass(ramp + bump, None, 3.0)
    assert np.nanstd(hp[5:35, 5:35] - (bump - bump.mean())[5:35, 5:35]) < 1.5 and abs(hp[20, 20]) > 2.5


# ---------------------------------------------------------------- GNSS referee (NGL) and NISAR GCOV brightness
def test_gnss_station_list_and_tenv3_parsing():
    from swell import gnss
    lst = "Sta Lat(deg) Long(deg) Hgt(m)\nTXDA 32.80 -96.80 150.0 x\nFAR1 40.0 -100.0 10\nTXFW 32.75 263.30 180.0\nbad line\n"
    st = gnss.stations(lst, [-97.05, 32.60, -96.55, 33.00])
    assert set(st) == {"TXDA", "TXFW"} and abs(st["TXFW"][1] + 96.70) < 1e-6   # 263.30 E is -96.70; FAR1 is outside
    assert set(gnss.stations(lst, [-96.75, 32.6, -96.6, 33.0])) == {"TXFW"}
    t = ("site YYMMMDD yyyy.yyyy __MJD week d reflon e0 east n0 north u0 up ant sig_e sig_n sig_u corr_en corr_eu corr_nu lat lon h\n"
         "TXDA 26JUL05 2026.5068 61226 2425 0 -97.0 12 0.123 34 0.456 0 0.0102 0 0.001 0.001 0.003 0 0 0 32.8 -96.8 150\n"
         "TXDA 26JUL06 2026.5096 61227 2425 1 -97.0 12 0.124 34 0.457 0 0.0080 0 0.001 0.001 0.003 0 0 0 32.8 -96.8 150\n")
    rows = gnss.parse_tenv3(t)
    import datetime as dt
    assert rows[0][0] == dt.date(2026, 7, 5) and abs(rows[0][1] - 10.2) < 1e-6 and abs(rows[1][1] - 8.0) < 1e-6
    cells = gnss.to_cells({"A": dict(lat=32.99, lon=-97.04), "B": dict(lat=31.0, lon=-97.0)}, [-97.05, 32.60, -96.55, 33.00], 60)
    assert cells["A"]["cell"] == [1, 1] and "B" not in cells


def test_gcov_window_and_summary(tmp_path):
    import h5py
    from pyproj import Transformer
    from swell import gcov
    bbox = [-97.05, 32.60, -96.55, 33.00]; n = 12
    tr = Transformer.from_crs(4326, 32614, always_xy=True); (x0, x1), (y0, y1) = tr.transform([bbox[0] - .05, bbox[2] + .05], [bbox[1] - .05, bbox[3] + .05])
    x = np.arange(x0, x1, 400.0); y = np.arange(y1, y0, -400.0)
    grids = []
    for k, wet in enumerate([0.1, 0.5, 0.2, 0.7, 0.3]):
        p = tmp_path / f"g{k}.h5"
        with h5py.File(p, "w") as f:
            g = f.create_group("/science/LSAR/GCOV/grids/frequencyA")
            g["HHHH"] = np.full((len(y), len(x)), 0.05 * (1 + wet), "f4"); g["HVHV"] = np.full((len(y), len(x)), 0.01, "f4")
            g["xCoordinates"] = x; g["yCoordinates"] = y; g["projection"] = 32614
        with h5py.File(p, "r") as f:
            win = gcov.window(f, bbox, n)
        assert win["co"].shape == (n, n) and win["pols"] == ("HH", "HV")
        grids.append((f"2026-07-{5 + 12 * k:02d}" if 5 + 12 * k < 32 else f"2026-08-{5 + 12 * k - 31:02d}", win))
    web = dict(paved=np.zeros((n, n)).tolist(), wetness=[0.1] * 12 + [0.5] * 12 + [0.2] * 12 + [0.7] * 12 + [0.3] * 12, pass_days=[0, 12, 24, 36, 48],
               artifact=[np.zeros((n, n)).tolist()] * 5)
    out = gcov.summarise(web, "2026-07-05", grids)
    assert out["wetness_vs_brightness"] > 0.9 and len(out["d_co_db"]) == 5 and out["d_co_db"][0][0][0] == 0.0
    assert "not used in the fit" in out["finding"]


def test_corrections_gate_and_gap_fill(tmp_path):
    import h5py
    from swell import corrections as CR
    rg = np.random.default_rng(1); ph_ = [rg.normal(0, 1, (30, 30)) for _ in range(3)]; junk = [rg.normal(0, 1, (30, 30)) for _ in range(3)]
    sign, st = CR.choose_sign(ph_, junk)
    assert sign == 0 and "not applied" in st["applied"]
    p, base = _cube_file(tmp_path)
    with h5py.File(p, "r+") as f:
        d = f[CR.RADAR_GRID + "/wetTroposphericPhaseScreen"]; a = d[...]; a[:, :, -2:] = np.nan; d[...] = a
    x = np.arange(1000, 17000, 500.0); y = np.arange(1000, 17000, 500.0)
    with h5py.File(p, "r") as f:
        scr, notes = CR.screens(f, x, y, 100.0)
    assert "troposphere" in scr and np.isfinite(scr["troposphere"]).all()
