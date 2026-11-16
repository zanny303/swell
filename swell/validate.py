"""One command regenerates everything:  python -m swell.validate [--site out/<name>.npz]

With no --site it runs the SYNTHETIC fixture and tags every output SYNTHETIC.
Writes: out/results.json, out/figures/*.png, out/stakeholder/*, site/data/site.json, paper/paper.md
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import contracts as C
from . import fit as F
from . import stakeholders as S
from . import stats as ST
from . import synthetic
from . import twin as TW
from . import similarity as SIM
from .paper import write_paper

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL_VERSION = "swell-0.1"


def load_site(path: str | None) -> dict:
    if path is None:
        return synthetic.make()
    z = np.load(path, allow_pickle=True)
    site = {k: z[k] for k in z.files}
    for k in ("source", "name"):
        site[k] = str(site[k])
    for k in ("n", "days"):
        site[k] = int(site[k])
    if "lep_low" in site: site["lep_low"] = float(site["lep_low"])
    site["inc_deg"] = float(site["inc_deg"]); site["bbox"] = [float(v) for v in site["bbox"]]
    site["gps"] = json.loads(str(site["gps"])) if "gps" in site else {}
    site["ref"] = site["ref"].astype(bool) if "ref" in site else np.zeros_like(site["lep"], bool)
    return site


def adversarial_check() -> dict:
    """Break one assumption at a time on the synthetic fixture. The named tests MUST fail."""
    must_fail = dict(no_clay=["T2", "T3", "T4"], control_moves=["Control"], wrong_soil_map=["T2"])
    out = {}
    for adv, names in must_fail.items():
        s = synthetic.make(adversarial=adv)
        tests = ST.run_all(s, F.fit_all(s))
        got = {t["name"].split()[0]: t["passed"] for t in tests}
        out[adv] = dict(expected_to_fail=names, failed=[k for k, v in got.items() if v is False],
                        caught=all(got[n] is False for n in names))
    return out


def _r(a, nd=1):
    return np.round(np.asarray(a, float), nd).tolist()


def figures(site, fr, tests, out: pathlib.Path):
    out.mkdir(parents=True, exist_ok=True)
    tag = f"[{site['source']}]"
    pd = site["pass_days"]
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.8))
    amp0, amp2 = ST._amp(fr["naive"]), ST._amp(fr["mcorr"])
    vm = float(np.nanquantile(amp0, .98))
    for a, d, t in ((ax[0], amp0, "Naive: phase = motion"), (ax[1], amp2, "SWELL: artifact removed")):
        im = a.imshow(d, vmin=0, vmax=vm, cmap="viridis"); a.set_title(f"{t}\nseasonal range (mm)"); a.axis("off")
    fig.colorbar(im, ax=ax[:2], shrink=.8)
    im = ax[2].imshow(site["lep"], cmap="magma"); ax[2].set_title("Soil map shrink-swell rating (%)"); ax[2].axis("off")
    fig.colorbar(im, ax=ax[2], shrink=.8); fig.suptitle(f"{tag} {site['name']}"); fig.savefig(out / "fig1_maps.png", dpi=140, bbox_inches="tight"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 3.6))
    for name, g in list(site["gps"].items())[:2]:
        i, j = g["cell"]
        up = (np.asarray(g["up_mm"]) - g["up_mm"][0]) * F.cosi(site)[i, j]; ax.plot(g["days"], up, lw=.6, alpha=.6, label=f"GPS {name} (projected)")
        ax.plot(pd, fr["naive_los"][:, i, j], "o--", ms=3, label=f"naive at {name}")
        ax.plot(pd, fr["los_corr"][:, i, j], "s-", ms=3, label=f"SWELL at {name}")
    ax.set_xlabel("day"); ax.set_ylabel("line-of-sight change (mm)"); ax.legend(fontsize=6, ncol=2); ax.set_title(f"{tag} GPS referee")
    fig.savefig(out / "fig2_gps.png", dpi=140, bbox_inches="tight"); plt.close(fig)

    t3 = next(t for t in tests if t["name"].startswith("T3"))
    fig, ax = plt.subplots(figsize=(6, 3.4))
    x = [r["day"] for r in t3["per_pass"]]
    for k, lab in (("rmse_swell", "SWELL twin"), ("rmse_persistence", "persistence"), ("rmse_rain_only", "rain-only")):
        ax.plot(x, [r[k] for r in t3["per_pass"]], "o-", label=lab)
    ax.set_xlabel("held-out pass (day)"); ax.set_ylabel("forecast RMSE (mm)"); ax.legend(); ax.set_title(f"{tag} Forecast holdout")
    fig.savefig(out / "fig3_forecast.png", dpi=140, bbox_inches="tight"); plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=None)
    args = ap.parse_args(argv)
    site = load_site(args.site)
    out = ROOT / "out"; out.mkdir(exist_ok=True)
    fr = F.fit_all(site)
    tests = ST.run_all(site, fr)
    pd = site["pass_days"]

    # action contracts on held-out passes: written from earlier passes only, then judged
    zs = S.zones(site)
    amp = np.nan_to_num(np.nanmax(fr["mcorr"][: fr["test"][0]], 0) - np.nanmin(fr["mcorr"][: fr["test"][0]], 0))
    okm = F.masks(site)["ok"]
    top = sorted([z for z in zs if np.mean([okm[i, j] for i, j in z["cells"]]) > .6],
                 key=lambda z: -float(np.mean([amp[i, j] for i, j in z["cells"]])))[:4]
    # spread of zone-mean one-step forecast errors on TRAINING passes: sets the contract band
    zerr = []
    for p in fr["train"][2:]:
        fc = TW.forecast_for_pass(site, fr, int(p))
        zerr += [float(np.nanmean((fc["mean"] - fr["mcorr"][p])[tuple(zip(*z["cells"]))])) for z in zs]
    zone_sigma = float(np.nanstd(zerr))
    # the reference ground is not perfectly still: the model's own estimate of how far it moved (plus its small
    # artifact) is carried into every contract band as extra uncertainty
    refm = F.masks(site)["ref"]
    model_days = F.predict(site, fr["par"])
    art = F.artifact(site, fr["beta"])
    contracts = []
    for p in fr["test"]:
        fc = TW.forecast_for_pass(site, fr, int(p))
        ref_off = float(np.mean(model_days[pd[p]][refm] * F.cosi(site)[refm] + art[p][refm])) if refm.any() else 0.0
        sig = float(np.hypot(zone_sigma, ref_off))
        for z in top:
            c = C.make(site, z, fc, "Municipal engineer", "Prioritise field inspection of drainage and pavement in this zone",
                       [f"passes 1..{int(p) - 1}", "soil map", "rain record"],
                       "Moisture artifact removed using open low-clay ground; residual artifact possible", MODEL_VERSION,
                       zone_sigma=sig)
            contracts.append(C.judge(c, site, fr["mcorr"][p], z))
    tally = {k: sum(c["arrival"] == k for c in contracts) for k in ("supported", "contradicted", "inconclusive")}

    hz = TW.horizon_maps(site, fr)
    storm = TW.scenario(site, fr, extra_rain_mm=75, rain_days=2, horizon=30)
    drain = TW.scenario(site, fr, extra_rain_mm=75, rain_days=2, wetting_reduction=.35, horizon=30)
    table = S.zone_table(site, fr, hz["drying"], hz["storm"])
    files = S.build(site, fr, table, int(pd[-1]) + 12, MODEL_VERSION)
    (out / "stakeholder").mkdir(exist_ok=True)
    web_st = ROOT / "site" / "data" / "stakeholder"; web_st.mkdir(parents=True, exist_ok=True)
    for old in list(web_st.glob("*")) + list((out / "stakeholder").glob("*")):
        old.unlink()
    for name, text in files.items():
        (out / "stakeholder" / name).write_text(text); (web_st / name).write_text(text)
    tw = TW.run(site, fr)
    last = TW.run(site, fr, upto_pass=len(pd) - 1)
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = ""
    par = {k: fr["par"][k] for k in ("alpha", "b", "T", "tau", "rmse_train")}
    results = dict(source=site["source"], site=site["name"], model_version=MODEL_VERSION, commit=commit,
                   n_passes=int(len(pd)), pass_days=pd.tolist(), train_passes=fr["train"].tolist(), test_passes=fr["test"].tolist(),
                   beta_mm_per_wetness=fr["beta"], beta_se=fr["beta_se"], params=par, tests=tests,
                   contracts=dict(tally=tally, n=len(contracts), zone_sigma_mm=zone_sigma),
                   signature=SIM.signature(site, fr), adversarial=adversarial_check() if site["source"] == "SYNTHETIC" else None,
                   zones_resolved=sum(r["status"] == "ok" for r in table), zones_total=len(table),
                   scenarios=dict(storm_75mm_day30_mean_mm=float(storm["scenario"][-1].mean()),
                                  storm_with_35pct_less_wetting_mean_mm=float(drain["scenario"][-1].mean())))
    if site["source"] == "SYNTHETIC":
        results["synthetic_truth"] = synthetic.TRUE
    (out / "results.json").write_text(json.dumps(results, indent=1, default=float))
    (out / "contracts.json").write_text(json.dumps(contracts, indent=1, default=float))
    figures(site, fr, tests, out / "figures")

    # web data (small): per-pass grids, forecast for the pass after the last one, and the fitted constants
    nxt = int(pd[-1])
    unresolved = TW.refuse(site, last["mean"][nxt], np.sqrt(last["var"][nxt]))
    web = dict(source=site["source"], name=site["name"], bbox=site["bbox"], n=site["n"], pass_days=pd.tolist(),
               inc_deg=site["inc_deg"], beta=fr["beta"], params=par, rain=_r(site["rain"]), wetness=_r(site["w"], 3),
               lep=_r(np.nan_to_num(site["lep"])), paved=_r(np.nan_to_num(site["paved"]), 2), coh=_r(np.nan_to_num(site["coh"]), 2),
               observed_los=[_r(np.nan_to_num(x, nan=-9999)) for x in site["los"]],
               inferred_motion=[_r(tw["mean"][d]) for d in pd], inferred_sd=[_r(np.sqrt(tw["var"][d])) for d in pd],
               artifact=[_r(a) for a in F.artifact(site, fr["beta"])], zones=table,
               reference=F.masks(site)["ref"].astype(int).tolist(), control=F.masks(site)["control"].astype(int).tolist(),
               unresolved=(unresolved | ~np.isfinite(site["lep"]) | ~np.isfinite(site["paved"])).astype(int).tolist(),   # no soil or land-cover value: refuse
               # Keep complete quantitative validation records for the evidence-grounded
               # browser copilot. The UI may summarize them but must not discard metrics.
               tests=tests,
               contracts=contracts[-4:], gps={k: dict(cell=list(v["cell"])) for k, v in site["gps"].items()})
    from . import pinn as PINN
    # Radar-derived moisture susceptibility: how many mm each cell moves per unit of (lagged) wetness, from the radar alone.
    # Independent of the soil map, so it can be compared with it (after Yun et al., NeurIPS 2022 CCAI workshop: deformation -> geology).
    from . import physics as ph
    _s = ph.unit_response(site["w"], fr["par"]["T"], fr["par"]["tau"], s0=site["w"][0]); _x = (_s[pd] - _s[pd[0]])[fr["train"]]
    _y = fr["mcorr"][fr["train"]]; _v = np.isfinite(_y)
    with np.errstate(all="ignore"):
        _g = np.where(_v, _x[:, None, None] * np.nan_to_num(_y), 0).sum(0) / np.maximum((np.where(_v, _x[:, None, None] ** 2, 0)).sum(0), 1e-9)
    _g = np.where(F.masks(site)["ok"] & (_v.sum(0) >= 3), _g, np.nan)
    web["susceptibility"] = [[None if not np.isfinite(v) else round(float(v), 2) for v in r] for r in _g]
    _m = np.isfinite(_g) & F.masks(site)["clay"]
    if _m.sum() > 30:
        from scipy.stats import spearmanr as _sp
        web["susceptibility_vs_clay_map"] = float(_sp(_g[_m], site["lep"][_m]).statistic)
    from . import rl as RL
    web["rl"] = RL.run(site, fr)       # crew-order policy learned inside the twin, scored against simple rules
    web["pinn"] = PINN.run(site, fr)   # ablation: physics fit vs network vs physics-informed network, on held-out passes
    results["pinn"] = web["pinn"]; results["rl"] = web["rl"]; (out / "results.json").write_text(json.dumps(results, indent=1, default=float))
    (ROOT / "site" / "data").mkdir(parents=True, exist_ok=True)
    def _clean(o):                                    # browsers reject NaN in JSON: every non-finite number becomes null
        if isinstance(o, dict): return {k: _clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
        if isinstance(o, np.ndarray): return _clean(o.tolist())
        if isinstance(o, (float, np.floating)): return float(o) if np.isfinite(o) else None
        if isinstance(o, np.integer): return int(o)
        if isinstance(o, np.bool_): return bool(o)
        return o
    (ROOT / "site" / "data" / "site.json").write_text(json.dumps(_clean(web), allow_nan=False))
    write_paper(results, ROOT / "paper" / "paper.md")
    for t in tests:
        print(f"{'PASS' if t['passed'] else 'FAIL' if t['passed'] is not None else 'n/a ':4s} {t['name']}")
    print("contracts:", tally, "| params:", {k: round(v, 2) for k, v in par.items()}, "| beta:", round(fr["beta"], 2))
    return results


if __name__ == "__main__":
    main()
