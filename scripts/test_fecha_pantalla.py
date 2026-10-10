#!/usr/bin/env python3.12
"""«Texto a fecha» en la web (10-10-2026, orden de Adolfo): con una fecha anterior a hoy, cada artículo enseña la redacción que estaba vigente ese día
(historial de redacciones, datos `hv` del build) y lo dice con un aviso. Uso:  env -u PYTHONPATH python3.12 scripts/test_fecha_pantalla.py [--capturas]
A) datos de prueba propios sobre el texto real del art. 10 de la LAU y del art. 9;  B) datos REALES compilados (hechos de la LAU en 2018-2019)."""
import os, sys, time, pathlib, re
os.environ.pop("PYTHONPATH", None)
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parents[1]
URL = "file://" + str(AQUI / "index.html").replace(" ", "%20")
CAPT = pathlib.Path(os.environ.get("CAPTURAS", AQUI / "scripts" / "_capturas")); CAPTURAS = "--capturas" in sys.argv
if CAPTURAS: CAPT.mkdir(exist_ok=True)
fallos, ok, saltadas = [], 0, []
def caso(n, cond, det=""):
    global ok
    if cond: ok += 1
    else: fallos.append(n)
    print(("  ok   " if cond else "  FALLA ") + n + ("" if cond else f"  -> {str(det)[:260]}"))

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(viewport={"width": 1280, "height": 860}, permissions=["clipboard-read", "clipboard-write"])
    ctx.add_init_script("window.__HOY='2026-10-10'")
    pg = ctx.new_page(); errs = []; ext = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("request", lambda r: ext.append(r.url) if not r.url.startswith(("file:", "data:", "blob:")) else None)
    pg.goto(URL); pg.wait_for_function("!!(window.__NT && window.__NT.hvTodos)"); time.sleep(0.6)
    real = pg.evaluate("()=>window.__NT.hvTodos()")      # datos reales ANTES de que las pruebas de abajo los pisen
    def abre(h):
        pg.evaluate("()=>{location.hash=''}"); time.sleep(0.15); pg.evaluate("h=>{location.hash=h}", h); time.sleep(0.45)
    def parrafos(): return [x for x in pg.evaluate("()=>[...document.querySelectorAll('#lector .a-body p')].map(p=>p.textContent.trim())") if x]
    def aviso(): return pg.inner_text("#lector .boe-fecha") if pg.locator("#lector .boe-fecha").count() else ""
    def fecha(v):
        pg.evaluate("v=>{const i=document.getElementById('f-fecha');i.value=v;i.dispatchEvent(new Event('change'))}", v); time.sleep(0.35)

    print("[A datos de prueba sobre el texto real del art. 10 LAU (3 tramos) y art. 9 (sin historial)]")
    pg.evaluate("()=>{sessionStorage.clear()}")
    abre("#a/lau/10"); hoy_txt = parrafos()
    HV = {"10": [["1995-01-01", "2013-06-05", "BOE-A-1994-26003", "Prórroga del contrato.", "1. Texto de 1995.\n\n2. Segundo apartado de 1995.", 0],
                 ["2013-06-06", "2026-10-06", "BOE-A-2013-5941", "Prórroga del contrato (título de 2013).", "1. Texto de 2013: tres años.", 0],
                 ["2026-10-07", "", "BOE-A-2026-20822", "Prórroga del contrato.", "", 1]]}
    pg.evaluate("([h])=>{window.__NT.ponerHv('lau',h)}", [HV]); abre("#a/lau/10")
    caso("sin fecha elegida el artículo es el de hoy; el selector «Texto a fecha» es un chip DENTRO de la barra de búsqueda y ya no hay fila encima del artículo", parrafos() == hoy_txt and pg.locator(".searchbar #fecha-chip #f-fecha").count() == 1 and pg.locator("#fecha-fila").count() == 0 and pg.locator("#lector .boe-fecha").count() == 0)
    abre("#a/lopj/1")
    caso("el chip es global: con una norma SIN historial (LOPJ) sigue en la barra y el artículo no lleva botón de redacciones", pg.locator(".searchbar #f-fecha").count() == 1 and pg.locator("#lector .rd-bt").count() == 0 and pg.locator("#lector article").count() == 1)
    pg.evaluate("()=>{window.__NT.fijaFecha('2018-10-01')}"); abre("#a/lopj/1")
    caso("…y con una fecha elegida el chip la mantiene (para poder quitarla) aunque esa norma no tenga historial", pg.input_value("#f-fecha") == "2018-10-01" and pg.locator("#f-hoy").is_visible())
    caso("…y el artículo de la LOPJ se muestra con el texto de hoy Y con un aviso claro de que esa norma no tiene historial (nunca en silencio)", "no tiene historial de redacciones" in aviso() and "texto de hoy" in aviso() and len(parrafos()) > 0, aviso())
    pg.evaluate("()=>{window.__NT.fijaFecha('')}")
    abre("#a/lau/10"); fecha("2018-10-01")
    caso("01-10-2018: se ve la redacción de 2013 y no la de hoy", parrafos() == ["1. Texto de 2013: tres años."], parrafos())
    caso("el aviso dice la fecha, que no es la de hoy, el periodo y la norma que la introdujo (enlace al BOE)",
         "01-10-2018" in aviso() and "no la de hoy" in aviso() and "06-06-2013" in aviso() and "06-10-2026" in aviso() and pg.locator("#lector .boe-fecha a[href*='BOE-A-2013-5941']").count() == 1, aviso())
    caso("avisa del límite: no resuelve el régimen transitorio, que decide el jurista", "régimen transitorio" in aviso() and "jurista" in aviso())
    caso("si el título era otro, lo dice, y sin punto doble al cerrar las comillas", "título de 2013" in aviso() and ".»" not in aviso(), aviso())
    caso("el chip se pone en ámbar, aparece la ✕ y el estado accesible dice qué se muestra", "on" in (pg.get_attribute("#fecha-chip", "class") or "").split() and pg.locator("#f-hoy").is_visible() and "01-10-2018" in pg.text_content("#f-estado"))
    caso("la fecha elegida queda en el campo", pg.input_value("#f-fecha") == "2018-10-01")
    fecha("2005-03-01")
    caso("2005: la redacción de 1995 con sus dos apartados y su ancla de apartado", parrafos() == ["1. Texto de 1995.", "2. Segundo apartado de 1995."] and pg.locator("#lector .a-body p.ap[data-ap='2']").count() == 1, parrafos())
    fecha("1994-12-31")
    caso("antes de existir: «no existía» y dice desde cuándo rige", "no existía" in aviso() and "01-01-1995" in aviso() and "no existía" in pg.inner_text("#lector .a-body"), aviso())
    fecha("2026-10-07")
    caso("el tramo VIGENTE a esa fecha se ve con el texto de hoy y el aviso dice que es la misma redacción", parrafos() == hoy_txt and "misma que rige hoy" in aviso() and "no indica la fecha de vigencia" in aviso(), aviso())
    fecha("2026-10-10")
    caso("la fecha de HOY es lo mismo que no elegir: sin aviso de fecha", parrafos() == hoy_txt and pg.locator("#lector .boe-fecha").count() == 0)
    fecha("2018-10-01"); pg.click("#lector .boe-fecha [data-fecha-hoy]"); time.sleep(0.3)
    caso("«Volver a hoy» del aviso restablece el texto de hoy y vacía el campo", parrafos() == hoy_txt and pg.input_value("#f-fecha") == "")
    fecha("2018-10-01"); pg.click("#f-hoy"); time.sleep(0.3)
    caso("la ✕ del chip hace lo mismo, devuelve el foco al campo y se oculta sin fecha", parrafos() == hoy_txt and pg.locator("#lector .boe-fecha").count() == 0 and not pg.locator("#f-hoy").is_visible() and "on" not in (pg.get_attribute("#fecha-chip", "class") or "").split() and pg.evaluate("()=>document.activeElement.id") == "f-fecha")
    fecha("2018-10-01")
    abre("#a/lau/9")
    caso("un artículo SIN historial dice que no lo tiene y enseña el de hoy (no miente: «puede no ser el que regía»)", "Sin historial de este artículo" in aviso() and "puede no ser" in aviso(), aviso())
    abre("#a/lau/10")
    caso("la fecha se conserva al abrir otro artículo y volver", "2018-10-01" == pg.input_value("#f-fecha") and parrafos() == ["1. Texto de 2013: tres años."])
    pg.evaluate("()=>{document.activeElement&&document.activeElement.blur&&document.activeElement.blur()}"); pg.keyboard.press("d")
    caso("tecla D lleva el foco al campo de fecha", pg.evaluate("()=>document.activeElement&&document.activeElement.id")=="f-fecha")
    pg.evaluate("()=>{document.activeElement.blur()}")
    pg.click("#b-copiar"); time.sleep(0.4); cb = pg.evaluate("()=>navigator.clipboard.readText()")
    caso("Copiar rotula la fecha y copia ESA redacción", "[Redacción vigente el 01-10-2018, no la de hoy]" in cb and "Texto de 2013: tres años." in cb and "Texto de 1995" not in cb, cb[:200])
    fecha("1994-12-31"); pg.click("#b-copiar"); time.sleep(0.4); cb = pg.evaluate("()=>navigator.clipboard.readText()")
    caso("Copiar antes de existir lo dice y no inventa texto", "no existía el 31-12-1994" in cb, cb[:200])
    fecha("2018-10-01")
    pg.reload(); pg.wait_for_function("!!(window.__NT && window.__NT.hvTodos)"); time.sleep(0.5)
    abre("#a/lau/10")
    caso("al recargar la página dentro de la misma sesión la fecha sigue visible (nunca una fecha antigua oculta)", pg.input_value("#f-fecha") == "2018-10-01" and "on" in (pg.get_attribute("#fecha-chip", "class") or "").split())
    caso("entrada no válida (tecleada a medias) no cambia nada", (pg.evaluate("()=>{window.__NT.fijaFecha('2018-1')}"), pg.input_value("#f-fecha"))[1] == "2018-10-01")
    pg.evaluate("()=>{window.__NT.fijaFecha('')}"); pg.evaluate("()=>{sessionStorage.clear()}")


    print("  — chip en la barra y «Redacciones: N» (datos de prueba: 4 periodos, uno de un día y el vigente con vigencia incierta) —")
    HV4 = {"10": [["1995-01-01", "2013-06-05", "BOE-A-1994-26003", "Prórroga del contrato.", "1. Texto de 1995.", 0],
                  ["2013-06-06", "2026-09-30", "BOE-A-2013-5941", "Prórroga del contrato.", "1. Texto de 2013: tres años.", 0],
                  ["2026-10-01", "2026-10-01", "BOE-A-2026-20266", "Prórroga del contrato.", "1. Texto de un solo día.", 0],
                  ["2026-10-02", "", "BOE-A-2026-20526", "Prórroga del contrato.", "", 1]],
           "9": [["1995-01-01", "", "BOE-A-1994-26003", "Plazo mínimo.", "", 0]]}
    pg.evaluate("([h])=>{window.__NT.ponerHv('lau',h)}", [HV4]); pg.evaluate("()=>{window.__NT.fijaFecha('')}"); abre("#a/lau/10")
    rb = lambda: pg.locator("#lector .rd-bt")
    items = lambda: pg.locator("#lector .rd-pop .rd-it")
    caso("el chip está dentro de la barra, en la misma fila que el buscador y sin salirse de ella (escritorio)",
         pg.evaluate("()=>{const s=document.querySelector('.searchbar').getBoundingClientRect(),c=document.getElementById('fecha-chip').getBoundingClientRect(),q=document.getElementById('q').getBoundingClientRect();return c.left>=s.left&&c.right<=s.right+1&&Math.abs(c.top-q.top)<6&&c.left>q.right-1}"))
    caso("sin fecha: chip sin ámbar y sin ✕ visible", "on" not in (pg.get_attribute("#fecha-chip", "class") or "").split() and not pg.locator("#f-hoy").is_visible())
    caso("el artículo con 4 redacciones lleva «Redacciones: 4» en la línea de meta", rb().count() == 1 and "Redacciones: 4" in rb().inner_text() and pg.locator("#lector .a-meta .rd-bt").count() == 1, rb().count())
    abre("#a/lau/9")
    caso("un artículo con UNA sola redacción (historial de un tramo) NO lleva el botón", rb().count() == 0 and pg.locator("#lector article").count() == 1)
    abre("#a/lau/8")
    caso("un artículo sin historial NO lleva el botón", rb().count() == 0 and pg.locator("#lector article").count() == 1)
    abre("#a/lau/10")
    rb().click(); time.sleep(0.25)
    caso("al pulsarlo se abre una lista con un periodo por redacción, la más reciente primero", items().count() == 4 and rb().get_attribute("aria-expanded") == "true" and "02-10-2026 → hoy" in items().nth(0).inner_text() and "1995" in items().nth(3).inner_text(), items().all_inner_texts())
    caso("cada periodo dice la norma del BOE que lo introdujo; el vigente lo dice y marca la vigencia incierta", "BOE-A-2026-20526" in items().nth(0).inner_text() and "vigente hoy" in items().nth(0).inner_text() and "vigencia incierta" in items().nth(0).inner_text() and "BOE-A-2013-5941" in items().nth(2).inner_text())
    caso("el tramo de un solo día se marca «tramo breve (1 día)»", "tramo breve (1 día)" in items().nth(1).inner_text(), items().nth(1).inner_text())
    caso("sin fecha elegida está marcado el periodo vigente hoy", items().nth(0).get_attribute("aria-checked") == "true" and sum(1 for i in range(4) if items().nth(i).get_attribute("aria-checked") == "true") == 1)
    caso("el desplegable queda bajo su botón, dentro del lector y sin tapar la barra de botones", pg.evaluate("()=>{const p=document.querySelector('.rd-pop').getBoundingClientRect(),b=document.querySelector('.rd-bt').getBoundingClientRect(),l=document.getElementById('lector').getBoundingClientRect(),bar=document.querySelector('.l-bar').getBoundingClientRect();return p.top>=b.bottom-1&&p.bottom<=l.bottom+1&&p.top>=bar.bottom-1&&p.left>=l.left-1&&p.right<=l.right+1}"))
    items().nth(2).click(); time.sleep(0.35)
    caso("elegir un periodo fija la fecha en SU INICIO y enseña esa redacción", pg.input_value("#f-fecha") == "2013-06-06" and parrafos() == ["1. Texto de 2013: tres años."] and "on" in (pg.get_attribute("#fecha-chip", "class") or "").split(), (pg.input_value("#f-fecha"), parrafos()))
    caso("…cierra el desplegable y devuelve el foco al botón", pg.locator("#lector .rd-pop").count() == 0 and pg.evaluate("()=>document.activeElement.className") == "rd-bt" and rb().get_attribute("aria-expanded") == "false")
    rb().click(); time.sleep(0.2)
    caso("al reabrirlo el marcado es el periodo de la fecha elegida", items().nth(2).get_attribute("aria-checked") == "true" and sum(1 for i in range(4) if items().nth(i).get_attribute("aria-checked") == "true") == 1)
    items().nth(0).click(); time.sleep(0.3)
    caso("elegir el periodo vigente = volver a hoy (fecha vacía, sin ámbar)", pg.input_value("#f-fecha") == "" and parrafos() == hoy_txt and "on" not in (pg.get_attribute("#fecha-chip", "class") or "").split())
    rb().click(); time.sleep(0.2); items().nth(3).click(); time.sleep(0.3)
    caso("el primer periodo fija 01-01-1995", pg.input_value("#f-fecha") == "1995-01-01" and parrafos() == ["1. Texto de 1995."])
    caso("(con una fecha elegida, cambiarla en el chip con el desplegable abierto lo cierra)", (rb().click(), time.sleep(0.2), pg.evaluate("v=>{const i=document.getElementById('f-fecha');i.value=v;i.dispatchEvent(new Event('change'))}", "2018-10-01"), time.sleep(0.3), pg.locator("#lector .rd-pop").count())[4] == 0)
    pg.evaluate("()=>{window.__NT.fijaFecha('')}")
    print("  — solo teclado —")
    pg.evaluate("()=>{document.activeElement&&document.activeElement.blur&&document.activeElement.blur()}"); abre("#a/lau/10"); pg.evaluate("()=>{document.activeElement.blur()}")
    pg.keyboard.press("v"); time.sleep(0.25)
    caso("tecla V abre el desplegable y el foco va al periodo marcado", pg.locator("#lector .rd-pop").count() == 1 and pg.evaluate("()=>document.activeElement.classList.contains('rd-it')&&document.activeElement.getAttribute('aria-checked')==='true'"))
    pg.keyboard.press("ArrowDown"); pg.keyboard.press("ArrowDown")
    caso("↓ ↓ baja dos periodos (sin disparar atajos globales ni mover el lector)", pg.evaluate("()=>document.activeElement.getAttribute('data-i')") == "1", pg.evaluate("()=>document.activeElement.getAttribute('data-i')"))
    pg.keyboard.press("ArrowUp")
    caso("↑ sube uno", pg.evaluate("()=>document.activeElement.getAttribute('data-i')") == "2")
    pg.keyboard.press("j"); caso("j también baja (como en las demás listas)", pg.evaluate("()=>document.activeElement.getAttribute('data-i')") == "1")
    pg.keyboard.press("End"); caso("Fin lleva al más antiguo", pg.evaluate("()=>document.activeElement.getAttribute('data-i')") == "0")
    pg.keyboard.press("Enter"); time.sleep(0.3)
    caso("Intro elige el periodo con el teclado y el foco vuelve al botón", pg.input_value("#f-fecha") == "1995-01-01" and pg.evaluate("()=>document.activeElement.className") == "rd-bt")
    pg.keyboard.press("v"); time.sleep(0.2); pg.keyboard.press("Escape"); time.sleep(0.2)
    caso("Escape cierra sin cambiar la fecha y devuelve el foco al botón", pg.locator("#lector .rd-pop").count() == 0 and pg.input_value("#f-fecha") == "1995-01-01" and pg.evaluate("()=>document.activeElement.className") == "rd-bt")
    pg.keyboard.press("v"); time.sleep(0.2); pg.keyboard.press("Tab"); time.sleep(0.2)
    caso("Tab cierra el desplegable", pg.locator("#lector .rd-pop").count() == 0)
    pg.evaluate("()=>{document.activeElement.blur()}"); pg.keyboard.press("d")
    caso("tecla D lleva el foco al campo de fecha del chip", pg.evaluate("()=>document.activeElement.id") == "f-fecha")
    pg.keyboard.press("Escape")
    caso("Escape en el campo de fecha vuelve al buscador", pg.evaluate("()=>document.activeElement.id") == "q")
    pg.evaluate("()=>{window.__NT.fijaFecha('')}")
    rb().click(); time.sleep(0.2); pg.mouse.click(5, 5); time.sleep(0.2)
    caso("un clic fuera cierra el desplegable", pg.locator("#lector .rd-pop").count() == 0)
    abre("#a/lau/10"); abre("#a/lau/10")
    caso("el desplegable es un menú accesible (role=menu, opciones menuitemradio con aria-checked)", (rb().click(), time.sleep(0.2), pg.locator("#lector .rd-pop[role=menu] .rd-it[role=menuitemradio][aria-checked]").count())[2] == 4)
    pg.keyboard.press("Escape")
    pg.evaluate("()=>{window.__NT.ponerHv('lau',null)}")

    print("  — fecha FUTURA y reformas ya publicadas —")
    FU = dict(f="2026-11-15", o="v", p=["1. Posterior de prueba."], s=[[[1, "1. Posterior de prueba."]]])
    pg.evaluate("([f,h])=>{window.__NT.poner('lau',{'10':[['f','2026-11-15']]});window.__NT.ponerFu('lau',{'10':f});window.__NT.ponerHv('lau',h)}", [FU, HV]); abre("#a/lau/10")
    caso("sin fecha: vigente de hoy con el aviso de reforma publicada", "entra en vigor el 15-11-2026" in pg.inner_text("#lector .boe-red"))
    fecha("2026-12-01")
    caso("fecha FUTURA posterior a la entrada en vigor: se ve la posterior (ya rige) y el aviso dice «en vigor desde»", "en vigor desde el 15-11-2026" in pg.inner_text("#lector .boe-red") and parrafos() == ["1. Posterior de prueba."], pg.inner_text("#lector .boe-red")[:100])
    fecha("2026-11-14")
    caso("fecha futura ANTERIOR a la entrada en vigor: sigue la vigente de hoy", "entra en vigor" in pg.inner_text("#lector .boe-red") and parrafos() == hoy_txt)
    fecha("2018-10-01")
    caso("fecha pasada: no se mezcla el aviso de la reforma futura (solo el aviso de fecha)", pg.locator("#lector .boe-red").count() == 0 and pg.locator("#lector .boe-fecha").count() == 1)
    pg.evaluate("()=>{window.__NT.fijaFecha('')}")
    pg.evaluate("()=>{window.__NT.poner('lau',null);window.__NT.ponerFu('lau',undefined)}")

    print("  — datos REALES compilados (página recargada) —")
    pg.goto(URL); pg.reload(); pg.wait_for_function("!!(window.__NT && window.__NT.hvTodos)"); time.sleep(0.6)
    real = pg.evaluate("()=>window.__NT.hvTodos()")
    print(f"    (normas con historial en este build: {sorted(real) or 'NINGUNA'})")
    if "lau" in real:
        for nid, d in real.items():
            rotos = [k for k, t in d.items() for a, b in zip(t, t[1:]) if not (a[1] and a[1] < b[0] and a[0] < b[0])]
            caso(f"{nid}: tramos ordenados y sin solapes en todos los artículos ({len(d)})", not rotos, rotos[:3])
        def txt_a(nid, k, f):
            fecha_ = f
            pg.evaluate("()=>{window.__HOY='2026-10-10'}"); abre(f"#a/{nid}/{k}"); fecha(fecha_); return " ".join(parrafos())
        caso("LAU 9 al 01-10-2018: «inferior a tres años» (Ley 4/2013)", "inferior a tres años" in txt_a("lau", "9", "2018-10-01"))
        caso("LAU 9 al 06-03-2019: «inferior a cinco años» (RDL 7/2019)", "inferior a cinco años" in txt_a("lau", "9", "2019-03-06"))
        caso("LAU 10 al 01-10-2018: tres años (y no la redacción de 2026 que sale si se toma la vigencia vacía como «desde siempre»)", "como mínimo tres años de duración" in txt_a("lau", "10", "2018-10-01"))
        caso("LAU 10 al 20-12-2018: cinco años (RDL 21/2018)", "como mínimo cinco años" in txt_a("lau", "10", "2018-12-20"))
        caso("LAU 10 al 01-02-2019: otra vez tres años (el RDL 21/2018 quedó sin efecto)", "como mínimo tres años de duración" in txt_a("lau", "10", "2019-02-01"))
        if CAPTURAS:
            txt_a("lau", "10", "2018-10-01"); pg.screenshot(path=str(CAPT / "F1-lau10-2018.png"))
        fecha("")
        abre("#a/lau/10"); fecha("2018-12-20")
        nrd = len(real["lau"]["10"])
        caso(f"datos reales: LAU 10 muestra «Redacciones: {nrd}» (una por tramo de vigencia) y el periodo marcado es el que contiene el 20-12-2018", pg.locator("#lector .rd-bt").count() == 1 and f"Redacciones: {nrd}" in pg.inner_text("#lector .rd-bt") and (pg.locator("#lector .rd-bt").click(), time.sleep(0.25), pg.evaluate("()=>[...document.querySelectorAll('.rd-it')].filter(i=>i.getAttribute('aria-checked')==='true').map(i=>i.textContent)"))[2] == [next(x for x in pg.evaluate("()=>[...document.querySelectorAll('.rd-it')].map(i=>i.textContent)") if "19-12-2018 → 23-01-2019" in x)], pg.evaluate("()=>[...document.querySelectorAll('.rd-it')].map(i=>i.textContent)"))
        pg.evaluate("()=>{const i=[...document.querySelectorAll('.rd-it')].find(i=>i.textContent.includes('06-06-2013 →'));i.click()}"); time.sleep(0.4)
        caso("datos reales: elegir «06-06-2013 → 18-12-2018» fija 06-06-2013 y la LAU 10 dice «como mínimo tres años de duración»", pg.input_value("#f-fecha") == "2013-06-06" and "como mínimo tres años de duración" in " ".join(parrafos()), (pg.input_value("#f-fecha"), " ".join(parrafos())[:120]))
        pg.evaluate("()=>{window.__NT.fijaFecha('')}")
        sin_boton = [(nid, k) for nid, d in real.items() for k, tr in d.items() if len(tr) == 1][:1]
        if sin_boton:
            nid, k = sin_boton[0]; abre(f"#a/{nid}/{k}")
            caso(f"datos reales: un artículo con una sola redacción ({nid} {k}) NO lleva el botón", pg.locator("#lector .rd-bt").count() == 0)
        abre("#a/lec/1"); fecha("2005-01-01")
        caso("LEC art. 1 con fecha 2005: muestra aviso de fecha (la LEC tiene historial)", pg.locator("#lector .boe-fecha").count() == 1, aviso()[:120])
        pg.evaluate("()=>{window.__NT.fijaFecha('')}")
        caso("normas con historial en el build: exactamente las 13 elegidas", len(real) == 13 and {"lau", "lph", "cc", "lec", "trlgdcu", "loe", "lh", "cp", "ce", "trlc", "ljv"} <= set(real), sorted(real))
    else:
        saltadas.append("datos reales: este build no trae historial (compilado sin red)")
        print("  SALTADAS las pruebas con datos reales: build sin red (no cuentan como correctas)")
    caso("sin errores de JavaScript", not errs, errs[:2])
    caso("cero peticiones fuera de file:/data:/blob:", not ext, ext[:3])

    print("  — móvil —")
    mp = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True).new_page()
    mp.add_init_script("window.__HOY='2026-10-10'")
    mp.goto(URL); mp.wait_for_function("!!(window.__NT && window.__NT.hvTodos)"); time.sleep(0.5)
    mp.evaluate("([h])=>{window.__NT.ponerHv('lau',h)}", [HV]); mp.evaluate("h=>{location.hash=h}", "#a/lau/10"); time.sleep(0.7)
    mp.evaluate("v=>{const i=document.getElementById('f-fecha');i.value=v;i.dispatchEvent(new Event('change'))}", "2018-10-01"); time.sleep(0.4)
    caso("móvil: la fecha se aplica y no hay scroll horizontal", mp.locator("#lector .boe-fecha").count() == 1 and mp.evaluate("document.documentElement.scrollWidth<=window.innerWidth+1"))
    caso("móvil: el chip de fecha va debajo del buscador, a todo el ancho y sin desbordar", mp.evaluate("()=>{const c=document.getElementById('fecha-chip').getBoundingClientRect(),q=document.getElementById('q').getBoundingClientRect();return c.top>q.bottom-1&&c.right<=window.innerWidth+1&&c.left>=-1}"))
    mp.evaluate("([h])=>{window.__NT.ponerHv('lau',h)}", [HV]); mp.evaluate("h=>{location.hash=h}", "#a/lau/10"); time.sleep(0.6)
    mp.locator("#lector .rd-bt").tap(); time.sleep(0.4)
    caso("móvil: el desplegable de redacciones cabe en la pantalla y se puede pulsar un periodo", mp.locator("#lector .rd-pop .rd-it").count() == 3 and mp.evaluate("()=>{const p=document.querySelector('.rd-pop').getBoundingClientRect();return p.left>=-1&&p.right<=window.innerWidth+1}"))
    if CAPTURAS: mp.screenshot(path=str(CAPT / "F3-movil-redacciones.png"))
    mp.locator("#lector .rd-it").nth(1).tap(); time.sleep(0.4)
    caso("móvil: elegir un periodo aplica la fecha y el aviso del artículo lo dice", mp.locator("#lector .boe-fecha").count() == 1 and "no la de hoy" in mp.inner_text("#lector .boe-fecha"))
    if CAPTURAS: mp.screenshot(path=str(CAPT / "F2-movil.png"))
    br.close()

print(f"\n{ok} correctas, {len(fallos)} fallos" + (f" ({len(saltadas)} saltadas: {saltadas})" if saltadas else ""))
if fallos: print("FALLOS:", fallos)
sys.exit(1 if fallos else 0)
