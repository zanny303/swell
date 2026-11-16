"""Record a walkthrough of SWELL on this computer, so it can be reviewed (and reused for the submission video).

    python -m pip install playwright
    python -m playwright install chromium
    python run_swell.py                 (leave it running in another window)
    python record_science_demo.py               records the real site that is loaded
    python record_science_demo.py --demo        records the bundled, labelled demo data instead

It opens a browser window, clicks through every step by itself (about 2 minutes), and writes into the folder demo_out:
    swell_demo.webm      the screen recording
    01_... .png          one screenshot per scene
    demo_report.txt      what loaded, what failed, page errors. No passwords or keys are written.

The Cesium token is read from the local .env only to switch on the 3D city in this recording browser. It is never printed.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "demo_science_out"


def env_value(name: str) -> str:
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*" + re.escape(name) + r"\s*=\s*(.*)\s*$", line)
            if m:
                return m.group(1).strip().strip('"').strip("'")
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8000"); ap.add_argument("--demo", action="store_true", help="use the bundled demo data")
    ap.add_argument("--short", action="store_true", help="seven-scene capture; raw recording is not guaranteed to be 30 seconds")
    ap.add_argument("--with-connections", action="store_true", help="also film the Connections page")
    ap.add_argument("--headless", action="store_true", help="no visible window (slower 3D on most computers)"); ap.add_argument("--vendor", help=argparse.SUPPRESS)
    a = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Run:\n  " + sys.executable + " -m pip install playwright\n  " + sys.executable + " -m playwright install chromium"); return 2
    if OUT.exists():
        OUT.rename(OUT.with_name(OUT.name + "-" + time.strftime("%Y%m%d-%H%M%S")))
    OUT.mkdir(); report, errors, shots = [], [], [0]
    note = lambda *t: (print(*t, flush=True), report.append(" ".join(str(x) for x in t)))

    with sync_playwright() as pw:
        args = ["--ignore-gpu-blocklist"] + (["--use-gl=swiftshader", "--enable-unsafe-swiftshader"] if a.headless else [])
        browser = pw.chromium.launch(headless=a.headless, args=args)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900}, record_video_dir=str(OUT), record_video_size={"width": 1600, "height": 900})
        token = env_value("CESIUM_ION_TOKEN")
        ctx.add_init_script("try{localStorage.setItem('swell.onboarded.v1','1');" + (f"localStorage.setItem('swell.cesiumIonToken.v1',{json.dumps(token)});" if token else "") + "}catch(e){}")
        studio_url = a.url + ("/index.html?demo=1&nohelp=1" if a.demo else "/index.html?nohelp=1")
        warm = ctx.new_page()                                               # warm-up visit, not kept: fills the browser cache so the filmed visit has no dead time
        try:
            warm.goto(studio_url, wait_until="domcontentloaded")
            warm.wait_for_function("() => typeof S !== 'undefined' && S && typeof lastField !== 'undefined' && lastField", timeout=90000)
            for _ in range(40):
                if warm.evaluate("() => viewer.scene.globe.tilesLoaded"): break
                warm.wait_for_timeout(500)
            warm.wait_for_timeout(1500)
        except Exception as ex: note("warm-up visit:", type(ex).__name__)
        wv = warm.video; warm.close()
        try: pathlib.Path(wv.path()).unlink()
        except Exception: pass
        page = ctx.new_page(); page.on("pageerror", lambda e: errors.append(str(e)[:300]))
        if a.vendor:                                                       # offline testing only: serve Cesium and three.js from a local folder
            v = pathlib.Path(a.vendor)
            def cz(route):
                f = v / "cesium/Build/Cesium" / route.request.url.split("/Build/Cesium/")[1].split("?")[0]
                route.fulfill(path=str(f)) if f.exists() else route.abort()
            page.route("https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/**", cz)
            page.route("https://cdn.jsdelivr.net/npm/three@0.128.0/**", lambda r: r.fulfill(path=str(v / "three" / r.request.url.split("three@0.128.0/")[1])))
        js = lambda code, arg=None: page.evaluate(code, arg)
        def click(sel):
            found = js("s => { const e = document.querySelector(s); if (!e) return false; e.click(); return true; }", sel)
            if not found: raise RuntimeError("Missing demo control: " + sel)
            return found
        wait = lambda s: page.wait_for_timeout(int(s * 1000))

        def settle(max_s=12):
            """Wait until the map has finished loading what is on screen (no fixed sleeps, so no dead time and no half-loaded shots)."""
            t0 = time.time()
            while time.time() - t0 < max_s:
                try:
                    if page.evaluate("() => typeof viewer !== 'undefined' && viewer.scene.globe.tilesLoaded"): break
                except Exception: pass
                page.wait_for_timeout(400)
            page.wait_for_timeout(700)

        def caption(text):
            page.evaluate("""t => { let c = document.getElementById('demoCap'); if (!c) { c = document.createElement('div'); c.id = 'demoCap';
                c.style.cssText = 'position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:99999;background:#04101cf2;color:#fff;border:1px solid #22c55e;border-radius:12px;padding:10px 18px;font:600 17px system-ui;max-width:1250px;text-align:center;box-shadow:0 6px 30px #000a';
                document.body.appendChild(c); } c.textContent = t; c.style.display = t ? 'block' : 'none'; }""", text)

        def shot(name):
            shots[0] += 1; page.screenshot(path=str(OUT / f"{shots[0]:02d}_{name}.png"))

        def scene(name, fn):
            note(f"scene: {name}")
            try: fn(); shot(name)
            except Exception as ex: note(f"  PROBLEM in {name}: {type(ex).__name__}: {str(ex)[:300]}"); shot(name + "_problem")

        # ---- 0. connections page
        def s_connect():
            page.goto(a.url + "/connections.html", wait_until="domcontentloaded")
            try: page.wait_for_function("() => /Tested/.test(document.getElementById('tested').textContent)", timeout=70000)
            except Exception: note("  connection tests did not finish in 70 s")
            rows = js("() => [...document.querySelectorAll('.row')].map(r => (r.classList.contains('ok') ? 'OK   ' : r.classList.contains('needs_key') ? 'KEY  ' : 'FAIL ') + r.querySelector('b').textContent + ' | ' + (r.querySelector('.d') || {textContent:''}).textContent.slice(0, 150))")
            for r in rows: note("  " + r)
            wait(2)
        if a.with_connections: scene("connections", s_connect)

        # ---- 1. open the studio
        page.goto(studio_url, wait_until="domcontentloaded")
        try:
            page.wait_for_function("() => typeof S !== 'undefined' && S && typeof C !== 'undefined' && C && typeof lastField !== 'undefined' && lastField", timeout=90000)
        except Exception:
            note("STOPPED: the Decision Studio did not load a site within 90 s."); shot("studio_did_not_load")
        info = js("() => (typeof S === 'undefined' || !S) ? null : ({name: S.name, source: S.source, n: S.n, passes: S.pass_days.length, bbox: S.bbox, tests: (S.tests || []).map(t => [t.name, t.passed]), sensors: Object.fromEntries(Object.entries(S.sensors || {}).map(([k, v]) => [k, v.status + ': ' + (v.finding || v.reason || '')])), synthetic: /SYNTH/i.test(S.source), shown: (typeof sampleDemoEnabled === 'undefined') ? null : sampleDemoEnabled})")
        note("site:", json.dumps(info)[:1500] if info else "none")
        if info and not info["synthetic"] and not js("() => S.scientific_validity?.version === 'swell-science-0.2'"):
            note("WARNING: recording uses pre-revision real data; revalidate first for updated benchmark.")
        note("science revision:", json.dumps(js("() => (typeof S !== 'undefined' && S) ? S.scientific_validity || null : null"))[:4000])
        if not info or (info["synthetic"] and not a.demo):
            note("No real site is loaded. Build one on the Connections page first, or run:  python record_science_demo.py --demo")
        else:
            settle(20); src = ("bundled demo data (synthetic, labelled)" if info["synthetic"] else f"real NISAR radar, {info['passes']} passes · experimental model")
            canvas = lambda: js("() => { const r = viewer.scene.canvas.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")

            def paint(tool, dx, dy):
                box = canvas(); cx, cy = box[0] + box[2] * .5, box[1] + box[3] * .45
                click(f"[data-tool={tool}]"); wait(.4); page.mouse.move(cx + dx, cy + dy); page.mouse.down()
                for k in range(12): page.mouse.move(cx + dx + 9 * k, cy + dy + 5 * k); wait(.07)
                page.mouse.up(); wait(1.2); click("[data-tool=select]")

            def s_site():
                caption(f"SWELL · {info['name']} · {src}"); click("[data-step=investigate]"); click("[data-v=map]"); click("#toSite"); settle(15)
                k = js("() => document.querySelectorAll('#passes figure').length")
                for i in range(0, k, max(1, k // (4 if a.short else 8))):
                    js("i => { const f = document.querySelectorAll('#passes figure')[i]; if (f) f.click(); }", i); wait(.7)
                js("() => { const f = document.querySelectorAll('#passes figure'); if (f.length) f[f.length - 1].click(); }")
                box = canvas(); page.mouse.click(box[0] + box[2] * .5, box[1] + box[3] * .45); wait(1.5 if a.short else 3)

            def s_understand():
                caption("One radar signal, competing mechanisms: moisture artifact and physical movement. SWELL tests the separation.")
                click("[data-step=understand]"); settle(8); click("[data-bottom-tab=causal]"); wait(1.5)
                for e in ("wet>art", "target>move"):
                    js("e => { const p = document.querySelector(`[data-e=\"${e}\"]`); if (p) p.dispatchEvent(new MouseEvent('click', {bubbles: true})); }", e); wait(2.2)

            def s_sim():
                caption("Change the ground: type a storm, then paint paving and green space straight onto the map.")
                click("[data-step=simulate]"); settle(8); click("[data-bottom-tab=scenario]"); wait(.6)
                page.fill("#ask", ""); page.type("#ask", "120 mm of rain over 4 days", delay=18 if a.short else 40); click("#run"); wait(1.5)
                paint("pave", -90, -40); paint("green", 40, 30)
                note("  cells changed by painting:", js("() => { let k = 0; for (let c = 0; c < n * n; c++) if (pWater[c] || pDrain[c] || pPave[c]) k++; return k; }"))

            def s_compare():
                caption("Modelled comparison under stated forcing. Not measured intervention benefit.")
                js("() => { const s = document.getElementById('viewSel'); if (s) { s.value = 'diff'; s.onchange(); } }"); click("[data-bottom-tab=report]"); wait(2.5 if a.short else 4)
                note("  report card:", (page.text_content("#rcBody") or "")[:260].replace("\n", " "))

            def s_twin():
                caption("The same ground as a 3D block: surface movement on top, clay zone below.")
                js("() => { const s = document.getElementById('viewSel'); if (s) { s.value = 'move'; s.onchange(); } }"); click("[data-v=twin]"); wait(4); click("[data-v=split]"); wait(.5)

            def s_decide():
                caption("Different stakeholders ask different questions. Results are experimental field-inspection hypotheses.")
                click("#clearPaint"); click("[data-bottom-tab=usecases]"); wait(.6)
                for role, uc in (("planner", "compare"), ("utility", "leak"), ("engineer", "rank"), ("resident", "mine"), ("emergency", "storm")):
                    js("r => setRole(r)", role); wait(.6); click(f"[data-uc={uc}]"); wait(2.4); shot(f"role_{role}")
                    note(f"  {role}/{uc}:", (page.text_content("#ucOut") or "")[:160].replace("\n", " "))

            def s_act():
                caption("Act: a plan for the chosen role, files that open in real tools, and one zip with the scenario you built.")
                click("#clearPaint"); js("r => setRole(r)", "engineer"); click("[data-step=act]"); settle(6); click("[data-bottom-tab=deliverables]"); wait(2.5)

            def s_cause():
                caption("Every link has its number, its equation and the paper behind it.")
                click("[data-step=understand]"); click("[data-v=map]"); settle(6); click("[data-bottom-tab=causal]"); wait(1.2)
                js("() => { const p = document.querySelector('[data-e=\"wet>art\"]'); if (p) p.dispatchEvent(new MouseEvent('click', {bubbles: true})); }"); wait(2)

            def s_worlds():
                page.goto(a.url + "/worlds.html", wait_until="domcontentloaded"); wait(5)
                for w in ("mars", "titan", "venus"):
                    js("w => { const e = document.querySelector(`[data-world=\"${w}\"]`); if (e) e.click(); }", w); wait(2.5); shot(f"world_{w}")

            def s_city():
                caption("Real terrain and real buildings, coloured by SWELL's estimate for the ground under them.")
                click("#clearPaint"); click("[data-v=map]"); wait(.6); click("#cityBtn"); wait(4); settle(25); wait(2)
                note("  3D city:", (page.text_content("#cityNote") or "")[:220]); shot("city_buildings")
                if js("() => document.body.classList.contains('city')"):
                    caption("Real city geometry, regional model overlay. Not a measurement of individual buildings.")
                    click("[data-city=photo]"); wait(6)
                    for _ in range(50):                                     # wait for the photorealistic tiles on screen, up to 25 s
                        if js("() => { try { return viewer.scene.primitives._primitives.some(p => p && p.tilesLoaded === true && p.show && p.root) } catch (e) { return false } }"): break
                        wait(.5)
                    wait(3); note("  photorealistic:", (page.text_content("#cityNote") or "")[:220]); shot("city_photoreal")
                    js("() => { const b = document.querySelector('[data-city=exit]'); if (b) b.click(); }"); wait(2)

            def s_verify():
                caption("Verify: compare with persistence and disclose failures. Retrospective testing is not independent field validation.")
                click("[data-step=verify]"); settle(8); click("[data-bottom-tab=research]"); wait(3)
                note("  tests:", json.dumps(info["tests"])); note("  research panel:", (page.text_content("#pinnOut") or "")[:400].replace("\n", " "))

            order = [("site", s_site), ("understand", s_understand), ("simulate", s_sim), ("before_after", s_compare), ("my_decisions", s_decide), ("city_3d", s_city), ("verify", s_verify)]
            for name, fn in order:
                scene(name, fn)
                if name != "worlds":
                    try: caption("")
                    except Exception: pass
        note("page errors:", len(errors)); [note("  " + e) for e in dict.fromkeys(errors)]
        video = page.video; ctx.close(); browser.close()
        try:
            src = pathlib.Path(video.path()); time.sleep(.5); src.replace(OUT / "swell_demo.webm")
        except Exception as ex: note("video file could not be renamed:", ex)
    (OUT / "demo_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nSaved in {OUT}: swell_demo.webm, {shots[0]} screenshots, demo_report.txt")
    return 0 if info and not info["synthetic"] and not any("PROBLEM in" in x for x in report) else 1


if __name__ == "__main__":
    sys.exit(main())
