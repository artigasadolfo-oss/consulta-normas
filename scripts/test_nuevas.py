#!/usr/bin/env python3.12
"""Pruebas de las 11 normas añadidas en el encargo N-1 (Ley 12/2023, LH, TRLC, Ley 5/2012, LJV, EGAE, LAJG, CP, LECrim, LODD, Arancel)
y de la exportación para LexArt.
Uso:  env -u PYTHONPATH python3.12 scripts/test_nuevas.py   (después de python3 build.py y scripts/exportar_para_lexart.py)
Cada cita directa se contrasta con el .md del espejo extraído APARTE (no con el HTML), y las de normas con RD de aprobación delante
(LH, TRLC, EGAE, LECrim, Arancel) deben dar el artículo de la norma aprobada, no el del RD que lleva el mismo número."""
import json, os, re, sys, time, pathlib, unicodedata
os.environ.pop("PYTHONPATH", None)
from playwright.sync_api import sync_playwright

AQUI = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import build
URL = "file://" + str(AQUI / "index.html").replace(" ", "%20")
CORPUS = build.TEXTO / "es"

fallos, ok = [], 0


def check(nombre, cond, detalle=""):
    global ok
    if cond:
        ok += 1
        print(f"  ok   {nombre}")
    else:
        fallos.append(nombre)
        print(f"  FALLA {nombre} {detalle}")


def solo_letras(s):
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[\W_]+", "", "".join(c for c in s if not unicodedata.combining(c)))


def fuente(boe, cab, anclaje=None):
    """Texto (sin notas, sin marcas) del artículo cuya cabecera casa con `cab`, buscando DESPUÉS de la línea de `anclaje` si lo hay."""
    lineas = (CORPUS / f"{boe}.md").read_text(encoding="utf-8").split("\n")
    i0 = 0
    if anclaje:
        i0 = next(i for i, l in enumerate(lineas) if re.match(r"^#{1,6} " + anclaje, l, re.I))
    out, dentro = [], False
    for l in lineas[i0:]:
        if re.match(r"^#{1,6} ", l):
            if dentro:
                break
            if re.match(r"^#{6} \**" + cab, l):
                dentro = True
            continue
        if dentro and l.strip() and not l.startswith(">"):
            out.append(l)
    return solo_letras(" ".join(out))


# (cita, id, boe, cabecera del artículo, anclaje del texto aprobado, trozo del rótulo mostrado)
CASOS = [
    ("1 ley 12/2023", "ley12-2023", "BOE-A-2023-12203", r"Art[ií]culo 1\.", None),
    ("1 lh", "lh", "BOE-A-1946-2453", r"Art[ií]culo 1\.", r"TÍTULO I\. Del Registro"),
    ("1 trlc", "trlc", "BOE-A-2020-4859", r"Art[ií]culo 1\.", r"TEXTO REFUNDIDO DE LA LEY CONCURSAL"),
    ("1 ley 5/2012", "ley5-2012", "BOE-A-2012-9112", r"Art[ií]culo 1\.", None),
    ("1 ljv", "ljv", "BOE-A-2015-7391", r"Art[ií]culo 1\.", None),
    ("1 egae", "egae", "BOE-A-2021-4568", r"Art[ií]culo 1\.", r"ESTATUTO GENERAL DE LA ABOGAC"),
    ("1 lajg", "lajg", "BOE-A-1996-750", r"Art[ií]culo 1\.", None),
    ("1 cp", "cp", "BOE-A-1995-25444", r"Art[ií]culo 1\.", None),
    ("505 lecrim", "lecrim", "BOE-A-1882-6036", r"Art[ií]culo 505\.", None),
    ("1 lecrim", "lecrim", "BOE-A-1882-6036", r"Art[ií]culo 1\.", r"LEY DE ENJUICIAMIENTO CRIMINAL"),
    ("2 lodd", "lodd", "BOE-A-2024-23630", r"Art[ií]culo 2\.", None),
    ("1 arancel", "arancel", "BOE-A-2024-8706", r"Art[ií]culo 1\.", r"ARANCEL DE DERECHOS"),
    ("588 bis b lecrim", "lecrim", "BOE-A-1882-6036", r"Art[ií]culo 588 bis b\.", None),
    ("624 bis trlc", "trlc", "BOE-A-2020-4859", r"Art[ií]culo 624\. bis\.", None),
]

with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errores, externas = [], []
    pg.on("pageerror", lambda e: errores.append(str(e)))
    pg.on("request", lambda r: externas.append(r.url) if not r.url.startswith(("file:", "data:", "blob:")) else None)
    pg.goto(URL)
    pg.wait_for_function("!document.querySelector('#carga')", timeout=20000)

    def consulta(q):
        pg.fill("#q", q)
        pg.wait_for_function("document.querySelector('#lista .item, #lista .vacio, #lector article')", timeout=5000)
        time.sleep(0.5)

    print("[normas nuevas: citas directas contrastadas con el .md]")
    for cita, nid, boe, cab, anclaje in CASOS:
        consulta(cita)
        pie = pg.inner_text("#lector .a-h") if pg.locator("#lector .a-h").count() else ""
        mostrado = solo_letras(" ".join(pg.eval_on_selector_all("#lector .a-body p:not(.nota):not(.sub), #lector .a-body li", "els=>els.map(e=>e.textContent)")))
        esperado = fuente(boe, cab, anclaje)
        check(f"«{cita}»: texto idéntico al .md (extraído aparte)", len(esperado) > 20 and mostrado.startswith(esperado[:200]) and len(mostrado) >= len(esperado) * 0.98, f"{len(mostrado)} vs {len(esperado)}; {pie!r}")
    consulta("1 lecrim")
    check("«1 lecrim»: es el artículo 1 de la LECrim, no el del Real Decreto de 1882", "No se impondrá pena alguna" in pg.inner_text("#lector"), pg.inner_text("#lector")[:200])
    consulta("da1 lh")
    check("«da1 lh»: disposición adicional primera de la LH", "Disposición adicional primera" in pg.inner_text("#lector .a-h"), pg.inner_text("#lector .a-h"))
    consulta("1 cp")
    check("«1 cp»: un solo artículo (la sigla filtra: no salen el 1 de las demás normas)", pg.locator("#lector article").count() == 1 and pg.locator("#lista .item").count() <= 1, f"{pg.locator('#lector article').count()} / {pg.locator('#lista .item').count()}")
    consulta("638 cp")
    check("«638 cp»: es el artículo 638 (con el bloque «Artículos 638 y 639» aparte)", "Artículo 638" in pg.inner_text("#lector .a-h"), pg.inner_text("#lector .a-h"))
    consulta("ley hipotecaria")
    check("«ley hipotecaria» abre la norma", pg.locator("#lector .a-h, #lector h1, #lector h2").count() > 0 and "Hipotecaria" in pg.inner_text("#lector"))

    print("\n[normas nuevas: aparecen en el Índice de normas con su recuento]")
    pg.evaluate("h=>{location.hash=h}", "#n"); time.sleep(0.4)
    check("índice de normas: 21 filas", pg.locator("#n-lista .nrow").count() == 21 == len(build.NORMAS), str(pg.locator("#n-lista .nrow").count()))
    for cfg in build.NORMAS[10:]:
        _, _, chunks, _, _, n_art, n_disp = build.analiza(cfg)
        pg.evaluate("h=>{location.hash=h}", f"#t/{cfg['id']}"); time.sleep(0.35)
        cab = pg.inner_text("#lector") if pg.locator("#lector").count() else ""
        check(f"{cfg['sigla']}: la cabecera dice «{n_art} artículos»", f"{n_art} artículos" in (pg.inner_text("#lista") + cab).replace("\xa0", " "), (pg.inner_text("#lista") + cab)[:200])

    print("\n[exportación para LexArt]")
    sal = AQUI / "salida" / "lexart-corpus.json"
    check("existe salida/lexart-corpus.json", sal.is_file())
    if sal.is_file():
        d = json.loads(sal.read_text(encoding="utf-8"))
        check("la exportación tiene las 21 normas, en el orden de build.py", [n["id"] for n in d["normas"]] == [c["id"] for c in build.NORMAS])
        man = {m["id"]: m for m in json.loads((AQUI / "normas.json").read_text(encoding="utf-8"))["normas"]}
        todo = True
        for n in d["normas"]:
            chunks = build.analiza(next(c for c in build.NORMAS if c["id"] == n["id"]))[2]
            r = n["recuento"]; m = man[n["id"]]
            igual = (len(n["bloques"]) == len(chunks) == r["bloques"] == m["bloques"] and r["articulos"] == m["articulos"] and r["disposiciones"] == m["disposiciones"] and n["sha256"] == m["sha256"])
            todo &= igual
            if not igual:
                print("     distinto:", n["sigla"], r, m)
        check("recuentos, bloques y huella de cada norma = los de build.py y normas.json", todo)
        check("incluye CE y D 11/1995 (esta con fuente «DOGV, importado a mano»)",
              {n["id"]: n["fuente"] for n in d["normas"]}.get("d11-1995") == "DOGV, importado a mano" and any(n["id"] == "ce" for n in d["normas"]))
        # el texto exportado de un artículo = el .md aparte
        cp = next(n for n in d["normas"] if n["id"] == "cp")
        b1 = next(b for b in cp["bloques"] if b["clave"] == "1")
        check("export: CP art. 1 igual al .md", solo_letras(b1["texto"]) == fuente("BOE-A-1995-25444", r"Art[ií]culo 1\."))
        lx = next(n for n in d["normas"] if n["id"] == "lecrim")
        b588 = [b["clave"] for b in lx["bloques"] if b["clave"].startswith("588 bis")]
        check("export: LECrim 588 bis a..k son once claves distintas", len(b588) == len(set(b588)) == 11, str(b588))
        check("export: todas las normas con título oficial, alias y fecha", all(n["titulo"] and n["alias"] and n["actualizada"] for n in d["normas"]))
        check("export: ninguna clave repetida dentro de una norma", all(len({b["clave"] for b in n["bloques"]}) == len(n["bloques"]) for n in d["normas"]))

    check("sin errores JS", not errores, str(errores[:3]))
    check("sin peticiones fuera de file:/data:/blob:", not externas, str(externas[:3]))
    br.close()

print(f"\n{ok} correctas, {len(fallos)} fallan")
sys.exit(1 if fallos else 0)
