"""The Earth Decision Studio is the home route even before a real site is connected."""
import os, threading, urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
import run_swell

def test_home_route_serves_earth_decision_studio(monkeypatch):
    monkeypatch.chdir(run_swell.ROOT)
    server=ThreadingHTTPServer(('127.0.0.1',0),run_swell.SWELLHandler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/',timeout=5) as r:
            body=r.read().decode('utf-8')
        assert 'Earth intelligence' in body
        assert 'Ask SWELL' in body
        assert 'Connections and real data' in body
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
