#!/usr/bin/env python3.12
"""Reformas ya publicadas que AÚN NO RIGEN (10-10-2026, orden de Adolfo): por defecto se ve la redacción vigente el día de la consulta; el aviso deja ver
la posterior con lo que cambia resaltado; el día que entra en vigor, la posterior pasa sola a ser la que se ve.
Uso:  env -u PYTHONPATH python3.12 scripts/test_reforma_futura.py [--capturas]
A) motor (sin red, XML sintético con la forma real de la API): extracción de la vigente y la posterior (versión con fecha futura y cita en nota),
   resaltado, clasificación del texto que lleva la herramienta y sustitución del cuerpo.   B) pantalla (Chromium, sin red) sobre el index.html compilado."""
import datetime as dt, os, sys, time, pathlib, re
os.environ.pop("PYTHONPATH", None)
AQUI = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI)); sys.path.insert(0, str(AQUI / "scripts"))
import build, contraste_boe as c

fallos, ok = [], 0
def caso(n, cond, det=""):
    global ok
    if cond: ok += 1
    else: fallos.append(n)
    print(("  ok   " if cond else "  FALLA ") + n + ("" if cond else f"  -> {det}"))

def ver(vig, pub, parrafos, id_norma="X", extra=""):
    return (f'<version id_norma="{id_norma}" fecha_publicacion="{pub}" fecha_vigencia="{vig}"><p class="articulo">{parrafos[0]}</p>'
            + "".join(f'<p class="parrafo">{t}</p>' for t in parrafos[1:]) + extra + "</version>")
def doc(*b): return "<response><data><texto>" + "".join(b) + "</texto></data></response>"
def bloque(i, t, *v): return f'<bloque id="{i}" tipo="precepto" titulo="{t}">' + "".join(v) + "</bloque>"
HOY = dt.date(2026, 10, 10)

print("[A1 versión con fecha de vigencia futura (caso LPH 10, Ley 4/2026, 23-10-2026)]")
xml = doc(bloque("a10", "Artículo diez",
    ver("19600812", "19600723", ["Artículo diez.", "1. Texto antiguo uno.", "a) Letra a.", "2. Texto antiguo dos."]),
    ver("20261023", "20261003", ["Artículo diez.", "1. Texto nuevo uno.", "a) Letra a.", "b) Letra nueva.", "2. Texto antiguo dos."], id_norma="BOE-A-2026-20528")))
d = c.futuras_detalle(xml, HOY)
caso("detecta el artículo con la fecha de vigencia futura", list(d) == ["10"] and d["10"]["f"] == "2026-10-23" and d["10"]["o"] == "v", d)
caso("la vigente (ant) es la de hoy y la posterior (post) la futura, sin rótulo ni notas",
     d["10"]["ant"] == ["1. Texto antiguo uno.", "a) Letra a.", "2. Texto antiguo dos."] and d["10"]["post"] == ["1. Texto nuevo uno.", "a) Letra a.", "b) Letra nueva.", "2. Texto antiguo dos."], d["10"])
caso("el día que entra en vigor deja de ser futura", c.futuras_detalle(xml, dt.date(2026, 10, 23)) == {})
caso("una versión futura con el MISMO texto no genera nada", c.futuras_detalle(xml.replace("Texto nuevo uno.", "Texto antiguo uno.").replace('<p class="parrafo">b) Letra nueva.</p>', ""), HOY) == {})

print("[A2 reforma anunciada solo en una nota «Téngase en cuenta…» (caso LAU 10, RDL 28/2026, 15-11-2026): la posterior se reconstruye]")
def nota(texto_cita, extra_notas=""):
    ps = "".join(f'<p class="parrafo">{t}</p>' for t in texto_cita)
    return ('<blockquote class="siempreSeVe"><p class="parrafo">Téngase en cuenta que, con efectos de 15 de noviembre de 2026, se modifica por el art. único del '
            'Real Decreto-ley 28/2026, de 6 de octubre, Ref. BOE-A-2026-20822#au, con la siguiente redacción:</p>' + ps + '</blockquote>'
            '<blockquote><p class="nota_pie">Se modifica por el art. 3.8 del Real Decreto-ley 29/2026. Ref. BOE-A-2026-20800#a3</p></blockquote>')
base = ["Artículo 10. Prórroga.", "1. Primero vigente.", "Segunda frase del uno.", "2. Segundo vigente.", "3. Tercero vigente."]
xml = doc(bloque("a10", "Artículo 10", ver("", "20261007", base, id_norma="BOE-A-2026-20822",
    extra=nota(["«2. Segundo NUEVO.", "a) Letra nueva.", "4. Cuarto NUEVO.»"]))))
d = c.futuras_detalle(xml, HOY)["10"]
caso("origen 'n', fecha de la nota", d["o"] == "n" and d["f"] == "2026-11-15", d)
caso("la vigente es el cuerpo de la versión (sin la nota ni las notas al pie)", d["ant"] == base[1:], d["ant"])
caso("fusión por apartado: el 2 se sustituye (con su letra), el 1 y el 3 se quedan y el 4, nuevo, se añade",
     d["post"] == ["1. Primero vigente.", "Segunda frase del uno.", "2. Segundo NUEVO.", "a) Letra nueva.", "3. Tercero vigente.", "4. Cuarto NUEVO."], d["post"])
xml_entero = xml.replace("«2. Segundo NUEVO.", "«Texto único nuevo sin apartado numerado.").replace('<p class="parrafo">a) Letra nueva.</p><p class="parrafo">4. Cuarto NUEVO.»</p>', "»")
dn = c.futuras_detalle(xml_entero.replace("nuevo.</p>»", "nuevo.»"), HOY)
caso("una cita que no empieza por un apartado numerado es el artículo entero", dn.get("10", {}).get("post") == ["Texto único nuevo sin apartado numerado."], dn)
caso("la nota con fecha ya pasada no ofrece nada", c.futuras_detalle(xml.replace("15 de noviembre de 2026", "15 de enero de 2026"), HOY) == {})
caso("nota sin párrafos citados (formato desconocido) -> no se inventa la posterior", c.futuras_detalle(xml.replace('<p class="parrafo">«2. Segundo NUEVO.</p>', "").replace('<p class="parrafo">a) Letra nueva.</p>', "").replace('<p class="parrafo">4. Cuarto NUEVO.»</p>', ""), HOY) == {})

print("[A3 resaltado: palabra a palabra solo entre párrafos parecidos]")
ant = ["1. El plazo es de cuatro meses desde la notificación.", "2. Se suprime este párrafo que no existe después."]
post = ["1. El plazo es de seis meses desde la notificación.", "3. Párrafo completamente nuevo sin parecido alguno."]
seg = c.segmentos_cambios(ant, post)
plano = lambda p, tipos: " ".join(x[1] for x in p if x[0] in tipos)
caso("lo que no cambia sale como igual (t=0)", seg[0][0] == [0, "1. El plazo es de"], seg[0])
caso("la palabra cambiada sale suprimida (t=2) y nueva (t=1)", [2, "cuatro"] in seg[0] and [1, "seis"] in seg[0], seg[0])
caso("un párrafo que desaparece sale ENTERO como suprimido", [[2, ant[1]]] in seg, seg)
caso("un párrafo nuevo sale ENTERO como nuevo (no se alinea con palabras sueltas del otro)", [[1, post[1]]] in seg, seg)
caso("quitando lo suprimido se reconstruye EXACTAMENTE la posterior", [plano(p, (0, 1)) for p in seg if plano(p, (0, 1))] == post, seg)
caso("quitando lo nuevo se reconstruye EXACTAMENTE la vigente", [plano(p, (0, 2)) for p in seg if plano(p, (0, 2))] == ant, seg)
caso("redacciones idénticas -> todo igual", all(x[0] == 0 for p in c.segmentos_cambios(ant, ant) for x in p))

print("[A4 qué texto lleva la herramienta: vigente / posterior / otro]")
fut = {"10": "2026-10-23", "11": "2026-10-23", "12": "2026-10-23"}
det = {k: dict(f="2026-10-23", o="v", ant=["a"], post=["b"], sk_post="POST" + k) for k in fut}
esp = {"10": "VIG10", "11": "POST11", "12": "OTRO"}; vig = {"10": "VIG10", "11": "VIG11", "12": "VIG12"}
r = dict(distintos=["11", "12"])
out = c.clasifica_futuras(det, fut, esp, vig, r)
caso("espejo == vigente -> 'ant'", out["10"]["espejo"] == "ant")
caso("espejo == posterior -> 'post' y YA NO es una diferencia", out["11"]["espejo"] == "post" and r["distintos"] == ["12"], (out, r))
caso("espejo distinto de las dos -> 'otro' y SIGUE siendo diferencia (error real)", out["12"]["espejo"] == "otro" and "12" in r["distintos"])
caso("no se filtra el esqueleto interno al resultado", all("sk_post" not in v for v in out.values()))

print("[A5 build.aplica_futuras: el cuerpo por defecto es la vigente del BOE y se conservan las notas]")
def trozos():
    return [dict(k="10", b="1. POSTERIOR del espejo.\n\n> <small>Se modifica por X.</small>"), dict(k="11", b="1. Vigente del espejo."), dict(k="12", b="1. Rara."), dict(k="99", b="Otro.")]
build.FUTURAS.clear()
build.FUTURAS["Z"] = {"10": dict(f="2026-10-23", o="v", ant=["1. Vigente BOE."], post=["1. POSTERIOR del espejo."], espejo="post"),
                      "11": dict(f="2026-10-23", o="v", ant=["1. Vigente del espejo."], post=["1. Posterior."], espejo="ant"),
                      "12": dict(f="2026-10-23", o="v", ant=["1. A."], post=["1. B."], espejo="otro")}
ch = trozos(); fu = build.aplica_futuras("Z", ch)
caso("espejo == posterior: el cuerpo pasa a ser la vigente del BOE", ch[0]["b"].startswith("1. Vigente BOE."), ch[0]["b"])
caso("…y conserva la nota de reforma del espejo", "> <small>Se modifica por X.</small>" in ch[0]["b"], ch[0]["b"])
caso("espejo == vigente: el cuerpo no se toca", ch[1]["b"] == "1. Vigente del espejo.")
caso("espejo 'otro': ni se toca ni se ofrece la posterior (sigue el aviso de diferencia)", ch[2]["b"] == "1. Rara." and "12" not in fu)
caso("devuelve fecha, origen, posterior limpia y resaltado de los que ofrece", set(fu) == {"10", "11"} and fu["10"]["f"] == "2026-10-23" and fu["10"]["p"] == ["1. POSTERIOR del espejo."] and fu["10"]["s"], fu)
caso("una norma sin reformas anunciadas -> nada", build.aplica_futuras("Y", trozos()) == {})
build.FUTURAS.clear()

print("\n[B pantalla: Chromium sobre el index.html compilado, sin red]")
from playwright.sync_api import sync_playwright
URL = "file://" + str(AQUI / "index.html").replace(" ", "%20")
CAPT = pathlib.Path(os.environ.get("CAPTURAS", AQUI / "scripts" / "_capturas")); CAPTURAS = "--capturas" in sys.argv
if CAPTURAS: CAPT.mkdir(exist_ok=True)
with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(viewport={"width": 1280, "height": 860}, permissions=["clipboard-read", "clipboard-write"])
    ctx.add_init_script("window.__HOY='2026-10-10'")
    pg = ctx.new_page(); errs = []; ext = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("request", lambda r: ext.append(r.url) if not r.url.startswith(("file:", "data:", "blob:")) else None)
    pg.goto(URL); pg.wait_for_function("!!(window.__NT && window.__NT.fuTodos)"); time.sleep(0.6)
    def abre(h):
        pg.evaluate("h=>{location.hash=''}", h); time.sleep(0.2); pg.evaluate("h=>{location.hash=h}", h); time.sleep(0.5)
    def parrafos(): return pg.evaluate("()=>[...document.querySelectorAll('#lector .a-body p')].map(p=>p.textContent.trim())")
    # datos de prueba propios: partimos del texto REAL del art. 10 LPH en pantalla y le aplicamos tres cambios conocidos
    pg.evaluate("()=>{window.__NT.ponerFu('lph',undefined)}"); abre("#a/lph/10")
    ant = [x for x in parrafos() if x]
    check_ant = len(ant) >= 3
    caso("hay texto real del art. 10 LPH del que partir", check_ant, ant[:2])
    post = list(ant); post[0] = post[0].replace(post[0].split()[2], "PALABRACAMBIADA", 1); del post[1]; post.append("9. Apartado totalmente nuevo de prueba sin parecido.")
    FU = dict(f="2026-10-23", o="v", p=post, s=c.segmentos_cambios(ant, post))
    pg.evaluate("([f])=>{window.__NT.poner('lph',{'10':[['f','2026-10-23']]});window.__NT.ponerFu('lph',{'10':f})}", [FU]); abre("#a/lph/10")
    caja = lambda: pg.inner_text("#lector .boe-red") if pg.locator("#lector .boe-red").count() else ""
    caso("ANTES de la fecha: por defecto se ve la redacción VIGENTE (el texto de hoy, sin marcas)", parrafos() == ant and pg.locator("#lector .a-body ins, #lector .a-body del").count() == 0, parrafos()[:2])
    caso("el aviso es claro: reforma publicada, entra en vigor el 23 de octubre de 2026 y estás viendo la vigente", "entra en vigor" in caja() and "vigente hoy" in caja() and "2026" in caja(), caja())
    caso("ofrece ver la posterior, con lo que cambia resaltado (botón con su tecla)", pg.locator("#lector .fut-bt").count() == 1 and "posterior" in pg.inner_text("#lector .fut-bt") and "R" in pg.inner_text("#lector .fut-bt"))
    pg.click("#lector .fut-bt"); time.sleep(0.3)
    caso("al pulsar: se ve la POSTERIOR y lo que cambia va resaltado (nuevo y suprimido)", pg.locator("#lector .a-body ins.cam").count() >= 2 and pg.locator("#lector .a-body del.cam").count() >= 1, pg.inner_html("#lector .a-body")[:200])
    caso("la posterior mostrada (sin lo suprimido) es EXACTAMENTE la posterior", [x for x in pg.evaluate("()=>[...document.querySelectorAll('#lector .a-body p')].map(p=>[...p.childNodes].filter(n=>n.nodeName!=='DEL').map(n=>n.textContent).join(' ').replace(/\\s+/g,' ').trim())") if x] == [" ".join(x.split()) for x in post])
    caso("el aviso cambia: NO está vigente hasta el 23 de octubre y explica el resaltado", "NO está vigente" in caja() and "23" in caja() and "suprimido" in caja(), caja())
    caso("el apartado nuevo conserva su ancla de apartado (data-ap)", pg.locator("#lector .a-body p.ap[data-ap='9']").count() == 1)
    if CAPTURAS: pg.screenshot(path=str(CAPT / "R1-posterior-resaltada.png"))
    caso("tras pulsar, el foco sigue en el botón (teclado)", pg.evaluate("()=>document.activeElement&&document.activeElement.classList.contains('fut-bt')"))
    pg.keyboard.press("r"); time.sleep(0.3)
    caso("tecla R: vuelve a la vigente", parrafos() == ant and "vigente hoy" in caja(), caja())
    pg.keyboard.press("R"); time.sleep(0.3)
    caso("tecla R otra vez: de nuevo la posterior", pg.locator("#lector .a-body ins.cam").count() >= 2)
    pg.keyboard.press("Enter"); time.sleep(0.3)
    caso("Intro con el foco en el botón alterna (accesible por teclado)", parrafos() == ant)
    pg.click("#lector .fut-bt"); time.sleep(0.2)
    pg.click("#b-copiar"); time.sleep(0.4)
    cb = pg.evaluate("()=>navigator.clipboard.readText()")
    caso("Copiar en la vista posterior lo dice: «REDACCIÓN POSTERIOR: NO VIGENTE HASTA…» y copia la posterior", "REDACCIÓN POSTERIOR: NO VIGENTE HASTA EL" in cb and "PALABRACAMBIADA" in cb, cb[:160])
    pg.click("#lector .fut-bt"); time.sleep(0.2); pg.click("#b-copiar"); time.sleep(0.4)
    cb = pg.evaluate("()=>navigator.clipboard.readText()")
    caso("Copiar en la vista vigente copia la vigente y avisa de la reforma que viene", "PALABRACAMBIADA" not in cb and "Reforma ya publicada que entra en vigor el" in cb, cb[-160:])
    abre("#a/lph/9"); abre("#a/lph/10")
    caso("al reabrir el artículo se vuelve a la vista por defecto (la vigente)", parrafos() == ant)
    caso("R en un artículo SIN reforma anunciada no hace nada ni falla", (abre("#a/lph/9"), pg.keyboard.press("r"), time.sleep(0.2))[0] is None and pg.locator("#lector .boe-red").count() == 0 and not errs, errs)

    print("  — el día que entra en vigor —")
    pg.evaluate("()=>{window.__HOY='2026-10-23'}"); abre("#a/lph/10")
    caso("EL DÍA de entrada en vigor, por defecto se ve la POSTERIOR (ya es la vigente) y sin marcas", [x for x in parrafos() if x] == [" ".join(x.split()) for x in post] and pg.locator("#lector .a-body ins, #lector .a-body del").count() == 0, parrafos()[:2])
    caso("el aviso pasa solo a «Reforma en vigor desde…» y ofrece ver la anterior", "en vigor desde el" in caja() and "anterior" in pg.inner_text("#lector .fut-bt"), caja())
    pg.click("#lector .fut-bt"); time.sleep(0.3)
    caso("«Ver la redacción anterior» enseña la que regía hasta entonces", parrafos() == ant and "Ya no rige" in caja(), caja())
    pg.evaluate("()=>{window.__HOY='2026-10-22'}"); abre("#a/lph/10")
    caso("la víspera todavía se ve la vigente de hoy", parrafos() == ant)
    pg.evaluate("()=>{window.__HOY='2026-10-10'}")

    print("  — reforma reconstruida desde una nota (origen 'n') y artículos sin posterior —")
    FUn = dict(FU, o="n")
    pg.evaluate("([f])=>{window.__NT.ponerFu('lph',{'10':f})}", [FUn]); abre("#a/lph/10"); pg.click("#lector .fut-bt"); time.sleep(0.3)
    caso("si la posterior se reconstruyó de una nota, la pantalla lo DICE", "reconstruida" in caja() and "boe.es" in caja(), caja())
    pg.evaluate("()=>{window.__NT.ponerFu('lph',undefined)}"); abre("#a/lph/10")
    caso("con aviso 'f' pero sin posterior disponible (sin red al compilar) se conserva el aviso de siempre", pg.locator("#lector .fut-bt").count() == 0 and "Hasta entonces rige el texto de esta pantalla" in pg.inner_text("#lector .boe-av"), pg.inner_text("#lector")[:150])
    pg.evaluate("()=>{window.__NT.poner('lph',null)}")

    print("  — datos REALES compilados (página recargada: sin los datos de prueba de arriba) —")
    pg.goto(URL); pg.reload(); pg.wait_for_function("!!(window.__NT && window.__NT.fuTodos)"); time.sleep(0.6)
    real = pg.evaluate("()=>window.__NT.fuTodos()")
    print(f"    (artículos reales con reforma anunciada en este build: {sum(len(d) for d in real.values())})")
    for nid, d in real.items():
        for k, f in d.items():
            limpio = [" ".join(x[1] for x in p if x[0] != 2) for p in f["s"]]
            caso(f"{nid} {k}: el resaltado, sin lo suprimido, reproduce la posterior limpia", [" ".join(x.split()) for x in limpio if x.strip()] == [" ".join(x.split()) for x in f["p"]])
            caso(f"{nid} {k}: fecha en formato AAAA-MM-DD y origen v/n", bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", f["f"])) and f["o"] in ("v", "n"))
            pg.evaluate("()=>{window.__HOY='2026-10-10'}")
            abre(f"#a/{nid}/{k}")
            if f["f"] > "2026-10-10":
                caso(f"{nid} {k}: hoy se ve la vigente (la posterior NO es la de por defecto) y el cuadro avisa", pg.locator("#lector .fut-bt").count() == 1 and "vigente hoy" in caja() and pg.locator("#lector .a-body ins, #lector .a-body del").count() == 0, caja()[:100])
                caso(f"{nid} {k}: el texto vigente mostrado no contiene la redacción posterior entera", [x for x in parrafos() if x] != [" ".join(x.split()) for x in f["p"]])
                if CAPTURAS: pg.screenshot(path=str(CAPT / f"R2-{nid}-{k}-vigente.png"))
                pg.click("#lector .fut-bt"); time.sleep(0.3)
                if CAPTURAS: pg.screenshot(path=str(CAPT / f"R3-{nid}-{k}-posterior.png"))
                caso(f"{nid} {k}: la vista posterior resalta cambios", pg.locator("#lector .a-body ins.cam").count() >= 1)
    caso("sin errores de JavaScript", not errs, errs[:2])
    caso("cero peticiones fuera de file:/data:/blob:", not ext, ext[:3])

    print("  — móvil —")
    mp = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True).new_page()
    mp.add_init_script("window.__HOY='2026-10-10'")
    mp.goto(URL); mp.wait_for_function("!!(window.__NT && window.__NT.fuTodos)"); time.sleep(0.5)
    mp.evaluate("([f])=>{window.__NT.poner('lph',{'10':[['f','2026-10-23']]});window.__NT.ponerFu('lph',{'10':f})}", [FU])
    mp.evaluate("h=>{location.hash=h}", "#a/lph/10"); time.sleep(0.7)
    mp.tap("#lector .fut-bt"); time.sleep(0.3)
    caso("móvil: se alterna con el dedo y no hay scroll horizontal", mp.locator("#lector .a-body ins.cam").count() >= 2 and mp.evaluate("document.documentElement.scrollWidth<=window.innerWidth+1"))
    if CAPTURAS: mp.screenshot(path=str(CAPT / "R4-movil-posterior.png"))
    br.close()

print(f"\n{ok} correctas, {len(fallos)} fallos")
if fallos: print("FALLOS:", fallos)
sys.exit(1 if fallos else 0)
