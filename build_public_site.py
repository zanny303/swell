"""Make a public, read-only copy of the SWELL Decision Studio that anyone can open without logging in (for judges).

    python build_public_site.py --repo https://github.com/<you>/<repo>

Writes public/ next to this file. On vercel.com: Add New -> Project -> import the repository -> Deploy (vercel.json serves
public/). Open the link in a private window to check.

What the public copy does: the real twin (map, 3D ground block, scenarios, painting changes, stakeholder answers,
before/after, cause and effect, research library, Verify with all test results, Worlds) runs entirely in the browser.
What it does not do: rebuild from NASA, save decisions, Ask SWELL, or the 3D city (needs a personal Cesium ion token).
No key, password or token is copied: the script refuses to finish if it finds one.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SECRET = [re.compile(p) for p in (r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", r"sk-[A-Za-z0-9_-]{20,}", r"AIza[0-9A-Za-z_-]{30,}",
                                   r"EARTHDATA_(USERNAME|PASSWORD)\s*=\s*\S+", r"(?i)ghp_[A-Za-z0-9]{30,}")]
SKIP = {"uploads", "__pycache__"}
# the public copy has no server: anything that would call the local API gets a clear "local app only" answer instead of an error page
PUBLIC_FETCH = ("(function(){var f=window.fetch;window.fetch=function(u,o){var s=typeof u==='string'?u:((u&&u.url)||'');"
                "if(/^\\/?(api|uploads)\\//.test(s)){return Promise.resolve(new Response(JSON.stringify({error:'Runs in the local SWELL app; this public copy is read-only'}),"
                "{status:503,headers:{'Content-Type':'application/json'}}));}return f.apply(this,arguments);};})();")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default="", help="public repository link shown on the page")
    ap.add_argument("--out", default="public", help="output folder (default public/; docs/ holds the project documentation)")
    ap.add_argument("--allow-synthetic", action="store_true", help="for testing only: publish the labelled synthetic fixture")
    a = ap.parse_args(argv)
    site = ROOT / "site"; data = json.loads((site / "data" / "site.json").read_text())
    synthetic = bool(re.search("SYNTH", data.get("source", ""), re.I))
    if synthetic and not a.allow_synthetic:
        print("STOPPED: site/data/site.json is the synthetic test fixture. Build the real twin first (python real_site.py --site dallas --yes).")
        return 2
    out = ROOT / a.out
    if out.exists():
        if not (out / ".swell_public").exists():                           # never delete a folder this script did not make
            print(f"STOPPED: {a.out}/ exists and was not made by this script. Choose another --out folder."); return 2
        shutil.rmtree(out)
    shutil.copytree(site, out, ignore=lambda d, names: [n for n in names if n in SKIP or n.endswith(".pyc")])
    built = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    passes = len(data.get("pass_days", [])); name = data.get("name", "site")
    repo = a.repo.strip()
    cfg = json.dumps(dict(built=built, repo=repo, source=data.get("source", ""), synthetic=synthetic))
    banner = (f'<div id="pubBanner" style="position:fixed;left:50%;transform:translateX(-50%);bottom:10px;z-index:9999;max-width:min(920px,94vw);'
              f'background:#0b1622f2;border:1px solid #2dd4bf;color:#e6eef4;border-radius:12px;padding:8px 14px;font:13px system-ui;box-shadow:0 6px 24px #0008">'
              f'<b style="color:#2dd4bf">Public replay</b> of the SWELL twin for <b>{name}</b> built from {passes} NASA NISAR passes'
              f'{" (SYNTHETIC TEST DATA)" if synthetic else ""}. Paint changes, run scenarios, switch roles and open Verify: it all runs in your browser. '
              f'Rebuilding from NASA, saving decisions and the 3D city run in the local app'
              + (f' (<a style="color:#2dd4bf" href="{repo}">code</a>)' if repo else "") +
              f'. <a href="#" style="color:#9fb3c3" onclick="this.parentNode.remove();return false">hide</a></div>')
    idx = out / "index.html"; s = idx.read_text()
    s = s.replace('<script src="model.js"></script>', f'<script>window.SWELL_PUBLIC={cfg};' + PUBLIC_FETCH + '</script>\n<script src="model.js"></script>', 1)
    s = s.replace("</body>", banner + "\n</body>", 1)
    s = s.replace('href="connections.html"><b>Connections and real data</b>', 'href="about.html"><b>About this public copy</b>')
    idx.write_text(s)
    about = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SWELL public copy</title>
<style>body{{background:#0b1622;color:#e6eef4;font:16px/1.5 system-ui;margin:0;padding:32px 16px}}main{{max-width:760px;margin:auto}}a{{color:#2dd4bf}}code{{background:#122436;padding:2px 6px;border-radius:6px}}</style></head>
<body><main><h1>SWELL: public read-only copy</h1>
<p>This page set is a copy of the SWELL Decision Studio with the twin built from NASA NISAR data for <b>{name}</b> ({passes} passes, built {built}). It needs no account.</p>
<p><a href="index.html">Open the Decision Studio</a> · <a href="worlds.html">Worlds</a>{' · <a href="' + repo + '">Code and instructions</a>' if repo else ''} · <a href="evidence/">Evidence files</a></p>
<p>Connecting data sources, rebuilding the twin from NASA's archive, saving decisions and the 3D city need the local app. In the repository: <code>python run_swell.py</code>, then open <code>http://127.0.0.1:8000/</code>.</p>
<p>Scenario numbers are model output under the inputs you choose. They are not observations, engineering designs or safety certifications.</p></main></body></html>"""
    (out / "about.html").write_text(about); (out / "connections.html").write_text(about)
    ev = out / "evidence"; ev.mkdir(exist_ok=True)
    for f in ("results.json", "contracts.json", "provenance.json", "real_site_provenance.json", "correction_study.md", "correction_study.json", "real_site_log.txt"):
        p = ROOT / "out" / f
        if p.exists():
            shutil.copy(p, ev / f)
    for f in ("PREREGISTRATION.md",):
        if (ROOT / f).exists():
            shutil.copy(ROOT / f, ev / f)
    (ev / "index.html").write_text("<!doctype html><meta charset=utf-8><title>SWELL evidence</title><body style='font:16px system-ui;background:#0b1622;color:#e6eef4;padding:24px'><h1>Evidence files</h1><ul>"
                                   + "".join(f"<li><a style='color:#2dd4bf' href='{p.name}'>{p.name}</a></li>" for p in sorted(ev.iterdir()) if p.name != "index.html") + "</ul></body>")
    (out / ".nojekyll").write_text(""); (out / ".swell_public").write_text("made by build_public_site.py; safe to delete and rebuild\n")
    bad = []
    for p in out.rglob("*"):
        if p.is_file() and p.suffix in {".html", ".js", ".json", ".md", ".txt", ".csv", ".css"}:
            t = p.read_text(errors="ignore")
            bad += [f"{p.relative_to(ROOT)}" for rx in SECRET if rx.search(t)]
    if bad:
        shutil.rmtree(out)
        print("STOPPED: something that looks like a key or token was found in: " + ", ".join(sorted(set(bad))) + ". Nothing was written.")
        return 3
    print(f"Public copy written to {out.relative_to(ROOT)}/ ({sum(1 for _ in out.rglob('*'))} files, {passes} passes, {'SYNTHETIC' if synthetic else 'real data'}).")
    print("Check it locally:  python -m http.server 8080 --directory " + a.out + "   then open http://127.0.0.1:8080/")
    print("Publish: push to GitHub, then on vercel.com import the repository and Deploy (vercel.json serves public/).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
