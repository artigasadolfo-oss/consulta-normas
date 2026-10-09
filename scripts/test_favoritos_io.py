#!/usr/bin/env python3.12
"""Exportar e importar favoritos (encargo P-E).  Uso:  env -u PYTHONPATH python3.12 scripts/test_favoritos_io.py [--sin-sabotaje]
Cada caso parte de un `normas.fav` sembrado en localStorage, actúa por la interfaz (botones y atajos) y mira el estado REAL
(localStorage, fichero descargado, aviso). Las claves salen de build.parse_norma, no del HTML.
Sabotaje: la suite se vuelve a pasar contra copias del index.html con tres averías (importar sin comprobar que existe, importar
al principio en vez de al final, no contar los ignorados); cada una tiene que poner la suite en rojo."""
import datetime, json, os, pathlib, re, sys, time
os.environ.pop("PYTHONPATH", None)
from playwright.sync_api import sync_playwright

AQUI = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import build

INDEX = AQUI / "index.html"
TMP = AQUI / "scripts" / "_favio_tmp"
TMP.mkdir(exist_ok=True)
HOY = datetime.date.today().isoformat()


class _Tee:
    """Copia lo que imprime a scripts/_favio_tmp/ultima-salida.txt (el lanzador solo enseña las últimas líneas)."""
    def __init__(self, f):
        self.f, self.o = f, sys.stdout

    def write(self, t):
        self.o.write(t)
        self.f.write(t)
        self.f.flush()

    def flush(self):
        self.o.flush()


sys.stdout = _Tee(open(TMP / "ultima-salida.txt", "w", encoding="utf-8"))


def url_de(p):
    return "file://" + str(p).replace(" ", "%20")


def claves_de(cfg):
    _, _, lineas = build.lee_norma(cfg)
    chunks, _ = build.parse_norma(cfg, lineas)
    return [c["k"] for c in chunks]


def prepara_datos():
    """Claves reales de varias normas, calculadas con el analizador del build."""
    por = {c["id"]: c for c in build.NORMAS}
    d = {"cfg": por}
    lec = claves_de(por["lec"])
    d["lec"] = lec
    d["lec_art"] = [k for k in ("282", "414", "10") if k in lec]
    lh = claves_de(por["lh"])
    d["lh_rd"] = next((k for k in lh if k.startswith("rd-") and k not in ("rd-cab", "rd-pre")), None)
    lopj = claves_de(por["lopj"])
    d["lopj_espacio"] = next((k for k in lopj if " " in k), None)
    lo1 = claves_de(por["lo1-2025"])
    d["lo1"] = next(k for k in lo1 if re.match(r"\d", k))
    cc = claves_de(por["cc"])
    d["cc_da"] = next((k for k in cc if re.match(r"da\d", k)), None)
    d["lph18"] = "18" in claves_de(por["lph"])
    d["rd_da"] = None
    for i in ("lh", "trlc", "egae", "arancel", "trlgdcu", "lecrim"):
        k = next((k for k in claves_de(por[i]) if re.fullmatch(r"rd-d[atdf]\d+", k)), None)
        if k:
            d["rd_da"] = (i, k)
            break
    return d


D = prepara_datos()
assert D["lec_art"] == ["282", "414", "10"] and D["lph18"], D
print("claves reales:", {k: v for k, v in D.items() if k not in ("cfg", "lec")})
SIG = lambda i: D["cfg"][i]["sigla"]


class Suite:
    def __init__(self, nombre, silencio=False):
        self.nombre, self.silencio, self.ok, self.fallos = nombre, silencio, 0, []

    def check(self, nombre, cond, detalle=""):
        if cond:
            self.ok += 1
            if not self.silencio:
                print(f"  ok   {nombre}")
        else:
            self.fallos.append(nombre)
            print(f"  FALLA {nombre} {str(detalle)[:260]}" if not self.silencio else f"     (rojo) {nombre}")


def corre(url, s):
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        pg = ctx.new_page()
        errores, externas, descargas, selectores = [], [], [], []
        pg.on("pageerror", lambda e: errores.append(str(e)))
        pg.on("console", lambda m: errores.append("console:" + m.text) if m.type == "error" else None)
        pg.on("request", lambda r: externas.append(r.url) if not r.url.startswith(("file:", "data:", "blob:")) else None)
        pg.on("download", lambda d: descargas.append(d))
        pg.on("filechooser", lambda f: selectores.append(f))
        pg.goto(url)
        pg.wait_for_selector("#q", timeout=20000)
        pg.wait_for_function("!document.querySelector('#carga')", timeout=20000)

        def home():
            pg.evaluate("()=>{location.hash='#n'}"); time.sleep(0.25)
            pg.evaluate("()=>{location.hash=''}")
            pg.wait_for_selector("#b-exp-fav", timeout=5000); time.sleep(0.15)

        def siembra(lista):
            pg.evaluate("v=>localStorage.setItem('normas.fav',JSON.stringify(v))", lista)

        def ls():
            return pg.evaluate("()=>JSON.parse(localStorage.getItem('normas.fav')||'[]')")

        def aviso():
            return pg.text_content("#fav-aviso") or ""

        def importa(datos, nombre="favoritos.json"):
            if not isinstance(datos, (bytes, bytearray)):
                datos = json.dumps(datos).encode()
            pg.evaluate("()=>{var s=document.getElementById('fav-aviso');s.textContent='';delete s.dataset.origen}")
            pg.set_input_files("#fav-fichero", files=[{"name": nombre, "mimeType": "application/json", "buffer": bytes(datos)}])
            try:
                pg.wait_for_function("()=>/^(Importados|No se ha importado|No he podido)/.test(document.getElementById('fav-aviso').textContent)", timeout=5000)
            except Exception:
                pass
            return aviso()

        def exporta(por_tecla=False):
            n0 = len(descargas)
            try:
                with pg.expect_download(timeout=3000) as dl:
                    if por_tecla:
                        pg.evaluate("()=>document.activeElement&&document.activeElement.blur()")
                        pg.keyboard.press("e")
                    else:
                        pg.click("#b-exp-fav")
                d = dl.value
            except Exception:
                return None, None
            ruta = TMP / f"{d.suggested_filename}"
            d.save_as(str(ruta))
            return d.suggested_filename, ruta.read_bytes()

        L = lambda n, k=None: ({"n": n} if k is None else {"n": n, "k": k})
        lec282, lec414, lec10 = (L("lec", k) for k in D["lec_art"])
        lph18 = L("lph", "18")

        print("\n[estado y accesibilidad]")
        s.check("carga sin errores JS ni peticiones de red", not errores and not externas, str(errores[:2]) + str(externas[:2]))
        siembra([]); home()
        be, bi, br_ = (pg.locator(x) for x in ("#b-exp-fav", "#b-imp-fav", "#b-reset-fav"))
        s.check("los tres botones existen, con sus atajos E e I visibles", be.count() == bi.count() == br_.count() == 1
                and "E" in be.inner_text() and "I" in bi.inner_text(), be.inner_text() + bi.inner_text())
        s.check("aria-label en exportar e importar, y el aviso es role=status", bool(be.get_attribute("aria-label")) and bool(bi.get_attribute("aria-label"))
                and pg.get_attribute("#fav-aviso", "role") == "status")
        s.check("el input de ficheros acepta .json y está oculto", pg.get_attribute("#fav-fichero", "accept").startswith(".json") and pg.evaluate("document.getElementById('fav-fichero').hidden"))
        s.check("sin favoritos, exportar está desactivado y dice por qué (título, aria-label y aviso)", be.get_attribute("aria-disabled") == "true"
                and "No hay favoritos" in be.get_attribute("title") and "no hay favoritos" in be.get_attribute("aria-label") and "No hay favoritos" in aviso(), aviso())
        pg.evaluate("()=>document.getElementById('b-exp-fav').click()"); time.sleep(0.4)
        s.check("sin favoritos, pulsar exportar no descarga nada", len(descargas) == 0)
        pg.evaluate("()=>{document.activeElement.blur()}"); pg.keyboard.press("e"); time.sleep(0.4)
        s.check("sin favoritos, la tecla E no descarga nada y lo dice", len(descargas) == 0 and "No hay favoritos" in aviso())
        # orden de tabulación: Exportar -> Importar -> Restablecer
        be.focus(); pg.keyboard.press("Tab")
        a1 = pg.evaluate("document.activeElement.id"); pg.keyboard.press("Tab"); a2 = pg.evaluate("document.activeElement.id")
        s.check("Tab recorre Exportar, Importar y Restablecer en ese orden", (a1, a2) == ("b-imp-fav", "b-reset-fav"), (a1, a2))

        print("\n[exportar]")
        siembra([lec282]); home()
        s.check("con 1 favorito el botón se activa", be.get_attribute("aria-disabled") == "false" and "No hay favoritos" not in aviso())
        nombre, datos = exporta()
        s.check("nombre favoritos-normas-AAAA-MM-DD.json con la fecha de hoy", nombre == f"favoritos-normas-{HOY}.json", nombre)
        j = json.loads(datos) if datos else None
        s.check("1 favorito: [{n,k,sig,id}] con ese orden de claves", j == [{"n": "lec", "k": "282", "sig": SIG("lec"), "id": "282"}] and list(j[0]) == ["n", "k", "sig", "id"], j)
        s.check("tras exportar, el aviso lo dice con la cifra", aviso().startswith("Exportados 1 en favoritos-normas-"), aviso())
        s.check("exportar no toca los favoritos guardados", ls() == [lec282])
        mixta = [L("lau"), lec414, L("cc"), lec10, lph18, lec282, L("lo1-2025"), L("lo1-2025", D["lo1"])]
        siembra(mixta); home()
        nombre, datos = exporta()
        j = json.loads(datos)
        esperado = []
        for f in mixta:
            e = {"n": f["n"]}
            if "k" in f:
                e["k"] = f["k"]
            e["sig"] = SIG(f["n"])
            if "k" in f:
                e["id"] = f["k"]
            esperado.append(e)
        s.check("N favoritos: mismo orden que en el menú, normas enteras como {n,sig} y artículos como {n,k,sig,id}", j == esperado, j)
        s.check("las normas enteras no llevan k ni id", all("k" not in e and "id" not in e for e in j if e["n"] in ("lau", "cc") or ("k" not in e)))
        s.check("sigla con barra (LO 1/2025) viaja tal cual", any(e["sig"] == "LO 1/2025" for e in j), [e["sig"] for e in j])
        n_antes = len(descargas)
        pg.evaluate("()=>document.activeElement&&document.activeElement.blur()"); pg.keyboard.press("e"); time.sleep(0.8)
        s.check("la tecla E exporta lo mismo", len(descargas) == n_antes + 1)

        print("\n[ida y vuelta]")
        siembra(mixta); home()
        _, datos = exporta()
        siembra([]); home()
        av = importa(datos)
        s.check("importar el propio export en blanco reproduce la lista idéntica y en el mismo orden", ls() == mixta, ls())
        s.check("aviso con las cifras exactas", av == f"Importados {len(mixta)} · ya estaban 0 · ignorados 0", av)
        av = importa(datos)
        s.check("importarlo otra vez no duplica nada: todo ya estaba", ls() == mixta and av == f"No se ha importado nada · ya estaban {len(mixta)} · ignorados 0", av)
        s.check("tras importar el foco vuelve al botón Importar", pg.evaluate("document.activeElement.id") == "b-imp-fav")

        print("\n[formatos: web, LexArt, mixto]")
        siembra([L("lau"), lec10]); home()
        lexart = [{"sig": SIG("lec"), "id": "282"}, {"sig": "LO 1/2025", "id": D["lo1"]}, {"sig": SIG("lph"), "id": "18"}]
        av = importa(lexart)
        s.check("fichero de LexArt {sig,id}: se añade al final en el orden del fichero y respeta lo existente",
                ls() == [L("lau"), lec10, lec282, L("lo1-2025", D["lo1"]), lph18] and av == "Importados 3 · ya estaban 0 · ignorados 0", (ls(), av))
        siembra([]); home()
        todas = [{"sig": c["sigla"]} for c in build.NORMAS]
        av = importa(todas)
        s.check("la sigla de CADA norma de la web se traduce a su id (lo1-2025, d11-1995, ley12-2023…)", ls() == [L(c["id"]) for c in build.NORMAS] and av == f"Importados {len(build.NORMAS)} · ya estaban 0 · ignorados 0", (ls()[:3], av))
        siembra([]); home()
        extra = []
        if D["lh_rd"]:
            extra.append({"sig": SIG("lh"), "id": D["lh_rd"]})
        if D["cc_da"]:
            extra.append({"sig": SIG("cc"), "id": D["cc_da"]})
        if D["lopj_espacio"]:
            extra.append({"sig": SIG("lopj"), "id": D["lopj_espacio"]})
        av = importa(extra)
        s.check("las claves de disposiciones y con espacios (rd-…, da1, «216 bis 2») pasan tal cual", len(ls()) == len(extra) and len(extra) >= 2 and av.startswith(f"Importados {len(extra)} "), (extra, ls(), av))
        siembra([]); home()
        estilo = [{"sig": SIG("cc"), "id": "DA 1"}, {"sig": SIG("lec"), "id": " 282 "}, {"sig": SIG("lec"), "id": "282"}]
        esperado_ = [L("cc", "da1"), lec282]
        if D["rd_da"]:
            i_, k_ = D["rd_da"]
            estilo.append({"sig": SIG(i_), "id": "RD " + k_[3:5].upper() + " " + k_[5:]})
            esperado_.append(L(i_, k_))
        av = importa(estilo)
        s.check("ids al estilo de LexArt («DA 1», «RD DA 1», con espacios sobrantes) se traducen a la clave de la web y no duplican", ls() == esperado_ and av == f"Importados {len(esperado_)} · ya estaban 1 · ignorados 0", (estilo, ls(), av))
        siembra([]); home()
        mixto = [{"n": "lec", "k": "282", "sig": "LEC", "id": "282"}, {"n": "cc"}, {"sig": "LPH", "id": "18"}, {"n": "lau", "sig": "LAU"}]
        av = importa(mixto)
        s.check("fichero mixto (web con sig/id, norma entera, solo LexArt)", ls() == [lec282, L("cc"), lph18, L("lau")] and av == "Importados 4 · ya estaban 0 · ignorados 0", (ls(), av))

        print("\n[duplicados, inexistentes, basura]")
        siembra([L("lau"), lec10]); home()
        av = importa([L("lau"), lec10, lec282, lec282, {"sig": "LEC", "id": "282"}])
        s.check("duplicados (con lo existente y dentro del fichero) no se añaden y se cuentan como «ya estaban»", ls() == [L("lau"), lec10, lec282] and av == "Importados 1 · ya estaban 4 · ignorados 0", (ls(), av))
        siembra([lec10]); home()
        inexistentes = [{"sig": "XYZ", "id": "1"}, {"n": "lec", "k": "99999"}, {"n": "nopelicula"}, {"sig": "LEC", "id": "zzz"}, {"n": "__proto__"},
                        {"n": "constructor", "k": "1"}, {"sig": "LEC", "id": "28 2"}, {"n": "lec", "k": "Z" * 30}, {"sig": "CC", "id": "DA 99999"}]
        av = importa(inexistentes)
        s.check("norma o clave inexistente (incluidas __proto__ y constructor): se ignora, no se guarda", ls() == [lec10] and av == f"No se ha importado nada · ya estaban 0 · ignorados {len(inexistentes)}", (ls(), av))
        basura = [1, "a", None, [], {}, {"n": 5}, {"n": "lec", "k": {"a": 1}}, True, {"n": "lec", "k": 282}]
        av = importa(basura)
        s.check("basura dentro de una lista JSON: se ignora y se cuenta", ls() == [lec10] and av == f"No se ha importado nada · ya estaban 0 · ignorados {len(basura)}", (ls(), av))
        siembra([L("lau"), {"n": "zzz", "k": "1"}, lec10]); home()
        av = importa([lec282, {"n": "zzz", "k": "9"}, L("cc")])
        s.check("mezcla exacta: nunca borra ni reordena (ni siquiera una entrada obsoleta ya guardada)", ls() == [L("lau"), {"n": "zzz", "k": "1"}, lec10, lec282, L("cc")] and av == "Importados 2 · ya estaban 0 · ignorados 1", (ls(), av))
        siembra([L("lau"), lec10]); home()
        av = importa([L("lau"), lec10, lec282, L("cc"), {"sig": "LPH", "id": "18"}, {"n": "x"}, 7, {"sig": "Q", "id": "1"}])
        s.check("cifras exactas del aviso: Importados 3 · ya estaban 2 · ignorados 3", av == "Importados 3 · ya estaban 2 · ignorados 3" and ls() == [L("lau"), lec10, lec282, L("cc"), lph18], (av, ls()))

        print("\n[ficheros que no valen]")
        previo = [L("lau"), lec10, lec414]
        siembra(previo); home()
        for nombre_, datos_, trozo in (
                ("no es JSON", b"esto no es json {", "no es JSON válido"),
                ("vacío", b"", "no es JSON válido"),
                ("JSON que no es lista", b'{"favoritos": [{"n":"lec"}]}', "no es una lista de favoritos"),
                ("un número JSON", b"42", "no es una lista de favoritos"),
                ("binario", bytes(range(256)) * 4, "no es JSON válido")):
            av = importa(datos_)
            s.check(f"fichero {nombre_}: avisa, no importa nada y no toca los favoritos", ls() == previo and av.startswith("No se ha importado nada") and trozo in av, (ls(), av))
        av = importa([])
        s.check("lista vacía []: sin éxito falso", ls() == previo and av == "No se ha importado nada · ya estaban 0 · ignorados 0", av)
        grande = json.dumps([{"n": "lec", "k": "282", "pad": "x" * 2000} for _ in range(600)]).encode()
        s.check("(el fichero de prueba pesa más de 1 MB)", len(grande) > 1048576, len(grande))
        av = importa(grande)
        s.check("más de 1 MB: se rechaza con aviso y sin tocar nada", ls() == previo and av.startswith("No se ha importado nada") and "1 MB" in av, av)
        av = importa([lec282] * 501)
        s.check("501 elementos: se rechaza con aviso (máximo 500) y sin tocar nada", ls() == previo and av.startswith("No se ha importado nada") and "501" in av and "500" in av, av)
        av = importa([lec282] * 500)
        s.check("500 elementos justos: se aceptan", ls() == previo + [lec282] and av == "Importados 1 · ya estaban 499 · ignorados 0", (av, ls()))

        print("\n[menú y teclado]")
        siembra([lec10]); pg.reload(); pg.wait_for_function("!document.querySelector('#carga')", timeout=20000); home()
        importa([L("lau"), lec282, L("cc")])
        filas_n = pg.eval_on_selector_all("#nav-fav .fchip", "els=>els.map(e=>e.textContent.trim())")
        filas_a = pg.eval_on_selector_all("#nav-fav .frow .fa", "els=>els.map(e=>e.innerText.replace(/\\s+/g,' ').trim())")
        s.check("el menú se repinta al importar: normas y artículos en el orden de fijado", filas_n == ["LAU", "CC"] and filas_a == ["LEC Art. 10", "LEC Art. 282"], (filas_n, filas_a))
        s.check("el botón Exportar se activa al llegar los primeros favoritos", be.get_attribute("aria-disabled") == "false")
        pg.evaluate("()=>{document.activeElement.blur()}")
        pg.evaluate("()=>{var s=document.getElementById('fav-aviso');s.textContent='';delete s.dataset.origen}")
        with pg.expect_file_chooser(timeout=3000) as fc:
            pg.keyboard.press("i")
        fc.value.set_files([{"name": "x.json", "mimeType": "application/json", "buffer": json.dumps([L("lph")]).encode()}])
        pg.wait_for_function("()=>/^Importados/.test(document.getElementById('fav-aviso').textContent)", timeout=5000)
        s.check("la tecla I abre el selector de ficheros y el fichero elegido se importa", L("lph") in ls() and aviso() == "Importados 1 · ya estaban 0 · ignorados 0", (aviso(), ls()))
        s.check("tras importar por teclado el foco vuelve a Importar", pg.evaluate("document.activeElement.id") == "b-imp-fav")
        # los atajos NO se disparan escribiendo en un campo
        n_d, n_s = len(descargas), len(selectores)
        pg.click("#q"); pg.keyboard.type("eiEI"); time.sleep(0.5)
        s.check("escribiendo en el buscador, E e I no disparan nada (y el texto se escribe)", len(descargas) == n_d and len(selectores) == n_s and pg.input_value("#q") == "eiEI", pg.input_value("#q"))
        pg.fill("#q", "")
        pg.keyboard.press("Control+e"); pg.keyboard.press("Control+i"); time.sleep(0.4)
        s.check("con Ctrl o Cmd, E e I tampoco se disparan", len(descargas) == n_d and len(selectores) == n_s)
        siembra([lec10]); home()
        with pg.expect_file_chooser(timeout=3000) as fc:
            pg.click("#b-imp-fav")
        s.check("el botón Importar abre el selector de ficheros", fc.value is not None)

        print("\n[otra pantalla, móvil]")
        pg.evaluate("()=>{location.hash='#n'}"); time.sleep(0.4)
        siembra([lec10])
        pg.evaluate("()=>document.activeElement&&document.activeElement.blur()")
        n_d = len(descargas)
        pg.keyboard.press("e"); time.sleep(0.8)
        s.check("la tecla E exporta desde cualquier pantalla (aquí, el Índice de normas) y avisa con un toast", len(descargas) == n_d + 1 and pg.locator(".toast").count() >= 1, pg.locator(".toast").all_inner_texts())
        m = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        mp = m.new_page(); merr = []
        mp.on("pageerror", lambda e: merr.append(str(e)))
        mp.goto(url); mp.wait_for_function("!document.querySelector('#carga')", timeout=20000)
        mp.evaluate("v=>localStorage.setItem('normas.fav',JSON.stringify(v))", [lec10])
        mp.evaluate("()=>{location.hash='#n'}"); time.sleep(0.3); mp.evaluate("()=>{location.hash=''}"); mp.wait_for_selector("#b-exp-fav"); time.sleep(0.2)
        mp.set_input_files("#fav-fichero", files=[{"name": "f.json", "mimeType": "application/json", "buffer": json.dumps([{"sig": "LEC", "id": "282"}, {"x": 1}]).encode()}])
        mp.wait_for_function("()=>/^Importados/.test(document.getElementById('fav-aviso').textContent)", timeout=5000)
        s.check("móvil: sin scroll horizontal tras importar y los botones no se cortan", mp.evaluate("document.documentElement.scrollWidth<=window.innerWidth+1")
                and mp.evaluate("[...document.querySelectorAll('#b-exp-fav,#b-imp-fav,#b-reset-fav')].every(b=>b.scrollWidth<=b.clientWidth+1&&b.getBoundingClientRect().right<=window.innerWidth+1)"), mp.text_content("#fav-aviso"))
        s.check("móvil: sin errores JS", not merr, merr[:2])
        m.close()
        home()
        s.check("escritorio: los tres botones enteros", pg.evaluate("[...document.querySelectorAll('#b-exp-fav,#b-imp-fav,#b-reset-fav')].every(b=>b.scrollWidth<=b.clientWidth+1)"))
        s.check("sin errores de consola ni de JS en toda la sesión", not errores, errores[:3])
        s.check("sin peticiones de red en toda la sesión", not externas, externas[:3])
        br.close()


def main():
    sabotaje = "--sin-sabotaje" not in sys.argv
    s = Suite("real")
    print(f"== suite sobre {INDEX.name}")
    corre(url_de(INDEX), s)
    print(f"\n{s.ok} correctas, {len(s.fallos)} fallos en la suite real")
    total_fallos = list(s.fallos)
    if sabotaje:
        html = INDEX.read_text(encoding="utf-8")
        AVERIAS = {
            "importar sin comprobar que existe": [
                ("if(!tieneNorma(n))return null;", "if(typeof n!=='string')return null;"),
                ("for(i=0;i<c.length;i++)if(m.has(c[i]))return c[i];\n  return null;", "return k;")],
            "reordenar al importar (lo nuevo al principio)": [("res.push(f);nuevos++;", "res.unshift(f);nuevos++;")],
            "contar mal en el aviso (los ignorados no se cuentan)": [("if(!f){ign++;return}", "if(!f){return}")],
        }
        for nombre, cambios in AVERIAS.items():
            h = html
            for viejo, nuevo in cambios:
                assert h.count(viejo) == 1, f"el sabotaje «{nombre}» ya no encuentra su objetivo: {viejo}"
                h = h.replace(viejo, nuevo)
            tmp = AQUI / "_sabotaje_favio.html"
            tmp.write_text(h, encoding="utf-8")
            try:
                ss = Suite(nombre, silencio=True)
                print(f"\n== sabotaje: {nombre}")
                corre(url_de(tmp), ss)
            finally:
                tmp.unlink()
            print(f"   -> {len(ss.fallos)} pruebas en rojo con la avería")
            if not ss.fallos:
                total_fallos.append(f"el sabotaje «{nombre}» NO pone la suite en rojo")
    print(f"\n{'OK' if not total_fallos else 'FALLOS'}: {len(total_fallos)} fallos")
    if total_fallos:
        print("FALLOS:", total_fallos)
        sys.exit(1)


main()
