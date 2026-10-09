#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
contraste_boe.py — contrasta, ARTÍCULO por artículo, el texto del espejo (el que lleva la herramienta) con el texto consolidado
VIGENTE de boe.es (API oficial de datos abiertos del BOE). Existe porque comparar solo fechas no basta: el 7 de octubre de 2026 el
espejo declaraba la misma fecha de actualización que boe.es y aun así le faltaba el apartado 6 del art. 22 LEC.

Cómo compara: de cada lado se saca el texto del artículo SIN notas de reforma y se reduce a su «esqueleto» (minúsculas, sin
espacios, signos, comillas, asteriscos ni indicadores ordinales): así el formato (markdown frente a XML, listas, negritas) no cuenta
y cualquier palabra o cifra distinta, sí. De la API se toma, por bloque, la última versión cuya fecha de vigencia ya ha llegado.

Salida (JSON, `boe_contraste.json` junto a la app): por norma, la fecha de actualización de boe.es, los artículos distintos,
los que solo están en boe.es y los que solo están en el espejo, y cuántos se compararon.
Uso: python3 scripts/contraste_boe.py [--solo LEC,LAU] [--salida ruta.json] [--cache carpeta] [--espejo-commit <sha>]
"""
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import build  # noqa: E402
import indice  # noqa: E402

API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/{id}/{que}"
ORD_RE = re.compile(r"[ºª°˚]")


def limpia_espejo(t):
    """Marcas propias del markdown del espejo que no son texto de la ley: `<sup>a</sup>` -> ª, otras etiquetas fuera."""
    t = re.sub(r"<sup>\s*([aoª-º])\s*</sup>", lambda m: {"a": "ª", "o": "º"}.get(m.group(1), m.group(1)), t)
    return re.sub(r"</?[a-zA-Z][^>]*>", "", t)


SUFIJOS = ("bis|ter|quater|quáter|quinquies|sexies|septies|octies|nonies|novies|decies|undecies|duodecies|terdecies|quaterdecies|quindecies|"
           "sexdecies|septdecies|octodecies")
ROTULO = re.compile(r"^\s*Art[ií]culo\s+(\d+(?:\s+(?:" + SUFIJOS + r")(?:\s+\d{1,2}\b)?)?(?:\s+[a-z]\b)?)\s*\.?", re.I)   # «216 bis 2» (artículo real de la LOPJ) no es el «216 bis»
ROTULO_LETRA = re.compile(r"^\s*Art[ií]culo\s+(?:[a-záéíóúñ]+)(?:\s+y\s+[a-záéíóúñ]+)?(?:\s+(?:" + SUFIJOS + r"))?\s*\.", re.I)


def sin_rotulo(t):
    """Quita el rótulo inicial «Artículo 22 bis.» (el que lleva cifras; el espejo y el BOE no lo escriben igual, y la clave ya lo identifica)."""
    if ROTULO.match(t):
        return ROTULO.sub("", t, count=1)
    return ROTULO_LETRA.sub("", t, count=1)  # «Artículo primero.» (LPH): solo con punto final, para no comerse texto


def esqueleto(texto):
    """Solo letras y cifras, en minúscula y SIN tildes ni ordinales (el espejo escribe «quater» donde el BOE «quáter»; un cambio que
    fuese solo de tilde no se detectará: es el precio de no dar falsos avisos por ese rótulo)."""
    t = unicodedata.normalize("NFD", texto).lower()
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = ORD_RE.sub("", t)
    t = re.sub(r"[\W_]+", "", t)
    # fórmula promulgatoria final («Por tanto, mando a todos los españoles…»): el BOE consolidado la omite, el espejo la conserva
    return re.sub(r"(portantomandoatodoslosespanoles|dadaenelpalaciodeelpardo).*$", "", t)


def descarga(boe_id, que="texto", cache=None, timeout=120):
    """Texto XML de la API del BOE. Con `cache` (carpeta) reutiliza lo ya bajado ese día (para pruebas)."""
    if cache:
        f = Path(cache) / f"{boe_id}-{que}-{dt.date.today().isoformat()}.xml"
        if f.is_file():
            return f.read_text(encoding="utf-8")
    # `curl` y no urllib: el Python de este Mac no valida la cadena de certificados del BOE (y no se desactiva la verificación).
    r = subprocess.run(["curl", "-sS", "-f", "-m", str(timeout), "-H", "Accept: application/xml", API.format(id=boe_id, que=que)],
                       capture_output=True, timeout=timeout + 20)
    if r.returncode != 0:
        raise RuntimeError(f"curl rc={r.returncode}: {(r.stderr or b'').decode('utf-8', 'replace').strip()[:120]}")
    txt = r.stdout.decode("utf-8")
    if cache:
        Path(cache).mkdir(parents=True, exist_ok=True)
        f.write_text(txt, encoding="utf-8")
    return txt


def fecha_actualizacion(boe_id, cache=None):
    m = re.search(r"<fecha_actualizacion>(\d{8})", descarga(boe_id, "metadatos", cache))
    return f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else None


def texto_p(p):
    """Texto de un elemento XML; `<sup>a</sup>` -> «ª» y `<sup>o</sup>` -> «º» (el espejo también lo normaliza), tablas incluidas."""
    out = []
    def rec(e):
        if e.tag == "sup" and (e.text or "").strip() in ("a", "o"):
            out.append("ª" if e.text.strip() == "a" else "º")
        else:
            out.append(e.text or "")
            for h in e:
                rec(h)
        out.append(e.tail or "")
    rec(p)
    out[-1] = ""  # la cola del propio elemento raíz no es suya
    return "".join(out)


def numero_compuesto(primero, resto):
    """«treinta» + «y uno» -> 31 (cardinales 31-99 en letra, como titula el BOE algunos artículos de la LOPJ)."""
    toks = (resto or "").split()
    if len(toks) >= 2 and toks[0].lower() == "y":
        a, b = build.numero_en_letra(primero), build.numero_en_letra(toks[1])
        if a and b and a >= 30 and b < 10:
            return a + b
    return None


DECENAS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90}
CENTENAS = {"cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300, "cuatrocientos": 400, "quinientos": 500,
            "seiscientos": 600, "setecientos": 700, "ochocientos": 800, "novecientos": 900}


def cardinal_en_letras(toks):
    """Cardinal compuesto en letra al principio de una lista de palabras -> (valor, palabras consumidas), o (None, 0).
    ['doscientos','treinta','y','uno','bis'] -> (231, 4); ['cuatrocientos','cincuenta','y','cinco'] -> (455, 4); ['primero'] -> (None, 0).
    El BOE titula así algunos artículos de la LOPJ (231, 455…): sin esto no se emparejan con el espejo y quedan SIN CONTRASTAR."""
    t = [build.sin_tildes(x.lower()) for x in toks]
    i = total = 0
    if i < len(t) and t[i] in CENTENAS:
        total += CENTENAS[t[i]]
        i += 1
    if i < len(t) and t[i] in DECENAS:
        total += DECENAS[t[i]]
        i += 1
        if i + 1 < len(t) and t[i] == "y" and build.CARD.get(t[i + 1], 99) < 10:
            total += build.CARD[t[i + 1]]
            i += 2
    elif i < len(t) and t[i] in build.CARD:
        total += build.CARD[t[i]]
        i += 1
    return (total, i) if total else (None, 0)


def clave_de_titulo(titulo):
    """«Artículo 22 quáter» / «Art 22 quáter» -> «22 quater»; «Artículo primero» -> «1»; «Artículo único» -> «unico»;
    «Artículo doscientos treinta y uno» -> «231»; «Disposición adicional primera» -> «da1»; None si no es ni lo uno ni lo otro."""
    t = (titulo or "").strip().rstrip(".").replace(")", "")  # «283 bis a)» -> «283 bis a», como en el espejo
    m = re.match(r"^Art(?:[ií]culo)?\.?\s+(.+)$", t, re.I)
    if m:
        resto = m.group(1).strip()
        primero, _, suf = resto.partition(" ")
        if re.match(r"^[uú]nico$", primero, re.I):
            return "unico"
        if not re.match(r"^\d", primero):
            toks = resto.split()
            n, usadas = cardinal_en_letras(toks)
            if n:
                return indice.clave_articulo(f"{n} {' '.join(toks[usadas:])}".strip())
            n = numero_compuesto(primero, suf)
            if n is None:
                n = build.numero_en_letra(primero)
            if n is None:
                o = build.ordinal(primero)
                n = o if isinstance(o, int) else None
            if n is None:
                return None
            if n is not None and numero_compuesto(primero, suf):
                suf = " ".join(suf.split()[2:])
            resto = f"{n} {suf}".strip()
        return indice.clave_articulo(resto)
    m = re.match(r"^Disposici[oó]n\s+(adicional|transitoria|final|derogatoria)(?:\s+(.+))?$", t, re.I)
    if m:
        pref = {"adicional": "da", "transitoria": "dt", "final": "df", "derogatoria": "dd"}[m.group(1).lower()]
        ordtxt = (m.group(2) or "").strip()
        n = build.ordinal(ordtxt) if ordtxt else "u"
        return f"{pref}{n}" if n is not None else None
    return None


def texto_version(v):
    return sin_rotulo(" ".join(texto_p(h) for h in v if h.tag != "blockquote" and not (h.get("class") or "").startswith("nota_pie")))  # blockquote = notas de reforma


def clave_orden(v_idx):
    """El BOE consolida por orden de PUBLICACIÓN, no de vigencia (la sentencia del TC de 28-02-2025 se publicó después de la LO 1/2025
    pero entró en vigor antes). Calibrado el 07-10-2026: elegir la de mayor `fecha_publicacion` reproduce la página oficial en los
    855 artículos de la LEC; la de mayor vigencia o la última del documento fallan en 8 y 16."""
    fv, i, v = v_idx
    return (v.get("fecha_publicacion") or "00000000", fv, i)


MESES = {m: i for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), 1)}
NOTA_FUTURA = re.compile(r"Téngase en cuenta que, con efectos de (\d{1,2}) de ([a-záéíóú]+) de (\d{4}), se modifica por", re.I)


def fecha_nota_futura(version):
    """'AAAA-MM-DD' si la versión lleva la nota «Téngase en cuenta que, con efectos de <fecha>, se modifica por … con la siguiente redacción»: así
    anuncia el BOE una reforma YA PUBLICADA que aún no rige cuando no crea una versión nueva con fecha futura. Caso real (09-10-2026): art. 10 LAU,
    RDL 28/2026, en vigor el 15-11-2026. Ojo: la versión que lleva la nota YA es el texto vigente (aquí, el del RDL 29/2026); el texto futuro va
    dentro de la nota, no en el cuerpo, y la `fecha_vigencia` vacía de esa versión NO significa «futura» (verificado en el cuerpo del artículo)."""
    for h in version:
        if h.tag == "blockquote":
            m = NOTA_FUTURA.search(" ".join(texto_p(h).split()))
            if m and m.group(2).lower() in MESES:
                return f"{m.group(3)}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return None


def bloques_boe(xml_texto, hoy=None):
    """Texto de cada artículo/disposición según la API del BOE. Devuelve (vigente, futuras):
    vigente = {clave: esqueleto} de la versión más recientemente publicada entre las que YA están en vigor en `hoy`;
    futuras = {clave: fecha 'AAAA-MM-DD'} de la primera reforma que entra en vigor DESPUÉS de `hoy`, solo si su texto difiere del vigente
    (aviso temprano: el RDL 29/2026, publicado el 7-10-2026, añadía el apartado 6 del art. 22 LEC con vigencia del 8-10-2026)."""
    hoy = (hoy or dt.date.today()).strftime("%Y%m%d")
    raiz = ET.fromstring(xml_texto)
    vigente, futuras = {}, {}
    for b in raiz.iter("bloque"):
        if b.get("tipo") != "precepto":
            continue
        vs0 = b.findall("version")
        k = None
        if vs0:  # el atributo `titulo` va en letra («Artículo quinto bis»); el primer párrafo lleva la cifra («Artículo 5 bis.»)
            primero = next((texto_p(p) for p in vs0[-1].findall("p")), "")
            m = ROTULO.match(primero)
            k = indice.clave_articulo(m.group(1)) if m else None
        k = k or clave_de_titulo(b.get("titulo"))
        if not k or k in vigente:
            continue
        vs = [(v.get("fecha_vigencia") or "00000000", i, v) for i, v in enumerate(b.findall("version"))]
        pasadas = [x for x in vs if x[0] <= hoy]
        if not pasadas:
            continue
        actual = max(pasadas, key=clave_orden)
        vigente[k] = esqueleto(texto_version(actual[2]))
        for fv, _, v in sorted((x for x in vs if x[0] > hoy), key=lambda x: (x[0], x[1])):
            if esqueleto(texto_version(v)) != vigente[k]:
                futuras[k] = f"{fv[:4]}-{fv[4:6]}-{fv[6:]}"
                break
        if k not in futuras:   # reforma anunciada solo en una nota «Téngase en cuenta que, con efectos de…» (no hay versión con fecha futura)
            fn = fecha_nota_futura(actual[2])
            if fn and fn.replace("-", "") > hoy:
                futuras[k] = fn
    return vigente, futuras


def bloques_espejo(chunks):
    """{clave: esqueleto} del texto del espejo (título y cuerpo, sin las notas de reforma que empiezan por «>»)."""
    out = {}
    for c in chunks:
        if c["k"] in ("cab", "pre"):
            continue
        b = c["b"] if isinstance(c["b"], str) else "\n".join(c["b"])
        # fuera: notas («>») y toda línea de encabezado («#…»): rótulos de la «Redacción anterior» y de capítulos/títulos que el espejo deja en el cuerpo
        cuerpo = "\n".join(ln for ln in b.split("\n") if not ln.lstrip().startswith(">") and not re.match(r'^\s*#', ln))
        e = c.get("e") or ""
        rotulo = "" if re.match(r"^Art[ií]culo\b", e, re.I) else e  # el rótulo de artículo no se compara (la clave ya lo identifica)
        out[c["k"]] = esqueleto(limpia_espejo(" ".join([rotulo, c.get("t") or "", cuerpo])))
    return out


CONOCIDAS = AQUI / "contraste_conocidas.json"


def sha(x):
    return hashlib.sha1(x.encode("utf-8")).hexdigest()[:12]


def carga_conocidas(ruta=None):
    """{sigla: {clave: [sha_boe, sha_espejo, motivo]}}: diferencias YA revisadas y accesorias (rótulos de derogados, capítulos, tablas
    que la API omite…). Solo valen mientras NO cambie ninguno de los dos textos: si cambia cualquiera, la excepción deja de aplicarse."""
    f = Path(ruta or CONOCIDAS)
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def compara(boe, esp, conocidas=None):
    comunes = [k for k in boe if k in esp]
    conocidas = conocidas or {}
    solo_ok = set(conocidas.get("_solo_boe", []))
    aceptadas = [k for k in comunes if boe[k] != esp[k] and k in conocidas and conocidas[k][:2] == [sha(boe[k]), sha(esp[k])]]
    distintos = sorted((k for k in comunes if boe[k] != esp[k] and k not in aceptadas), key=indice.orden_natural)
    return dict(comparados=len(comunes), distintos=distintos, aceptadas=len(aceptadas),
                solo_boe=sorted((k for k in boe if k not in esp and k not in solo_ok), key=indice.orden_natural),
                solo_espejo=sorted((k for k in esp if k not in boe), key=indice.orden_natural))


def rutas_posibles(cfg):
    """Rutas de una norma dentro del espejo: la antigua (`es/BOE-….md`) y la del formato nuevo de legalize (v0.4, desde octubre de 2026),
    que reparte las leyes en subcarpetas con los dos primeros caracteres del SHA-1 del identificador (`es/06/BOE-A-2000-323.md`)."""
    d = cfg.get("dir", "es")
    return [f"{d}/{cfg['boe']}.md", f"{d}/{hashlib.sha1(cfg['boe'].encode()).hexdigest()[:2]}/{cfg['boe']}.md"]


def cabecera_meta(txt):
    m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
    meta = {}
    for ln in (m.group(1).splitlines() if m else []):
        k, _, v = ln.partition(":")
        meta[k.strip()] = v.strip().strip('"')
    return meta, (txt[m.end():] if m else txt)


def chunks_de(cfg, commit=None):
    """Chunks de una norma: del árbol de trabajo o, con `commit`, de `git show commit:ruta` (mismo parser que el build). Con `commit` se
    prueba la ruta antigua y la del formato nuevo de legalize."""
    if not commit:
        raw, meta, lineas = build.lee_norma(cfg)
        return build.parse_norma(cfg, lineas)[0], meta
    for ruta in rutas_posibles(cfg):
        r = subprocess.run(["git", "-C", str(build.CORPUS), "show", f"{commit}:{ruta}"], capture_output=True, timeout=90)
        if r.returncode == 0:
            meta, cuerpo = cabecera_meta(r.stdout.decode("utf-8"))
            return build.parse_norma(cfg, cuerpo.split("\n"))[0], meta
    return None, {}


def contrasta(solo=None, cache=None, commit=None, hoy=None, normas=None):
    normas = normas or build.NORMAS
    res = {}
    for cfg in normas:
        if cfg.get("dir", "es") != "es" or not cfg["boe"].startswith("BOE-"):
            continue  # normas autonómicas importadas a mano: las vigila el estado del DOGV, no esta comprobación
        if solo and cfg["sigla"] not in solo:
            continue
        try:
            chunks, meta = chunks_de(cfg, commit)
            vig, fut = bloques_boe(descarga(cfg["boe"], "texto", cache), hoy)
            r = compara(vig, bloques_espejo(chunks), carga_conocidas().get(cfg["sigla"]))
            r["conocidas_obsoletas"] = []
            r["futuras"] = dict(sorted(fut.items(), key=lambda kv: indice.orden_natural(kv[0])))
            r["boe_actualizada"] = fecha_actualizacion(cfg["boe"], cache)
            r["espejo_actualizada"] = meta.get("last_updated")
        except Exception as e:  # nunca silencio: el vigía lo mostrará
            r = dict(error=f"{type(e).__name__}: {e}"[:200])
        res[cfg["sigla"]] = r
    return dict(generado=dt.datetime.now().isoformat(timespec="seconds"), espejo_commit=commit or build.git_head(), normas=res)


def main():
    a = sys.argv[1:]
    def opt(n, d=None):
        return a[a.index(n) + 1] if n in a else d
    solo = set(opt("--solo").split(",")) if opt("--solo") else None
    res = contrasta(solo, opt("--cache"), opt("--espejo-commit"))
    salida = Path(opt("--salida", AQUI / "boe_contraste.json"))
    salida.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for s, r in res["normas"].items():
        if "error" in r:
            print(f"{s:10s} ERROR {r['error']}")
        else:
            print(f"{s:10s} comparados {r['comparados']:4d} | distintos {len(r['distintos']):3d} {r['distintos'][:14]} | solo boe {len(r['solo_boe'])} | solo espejo {len(r['solo_espejo'])} | boe {r['boe_actualizada']} espejo {r['espejo_actualizada']}")
    print("escrito", salida)


if __name__ == "__main__":
    main()
