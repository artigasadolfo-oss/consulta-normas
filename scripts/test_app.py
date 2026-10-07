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
CORPUS = pathlib.Path.home() / "Documents/iA/LEYES/legalize-es/es"
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
    check("tantas normas en el menú como en build.py", pg.locator("#nav-normas .navlink").count() == len(build.NORMAS), str(pg.locator("#nav-normas .navlink").count()))
    check("LOPDGDD ya no está", pg.locator("#nav-normas .navlink[data-n=lopdgdd]").count() == 0)
    check("las tres nuevas están (LOE, TRLGDCU)", all(pg.locator(f"#nav-normas .navlink[data-n={x}]").count() == 1 for x in ("loe", "trlgdcu")))
    # el número que se muestra es el de ARTÍCULOS reales (con bis/ter), sin disposiciones adicionales/transitorias/derogatorias/finales
    esperado = {"lec": 827 + 40, "lopj": 642 + 71, "cc": 1976 + 22, "ce": 169, "lau": 51 + 2, "lph": 24, "loe": 20}
    got = {n: int(pg.inner_text(f"#nav-normas .navlink[data-n={n}] .ct")) for n in esperado}
    check("menú: nº de artículos reales (sin disposiciones)", got == esperado, str(got))
    consulta(pg, "lec")
    cab_ = pg.inner_text("#lector .a-meta") if pg.locator("#lector .a-meta").count() else ""
    check("cabecera LEC: «867 artículos · 49 disposiciones»", "867 artículos · 49 disposiciones" in cab_ and "y disposiciones" not in cab_, cab_)
    check("LOFCE ya no está", pg.locator("#nav-normas .navlink[data-n=lofce]").count() == 0)

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
    check("D 11/1995 está en el menú", pg.locator("#nav-normas .navlink[data-n=d11-1995]").count() == 1)
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

    print("\n[sin norma / rango / lista]")
    consulta(pg, "21")
    n = pg.locator("#lista .item").count()
    esperadas = 0
    for cfg_ in build.NORMAS:
        _, _, l_ = build.lee_norma(cfg_); ch_, _ = build.parse_norma(cfg_, l_)
        esperadas += any(c_["k"] == "21" for c_ in ch_)
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
    pg.click("#nav-normas .navlink[data-n=lph]"); time.sleep(0.3)
    check("índice de la LPH: 32 entradas", pg.locator("#lista .item").count() == 32, str(pg.locator('#lista .item').count()))
    pg.click("#lista .item:has-text('Art. 18')"); time.sleep(0.4)
    check("abrir desde el índice", "Artículo 18" in pg.inner_text("#lector .a-h"))
    # copiar
    pg.click("#b-copiar"); time.sleep(0.2)
    cp = pg.evaluate("navigator.clipboard.readText()")
    check("Copiar: cita + texto + fecha", cp.startswith("Art. 18 LPH") and "Texto consolidado BOE" in cp, cp[:60])
    # notas
    pg.click("#b-notas") if pg.locator("#b-notas").count() else None
    if pg.locator("#b-notas").count():
        check("Notas de reforma se muestran", pg.locator("#lector p.nota").first.is_visible())

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
