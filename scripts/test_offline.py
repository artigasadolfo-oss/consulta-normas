#!/usr/bin/env python3.12
"""Comprueba que la versión servida por HTTP (GitHub Pages) funciona SIN red tras la primera visita."""
import os, subprocess, sys, time, pathlib, socket
os.environ.pop("PYTHONPATH", None)
from playwright.sync_api import sync_playwright

AQUI = pathlib.Path(__file__).resolve().parents[1]
s = socket.socket(); s.bind(("127.0.0.1", 0)); puerto = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(puerto), "--bind", "127.0.0.1"], cwd=AQUI,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.2)
fallos = []
try:
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context()
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(f"http://127.0.0.1:{puerto}/index.html")
        pg.wait_for_function("!document.querySelector('#carga')", timeout=15000)
        pg.evaluate("navigator.serviceWorker.ready.then(()=>1)")
        time.sleep(1.5)
        cacheado = pg.evaluate("caches.keys().then(async ks=>{let n=[];for(const k of ks){const c=await caches.open(k);n.push(...(await c.keys()).map(r=>new URL(r.url).pathname))}return n})")
        print("en caché:", cacheado)
        if not any(x.endswith("index.html") or x == "/" for x in cacheado):
            fallos.append("index.html no quedó en la caché del service worker")
        pg.reload(); pg.wait_for_function("!document.querySelector('#carga')", timeout=15000)  # 2.ª visita: ya controlada por el SW
        ctx.set_offline(True)
        pg.reload()
        pg.wait_for_function("!document.querySelector('#carga')", timeout=15000)
        pg.fill("#q", "282 lec"); time.sleep(0.6)
        h = pg.inner_text("#lector .a-h")
        print("offline ->", h)
        if "Artículo 282" not in h:
            fallos.append("sin red no abre el artículo 282")
        if errs:
            fallos.append(f"errores JS: {errs[:2]}")
        br.close()
finally:
    srv.terminate()
print("OFFLINE OK" if not fallos else f"FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
