import os, sys, time, pathlib, json, random
os.environ.pop("PYTHONPATH", None)
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parents[1]
URL = "file://" + str(AQUI / "index.html").replace(" ", "%20")
random.seed(7)
with sync_playwright() as p:
    br = p.chromium.launch(); pg = br.new_page()
    pg.goto(URL); pg.wait_for_function("!document.querySelector('#carga')")
    muestras = []
    stats = {}
    for nid, rango in [("lec", range(1, 828, 7)), ("lau", range(1, 52)), ("lph", range(1, 25)), ("cc", range(1, 1977, 25)), ("lopj", range(1, 643, 11)), ("ce", range(10, 170, 5)), ("lo1-2025", range(1, 25)), ("loe", range(1, 21)), ("trlgdcu", range(1, 171, 4)), ("lofce", range(1, 39))]:
        tot = 0
        for k in rango:
            pg.evaluate(f"location.hash='#a/{nid}/{k}'"); time.sleep(0.03)
            if pg.locator('#lector .a-body').count() == 0: continue
            r = pg.evaluate("""()=>[...document.querySelectorAll('#lector .a-body a.ref')].map(a=>{
              const p=a.closest('p,li'); const t=p?p.textContent:''; const i=t.indexOf(a.textContent);
              return {txt:a.textContent, tit:a.title, ctx:t.slice(Math.max(0,i-40), i+a.textContent.length+90)}})""")
            tot += len(r)
            for x in r: muestras.append((nid, k, x))
        stats[nid] = tot
    print("enlaces por norma (muestra):", stats)
    random.shuffle(muestras)
    for nid, k, x in muestras[:int(sys.argv[1]) if len(sys.argv) > 1 else 45]:
        print(f"[{nid} art {k}] -> {x['tit'][:60]!r}\n     …{x['ctx']!r}")
    br.close()
