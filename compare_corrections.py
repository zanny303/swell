"""Correction study: run the same real site through four correction chains and put the scores side by side.

    python compare_corrections.py                 (uses the site last built by real_site.py, keeps variant B)
    python compare_corrections.py --keep A        (afterwards show the first-run processing in the app instead)

Nothing is downloaded again except NISAR's small troposphere / tide layers, if the saved radar windows lack them.

  A  first run         ionosphere layer + reference surface through stable ground (what the first Dallas run used)
  B  NISAR layers      A + NISAR's own troposphere and solid-Earth-tide layers. DEFAULT from this version on, chosen because
                       NASA ships these layers for exactly this purpose (the plan listed them before any real data; a
                       shape check skipped them). Chosen before scoring, kept whatever the scores say.
  C  local contrast    B + a 5 km high-pass that keeps only differences between neighbouring ground. EXPLORATORY.
  D  raw               ionosphere only, no surface, no layers. Context: how much the corrections matter.

Writes out/correction_study.json, out/correction_study.md and a `correction_study` block in site/data/site.json that the
Verify step shows. Every variant is reported, including the ones that fail.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "out"
VARIANTS = {
    "A": dict(label="First run: ionosphere + reference surface", detrend=2, troposphere=False, tides=False, highpass_km=0.0, status="as first reported"),
    "B": dict(label="+ NISAR troposphere and tide layers", detrend=2, troposphere=True, tides=True, highpass_km=0.0, status="default from this version"),
    "C": dict(label="B + 5 km local-contrast filter", detrend=2, troposphere=True, tides=True, highpass_km=5.0, status="exploratory"),
    "D": dict(label="Raw: ionosphere only", detrend=0, troposphere=False, tides=False, highpass_km=0.0, status="context"),
}
SNAP = ["out", "site/data", "paper"]


def _snapshot(dst: pathlib.Path):
    if dst.exists():
        shutil.rmtree(dst)
    for rel in SNAP:
        src = ROOT / rel
        if src.exists():
            shutil.copytree(src, dst / rel, ignore=shutil.ignore_patterns("_compare_backup", "correction_runs"))


def _restore(src: pathlib.Path):
    for rel in SNAP:
        s, d = src / rel, ROOT / rel
        if not s.exists():
            continue
        for sub in ("stakeholder",):                                     # validate rewrites these lists; clear before copying back
            for base in (d / sub,):
                if base.exists():
                    for f in base.glob("*"):
                        if f.is_file():
                            f.unlink()
        try:
            shutil.copytree(s, d, dirs_exist_ok=True)
        except Exception as ex:
            print(f"note: could not restore {rel} completely ({ex}); the backup is in out/_compare_backup")


def _summary(results: dict, prov: dict) -> dict:
    tests = [dict(name=t.get("name"), passed=t.get("passed")) for t in results.get("tests", [])]
    pinn = results.get("pinn") or {}
    held = {k: (round(v, 2) if isinstance(v, (int, float)) else v) for k, v in (pinn.get("heldout_rmse_mm") or {}).items()}
    nc = prov.get("nisar_corrections") or {}
    return dict(tests=tests, passed=sum(t["passed"] is True for t in tests), failed=sum(t["passed"] is False for t in tests),
                not_run=sum(t["passed"] is None for t in tests), params={k: results.get("params", {}).get(k) for k in ("alpha", "b", "T", "rmse_train")},
                contracts=(results.get("contracts") or {}).get("tally"), heldout=held,
                nisar_layers=dict(pairs=nc.get("pairs_with_layers", 0), applied=nc.get("applied"), variance_removed_pct=nc.get("variance_removed_pct")),
                high_pass=prov.get("high_pass"), reference_surface=prov.get("scene_surface_filter"))


def run(keep: str = "B", only: list[str] | None = None, quiet: bool = True) -> dict:
    sys.path.insert(0, str(ROOT))
    import real_site as R
    from swell import ingest, validate
    provp = OUT / "real_site_provenance.json"
    if not provp.exists():
        raise SystemExit("Build the real twin first: python real_site.py --site dallas --yes")
    rp = json.loads(provp.read_text()); key = rp["site"]; bbox = rp["bbox"]; pairs = rp["steps"]["radar"]["pairs"]
    ingest.SITES.setdefault(key, dict(name=rp.get("name", key), bbox=bbox)); ingest.SITES[key]["bbox"] = bbox
    work = ROOT / "data" / key; gdir = work / "gunw"
    if not all((gdir / p["name"]).exists() for p in pairs):
        raise SystemExit(f"The saved radar windows are missing from {gdir}. Run real_site.py again first.")
    try:
        R.augment_cubes(pairs, gdir)
    except Exception as ex:
        print(f"note: NISAR correction layers could not be fetched ({type(ex).__name__}); variants B and C will equal A")
    layout = R.detect_layout(gdir / pairs[0]["name"]); ingest.PATHS.update(layout)
    backup = OUT / "_compare_backup"; _snapshot(backup)
    study = dict(site=rp.get("name", key), pairs=len(pairs), first=pairs[0]["ref"], last=pairs[-1]["sec"], kept=keep, variants={},
                 rule="Variant B is the default because NASA supplies these layers for this purpose. It was chosen before the scores below were seen and is kept whatever they say. C and D are exploratory context.")
    old_cwd = pathlib.Path.cwd()
    try:
        os.chdir(ROOT)
        for name in (only or list(VARIANTS)):
            v = VARIANTS[name]; print(f"variant {name}: {v['label']} ...", flush=True)
            buf = io.StringIO()
            try:
                with (contextlib.redirect_stdout(buf) if quiet else contextlib.nullcontext()):
                    ingest.build(key, str(gdir), str(work / "rain.csv"), str(work / "clay.tif"), str(work / "paved.tif"), str(work / "gps.json") if (work / "gps.json").exists() else None, n=rp.get("grid", 60),
                                 lep_low=rp.get("lep_low", 1.5), clay_layer="SoilGrids clay content 30-60 cm (%), not a shrink-swell rating",
                                 detrend=v["detrend"], troposphere=v["troposphere"], tides=v["tides"], highpass_km=v["highpass_km"])
                    validate.main(["--site", str(OUT / f"{key}.npz")])
                res = json.loads((OUT / "results.json").read_text()); prov = json.loads((OUT / "provenance.json").read_text())
                s = _summary(res, prov); s.update(label=v["label"], status=v["status"])
                rd = OUT / "correction_runs" / name; rd.mkdir(parents=True, exist_ok=True)
                for f in ("results.json", "contracts.json", "provenance.json"):
                    shutil.copy(OUT / f, rd / f)
            except Exception as ex:
                s = dict(label=v["label"], status=v["status"], error=f"{type(ex).__name__}: {str(ex)[:300]}")
            study["variants"][name] = s
            print(f"variant {name} result: " + (s.get("error") or f"{s['passed']} pass, {s['failed']} fail, {s['not_run']} not run; alpha {s['params']['alpha']}; held-out {s['heldout']}"), flush=True)
        # leave the app on the chosen variant
        if keep in study["variants"] and "error" not in study["variants"][keep]:
            v = VARIANTS[keep]
            with contextlib.redirect_stdout(io.StringIO()):
                ingest.build(key, str(gdir), str(work / "rain.csv"), str(work / "clay.tif"), str(work / "paved.tif"), str(work / "gps.json") if (work / "gps.json").exists() else None, n=rp.get("grid", 60),
                             lep_low=rp.get("lep_low", 1.5), clay_layer="SoilGrids clay content 30-60 cm (%), not a shrink-swell rating",
                             detrend=v["detrend"], troposphere=v["troposphere"], tides=v["tides"], highpass_km=v["highpass_km"])
                validate.main(["--site", str(OUT / f"{key}.npz")])
            _keep_extra(backup)
        else:
            _restore(backup); study["kept"] = "unchanged (previous build restored)"
    finally:
        os.chdir(old_cwd)
    sj = ROOT / "site" / "data" / "site.json"
    try:
        web = json.loads(sj.read_text()); web["correction_study"] = study; sj.write_text(json.dumps(web))
    except Exception as ex:
        print(f"note: could not add the study to site.json ({ex})")
    (OUT / "correction_study.json").write_text(json.dumps(study, indent=1, default=str))
    (OUT / "correction_study.md").write_text(markdown(study))
    print(markdown(study))
    return study


def _keep_extra(backup: pathlib.Path):
    """validate rewrites site.json; carry over blocks written by other steps (other satellites, wetness check)."""
    try:
        old = json.loads((backup / "site" / "data" / "site.json").read_text())
        sj = ROOT / "site" / "data" / "site.json"; web = json.loads(sj.read_text())
        for k, v in old.items():
            if k not in web and k != "correction_study":
                web[k] = v
        sj.write_text(json.dumps(web))
    except Exception:
        pass


def markdown(study: dict) -> str:
    names = [t["name"] for v in study["variants"].values() for t in v.get("tests", [])]
    names = list(dict.fromkeys(names))
    head = "| Test | " + " | ".join(f"{k}: {v['label']}" for k, v in study["variants"].items()) + " |"
    rows = [head, "|" + "---|" * (len(study["variants"]) + 1)]
    for n in names:
        cells = []
        for v in study["variants"].values():
            t = next((t for t in v.get("tests", []) if t["name"] == n), None)
            cells.append("—" if t is None else ("not run" if t["passed"] is None else ("pass" if t["passed"] else "fail")))
        rows.append(f"| {n} | " + " | ".join(cells) + " |")
    extra = []
    for k, v in study["variants"].items():
        if "error" in v:
            extra.append(f"- {k}: did not run ({v['error']})"); continue
        nl = v["nisar_layers"]
        r2 = lambda q: "n/a" if q is None else f"{q:.2f}"
        extra.append(f"- {k} ({v['status']}): fitted clay response alpha {r2(v['params']['alpha'])}, training error {r2(v['params']['rmse_train'])} mm, "
                     f"held-out {v['heldout'] or 'n/a'}, promises {v['contracts']}, NISAR layers on {nl['pairs']} pairs"
                     + (f" ({nl['applied']}, {nl['variance_removed_pct']} % of scene variance removed)" if nl["pairs"] else ""))
    return (f"# Correction study: {study['site']}, {study['pairs']} NISAR pairs, {study['first']} to {study['last']}\n\n{study['rule']}\n\n"
            + "\n".join(rows) + "\n\n" + "\n".join(extra) + f"\n\nThe app now shows variant: {study['kept']}.\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", default="B", choices=list(VARIANTS) + ["none"], help="which variant the app shows afterwards (default B)")
    ap.add_argument("--only", nargs="*", choices=list(VARIANTS), help="run only these variants")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    if not a.verbose:
        import warnings; warnings.filterwarnings("ignore")
    run(keep=a.keep, only=a.only, quiet=not a.verbose)
