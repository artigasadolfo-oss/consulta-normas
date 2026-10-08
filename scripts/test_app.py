#!/usr/bin/env python3.12
"""Pruebas funcionales de Consulta de normas en Chromium real (Playwright).
Uso:  env -u PYTHONPATH python3.12 scripts/test_app.py [--capturas]
Cada prueba contrasta contra el CORPUS (el .md del BOE), no contra el propio HTML.
"""
import os, re, sys, time, pathlib, json
os.environ.pop("PYTHONPATH", None)
from playwright.sync_api import sync_playwright

AQUI = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import build
URL = "file://" + str(AQUI / "index.html").replace(" ", "%20")
CORPUS = (build.TEXTO if (build.TEXTO / "es").is_dir() else pathlib.Path.home() / "Documents/iA/LEYES/legalize-es") / "es"   # el MISMO texto que el build
CAPT = pathlib.Path(os.environ.get("CAPTURAS", AQUI / "scripts" / "_capturas"))
CAPTURAS = "--capturas" in sys.argv
if CAPTURAS:
    CAPT.mkdir(exist_ok=True)

fallos, ok = [], 0


def check(nombre, cond, detalle=""):
    global ok
    if cond:
        ok += 1
        print(f"  ok   {nombre}")
    else:
        fallos.append(nombre)
        print(f"  FALLA {nombre} {detalle}")


def decreto_parrafos(ini_regex, fin_regex):
    """Párrafos de un artículo del Decreto 11/1995 tomados de la copia VERBATIM de la carpeta DOGV (con la única
    regularización declarada: «Ñ» mayúscula dentro de palabra -> «ñ»)."""
    f = next((pathlib.Path.home() / "Documents/iA/LEYES/DOGV").glob("DOGV 42036*.md"))
    txt = f.read_text(encoding="utf-8").split("\n---\n", 1)[1].split("\n")
    out, dentro = [], False
    for ln in txt:
        if re.match(ini_regex, ln):
            dentro = True
            continue
        if dentro and re.match(fin_regex, ln):
            break
        if dentro and ln.strip():
            out.append(re.sub(r"(?<=[a-záéíóúü])Ñ(?=[a-záéíóúü])", "ñ", ln.strip()))
    return out


def fuente_articulo(boe, cabecera_regex, dir_="es"):
    """Texto del artículo directamente del .md (sin notas), para contrastar."""
    txt = (CORPUS.parent / dir_ / f"{boe}.md").read_text(encoding="utf-8").split("\n")
    out, dentro = [], False
    for ln in txt:
        if re.match(r"^#{1,6} ", ln):
            if dentro:
                break
            if re.match(cabecera_regex, ln.split(" ", 1)[1]):
                dentro = True
            continue
        if dentro and ln.strip() and not ln.startswith(">"):
            out.append(re.sub(r"\*\*", "", ln).strip())
    return out


def lector_parrafos(pg):
    return pg.eval_on_selector_all("#lector .a-body p:not(.nota):not(.sub)", "els=>els.map(e=>e.textContent.trim())")


def consulta(pg, q):
    pg.fill("#q", q)
    pg.wait_for_function("document.querySelector('#lista .item, #lista .vacio')", timeout=5000)
    time.sleep(0.45)


with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
    pg = ctx.new_page()
    errores, externas = [], []
    pg.on("pageerror", lambda e: errores.append(str(e)))
    pg.on("console", lambda m: errores.append("console:" + m.text) if m.type == "error" else None)
    pg.on("request", lambda r: externas.append(r.url) if not r.url.startswith(("file:", "data:", "blob:")) else None)
    t0 = time.time()
    pg.goto(URL)
    pg.wait_for_selector("#q", timeout=15000)
    pg.wait_for_function("!document.querySelector('#carga')", timeout=15000)
    print(f"carga: {time.time()-t0:.2f}s")
    check("carga sin errores JS", not errores, str(errores[:3]))
    check("sin peticiones a internet", not externas, str(externas[:3]))
    # ---------- menú lateral nuevo: solo pantallas fijas y favoritos; las normas viven en el Índice de normas (#n) ----------
    def vaya(h):
        pg.evaluate("h=>{location.hash=h}", h); time.sleep(0.35)
    check("menú: ya no lista las normas (no crece con cada norma nueva)", pg.locator("#nav-normas").count() == 0 and pg.locator("#nav-fav .navlink[data-n]").count() == 0)
    check("menú: cuatro pantallas fijas (Buscar, Índice de normas, Índice de conceptos, Fórmulas de sala) con su tecla", all(pg.locator(s).count() == 1 for s in ("#nav-buscar", "#nav-normas-i", "#nav-indice", "#nav-formulas")) and pg.locator(".snav .kb").count() == 4)
    check("menú: sin contadores (ni en el Índice de normas ni en los favoritos)", pg.locator("#nav-fav .ct, #nav-fav small, .snav .ct").count() == 0)
    print("\n[índice de normas (#n)]")
    vaya("#n")
    check("índice de normas: una fila por norma, tantas como en build.py", pg.locator("#n-lista .nrow").count() == len(build.NORMAS), str(pg.locator("#n-lista .nrow").count()))
    check("índice de normas: LOPDGDD y LOFCE ya no están", pg.locator("#n-lista .nrow[data-n=lopdgdd], #n-lista .nrow[data-n=lofce]").count() == 0)
    check("índice de normas: están LOE, TRLGDCU y el decreto valenciano", all(pg.locator(f"#n-lista .nrow[data-n={x}]").count() == 1 for x in ("loe", "trlgdcu", "d11-1995")))
    check("índice de normas: el título completo, sin recortar con «…» ni a una línea", pg.evaluate("[...document.querySelectorAll('#n-lista .nt')].every(e=>!e.textContent.includes('…')&&e.scrollHeight<=e.clientHeight+1)"))
    check("índice de normas: el filtro por palabra del título encuentra la norma («arrendamientos» -> LAU)", (lambda: (pg.fill("#nq", "arrendamientos"), time.sleep(0.3), pg.locator("#n-lista .nrow").count() == 1 and pg.locator("#n-lista .nrow[data-n=lau]").count() == 1)[-1])())
    pg.fill("#nq", "29/1994"); time.sleep(0.3)
    check("índice de normas: el filtro encuentra por número de ley («29/1994» -> LAU)", pg.locator("#n-lista .nrow[data-n=lau]").count() == 1)
    pg.fill("#nq", "zzzz"); time.sleep(0.3)
    check("índice de normas: un filtro sin resultados lo dice", "Ninguna norma coincide" in pg.inner_text("#n-lista"))
    pg.fill("#nq", ""); time.sleep(0.2)
    # el número que se muestra es el de ARTÍCULOS reales (con bis/ter), sin disposiciones adicionales/transitorias/derogatorias/finales
    esperado = {"lec": 827 + 40, "lopj": 642 + 71, "cc": 1976 + 22, "ce": 169, "lau": 51 + 2, "lph": 24, "loe": 20}
    def cuenta_cab(n):
        pg.evaluate("h=>{location.hash=h}", f"#t/{n}"); time.sleep(0.3)
        m_ = re.match(r"(\d+) artículos", pg.inner_text("#lector .a-meta"))
        return int(m_.group(1)) if m_ else None
    got = {n: cuenta_cab(n) for n in esperado}
    check("cabecera de cada norma: nº de artículos reales (sin disposiciones)", got == esperado, str(got))
    vaya("#n/lec")
    ficha_ = pg.inner_text("#lector .nd-meta")
    check("ficha de la norma: «867 artículos» y «más 49 disposiciones» por separado", "867 artículos" in ficha_ and "49 disposiciones" in ficha_ and "y disposiciones" not in ficha_, ficha_)
    vaya("")
    print("\n[favoritos: normas y artículos fijados a mano; en el menú, cada artículo en UNA línea]")
    def filas_n():
        return pg.eval_on_selector_all("#nav-fav .fchip", "els=>els.map(e=>e.textContent.trim())")

    def filas_a():
        return pg.eval_on_selector_all("#nav-fav .frow .fa", "els=>els.map(e=>e.innerText.replace(/\\s+/g,' ').trim())")
    check("favoritos: al estrenar está vacío (nada impuesto) y explica cómo fijar", filas_n() == [] and filas_a() == [] and "Aquí salen" in pg.inner_text("#nav-fav"), pg.inner_text("#nav-fav")[:80])
    for k in ("1", "2", "3", "4"):
        vaya(f"#a/lopj/{k}")
    check("favoritos: consultar mucho una norma NO la sube ni la fija (sin orden por uso)", filas_n() == [] and filas_a() == [])
    vaya("#n")
    check("índice de normas: cada norma tiene su estrella, sin pulsar", pg.locator("#n-lista .fs").count() == len(build.NORMAS) and pg.locator("#n-lista .fs.on").count() == 0)
    pg.click("#n-lista .fs[data-n=lau]"); time.sleep(0.25)
    check("favoritos: la estrella de LAU la fija en el menú (y no abre la norma)", filas_n() == ["LAU"] and pg.get_attribute("#n-lista .fs[data-n=lau]", "aria-pressed") == "true" and not pg.evaluate("location.hash").startswith("#t/"), str(filas_n()) + pg.evaluate("location.hash"))
    pg.click("#n-lista .fs[data-n=cc]"); time.sleep(0.25)
    pg.click("#n-lista .fs[data-n=lec]"); time.sleep(0.25)
    check("favoritos: las normas quedan en el orden en que las fijas (LAU, CC, LEC)", filas_n() == ["LAU", "CC", "LEC"], str(filas_n()))
    check("índice de normas: las favoritas salen primero, bajo «Favoritas»", pg.evaluate("[...document.querySelectorAll('#n-lista .nrow')].slice(0,3).map(e=>e.dataset.n)") == ["lau", "cc", "lec"] and "Favoritas" in pg.text_content("#n-lista"))
    vaya("#a/lec/282")
    check("favoritos: el botón ★ del artículo arranca sin pulsar", pg.get_attribute("#b-fav", "aria-pressed") == "false")
    pg.click("#b-fav"); time.sleep(0.25)
    check("favoritos: fijar un artículo NO añade ni quita normas del menú", filas_n() == ["LAU", "CC", "LEC"] and filas_a() == ["LEC Art. 282"], str(filas_n()) + str(filas_a()))
    alto_ = pg.evaluate("document.querySelector('#nav-fav .frow').offsetHeight")
    tit_ = pg.inner_text("#lector .a-h small")
    check("favoritos: el artículo ocupa UNA línea (sin título ni descripción) y el título queda en el tooltip", alto_ <= 34 and tit_ and tit_ not in pg.inner_text("#nav-fav") and tit_ in pg.get_attribute("#nav-fav .frow .fa", "title"), f"alto={alto_} {tit_[:40]}")
    vaya("#a/lec/414"); pg.click("#b-fav"); time.sleep(0.2)
    vaya("#a/lec/10"); pg.click("#b-fav"); time.sleep(0.2)
    check("favoritos: los artículos salen en el orden en que los fijas (no por número ni por norma)", filas_a() == ["LEC Art. 282", "LEC Art. 414", "LEC Art. 10"], str(filas_a()))
    vaya("#a/lec/282")
    check("favoritos: el artículo abierto queda marcado en el menú", pg.evaluate("document.querySelector('#nav-fav .frow.sel .fa').dataset.k") == "282")
    pg.evaluate("document.activeElement&&document.activeElement.blur()"); pg.keyboard.press("f"); time.sleep(0.2)
    check("favoritos: la tecla F quita el artículo abierto", filas_a() == ["LEC Art. 414", "LEC Art. 10"] and pg.get_attribute("#b-fav", "aria-pressed") == "false", str(filas_a()))
    pg.keyboard.press("f"); time.sleep(0.2)
    check("favoritos: la tecla F lo vuelve a fijar (al final, como los demás)", filas_a() == ["LEC Art. 414", "LEC Art. 10", "LEC Art. 282"], str(filas_a()))
    vaya("#a/lph/18"); pg.click("#b-fav"); time.sleep(0.2)
    check("favoritos: fijar un artículo de una norma no fijada NO la mete en las normas favoritas", filas_n() == ["LAU", "CC", "LEC"] and "LPH Art. 18" in filas_a(), str(filas_n()) + str(filas_a()))
    pg.reload(); pg.wait_for_function("!document.querySelector('#carga')", timeout=15000)
    check("favoritos: persisten tras recargar (normas, artículos y orden)", filas_n() == ["LAU", "CC", "LEC"] and filas_a()[:3] == ["LEC Art. 414", "LEC Art. 10", "LEC Art. 282"], str(filas_n()) + str(filas_a()))
    pg.click("#nav-fav .fchip[data-n=lec]"); time.sleep(0.4)
    check("favoritos: pulsar una norma del menú abre su índice de artículos", pg.evaluate("location.hash") == "#t/lec" and pg.locator("#lista .item").count() > 800, pg.evaluate("location.hash"))
    pg.click("#nav-fav .fa[data-k='414']"); time.sleep(0.4)
    check("favoritos: pinchar un artículo del menú abre su texto", pg.evaluate("location.hash") == "#a/lec/414" and "Artículo 414" in pg.inner_text("#lector .a-h"), pg.evaluate("location.hash"))
    pg.click("#nav-fav .frow[data-k='414'] .fs"); time.sleep(0.25)
    check("favoritos: la estrella de la fila del menú lo quita sin navegar", "LEC Art. 414" not in filas_a() and pg.evaluate("location.hash") == "#a/lec/414", str(filas_a()))
    vaya("")
    pg.evaluate("document.activeElement&&document.activeElement.blur()"); pg.keyboard.press("m"); time.sleep(0.15)
    check("teclado: M entra en el menú (primera favorita enfocada)", pg.evaluate("document.activeElement.classList.contains('fchip')") and pg.evaluate("document.activeElement.dataset.n") == "lau", pg.evaluate("document.activeElement.className"))
    pg.keyboard.press("Delete"); time.sleep(0.2)
    check("teclado: Supr quita del menú la favorita enfocada", filas_n() == ["CC", "LEC"], str(filas_n()))
    pg.keyboard.press("Escape"); pg.evaluate("document.activeElement&&document.activeElement.blur()")
    pg.keyboard.press("n"); time.sleep(0.4)
    check("teclado: N abre el Índice de normas con el filtro enfocado", pg.evaluate("location.hash").startswith("#n") and pg.evaluate("document.activeElement.id") == "nq", pg.evaluate("location.hash"))
    pg.keyboard.type("lopj"); time.sleep(0.3)
    check("teclado: el filtro selecciona la primera coincidencia y Enter abre sus artículos", pg.evaluate("location.hash") == "#n/lopj", pg.evaluate("location.hash"))
    pg.keyboard.press("Enter"); time.sleep(0.4)
    check("teclado: Enter abre el índice de artículos de la norma", pg.evaluate("location.hash") == "#t/lopj", pg.evaluate("location.hash"))
    pg.evaluate("document.activeElement&&document.activeElement.blur()")
    pg.keyboard.press("c"); time.sleep(0.3); h_c = pg.evaluate("location.hash")
    pg.evaluate("document.activeElement&&document.activeElement.blur()")
    pg.keyboard.press("s"); time.sleep(0.3); h_s = pg.evaluate("location.hash")
    check("teclado: C abre el Índice de conceptos y S las Fórmulas de sala", h_c == "#i" and h_s == "#f", f"{h_c} {h_s}")
    pg.once("dialog", lambda d: d.accept()); vaya(""); pg.click("#b-reset-fav"); time.sleep(0.3)
    check("favoritos: «Restablecer» los vacía todos (normas y artículos)", filas_n() == [] and filas_a() == [], str(filas_n()) + str(filas_a()))
    print()
    consulta(pg, "lec")
    cab_ = pg.inner_text("#lector .a-meta") if pg.locator("#lector .a-meta").count() else ""
    check("cabecera LEC: «867 artículos · 49 disposiciones»", "867 artículos · 49 disposiciones" in cab_ and "y disposiciones" not in cab_, cab_)

    print("\n[consulta directa]")
    consulta(pg, "282 LEC")
    h = pg.inner_text("#lector .a-h")
    check("282 LEC: cabecera", h.startswith("Artículo 282") and "Iniciativa de la actividad probatoria" in h, h)
    esperado = fuente_articulo("BOE-A-2000-323", r"Art[ií]culo 282\.")
    check("282 LEC: texto idéntico al BOE", lector_parrafos(pg) == esperado, f"{lector_parrafos(pg)[:1]} vs {esperado[:1]}")
    if CAPTURAS: pg.screenshot(path=str(CAPT / "01-282-lec.png"))

    consulta(pg, "art. 18.3 de la LPH")
    check("18.3 LPH: abre art. 18", "Artículo 18" in pg.inner_text("#lector .a-h"))
    check("18.3 LPH: resalta apartado 3", pg.locator("#lector p.ap.foco").count() == 1 and pg.get_attribute("#lector p.ap.foco", "data-ap") == "3")
    esperado = fuente_articulo("BOE-A-1960-10906", r"Art[ií]culo dieciocho\.")
    check("18 LPH: texto idéntico al BOE", lector_parrafos(pg) == esperado)

    consulta(pg, "1902 cc")
    esperado = fuente_articulo("BOE-A-1889-4763", r"Art[ií]culo 1902\.")
    check("1902 CC: texto idéntico", lector_parrafos(pg) == esperado and "daño" in " ".join(esperado))

    consulta(pg, "5 lo 1/2025")
    check("5 LO 1/2025: requisito de procedibilidad", "Requisito de procedibilidad" in pg.inner_text("#lector .a-h"))
    esperado = fuente_articulo("BOE-A-2025-76", r"Art[ií]culo 5\. Requisito")
    check("5 LO 1/2025: texto idéntico", lector_parrafos(pg) == esperado)

    consulta(pg, "9 lau")
    check("9 LAU: plazo mínimo", "Plazo mínimo" in pg.inner_text("#lector .a-h"))
    consulta(pg, "da 1 lec")
    check("da 1 lec: disposición adicional primera", "Disposición adicional primera" in pg.inner_text("#lector .a-h"), pg.inner_text("#lector .a-h"))
    consulta(pg, "c.c. 1")
    check("c.c. 1: formato con puntos", "Artículo 1" in pg.inner_text("#lector .a-h") and "CC" in pg.inner_text("#lector .a-eye"))
    consulta(pg, "Ley de Enjuiciamiento Civil artículo 283 bis a")
    check("283 bis a LEC (sufijo con letra)", "283 bis a" in pg.inner_text("#lector .a-h"), pg.inner_text("#lector .a-h"))
    # un número que NO tiene cabecera propia pero cae dentro de un rango de derogados
    for q_, rng_ in [("285 lopj", "279 a 291"), ("411 lopj", "411 a 413")]:
        consulta(pg, q_)
        check(f"{q_}: cae en el rango «{rng_}»", rng_ in pg.inner_text("#lector .a-h"), pg.inner_text("#lector .a-h"))
    consulta(pg, "1231-1235 cc")
    check("1231-1235 CC: rango + artículos propios sin duplicar", pg.locator("#lector article").count() == 6, str(pg.locator("#lector article").count()))
    consulta(pg, "9999 lec")
    check("9999 LEC: avisa de que no existe", "llega al 827" in pg.inner_text("#lista"), pg.inner_text("#lista")[:200])

    def probar_(nid, k, txt):
        return pg.evaluate("([n,k,t])=>window.__NT.probar(n,k,t)", [nid, k, txt])

    print("\n[normas nuevas: LOE, TRLGDCU]")
    consulta(pg, "17 loe")
    check("17 LOE: cabecera", "Artículo 17" in pg.inner_text("#lector .a-h") and "LOE" in pg.inner_text("#lector .a-eye"), pg.inner_text("#lector .a-h"))
    check("17 LOE: texto idéntico al BOE", lector_parrafos(pg) == fuente_articulo("BOE-A-1999-21567", r"Art[ií]culo 17\.") and len(lector_parrafos(pg)) > 3)
    consulta(pg, "3 trlgdcu")
    check("3 TRLGDCU: texto idéntico", lector_parrafos(pg) == fuente_articulo("BOE-A-2007-20555", r"Art[ií]culo 3\.") and "TRLGDCU" in pg.inner_text("#lector .a-eye"))
    consulta(pg, "ley de consumidores y usuarios 59 bis")
    check("alias «ley de consumidores y usuarios» + 59 bis", "59 bis" in pg.inner_text("#lector .a-h"), pg.inner_text("#lector .a-h"))
    consulta(pg, "df 1 trlgdcu")
    h_ = pg.inner_text("#lector .a-h")
    check("DF 1 TRLGDCU es la del texto refundido, no la del RDL", "Disposición final primera" in h_ and "RDL" not in h_, h_)
    consulta(pg, "recepción de la obra")
    ids_ = pg.eval_on_selector_all("#lista .item", "els=>els.map(e=>e.querySelector('.sg-chip').textContent+' '+e.querySelector('.ar').textContent)")
    print("   «recepción de la obra»:", ids_[:6])
    check("«recepción de la obra» encuentra la LOE", any(x.startswith("LOE") for x in ids_[:12]), str(ids_[:8]))
    consulta(pg, "garantía conformidad consumidores")
    check("concepto de consumo: hay resultados en TRLGDCU", pg.locator("#lista .item .sg-chip:text('TRLGDCU')").count() > 0)

    print("\n[Decreto 11/1995, de servicios a domicilio (DOGV, importado a mano)]")
    check("D 11/1995 está en el Índice de normas", (pg.evaluate("h=>{location.hash=h}", "#n"), time.sleep(0.3), pg.fill("#nq", ""), time.sleep(0.2), pg.locator("#n-lista .nrow[data-n=d11-1995]").count() == 1)[-1])
    consulta(pg, "2 decreto 11/1995")
    h_ = pg.inner_text("#lector .a-h")
    esp_ = decreto_parrafos(r"^Artículo segundo\.", r"^Artículo tercero\.")
    check("2 D 11/1995: cabecera «Artículo 2 · Presupuestos»", "Artículo 2" in h_ and "Presupuestos" in h_, h_)
    check("2 D 11/1995: texto idéntico a la copia de la carpeta DOGV (con Ñ→ñ)", lector_parrafos(pg) == esp_ and len(esp_) > 15, f"{len(lector_parrafos(pg))} vs {len(esp_)}")
    check("2 D 11/1995: «señal» y «tamaño» sin la Ñ defectuosa", "señal" in pg.inner_text("#lector") and "tamaño" in pg.inner_text("#lector") and not re.search(r"[a-záéíóú]Ñ|Ñ[a-záéíóú]", pg.inner_text("#lector .a-body")), "")
    consulta(pg, "2.7 d 11/1995")
    check("2.7 D 11/1995: resalta el apartado 7", pg.locator("#lector p.ap.foco").count() == 1 and pg.get_attribute("#lector p.ap.foco", "data-ap") == "7")
    consulta(pg, "df 2 decreto 11/1995")
    check("DF 2 D 11/1995: disposición final segunda", "Disposición final segunda" in pg.inner_text("#lector .a-h"), pg.inner_text("#lector .a-h"))
    consulta(pg, "3 d 11/1995")
    hrefs_ = pg.eval_on_selector_all("#lector a.ref", "els=>els.map(a=>a.getAttribute('href'))")
    check("art. 3: «artículo 2.7» enlaza al apartado 7 del artículo 2 del propio decreto", "#a/d11-1995/2/7" in hrefs_, str(hrefs_))
    check("art. 3: no se enlaza «artículos 32 y 35 de la Ley 2/1987» (es otra norma)", not any(h.startswith(("#a/d11-1995/32", "#a/d11-1995/35")) for h in hrefs_))
    consulta(pg, "6 d 11/1995")
    check("art. 6: «artículos 32 y 35 de la Ley de la Generalitat Valenciana 2/1987» no se enlaza", pg.locator("#lector a.ref").count() == 0, str(pg.locator("#lector a.ref").count()))
    consulta(pg, "presupuesto previo por escrito")
    ids3_ = pg.eval_on_selector_all("#lista .item", "els=>els.map(e=>e.querySelector('.sg-chip').textContent+' '+e.querySelector('.ar').textContent)")
    check("«presupuesto previo por escrito» encuentra D 11/1995 art. 2 entre los 5 primeros", "D 11/1995 Art. 2" in ids3_[:5], str(ids3_[:5]))
    check("«artículo 2 del Decreto 11/1995, de 10 de enero» -> D 11/1995 art. 2", "#a/d11-1995/2" in probar_("lec", "1", "según el artículo 2 del Decreto 11/1995, de 10 de enero, del Gobierno Valenciano"))

    print("\n[familia de un artículo: el normal y todos sus bis/ter/quater]")
    def fam_(q):
        consulta(pg, q)
        return pg.eval_on_selector_all("#lista .item .ar", "els=>els.map(e=>e.textContent.trim())")
    F_ = {q: fam_(q) for q in ("11 lec", "11 bis lec", "11bis lec", "11 ter lec", "545 lec", "545 bis lec", "545bis lec", "283 bis lec", "9 bis lau", "9bis lau", "282 lec")}
    check("familia: «11 LEC» da el 11 y TODOS sus bis/ter/quater, con el 11 primero", F_["11 lec"] == ["Art. 11", "Art. 11 bis", "Art. 11 ter", "Art. 11 quater"], str(F_["11 lec"]))
    check("familia: «11 bis LEC» y «11bis LEC» dan la misma familia, con el 11 bis primero", F_["11 bis lec"] == F_["11bis lec"] and F_["11 bis lec"][0] == "Art. 11 bis" and set(F_["11 bis lec"]) == set(F_["11 lec"]), str(F_["11 bis lec"]))
    check("familia: «11 ter LEC» pone el 11 ter primero y trae también el 11", F_["11 ter lec"][0] == "Art. 11 ter" and "Art. 11" in F_["11 ter lec"], str(F_["11 ter lec"]))
    check("familia: «545», «545 bis» y «545bis» (el 545 bis NO existe en la LEC) dan el 545", F_["545 lec"] == F_["545 bis lec"] == F_["545bis lec"] == ["Art. 545"], str((F_["545 lec"], F_["545 bis lec"], F_["545bis lec"])))
    consulta(pg, "545 bis lec")
    check("familia: si lo pedido no existe, lo dice («no tiene el artículo 545 bis»)", "no tiene el artículo 545 bis" in pg.inner_text("#lista"), pg.inner_text("#lista")[:160])
    check("familia: «283 bis LEC» (solo existe con letras) enseña el 283 y el 283 bis a) a k)", F_["283 bis lec"][0] == "Art. 283" and sum(1 for x in F_["283 bis lec"] if x.startswith("Art. 283 bis")) == 11, str(F_["283 bis lec"]))
    check("familia: «9 bis LAU» y «9bis LAU» dan el 9 bis primero y también el 9", F_["9 bis lau"] == F_["9bis lau"] == ["Art. 9 bis", "Art. 9"], str((F_["9 bis lau"], F_["9bis lau"])))
    check("familia: un artículo sin variantes sigue dando solo él («282 LEC»)", F_["282 lec"] == ["Art. 282"], str(F_["282 lec"]))
    print("\n[índice de conceptos (contenido del Armero)]")
    _v, _a, muestra = build.indice.carga(pathlib.Path(os.environ.get("CONSULTA_NORMAS_INDICE", AQUI / "indice")))   # muestra + tandas del Armero, tal cual
    AVISO_ = "Índice orientativo. No sustituye la lectura del precepto ni recoge jurisprudencia. Contrasta con el texto antes de invocarlo."
    def slug_(s): return build.indice.slug(s)
    check("índice: entrada «Índice de conceptos» en el menú", pg.locator("#nav-indice").is_visible())
    cads_ = pg.evaluate("()=>window.__NT.idx().voces.filter(v=>v.es==='caducada').map(v=>v.v)")
    check("índice REAL: ninguna voz sale caducada sin que haya cambiado nada (una norma importada a mano sin línea base la caducaría por prudencia)", cads_ == [], str(cads_))
    pg.evaluate("h=>{location.hash=h}", ""); time.sleep(0.3)
    pg.click("#nav-indice"); time.sleep(0.4)
    check("índice: lista todas las voces (muestra + tanda 1 del Armero)", pg.locator("#lista .idx-row").count() == len(muestra) >= 16 and pg.evaluate("location.hash") == "#i", str(pg.locator("#lista .idx-row").count()))
    check("índice: el aviso del Armero está siempre visible, con su texto exacto", AVISO_ in pg.inner_text("#lector .idx-aviso"), pg.inner_text("#lector .idx-aviso"))
    pg.click("#lista .idx-row >> text=Declinatoria"); time.sleep(0.4)
    check("índice: abre la voz «Declinatoria» (ruta #i/declinatoria)", pg.evaluate("location.hash") == "#i/declinatoria" and pg.inner_text("#lector .a-h") == "Declinatoria")
    meta_ = pg.inner_text("#lector .a-meta")
    estado_decl = pg.evaluate("window.__NT.idx().voces.filter(v=>v.s==='declinatoria')[0].es")
    check("índice: muestra fecha de revisión, revisor y, si es provisional, «vigencia no contrastada con el BOE»", "Revisada el 07-10-2026" in meta_ and "armero" in meta_ and (("Provisional: vigencia no contrastada con el BOE" in meta_) == (estado_decl == "provisional")), meta_ + " / " + estado_decl)
    check("índice: las dos secciones, con la etiqueta «Conexión doctrinal, no textual»", "regula" in pg.inner_text("#lector").lower() and "conexión doctrinal, no textual" in pg.inner_text("#lector").lower())
    for v_ in muestra:
        pg.evaluate("h=>{location.hash=h}", "#i/" + slug_(v_["voz"])); time.sleep(0.3)
        esp_r = [r for r in v_["remisiones"] if r["tipo"] == "regula"]; esp_c = [r for r in v_["remisiones"] if r["tipo"] == "conexa"]
        got_r = pg.locator("#lector ul.idx-lista:not(.idx-conexa) li").count(); got_c = pg.locator("#lector ul.idx-conexa li").count()
        check(f"índice: «{v_['voz']}»: {len(esp_r)} regula + {len(esp_c)} conexa, como en el YAML", (got_r, got_c) == (len(esp_r), len(esp_c)), f"{got_r},{got_c}")
    pg.evaluate("h=>{location.hash=h}", "#i/desahucio-por-precario"); time.sleep(0.3)
    nc_ = pg.inner_text("#lector .idx-nc")
    check("índice: «No consta en norma» siempre visible y con sus 3 entradas (no plegado)", "No consta en norma" in nc_ and pg.locator("#lector .idx-nc li").count() == 3 and pg.locator("#lector details").count() == 0, nc_[:80])
    pg.evaluate("h=>{location.hash=h}", "#i/requisito-de-procedibilidad-masc"); time.sleep(0.3)
    # las afines que existen como voz son enlace; las que aún no existen, texto (se calcula con las voces reales: crecen con cada tanda)
    import unicodedata as _ud
    _nq = lambda s: re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", "".join(ch for ch in _ud.normalize("NFD", s.lower()) if not _ud.combining(ch)))).strip()
    _v, _a, _vs = build.indice.carga(pathlib.Path(os.environ.get("CONSULTA_NORMAS_INDICE", AQUI / "indice")))
    _nombres = {_nq(x["voz"]) for x in _vs}
    _af = next(x for x in _vs if build.indice.slug(x["voz"]) == "requisito-de-procedibilidad-masc").get("afines") or []
    _con = [a for a in _af if _nq(a) in _nombres]; _sin = [a for a in _af if _nq(a) not in _nombres]
    _links = pg.eval_on_selector_all("#lector a[href^='#i/']", "els=>els.map(a=>a.textContent)")
    check("índice: las voces afines que existen son enlace; las que no, texto", bool(_af) and sorted(_links) == sorted(_con) and all(a in pg.inner_text("#lector") for a in _sin), f"enlaces={_links} esperados={_con} sin voz={_sin}")
    # cada remisión abre EXACTAMENTE su artículo, y su apartado se localiza
    malas, tolerados = [], []
    ids_norma = {n["sigla"]: n["id"] for n in build.NORMAS}
    for v_ in muestra:
        pg.evaluate("h=>{location.hash=h}", "#i/" + slug_(v_["voz"])); time.sleep(0.2)
        hrefs = pg.eval_on_selector_all("#lector ul.idx-lista a.ref", "els=>els.map(a=>a.getAttribute('href'))")
        for r in v_["remisiones"]:
            k_ = build.indice.clave_articulo(r["articulo"]); nid = ids_norma[r["norma"]]
            ap_ = build.indice.apartado_numerico(r.get("apartado"))
            esperado = f"#a/{nid}/{__import__('urllib.parse').parse.quote(k_, safe='')}" + (f"/{ap_}" if ap_ else "")
            if esperado not in hrefs:
                malas.append(("sin enlace", v_["voz"], r["norma"], r["articulo"], esperado)); continue
            pg.evaluate("()=>document.querySelectorAll('.toast').forEach(e=>e.remove())")   # el aviso dura 2,6 s: no atribuir el de la remisión anterior
            pg.evaluate("h=>{location.hash=h}", esperado); time.sleep(0.12)
            cab = pg.inner_text("#lector .a-h")
            ok_cab = (cab.startswith("Artículo " + k_) if re.match(r"^\d", k_) else cab.startswith("Disposición"))
            toast_ = pg.evaluate("(document.querySelector('.toast')||{}).textContent||''")
            if ok_cab and "No localizo el apartado" in toast_ and pg.evaluate("([n,k])=>window.__NT.avisoBoe(n,k,'2026-10-08')", [nid, k_]):
                tolerados.append((v_["voz"], r["norma"], r["articulo"]))   # cita un apartado del texto NUEVO (reforma ya en vigor que el espejo no trae)
                continue
            if not ok_cab or "No localizo" in toast_:
                malas.append(("abre mal", v_["voz"], r["norma"], r["articulo"], cab[:40], toast_))
    total_rem = sum(len(v_["remisiones"]) for v_ in muestra)
    if tolerados:
        print(f"  (aviso: {len(tolerados)} remisiones citan un apartado del texto nuevo de artículos con reforma publicada; el espejo aún no lo trae: {sorted({x[1] + ' ' + x[2] for x in tolerados})[:12]})")
    check(f"índice: las {total_rem} remisiones de las {len(muestra)} voces abren su artículo (y su apartado se localiza, salvo reformas ya publicadas)", not malas, "; ".join(f"{m[1]} -> {m[2]} {m[3]}: {m[-1] if m[0]=='abre mal' else 'sin enlace'}" for m in malas[:12]))
    pg.evaluate("h=>{location.hash=h}", "#i/declinatoria"); time.sleep(0.3)
    pg.click("#lector ul.idx-lista a.ref >> nth=2"); time.sleep(0.4)
    h_art = pg.evaluate("location.hash"); pg.go_back(); time.sleep(0.5)
    check("índice: desde el artículo, «atrás» vuelve a la voz", h_art.startswith("#a/lec/65") and pg.evaluate("location.hash") == "#i/declinatoria", h_art + " -> " + pg.evaluate("location.hash"))
    pg.evaluate("h=>{location.hash=h}", "#i"); time.sleep(0.3)
    pg.fill("#iq", "masc"); time.sleep(0.2)
    check("índice: el filtro encuentra por sinónimo («masc»)", pg.locator("#idx-voces .idx-row").count() >= 1 and "Requisito de procedibilidad" in pg.inner_text("#idx-voces"), pg.inner_text("#idx-voces")[:120])
    pg.fill("#iq", "ocupacion sin titulo"); time.sleep(0.2)
    check("índice: el filtro ignora tildes y encuentra «ocupación sin título» (sinónimo)", pg.locator("#idx-voces .idx-row").count() == 1 and "precario" in pg.inner_text("#idx-voces").lower())
    pg.fill("#iq", "zzzz"); time.sleep(0.2)
    check("índice: filtro sin coincidencias lo dice", "Ninguna voz coincide" in pg.inner_text("#idx-voces"))
    n_items = {}
    for q_, esperada in (("declinatoria de jurisdicción", "declinatoria"), ("precario", "desahucio-por-precario"), ("ocupación sin título", "desahucio-por-precario"), ("legitimación", "falta-de-legitimacion"), ("MASC", "requisito-de-procedibilidad-masc")):
        consulta(pg, q_)
        hits_ = pg.eval_on_selector_all("#lista .idx-hit a", "els=>els.map(a=>a.getAttribute('href'))")
        n_items[q_] = pg.locator("#lista .item").count()
        check(f"búsqueda «{q_}»: ofrece la voz del índice sobre los resultados", f"#i/{esperada}" in hits_, str(hits_))
    check("búsqueda: la voz del índice no desplaza ni cuenta como resultado (sigue habiendo los 8 de «declinatoria de jurisdicción»)", n_items["declinatoria de jurisdicción"] == 8, str(n_items))
    consulta(pg, "282 lec")
    check("búsqueda de un artículo concreto: no sale el cuadro del índice", pg.locator("#lista .idx-hit").count() == 0)
    # voz caducada (se simula sobre los datos cargados; el contenido del Armero no se toca)
    pg.evaluate("()=>{var v=window.__NT.idx().voces.filter(x=>x.s==='declinatoria')[0];v.es='caducada';v.cad=[{n:'LEC',k:'63',r:'cambia'},{n:'LEC',k:'66',r:'falta'},{n:'LEC',k:'64 bis',r:'nuevo'},{n:'LEC',k:'416',r:'cambia',v:'vigilar'}];window.__NT.vistaIndice(v.s)}"); time.sleep(0.3)
    cad_ = pg.inner_text("#lector .idx-cad")
    check("índice: voz caducada -> aviso en rojo que nombra CADA artículo y el motivo, y manda leer el texto vigente",
          "Caducada" in cad_ and "ha cambiado el texto de LEC Art. 63" in cad_ and "ya no se encuentra LEC Art. 66" in cad_ and "ha aparecido LEC" in cad_ and "(artículo vigilado)" in cad_ and "Lee el texto vigente" in cad_, cad_)
    check("índice: voz caducada -> etiqueta «caducada» en su fila de la lista", pg.locator("#lista .idx-row", has_text="Declinatoria").locator(".ie-cad").count() == 1)
    pg.evaluate("()=>{var v=window.__NT.idx().voces.filter(x=>x.s==='declinatoria')[0];v.cad=[{n:'D 11/1995',r:'estado',antes:'in_force',ahora:'repealed'}];window.__NT.vistaIndice(v.s)}"); time.sleep(0.3)
    cad_e_ = pg.inner_text("#lector .idx-cad")
    check("índice: voz caducada por cambio del estado oficial de una norma -> lo dice, de qué a qué y manda leer el texto vigente", "ha cambiado el estado oficial de D 11/1995 (antes «in_force», ahora «repealed»)" in cad_e_ and "Lee el texto vigente" in cad_e_, cad_e_)
    pg.evaluate("()=>{var v=window.__NT.idx().voces.filter(x=>x.s==='declinatoria')[0];v.cad=[{n:'LEC',r:'?'}];window.__NT.vistaIndice(v.s)}"); time.sleep(0.3)
    check("índice: espejo no comprobable -> lo dice (no inventa una norma)", "no se ha podido comprobar" in pg.inner_text("#lector .idx-cad"), pg.inner_text("#lector .idx-cad"))
    pg.evaluate("()=>{var v=window.__NT.idx().voces.filter(x=>x.s==='declinatoria')[0];v.es='provisional';v.cad=[];window.__NT.vistaIndice(v.s)}"); time.sleep(0.2)
    # campo nuevo del Armero: «fuera de la herramienta» (bloque propio, nunca plegado)
    pg.evaluate("h=>{location.hash=h}", "#i/falta-de-jurisdiccion-competencia-internacional"); time.sleep(0.4)
    fh_ = pg.inner_text("#lector .idx-nc") if pg.locator("#lector .idx-nc").count() else ""
    check("índice: «Rige también, fuera de la herramienta» (Reglamento UE 1215/2012) se pinta como bloque propio, sin plegar", "Rige también, fuera de la herramienta" in fh_ and "1215/2012" in fh_ and pg.locator("#lector details").count() == 0, fh_[:120])
    pg.evaluate("h=>{location.hash=h}", "#i/postulacion-abogado-y-procurador"); time.sleep(0.4)
    check("índice: las voces de la tanda 1 se abren (p. ej. «Postulación (abogado y procurador)»)", pg.inner_text("#lector .a-h").startswith("Postulación") and pg.locator("#lector ul.idx-lista li").count() >= 5, pg.inner_text("#lector .a-h"))
    pg.evaluate("h=>{location.hash=h}", ""); time.sleep(0.3)
    check("portada: ofrece abrir el índice y el texto de favoritos es el vigente", pg.locator("#lista a[href='#i']").count() == 1 and "suben solas" not in pg.inner_text("#lector"), pg.inner_text("#lector")[-300:])

    print("\n[sin norma / rango / lista]")
    consulta(pg, "21")
    n = pg.locator("#lista .item").count()
    esperadas = 0
    for cfg_ in build.NORMAS:
        _, _, l_ = build.lee_norma(cfg_); ch_, _ = build.parse_norma(cfg_, l_)
        esperadas += sum(1 for c_ in ch_ if c_["k"] == "21" or re.match(r"^21 (bis|ter|quater|quinquies|sexies|septies|octies)", c_["k"]))   # el 21 y su familia (21 bis…)
    check(f"21 sin norma: sale en las {esperadas} normas que lo tienen", n == esperadas, f"{n} vs {esperadas}")
    consulta(pg, "63-65 lec")
    arts = pg.locator("#lector article").count()
    check("63-65 LEC: tres artículos seguidos", arts == 3, f"{arts}")
    consulta(pg, "63, 65 lec")
    check("63, 65 LEC: lista de dos", pg.locator("#lector article").count() == 2)

    print("\n[concepto]")
    t = time.time()
    consulta(pg, "declinatoria de jurisdicción")
    ms = time.time() - t
    items = pg.eval_on_selector_all("#lista .item", "els=>els.map(e=>e.querySelector('.sg-chip').textContent+' '+e.querySelector('.ar').textContent)")
    print("   primeros:", items[:8])
    check("declinatoria: hay resultados", len(items) > 3, str(len(items)))
    check("declinatoria: LEC art. 63 entre los 5 primeros", any(x == "LEC Art. 63" for x in items[:5]), str(items[:5]))
    check("declinatoria: resalta el término", pg.locator("#lector mark").count() > 0)
    if CAPTURAS: pg.screenshot(path=str(CAPT / "02-declinatoria.png"))
    consulta(pg, "declinatoria jurisdiccion lec")
    check("filtro de norma por sufijo (lec)", pg.locator("#lista .item .sg-chip:not(:text('LEC'))").count() == 0)
    # clic en chip LAU
    consulta(pg, "arrendamiento")
    chips = pg.eval_on_selector_all("#chips .chip", "els=>els.map(e=>e.textContent.trim())")
    print("   chips:", chips)
    check("chips por norma", len(chips) >= 3)
    pg.click("#chips .chip:has-text('LAU')")
    time.sleep(0.3)
    check("clic en chip LAU filtra", pg.locator("#lista .item .sg-chip:not(:text('LAU'))").count() == 0 and pg.locator("#lista .item").count() > 0)
    consulta(pg, "zzzqqq")
    check("sin resultados: mensaje", "Sin resultados" in pg.inner_text("#lista"))

    print("\n[teclado]")
    consulta(pg, "prescripción")
    t1 = pg.inner_text("#lector .a-h")
    pg.press("#q", "ArrowDown")
    time.sleep(0.2)
    t2 = pg.inner_text("#lector .a-h")
    check("↓ cambia el artículo del lector", t1 != t2 or pg.locator("#lista .item.sel").get_attribute("data-ix") == "1", f"{t1} / {t2}")
    pg.press("#q", "Enter")
    time.sleep(0.2)
    check("Enter pasa el foco al lector", pg.evaluate("document.activeElement.id") == "lector")
    h1 = pg.inner_text("#lector .a-h")
    pg.keyboard.press("ArrowRight")
    time.sleep(0.2)
    check("→ siguiente artículo", pg.inner_text("#lector .a-h") != h1)
    pg.keyboard.press("ArrowLeft")
    time.sleep(0.2)
    check("← artículo anterior", pg.inner_text("#lector .a-h") == h1)
    pg.keyboard.press("/")
    check("/ vuelve al buscador", pg.evaluate("document.activeElement.id") == "q")
    pg.keyboard.press("Escape"); pg.keyboard.press("Escape")

    print("\n[referencias cruzadas y navegación]")
    # casos concretos: el enlace debe apuntar donde dice el texto y NO enlazar remisiones a otras normas
    def enlaces(q_):
        consulta(pg, q_)
        return pg.eval_on_selector_all("#lector a.ref", "els=>els.map(a=>[a.textContent,a.getAttribute('href')])")
    e = enlaces("25 lau")
    check("LAU 25: «artículo 1.518 del Código Civil» -> CC 1518 (no CC 1)", ["1.518", "#a/cc/1518"] in e, str(e))
    def probar(nid, k, txt):
        return pg.evaluate("([n,k,t])=>window.__NT.probar(n,k,t)", [nid, k, txt])
    check("«artículo 5.1.d) del Reglamento (UE)» NO se enlaza (LEC 1 como contexto)", "<a" not in probar("lec", "1", "Al amparo del artículo 5.1.d) del Reglamento (UE) 2016/679, no será imputable."))
    check("«artículo 2.2.c) del Reglamento (UE)» NO se enlaza", "<a" not in probar("lec", "1", "Al amparo del artículo 2.2.c) del Reglamento (UE) 2016/679, se considera excluido."))
    check("«artículo 6 de dicha ley» NO se enlaza", "<a" not in probar("lec", "1", "lo previsto en el artículo 6 de dicha ley."))
    check("«artículo 6 de la misma ley» NO se enlaza", "<a" not in probar("lau", "1", "lo previsto en el artículo 6 de la misma ley."))
    check("«artículo 5 de la Ley Hipotecaria» NO se enlaza", "<a" not in probar("lec", "1", "conforme al artículo 5 de la Ley Hipotecaria."))
    check("«artículo 1.518 del Código Civil» -> CC 1518", "#a/cc/1518" in probar("lau", "25", "conforme al artículo 1.518 del Código Civil, cuando"))
    check("«artículo 443 de esta Ley» -> LEC 443", "#a/lec/443" in probar("lec", "22", "la vista prevenida en el artículo 443 de esta Ley, tras la cual"))
    check("en la LO 1/2025 «artículo 63 de esta Ley» NO se enlaza (cita la ley que modifica)", "<a" not in probar("lo1-2025", "22", "según el artículo 63 de esta Ley."))
    check("en la LO 1/2025 «artículo 63 de la Ley de Enjuiciamiento Civil» -> LEC 63", "#a/lec/63" in probar("lo1-2025", "22", "según el artículo 63 de la Ley de Enjuiciamiento Civil."))
    check("«artículo 17 de la Ley de Ordenación de la Edificación» -> LOE 17", "#a/loe/17" in probar("lec", "1", "conforme al artículo 17 de la Ley de Ordenación de la Edificación."))
    check("«artículo 3 del texto refundido de la Ley General para la Defensa de los Consumidores y Usuarios» -> TRLGDCU 3", "#a/trlgdcu/3" in probar("lec", "1", "con arreglo al artículo 3 del texto refundido de la Ley General para la Defensa de los Consumidores y Usuarios, aprobado"))
    check("«artículo 51.1 y 2 de la Constitución»: enlaza el 51 (apartado 1) y NO el «2» (es apartado)", (lambda r: "#a/ce/51/1" in r and "#a/ce/2" not in r)(probar("trlgdcu", "1", "En desarrollo del artículo 51.1 y 2 de la Constitución que")))
    check("«artículos 9.5 y 49.1.35.ª del Estatut d’Autonomia» (en valenciano) NO se enlaza a la propia ley", "<a" not in probar("lec", "1", "que le atribuyen los artículos 9.5 y 49.1.35.ª del Estatut d’Autonomia de la Comunitat Valenciana."))
    check("«artículo 9.5 del Estatuto de Autonomía» (en castellano) NO se enlaza", "<a" not in probar("lec", "1", "que le atribuye el artículo 9.5 del Estatuto de Autonomía de la Comunitat Valenciana."))
    check("«artículos 63 y 64 de esta Ley» sigue enlazando ambos", (lambda r: "#a/lec/63" in r and "#a/lec/64" in r)(probar("lec", "1", "conforme a los artículos 63 y 64 de esta Ley")))
    consulta(pg, "22 lec")
    check("LEC 22: «artículo 443 de esta Ley» -> LEC 443", any(h == "#a/lec/443" for _, h in pg.eval_on_selector_all("#lector a.ref", "els=>els.map(a=>[a.textContent,a.getAttribute('href')])")))
    consulta(pg, "13 lph")
    check("LPH 13: «17.7.ª» -> LPH 17 apartado 7", any(h == "#a/lph/17/7" for _, h in pg.eval_on_selector_all("#lector a.ref", "els=>els.map(a=>[a.textContent,a.getAttribute('href')])")))
    pg.goto(URL + "#a/lph/17/7"); pg.wait_for_function("document.querySelector('#lector .a-h')"); time.sleep(0.5)
    check("LPH 17 apartado 7ª se resalta", pg.locator("#lector p.ap.foco").count() == 1, str(pg.locator("#lector p.ap.foco").count()))
    pg.fill("#q", "22 lec"); time.sleep(0.5)
    refs = pg.locator("#lector a.ref").count()
    print("   enlaces en LEC 22:", refs)
    if refs:
        href = pg.get_attribute("#lector a.ref >> nth=0", "href")
        pg.click("#lector a.ref >> nth=0")
        time.sleep(0.4)
        check("clic en referencia navega", pg.evaluate("location.hash") == href, f"{pg.evaluate('location.hash')} vs {href}")
        pg.go_back(); time.sleep(0.4)
        check("Atrás vuelve a la consulta", "Artículo 22" in pg.inner_text("#lector .a-h"), pg.inner_text("#lector .a-h"))
    # norma: índice
    pg.evaluate("h=>{location.hash=h}", "#t/lph"); time.sleep(0.3)
    check("índice de la LPH: 32 entradas", pg.locator("#lista .item").count() == 32, str(pg.locator('#lista .item').count()))
    pg.click("#lista .item:has-text('Art. 18')"); time.sleep(0.4)
    check("abrir desde el índice", "Artículo 18" in pg.inner_text("#lector .a-h"))
    # ---------- fórmulas de sala (contenido del Armero) ----------
    print("\n[fórmulas de sala]")
    import os as _os
    _fv, _fa, _fs = build.formulas.carga(pathlib.Path(_os.environ.get("CONSULTA_NORMAS_FORMULAS", AQUI / "formulas")))
    if _fs:
        pg.evaluate("h=>{location.hash=h}", "#f"); time.sleep(0.6)
        check("fórmulas: el menú lateral tiene «Fórmulas de sala» y queda marcado", pg.locator("#nav-formulas.sel").count() == 1)
        check(f"fórmulas: la lista muestra las {len(_fs)} fórmulas", pg.locator("#lista .idx-row").count() == len(_fs), str(pg.locator("#lista .idx-row").count()))
        check("fórmulas: el cuadro (tabla) muestra las mismas, con tres columnas", pg.locator("#lector table.fm-tab tbody tr:not(.fm-g)").count() == len(_fs) and pg.locator("#lector table.fm-tab thead th").count() == 3)
        check("fórmulas: lleva el aviso «orientativas»", "Fórmulas orientativas" in pg.inner_text("#lector .idx-aviso"))
        n_j = sum(1 for f in _fs if "juicio" in f["momento"])
        pg.click("#lista .fm-chip[data-m=juicio]"); time.sleep(0.2)
        check("fórmulas: filtrar por «Juicio» deja solo las de juicio (lista y cuadro)", pg.locator("#lista .idx-row").count() == n_j and pg.locator("#lector table.fm-tab tbody tr:not(.fm-g)").count() == n_j, f"{pg.locator('#lista .idx-row').count()} vs {n_j}")
        pg.click("#lista .fm-chip[data-m='']"); time.sleep(0.2)
        pg.fill("#fq", "zzzzzz"); time.sleep(0.2)
        check("fórmulas: un filtro sin resultados lo dice", "Ninguna fórmula coincide" in pg.inner_text("#lista"))
        pg.fill("#fq", build.indice.slug(_fs[0]["situacion"]).split("-")[0]); time.sleep(0.2)
        check("fórmulas: filtrar por una palabra de la situación encuentra la fórmula", pg.locator("#lista .idx-row").count() >= 1)
        pg.fill("#fq", ""); time.sleep(0.2)
        malas_f = []
        ids_ = {n["sigla"]: n["id"] for n in build.NORMAS}
        import urllib.parse as _up
        for f in _fs:
            sl = build.indice.slug(f["situacion"])
            pg.evaluate("h=>{location.hash=h}", "#f/" + sl); time.sleep(0.12)
            hrefs = pg.eval_on_selector_all("#lector ul.idx-lista a.ref", "els=>els.map(a=>a.getAttribute('href'))")
            esp = []
            for b in f.get("bases") or []:
                ap_ = build.indice.apartado_numerico(b.get("apartado"))
                esp.append(f"#a/{ids_[b['norma']]}/{_up.quote(build.indice.clave_articulo(b['articulo']), safe='')}" + (f"/{ap_}" if ap_ else ""))
            if hrefs != esp or pg.inner_text("#lector .a-h").strip() != f["situacion"].strip():
                malas_f.append((f["situacion"], hrefs[:3], esp[:3]))
        check(f"fórmulas: las {len(_fs)} fichas se abren y enlazan cada base a su artículo", not malas_f, str(malas_f[:3]))
        f0 = next((f for f in _fs if f.get("bases")), _fs[0])
        pg.evaluate("h=>{location.hash=h}", "#f/" + build.indice.slug(f0["situacion"])); time.sleep(0.4)
        pg.click("#lector ul.idx-lista a.ref >> nth=0"); time.sleep(0.4)
        check("fórmulas: pinchar una base abre el texto del artículo", pg.evaluate("location.hash").startswith("#a/") and "Art" in pg.inner_text("#lector .a-h"), pg.evaluate("location.hash"))
        pg.evaluate("h=>{location.hash=h}", "#f/" + build.indice.slug(f0["situacion"])); time.sleep(0.4)
        pg.click("#b-copiar-f"); time.sleep(0.3)
        cp_f = pg.evaluate("navigator.clipboard.readText()")
        check("fórmulas: Copiar deja en el portapapeles la fórmula y entre paréntesis su base", cp_f.startswith(f0["formula"].strip()[:40]) and (not f0.get("bases") or "(" in cp_f), cp_f[:90])
        pg.evaluate("()=>{var f=window.__NT.fx().f[0];f.es='caducada';f.cad=[{n:'LEC',k:'302',r:'cambia'}];window.__NT.vistaFormulas(f.s)}"); time.sleep(0.3)
        cad_f = pg.inner_text("#lector .idx-cad") if pg.locator("#lector .idx-cad").count() else ""
        check("fórmulas: si caduca, aviso en rojo que nombra el artículo que cambió", "Caducada" in cad_f and "ha cambiado el texto de LEC" in cad_f and "Lee el texto vigente" in cad_f, cad_f)
        check("fórmulas: la etiqueta «caducada» sale en la lista", pg.locator("#lista .idx-row .ie-cad").count() == 1)
        pg.evaluate("()=>{var f=window.__NT.fx().f[0];f.es=f.eo;f.cad=[];window.__NT.vistaFormulas(null)}")
    else:
        print("  (sin ficheros en formulas/: se omiten las pruebas de la pantalla)")
    pg.evaluate("h=>{location.hash=h}", "#t/lph"); time.sleep(0.3)
    pg.click("#lista .item:has-text('Art. 18')"); time.sleep(0.4)
    # avisos del contraste con boe.es (se simulan sobre los datos cargados: no dependen de la red)
    pg.evaluate("()=>{window.__NT.poner('lec',{'22':[['f','2026-10-08']],'33':[['d']],'439':[['d'],['f','2026-11-01']]})}")
    futura_ = pg.evaluate("()=>window.__NT.avisoBoe('lec','22','2026-10-07')")
    vigor_ = pg.evaluate("()=>window.__NT.avisoBoe('lec','22','2026-10-08')")
    difiere_ = pg.evaluate("()=>window.__NT.avisoBoe('lec','33','2026-10-07')")
    ambos_ = pg.evaluate("()=>window.__NT.avisoBoe('lec','439','2026-10-07')")
    check("aviso boe.es: reforma futura -> «Entra en vigor el 08-10-2026» y sigue rigiendo el texto de la pantalla", "Entra en vigor el 08-10-2026" in futura_ and "Hasta entonces rige el texto" in futura_, futura_)
    check("aviso boe.es: el día de la entrada en vigor pasa solo a «en vigor desde» (la fecha la pone el dispositivo)", "en vigor desde el 08-10-2026" in vigor_ and "Entra en vigor" not in vigor_, vigor_)
    check("aviso boe.es: texto distinto del consolidado -> avisa de contrastar antes de citar", "difiere del consolidado de boe.es" in difiere_ and "antes de citar" in difiere_, difiere_)
    check("aviso boe.es: diferencia y reforma futura a la vez -> los dos avisos", ambos_.count("boe-av") == 2, ambos_)
    check("aviso boe.es: artículo sin aviso -> nada", pg.evaluate("()=>window.__NT.avisoBoe('lec','1','2026-10-07')") == "")
    pg.evaluate("()=>{window.__NT.poner('lec',{'2':[['d']]})}"); pg.evaluate("h=>{location.hash=h}", "#a/lec/2"); time.sleep(0.6)
    check("aviso boe.es: se ve en pantalla encima del texto del artículo", pg.locator("#lector article .boe-av").count() == 1 and "difiere" in pg.inner_text("#lector .boe-av"), pg.inner_text("#lector")[:120])
    pg.evaluate("()=>{window.__NT.poner('lec',null)}"); pg.evaluate("h=>{location.hash=h}", "#a/lec/3"); time.sleep(0.4)
    check("aviso boe.es: sin avisos no hay banner", pg.locator("#lector .boe-av").count() == 0)
    pg.evaluate("h=>{location.hash=h}", "#t/lph"); time.sleep(0.3)
    pg.click("#lista .item:has-text('Art. 18')"); time.sleep(0.4)
    # rótulos de título/capítulo del índice de una norma: solo UNO pegado arriba a la vez (antes se apilaban los 130 de la LEC)
    pg.evaluate("h=>{location.hash=h}", "#t/lec"); time.sleep(0.5)
    maxp_ = 0
    for y_ in range(0, 70000, 900):
        maxp_ = max(maxp_, pg.evaluate("""y=>{var l=document.querySelector('#lista');l.scrollTop=y;
          var t=l.getBoundingClientRect().top;
          return [...l.querySelectorAll('.grp')].filter(e=>{var r=e.getBoundingClientRect();return r.top<=t+60&&r.bottom>t+30}).length}""", y_))
    check("índice de la LEC: rótulos de título pegados arriba al desplazarse: como mucho el que sale y el que entra (no apilados)", pg.locator("#lista .grp").count() > 50 and maxp_ <= 2, f"{pg.locator('#lista .grp').count()} rótulos; pegados a la vez: {maxp_}")
    pg.evaluate("()=>{document.querySelector('#lista').scrollTop=0}")
    pg.evaluate("h=>{location.hash=h}", "#t/lph"); time.sleep(0.3)
    pg.click("#lista .item:has-text('Art. 18')"); time.sleep(0.4)
    # copiar
    pg.click("#b-copiar"); time.sleep(0.2)
    cp = pg.evaluate("navigator.clipboard.readText()")
    check("Copiar: cita + texto + fecha", cp.startswith("Art. 18 LPH") and "Texto consolidado BOE" in cp, cp[:60])
    # notas
    pg.click("#b-notas") if pg.locator("#b-notas").count() else None
    if pg.locator("#b-notas").count():
        check("Notas de reforma se muestran", pg.locator("#lector p.nota").first.is_visible())

    print("\n[teclado: Cmd+K, j/k, flechas, Tab y Escape en todas las listas]")
    def foco_():
        return pg.evaluate("()=>{var a=document.activeElement;return a?(a.id||a.tagName):''}")
    def suelta_():
        pg.evaluate("()=>{if(document.activeElement)document.activeElement.blur()}")
    def hash_():
        return pg.evaluate("location.hash")
    pantallas_ = ["#", "#q/arrendamiento", "#a/lec/22", "#t/lph", "#n", "#n/lau", "#i", "#i/declinatoria", "#f", "#f/" ]
    mal_ = []
    for h_ in pantallas_[:-1]:
        vaya(h_); suelta_()
        pg.keyboard.press("Meta+k"); time.sleep(0.1); a1_ = foco_(); suelta_()
        pg.keyboard.press("Control+k"); time.sleep(0.1); a2_ = foco_(); suelta_()
        if a1_ != "q" or a2_ != "q": mal_.append((h_, a1_, a2_))
    check("teclado: Cmd+K y Ctrl+K llevan al buscador desde las 9 pantallas", not mal_, str(mal_))
    # resultados de búsqueda: j/k mueven la selección
    consulta(pg, "arrendamiento"); suelta_()
    def sel_res():
        return pg.evaluate("(()=>{var s=document.querySelector('#lista .item.sel');return s?s.dataset.ix:null})()")
    pg.keyboard.press("j"); s1_ = sel_res(); pg.keyboard.press("j"); s2_ = sel_res(); pg.keyboard.press("k"); s3_ = sel_res()
    check("teclado: j y k suben y bajan en los resultados de una búsqueda", (s1_, s2_, s3_) == ("1", "2", "1"), str((s1_, s2_, s3_)))
    # índice de conceptos
    def fila_sel(c_):
        return pg.evaluate("(c=>{var s=document.querySelector(c+' .idx-row.sel');return s?s.getAttribute('href'):null})", c_)
    vaya("#i"); suelta_()
    pg.fill("#iq", ""); time.sleep(0.2); IDX_N_ = pg.locator("#idx-voces .idx-row").count()
    check("teclado: el índice de conceptos lista todas las voces (más de 100)", IDX_N_ > 100, str(IDX_N_))
    suelta_(); pg.keyboard.press("j"); time.sleep(0.25); h1_ = hash_(); r1_ = fila_sel("#idx-voces")
    pg.keyboard.press("j"); time.sleep(0.25); h2_ = hash_()
    pg.keyboard.press("k"); time.sleep(0.25); h3_ = hash_()
    check("teclado: j y k recorren las voces del índice de conceptos y abren su ficha", h1_.startswith("#i/") and h2_.startswith("#i/") and h1_ != h2_ and h3_ == h1_ and r1_ == h1_, str((h1_, h2_, h3_)))
    pg.keyboard.press("ArrowDown"); time.sleep(0.25)
    check("teclado: la flecha abajo hace lo mismo que j", hash_() == h2_, hash_())
    check("teclado: la voz abierta se ve en la lista (selección visible, sin salirse de la zona)", pg.evaluate("(()=>{var s=document.querySelector('#idx-voces .idx-row.sel');if(!s)return false;var r=s.getBoundingClientRect(),l=document.querySelector('#lista').getBoundingClientRect();return r.top>=l.top-1&&r.bottom<=l.bottom+1})()"))
    # el filtro no se pierde al moverse y las flechas funcionan desde el propio campo
    pg.fill("#iq", "a"); time.sleep(0.2); n_a_ = pg.locator("#idx-voces .idx-row").count()
    pg.focus("#iq"); pg.keyboard.press("ArrowDown"); time.sleep(0.25); pg.keyboard.press("ArrowDown"); time.sleep(0.25)
    check("teclado: moverse con flechas desde el filtro conserva el texto y el foco en el campo", pg.input_value("#iq") == "a" and foco_() == "iq" and pg.locator("#idx-voces .idx-row").count() == n_a_, f"{pg.input_value('#iq')!r} {foco_()} {n_a_}")
    pg.keyboard.press("Escape"); time.sleep(0.2)
    check("teclado: Escape limpia el filtro (y devuelve toda la lista) sin salir del campo", pg.input_value("#iq") == "" and foco_() == "iq" and pg.locator("#idx-voces .idx-row").count() == IDX_N_)
    pg.keyboard.press("Escape"); time.sleep(0.1)
    check("teclado: un segundo Escape sale del campo", foco_() != "iq", foco_())
    # Tabulador: una sola parada en la lista (no 100+), y del filtro se salta al contenido
    paradas_ = pg.evaluate("document.querySelectorAll('#idx-voces .idx-row[tabindex=\"0\"]').length"); fuera_ = pg.evaluate("document.querySelectorAll('#idx-voces .idx-row:not([tabindex=\"0\"])').length")
    check("tabulador: la lista de voces tiene UNA sola parada (la voz abierta); las demás no estorban", paradas_ == 1 and fuera_ == IDX_N_ - 1 and all(pg.evaluate("[...document.querySelectorAll('#idx-voces .idx-row')].every(e=>e.getAttribute('tabindex')==='0'||e.getAttribute('tabindex')==='-1')") for _ in (0,)), f"{paradas_} {fuera_}")
    pg.focus("#iq"); orden_ = []
    for _ in range(4):
        pg.keyboard.press("Tab"); orden_.append(pg.evaluate("(()=>{var a=document.activeElement;return a.closest('#idx-voces')?'fila':(a.closest('#lector')?'contenido':(a.id||a.tagName))})()"))
    check("tabulador: filtro -> la voz abierta -> contenido de la ficha, en pocos saltos", orden_[0] == "fila" and "contenido" in orden_[1:], str(orden_))
    # fórmulas de sala
    vaya("#f"); suelta_()
    check("teclado: la lista de fórmulas tiene UNA parada de tabulador", pg.evaluate("document.querySelectorAll('#fx-lista .idx-row[tabindex=\"0\"]').length") == 1)
    pg.keyboard.press("j"); time.sleep(0.25); f1_ = hash_(); pg.keyboard.press("j"); time.sleep(0.25); f2_ = hash_(); pg.keyboard.press("k"); time.sleep(0.25); f3_ = hash_()
    check("teclado: j y k recorren las fórmulas de sala y abren cada una", f1_.startswith("#f/") and f2_.startswith("#f/") and f1_ != f2_ and f3_ == f1_ and fila_sel("#fx-lista") == f1_, str((f1_, f2_, f3_)))
    pg.click("#fq"); pg.keyboard.type("reposicion"); time.sleep(0.3); nf_ = pg.locator("#fx-lista .idx-row").count()
    pg.keyboard.press("ArrowDown"); time.sleep(0.25); pg.keyboard.press("ArrowDown"); time.sleep(0.25)
    check("teclado: en fórmulas el filtro sobrevive a moverse con flechas y j/k solo recorre las filtradas", pg.input_value("#fq") == "reposicion" and pg.locator("#fx-lista .idx-row").count() == nf_ and 0 < nf_ < 120 and foco_() == "fq", f"{nf_} {pg.input_value('#fq')!r}")
    pg.keyboard.press("Escape"); time.sleep(0.2)
    check("teclado: Escape limpia el filtro de fórmulas", pg.input_value("#fq") == "" and pg.locator("#fx-lista .idx-row").count() == 120)
    pg.click(".fm-chip[data-m=juicio]"); time.sleep(0.3); suelta_(); pg.keyboard.press("j"); time.sleep(0.25)
    sel_f_ = pg.evaluate("document.querySelector('#fx-lista .idx-row.sel')?document.querySelector('#fx-lista .idx-row.sel').getAttribute('href'):null")
    todas_juicio_ = pg.evaluate("[...document.querySelectorAll('#fx-lista .idx-row')].map(e=>e.getAttribute('href'))")
    check("teclado: con un momento elegido (juicio), j se queda dentro de esa lista", sel_f_ in todas_juicio_ and len(todas_juicio_) < 120, str(len(todas_juicio_)))
    pg.click(".fm-chip[data-m='']"); time.sleep(0.2)
    # índice de normas: la rueda de tabulador también
    vaya("#n"); pg.fill("#nq", ""); time.sleep(0.2)
    check("tabulador: la lista de normas tiene UNA parada", pg.evaluate("document.querySelectorAll('#n-lista .idx-row[tabindex=\"0\"]').length") == 1)
    vaya("")
    check("teclado: sin errores JS tras todo el recorrido", not errores, str(errores[:2]))

    print("\n[móvil]")
    m = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    mp = m.new_page(); merr = []
    mp.on("pageerror", lambda e: merr.append(str(e)))
    mp.goto(URL); mp.wait_for_function("!document.querySelector('#carga')", timeout=15000)
    check("móvil: hamburguesa visible", mp.locator("#mnav").is_visible())
    mp.fill("#q", "282 lec"); time.sleep(0.6)
    check("móvil: consulta directa abre el lector", mp.evaluate("document.body.classList.contains('ver-lector')"))
    check("móvil: sin scroll horizontal", mp.evaluate("document.documentElement.scrollWidth<=window.innerWidth+1"))
    if CAPTURAS: mp.screenshot(path=str(CAPT / "03-movil-282.png"))
    mp.click("#b-volver"); time.sleep(0.4)
    check("móvil: Resultados vuelve al buscador", not mp.evaluate("document.body.classList.contains('ver-lector')"))
    mp.fill("#q", "declinatoria"); time.sleep(0.7)
    check("móvil: lista visible tras buscar", mp.locator("#lista .item").first.is_visible())
    if CAPTURAS: mp.screenshot(path=str(CAPT / "04-movil-lista.png"))
    mp.click("#lista .item >> nth=0"); time.sleep(0.4)
    check("móvil: tocar resultado abre lector", mp.evaluate("document.body.classList.contains('ver-lector')"))
    mp.click("#b-volver"); time.sleep(0.3)
    mp.click("#mnav"); time.sleep(0.4)
    check("móvil: menú lateral abre", mp.evaluate("document.body.classList.contains('navopen')"))
    check("móvil: sin errores JS", not merr, str(merr[:2]))

    if CAPTURAS:
        pg.goto(URL + "#a/lec/282"); time.sleep(0.8); pg.screenshot(path=str(CAPT / "05-escritorio.png"))
    br.close()

print(f"\n{ok} correctas, {len(fallos)} fallos")
if fallos:
    print("FALLOS:", fallos)
    sys.exit(1)
