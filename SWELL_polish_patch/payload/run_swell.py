"""Serve SWELL and its additive Worlds dashboard.
Run: python run_swell.py
"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode
from email.parser import BytesParser
from email.policy import default
from datetime import datetime, timezone
import json, os, re, uuid, urllib.request, urllib.error
import earth_services as earth
import geo_services as geo
import location_services as loc

ROOT = Path(__file__).resolve().parent / "site"
UPLOAD_ROOT = ROOT / "uploads" / "worlds"
MAX_UPLOAD = 500 * 1024 * 1024
PDS_SEARCH = "https://pds.nasa.gov/api/search/1/products"

# ---- Connections + real-site builder (local machine only) ----
import subprocess, sys, threading
APP = Path(__file__).resolve().parent
JOB = {"proc": None, "log": [], "state": "idle", "mode": None, "started": None}
JOB_LOCK = threading.Lock()

def _local_only(handler):
    """Keys and jobs may only be touched from this computer, through this address (blocks other sites and other machines)."""
    host = (handler.headers.get("Host") or "").split(":")[0]
    origin = handler.headers.get("Origin")
    return (handler.client_address[0] in ("127.0.0.1", "::1") and host in ("127.0.0.1", "localhost")
            and (origin is None or urlparse(origin).hostname in ("127.0.0.1", "localhost")))

def _redact_secrets(message):
    """Never echo a saved credential through an API error response."""
    value = str(message)
    try:
        import connections
        connections.load_env()
        for key in connections.KEYS:
            secret = os.environ.get(key)
            if secret:
                value = value.replace(secret, "•••")
    except Exception:
        pass
    return value[:500]

def _start_real_site(payload):
    mode = payload.get("mode"); args = [sys.executable, "-u", str(APP / "real_site.py")]
    if mode not in ("check", "build", "extras"): raise ValueError("mode must be check, build or extras")
    if payload.get("site"):
        if not re.fullmatch(r"[a-z0-9_]{2,30}", str(payload["site"])): raise ValueError("invalid site")
        args += ["--site", str(payload["site"])]
    else:
        b = [float(x) for x in payload["bbox"]]
        if len(b) != 4 or not (-180 <= b[0] < b[2] <= 180 and -90 <= b[1] < b[3] <= 90) or (b[2] - b[0]) > 1.5 or (b[3] - b[1]) > 1.5: raise ValueError("box must be valid and at most 1.5 degrees wide")
        args += ["--bbox", *[f"{x:.4f}" for x in b], "--name", re.sub(r"[^A-Za-z0-9 ,.\-]", "", str(payload.get("name") or "My place"))[:60] or "My place"]
    args += ["--check", "--install-deps"] if mode == "check" else ["--extras-only"] if mode == "extras" else ["--yes", "--install-deps"]   # missing Python packages are installed as part of the job
    with JOB_LOCK:
        if JOB["proc"] is not None and JOB["proc"].poll() is None: raise RuntimeError("a job is already running")
        import connections; connections.load_env()
        JOB.update(log=[], state="running", mode=mode, started=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        proc = subprocess.Popen(args, cwd=str(APP), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        JOB["proc"] = proc
    def pump():
        for line in proc.stdout:
            line = line.rstrip()
            if line and "Warning" not in line and not line.startswith("  "): JOB["log"].append(line[:600]); del JOB["log"][:-400]
        code = proc.wait(); JOB["state"] = "done" if code == 0 else "failed"
    threading.Thread(target=pump, daemon=True).start()

class SWELLHandler(SimpleHTTPRequestHandler):
    def _json(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/assurance/'):
            import science_assurance as assurance
            return assurance.http_get(self,APP,ROOT)
        if parsed.path.startswith('/api/mission/'):
            import stakeholder_mission as mission
            return mission.http_get(self,APP,ROOT)
        if parsed.path in ('/earth', '/earth/'):   # Earth is the main workspace; Worlds stays at /worlds.html
            self.path = '/index.html'; return super().do_GET()
        if parsed.path == '/':
            # Earth Decision Studio is always the home workspace. Synthetic fixtures
            # remain hidden by default inside index.html; data connection is a clear
            # next step, not a separate landing experience that strands new users.
            # Prefer the guided decision workflow when a real NISAR study exists.
            # Keep the classic Earth Studio at /index.html and /earth.
            try:
                active=json.loads((ROOT/'data'/'site.json').read_text(encoding='utf-8'))
                source=str(active.get('source','')).upper()
                ready='NISAR' in source and 'SYNTH' not in source and (APP/'out'/'real_site_provenance.json').is_file()
            except (OSError,ValueError,TypeError):ready=False
            self.path='/decision-mission.html' if ready else '/index.html'
            return super().do_GET()
        if parsed.path == '/api/connections':
            try:
                import connections
                q = parse_qs(parsed.query); lat = float(q.get('lat', ['32.7767'])[0]); lon = float(q.get('lon', ['-96.7970'])[0])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180): raise ValueError('bad coordinates')
                return self._json(200, connections.run(lat, lon))
            except Exception as exc: return self._json(400, {'error': str(exc)[:300]})
        if parsed.path == '/api/ai/status':
            try:
                import ai_provider
                return self._json(200, ai_provider.status())
            except Exception as exc:
                return self._json(200, {'provider': 'none', 'configured': False, 'warning': str(exc)[:240]})
        if parsed.path == '/api/ai/models':
            if not _local_only(self): return self._json(403, {'error': 'Provider model discovery is restricted to this computer.'})
            try:
                import ai_provider
                return self._json(200, ai_provider.list_models())
            except Exception as exc:
                return self._json(502, {'error': _redact_secrets(exc)})
        if parsed.path == '/api/system/health':
            try:
                site_path = ROOT / 'data' / 'site.json'
                site = json.loads(site_path.read_text(encoding='utf-8')) if site_path.exists() else {}
                source = str(site.get('source', 'UNAVAILABLE'))
                synthetic = 'SYNTH' in source.upper()
                real = bool(site) and not synthetic and bool(site.get('pass_days'))
                provenance_path = APP / 'out' / 'real_site_provenance.json'
                provenance = json.loads(provenance_path.read_text(encoding='utf-8')) if provenance_path.exists() else {}
                connection_path = APP / 'out' / 'connection_status.json'
                connection_report = json.loads(connection_path.read_text(encoding='utf-8')) if connection_path.exists() else None
                import ai_provider, connections
                ai = ai_provider.status()
                sensors = site.get('sensors') if isinstance(site.get('sensors'), dict) else {}
                return self._json(200, {
                    'site': {'loaded': bool(site), 'real_site_loaded': real, 'synthetic': synthetic,
                             'name': site.get('name'), 'source': source, 'pass_count': len(site.get('pass_days', [])),
                             'last_pass_day': (site.get('pass_days') or [None])[-1], 'bbox': site.get('bbox'),
                             'sensors': sensors, 'file_mtime': site_path.stat().st_mtime if site_path.exists() else None,
                             'provenance_available': bool(provenance), 'provenance_steps': list((provenance.get('steps') or {}).keys())},
                    'job': {'state': JOB['state'], 'mode': JOB['mode'], 'started': JOB['started'], 'log': JOB['log'][-80:]},
                    'ai': ai, 'keys_set': connections.key_state(),
                    'connections': ({'checked_utc': connection_report.get('checked_utc'),
                                     'ok_count': sum(1 for x in connection_report.get('results', []) if x.get('status') == 'ok'),
                                     'total_count': len(connection_report.get('results', [])),
                                     'results': connection_report.get('results', [])} if connection_report else None),
                    'next_step':  ('Open the real study workspace.' if real else
                                  'API checks do not load a site. Find compatible NISAR passes, then run Build the real twin.' if not synthetic else
                                  'Synthetic fixture is present for software testing only. Build a real site from compatible NISAR acquisitions before site-specific decisions.')
                })
            except Exception as exc:
                return self._json(500, {'error': 'Could not assemble SWELL health status: ' + str(exc)[:300]})
        if parsed.path == '/api/decisions':
            try:
                if not _local_only(self): return self._json(403, {'error': 'Decision ledger is available only on this computer.'})
                import decision_ledger
                q = parse_qs(parsed.query)
                site_name = (q.get('site') or [None])[0]
                limit = int((q.get('limit') or ['50'])[0])
                return self._json(200, {'records': decision_ledger.list_records(APP, site_name, limit), 'integrity': decision_ledger.verify(APP)})
            except Exception as exc: return self._json(400, {'error': str(exc)[:300]})
        if parsed.path == '/api/decisions/verify':
            try:
                if not _local_only(self): return self._json(403, {'error': 'Decision ledger is available only on this computer.'})
                import decision_ledger
                return self._json(200, decision_ledger.verify(APP))
            except Exception as exc: return self._json(400, {'error': str(exc)[:300]})
        if parsed.path == '/api/nasa/nisar-catalog':
            try:
                q = parse_qs(parsed.query)
                if (q.get('site') or [None])[0]:
                    from swell.ingest import SITES
                    site_key = (q.get('site') or [None])[0]
                    if site_key not in SITES: raise ValueError('Unknown study site.')
                    bbox = SITES[site_key]['bbox']
                else:
                    bbox = [float(q[k][0]) for k in ('west', 'south', 'east', 'north')]
                import nasa_catalog
                result = nasa_catalog.search_nisar_gunw(bbox, (q.get('start') or ['2025-08-01'])[0], (q.get('end') or [None])[0], int((q.get('limit') or ['30'])[0]))
                return self._json(200, result)
            except ValueError as exc: return self._json(400, {'error': str(exc)[:300]})
            except Exception as exc: return self._json(502, {'error': 'NASA CMR catalog unavailable: ' + str(exc)[:300]})
        if parsed.path == '/api/real-site/status':
            try:
                site = json.loads((ROOT/'data'/'site.json').read_text(encoding='utf-8'))
                source = str(site.get('source', 'UNAVAILABLE'))
                real = 'SYNTH' not in source.upper() and bool(site.get('pass_days'))
                name = site.get('name') if real else None
                pass_count = len(site.get('pass_days', []))
            except Exception:
                real, name, source, pass_count = False, None, 'UNAVAILABLE', 0
            return self._json(200, {'state': JOB['state'], 'mode': JOB['mode'], 'started': JOB['started'],
                                    'log': JOB['log'][-200:], 'real_site_loaded': real, 'real_site_name': name,
                                    'source': source, 'pass_count': pass_count,
                                    'next_step': 'Open Decision Studio; reload the browser if it was already open during the build.' if real else 'Connection checks are not a loaded site. Find compatible radar passes and build the real twin.'})
        if parsed.path == '/api/science/events':
            try:
                import science_events
                return self._json(200,science_events.events())
            except Exception as exc:return self._json(502,{'error':f'NASA EONET unavailable: {exc}. No substitute events.'})
        if parsed.path == '/api/science/radar-files':
            try:
                import science_observations as so
                return self._json(200,so.local_radar_files(ROOT))
            except Exception as exc:return self._json(400,{'error':str(exc)})
        if parsed.path == '/api/science/observations':
            try:
                import science_observations as so
                return self._json(200,so.list_observations(ROOT,parse_qs(parsed.query)['id'][0]))
            except Exception as exc:return self._json(400,{'error':str(exc)})
        if parsed.path.startswith("/api/site-twin/"):
            try:
                import site_twin as twin
                q={k:v[0] for k,v in parse_qs(parsed.query).items()}; action=parsed.path.rsplit('/',1)[-1]
                if action=='imagery':
                    data=twin.imagery(ROOT,q['id']);self.send_response(200);self.send_header('Content-Type','image/jpeg');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
                if action=='forecast':return self._json(200,twin.hourly_forecast(q,ROOT))
                if action=='evidence':return self._json(200,twin.evidence(q))
                return self._json(404,{'error':'Unknown site action'})
            except Exception as exc: return self._json(502,{'error':f'Site Twin {action} failed: {exc}'})
        if parsed.path == "/api/location/snapshot":
            try: return self._json(200,loc.snapshot(parse_qs(parsed.query)))
            except (ValueError,TypeError): return self._json(400,{"error":"Invalid location coordinates"})
        if parsed.path.startswith("/api/geo/raster-tile/"):
            try:
                match=re.fullmatch(r"/api/geo/raster-tile/([0-9a-f]{64})/(\d+)/(\d+)/(\d+)\.png",parsed.path)
                if not match: raise ValueError("Invalid raster tile path")
                digest,z,x,y=match.groups();data=geo.raster_tile(ROOT,digest,int(z),int(x),int(y))
                self.send_response(200);self.send_header("Content-Type","image/png");self.send_header("Cache-Control","public, max-age=86400");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);return
            except FileNotFoundError: return self._json(404,{"error":"Raster not found"})
            except Exception: return self._json(400,{"error":"Unable to render raster tile; check source and address"})
        if parsed.path in ("/api/geo/forecast", "/api/geo/quakes", "/api/geo/fires", "/api/geo/wmts"):
            try:
                fn={"/api/geo/forecast":geo.forecast,"/api/geo/quakes":geo.quakes,"/api/geo/fires":geo.fires,"/api/geo/wmts":geo.wmts}[parsed.path]
                return self._json(200,fn(parse_qs(parsed.query)))
            except ValueError as exc: return self._json(400,{"error":str(exc)})
            except Exception: return self._json(502,{"error":"Upstream source unavailable; no substitute data used"})
        if parsed.path in ("/api/earth/catalog", "/api/earth/granules", "/api/earth/gibs"):
            try:
                q=parse_qs(parsed.query)
                result=earth.catalog(q) if parsed.path.endswith("catalog") else earth.granules(q) if parsed.path.endswith("granules") else earth.capabilities()
                return self._json(200,result)
            except ValueError as exc: return self._json(400,{"error":str(exc)})
            except Exception as exc: return self._json(502,{"error":"Provider unavailable or response invalid: "+str(exc)})
        if parsed.path == "/api/worlds/mosaic":
            try:
                import world_mosaics
                body=(parse_qs(parsed.query).get('body') or [''])[0]
                data=world_mosaics.mosaic(body, APP)
                self.send_response(200); self.send_header('Content-Type','image/jpeg'); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','public, max-age=86400'); self.end_headers(); self.wfile.write(data); return
            except ValueError as exc: return self._json(400, {'error':str(exc)[:300]})
            except Exception as exc: return self._json(502, {'error':'NASA Trek mosaic unavailable: '+str(exc)[:250]})
        if parsed.path in ("/api/worlds/pds-search", "/api/worlds/native-dem"):
            import planetary_products as pp
            q = parse_qs(parsed.query)
            try:
                if parsed.path.endswith("native-dem"):
                    if not _local_only(self): return self._json(403, {"error": "Local workspace only"})
                    return self._json(200, pp.dem_window(q.get("body", [""])[0], q.get("lat", [""])[0], q.get("lon", [""])[0]))
                keywords = q.get("keywords", [""])[0]
                body = q.get("body", [keywords])[0]
                return self._json(200, pp.search(body, keywords, q.get("limit", ["12"])[0]))
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            except Exception as exc:
                return self._json(502, {"error": "Planetary provider unavailable: " + str(exc)[:250]})
        if parsed.path == "/api/worlds/files":
            body = re.sub(r"[^a-z0-9_-]", "", (parse_qs(parsed.query).get("body") or ["mars"])[0].lower())
            folder = UPLOAD_ROOT / body
            files = []
            manifest_path = folder / "manifest.json"
            records = {}
            if manifest_path.exists():
                try:
                    records = {r.get("stored_name"): r for r in json.loads(manifest_path.read_text())}
                except Exception:
                    records = {}
            if folder.exists():
                for p in sorted(folder.iterdir()):
                    if p.is_file() and p.name != "manifest.json":
                        record = records.get(p.name, {})
                        files.append({"name": record.get("original_name", p.name),
                                      "stored_name": p.name, "size": p.stat().st_size,
                                      "url": f"/uploads/worlds/{body}/{p.name}",
                                      "crs": record.get("crs", "UNKNOWN"),
                                      "units": record.get("units", ""),
                                      "observation_time": record.get("observation_time", ""),
                                      "description": record.get("description", ""),
                                      "sha256": record.get("sha256", "")})
            return self._json(200, {"body": body, "files": files})
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/assurance/'):
            import science_assurance as assurance
            return assurance.http_post(self,APP,ROOT,_local_only,_redact_secrets)
        if parsed.path.startswith('/api/mission/'):
            import stakeholder_mission as mission
            return mission.http_post(self,APP,ROOT,_local_only,_redact_secrets)
        if parsed.path in ('/api/external/gnss', '/api/external/research', '/api/external/terrain'):
            if not _local_only(self) or 'application/json' not in (self.headers.get('Content-Type') or ''):
                return self._json(403, {'error':'External research requests are local-only.'})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=4096:return self._json(413,{'error':'Invalid request size'})
                payload=json.loads(self.rfile.read(n))
                import external_evidence as ev
                if parsed.path.endswith('/gnss'):return self._json(200,ev.gnss(APP))
                if parsed.path.endswith('/research'):return self._json(200,ev.search(APP,payload['question']))
                import terrain_routing
                return self._json(200,terrain_routing.analyze(ROOT,payload['id']))
            except (ValueError,KeyError,TypeError,FileNotFoundError) as exc:return self._json(400,{'error':_redact_secrets(exc)})
            except Exception as exc:return self._json(502,{'error':_redact_secrets(exc)})
        if parsed.path == '/api/ai/chat':
            if not _local_only(self) or 'application/json' not in (self.headers.get('Content-Type') or ''):
                return self._json(403, {'error': 'AI requests are restricted to this computer; configure authentication before hosting SWELL.'})
            try:
                n = int(self.headers.get('Content-Length', '0'))
                if not 0 < n <= 40000: return self._json(413, {'error': 'Invalid request size'})
                payload = json.loads(self.rfile.read(n))
                import ai_provider
                result = ai_provider.ask(payload.get('question', ''), APP, payload.get('context'))
                return self._json(200, result)
            except (ValueError, KeyError, TypeError) as exc: return self._json(400, {'error': str(exc)[:300]})
            except Exception as exc: return self._json(502, {'error': _redact_secrets(exc)})
        if parsed.path == '/api/ai/test':
            if not _local_only(self) or 'application/json' not in (self.headers.get('Content-Type') or ''):
                return self._json(403, {'error': 'AI provider tests are restricted to this computer.'})
            try:
                import ai_provider
                return self._json(200, ai_provider.test_connection())
            except Exception as exc:
                return self._json(502, {'error': _redact_secrets(exc)})
        if parsed.path == '/api/decisions':
            if not _local_only(self) or 'application/json' not in (self.headers.get('Content-Type') or ''):
                return self._json(403, {'error': 'Decision writes are restricted to this computer; configure authentication before hosting SWELL.'})
            try:
                n = int(self.headers.get('Content-Length', '0'))
                if not 0 < n <= 50000: return self._json(413, {'error': 'Invalid request size'})
                payload = json.loads(self.rfile.read(n))
                import decision_ledger
                return self._json(201, decision_ledger.append(payload, APP))
            except (ValueError, KeyError, TypeError) as exc: return self._json(400, {'error': str(exc)[:300]})
            except Exception as exc: return self._json(500, {'error': 'Could not append decision record: ' + str(exc)[:300]})
        if parsed.path in ('/api/connections/keys', '/api/real-site'):
            if not _local_only(self) or 'application/json' not in (self.headers.get('Content-Type') or ''): return self._json(403, {'error': 'Only this computer can change keys or start jobs.'})
            try:
                n = int(self.headers.get('Content-Length', '0'))
                if not 0 < n <= 20000: return self._json(413, {'error': 'Invalid request size'})
                payload = json.loads(self.rfile.read(n))
                if parsed.path == '/api/connections/keys':
                    import connections
                    changed = connections.save_keys(payload); return self._json(200, {'saved': changed, 'keys_set': connections.key_state()})
                _start_real_site(payload); return self._json(200, {'state': 'running'})
            except Exception as exc: return self._json(400, {'error': str(exc)[:300]})
        if parsed.path.startswith('/api/science/'):
            try:
                import science_observations as so
                action=parsed.path.rsplit('/',1)[-1];n=int(self.headers.get('Content-Length','0'));q={k:v[0] for k,v in parse_qs(parsed.query).items()}
                if not 0<n<=(50_000_000 if action=='water-import' else 100_000):return self._json(413,{'error':'Invalid request size'})
                raw=self.rfile.read(n)
                if action=='water-import':return self._json(200,so.register_water(ROOT,q['id'],raw,q['product'],q['observed_utc'],q['filename']))
                p=json.loads(raw)
                if action=='radar-pair':return self._json(200,so.register_local_pair(ROOT,p))
                if action=='water-download':return self._json(200,so.download_water(ROOT,p['id'],p['product'],p['granule_id']))
                if action=='water-compare':return self._json(200,so.compare_registered(ROOT,p))
                if action=='plan':
                    import science_plans
                    return self._json(200,science_plans.plan(p,ROOT))
                return self._json(404,{'error':'Unknown science action'})
            except Exception as exc:return self._json(400,{'error':str(exc)})
        if parsed.path == '/api/site-twin/cross-site-similarity':
            if not _local_only(self) or 'application/json' not in (self.headers.get('Content-Type') or ''):
                return self._json(403, {'error': 'Cross-site comparison is restricted to this computer.'})
            try:
                n = int(self.headers.get('Content-Length', '0'))
                if not 0 < n <= 16 * 1024 * 1024:
                    return self._json(413, {'error': 'Upload up to 16 MB of validated result JSON.'})
                payload = json.loads(self.rfile.read(n))
                uploads = payload.get('results') if isinstance(payload, dict) else None
                if not isinstance(uploads, list) or len(uploads) > 8:
                    return self._json(400, {'error': 'Upload between 1 and 8 other SWELL results.json files.'})
                active = json.loads((ROOT / 'data' / 'site.json').read_text(encoding='utf-8'))
                if 'SYNTH' in str(active.get('source', '')).upper():
                    return self._json(409, {'error': 'Cross-site research is disabled for the synthetic fixture. Load a real site first.'})
                current_path = APP / 'out' / 'results.json'
                if not current_path.exists():
                    return self._json(409, {'error': 'No validation results.json found. Run the real-site validation pipeline first.'})
                current = json.loads(current_path.read_text(encoding='utf-8'))
                current_name = str(active.get('name') or current.get('site') or 'Active site')
                if str(current.get('site') or '') != current_name or str(current.get('source') or '') != str(active.get('source') or ''):
                    return self._json(409, {'error': 'The saved validation results do not match the active site. Rebuild or revalidate this site before comparing.'})
                import swell.similarity as similarity
                ok, reason = similarity.eligible(current)
                if not ok:
                    return self._json(409, {'error': 'The active site does not meet the cross-site validation gate: ' + reason})
                results = {current_name: current}
                excluded = []
                for i, item in enumerate(uploads):
                    if not isinstance(item, dict):
                        excluded.append({'upload': i + 1, 'reason': 'not a JSON object'}); continue
                    name = str(item.get('site') or item.get('name') or f'Uploaded site {i+1}')[:100]
                    if name in results:
                        excluded.append({'upload': name, 'reason': 'duplicate site name'}); continue
                    eligible, why = similarity.eligible(item)
                    if not eligible:
                        excluded.append({'upload': name, 'reason': why}); continue
                    results[name] = {"site": name, "source": item.get("source"),
                                     "tests": item.get("tests"), "signature": item.get("signature")}
                if len(results) < 2:
                    return self._json(200, {'site': current_name, 'matches': [], 'compared_sites': 1, 'excluded': excluded,
                        'note': 'No additional uploaded site passed the validation gate.'})
                ranked = similarity.sisters(results).get(current_name, [])
                return self._json(200, {'site': current_name, 'matches': ranked, 'compared_sites': len(results),
                    'excluded': excluded,
                    'method': 'Standardized Euclidean distance across gain per clay rating, relaxation time, delay, artifact strength and artifact share.',
                    'limitation': 'Descriptive physical-signature similarity only. It does not prove causal equivalence, transferability or intervention effectiveness.'})
            except Exception as exc:
                return self._json(400, {'error': 'Cross-site comparison failed: ' + str(exc)[:300]})
        if parsed.path.startswith('/api/site-twin/'):
            try:
                import site_twin as twin
                action=parsed.path.rsplit('/',1)[-1]; n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=(50*1024*1024 if action in ('upload','compare','imagery-upload') else 2*1024*1024):return self._json(413,{'error':'Request too large'})
                raw=self.rfile.read(n)
                if action=='imagery-upload':
                    q={k:v[0] for k,v in parse_qs(parsed.query).items()};return self._json(200,twin.register_photo(ROOT,q['id'],raw,q.get('acquired')))
                if action=='upload':
                    q={k:v[0] for k,v in parse_qs(parsed.query).items()};q['meters']=q.get('meters')=='true';return self._json(200,twin.acquire(q,ROOT,raw))
                payload=json.loads(raw)
                if action=='compare':
                    import base64
                    return self._json(200,twin.compare_water(payload,ROOT,base64.b64decode(payload.pop('raster_base64'),validate=True)))
                if action=='calibrate':
                    import hybrid_calibration as hy
                    return self._json(200,hy.train(payload['csv'].encode()))
                if action == 'forecast-calibrate':
                    import forecast_verification
                    return self._json(200, forecast_verification.calibrate(payload['csv'].encode('utf-8'), float(payload.get('nominal_coverage', .90))))
                if action in ('numerical-review','asset-review','soil-review','research','local-evidence','train-point','predict-point'):
                    import decision_engine as de
                    return self._json(200,{'numerical-review':de.numerical_review,'asset-review':de.asset_review,'soil-review':de.soil_review,'research':de.research,'local-evidence':de.local_evidence,'train-point':de.train_point,'predict-point':de.predict_point}[action](payload,ROOT))
                if action=='literature':
                    import literature_rag
                    corpus=os.environ.get('SWELL_LITERATURE_CORPUS') or str(ROOT.parent/'literature'/'corpus.json')
                    if not corpus:raise ValueError('Configure SWELL_LITERATURE_CORPUS on the server first')
                    sources=literature_rag.retrieve(payload['question'],corpus)
                    return self._json(200,{'sources':sources,**literature_rag.explain(payload['question'],sources,os.environ.get('SWELL_OLLAMA_MODEL'))})
                if action=='ensemble':
                    import forecast_ensemble
                    return self._json(200,forecast_ensemble.evaluate(payload,ROOT))
                if action=='terrain':return self._json(200,twin.acquire(payload,ROOT))
                if action=='run':return self._json(200,twin.run(payload,ROOT))
                if action=='package':
                    data=twin.pack(payload,ROOT);self.send_response(200);self.send_header('Content-Type','application/zip');self.send_header('Content-Disposition','attachment; filename="SWELL-site-review.zip"');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
                return self._json(404,{'error':'Unknown site action'})
            except (ValueError,KeyError,TypeError,FileNotFoundError) as exc:return self._json(400,{'error':str(exc)})
            except Exception as exc:return self._json(502,{'error':f'Site Twin {locals().get("action","request")} failed: {exc}. No substitute data was used.'})
        if parsed.path in ("/api/location/screen", "/api/location/package"):
            try:
                n=int(self.headers.get("Content-Length","0"))
                if not 0<n<=100000: return self._json(413,{"error":"Invalid request size"})
                payload=json.loads(self.rfile.read(n));
                if not isinstance(payload,dict): raise ValueError("Object required")
                if parsed.path.endswith("screen"): return self._json(200,loc.screen(payload))
                data=loc.export(payload);self.send_response(200);self.send_header("Content-Type","application/zip");self.send_header("Content-Disposition",'attachment; filename="SWELL-draft-review.zip"');self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);return
            except ImportError: return self._json(501,{"error":"Install requirements-location.txt for CAD exports"})
            except (ValueError,TypeError,KeyError): return self._json(400,{"error":"Invalid scenario or coordinate inputs"})
        if parsed.path == "/api/earth/raster":
            try:
                length=int(self.headers.get("Content-Length","0"))
                if not 0<length<=50*1024*1024: return self._json(413,{"error":"Maximum 50 MB raster"})
                data=self.rfile.read(length)
                name=(parse_qs(parsed.query).get("name") or ["raster.tif"])[0][:150]
                return self._json(201,earth.raster_preview(data,name,ROOT))
            except ImportError: return self._json(501,{"error":"Install requirements-earth.txt for raster processing"})
            except Exception as exc: return self._json(400,{"error":str(exc)})
        if parsed.path != "/api/worlds/upload":
            return self._json(404, {"error": "Unknown API route."})
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD + 2_000_000:
            return self._json(413, {"error": "Upload is empty or exceeds the 500 MB limit."})
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            return self._json(415, {"error": "Expected multipart/form-data."})
        body_bytes = self.rfile.read(length)
        message = BytesParser(policy=default).parsebytes(
            (f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n").encode() + body_bytes
        )
        world, uploaded = "mars", None
        metadata = {"crs": "UNKNOWN", "units": "", "observation_time": "", "description": ""}
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            payload = part.get_payload(decode=True) or b""
            if name == "body":
                world = payload.decode("utf-8", "replace").strip().lower()
            elif name == "file":
                uploaded = (part.get_filename(), payload)
            elif name in metadata:
                metadata[name] = payload.decode("utf-8", "replace")[:1000]
        world = re.sub(r"[^a-z0-9_-]", "", world)[:32] or "mars"
        if not uploaded:
            return self._json(400, {"error": "No file field was supplied."})
        filename, content = uploaded
        filename = Path(filename or "upload.bin").name
        filename = re.sub(r"[^A-Za-z0-9._ -]", "_", filename).strip(" .")[:150] or "upload.bin"
        if len(content) > MAX_UPLOAD:
            return self._json(413, {"error": "File exceeds the 500 MB per-file limit."})
        folder = UPLOAD_ROOT / world
        folder.mkdir(parents=True, exist_ok=True)
        # Prefix UUID avoids overwrites and preserves the original display name in manifest.
        uid = uuid.uuid4().hex[:12]
        stored = f"{uid}-{filename}"
        target = folder / stored
        target.write_bytes(content)
        manifest_path = folder / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
        except Exception:
            manifest = []
        record = {"id": uid, "original_name": filename, "stored_name": stored,
                  "size": len(content), "world": world,
                  "uploaded_utc": datetime.now(timezone.utc).isoformat(),
                  "sha256": __import__("hashlib").sha256(content).hexdigest(), **metadata}
        manifest.append(record)
        manifest_path.write_text(json.dumps(manifest, indent=2))
        return self._json(201, {"id": uid, "name": filename, "path": f"/uploads/worlds/{world}/{stored}",
                                "size": len(content), "sha256": record["sha256"], "world": world, "crs": metadata["crs"]})

    def log_message(self, fmt, *args):
        # Keep normal request logs concise.
        super().log_message(fmt, *args)

if __name__ == "__main__":
    try:
        import connections; connections.load_env()   # keys from .env, never printed
    except Exception: pass
    os.chdir(ROOT)
    address = ("127.0.0.1", 8000)
    print(f"SWELL running at http://{address[0]}:{address[1]}")
    print("Earth Decision Studio: http://127.0.0.1:8000/")
    print("Connect real data: http://127.0.0.1:8000/connections.html")
    ThreadingHTTPServer(address, SWELLHandler).serve_forever()
