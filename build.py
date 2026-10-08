#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — Genera index.html (Consulta de normas) a partir del corpus legalize-es.

Es el espejo del BOE consolidado que ya mantiene el vigilante diario
(~/Documents/iA/LEYES/legalize-es). Aquí NO se interpreta ni se resume nada:
se trocea cada norma en artículos y se incrusta tal cual.

Uso:
    python3 build.py              # regenera index.html + normas.json
    python3 build.py --comprobar  # solo analiza y verifica, no escribe

Garantía de fidelidad: tras trocear, verifica que cada línea del BOE (salvo las
cabeceras de artículo y de estructura) aparece exactamente una vez en un
artículo. Si falta o sobra una, el build FALLA en vez de publicar texto cojo.
"""
import base64
import datetime as dt
import formulas
import indice
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CORPUS = Path.home() / "Documents/iA/LEYES/legalize-es"   # el espejo (git): lo mueve un cron cada mañana
ES = CORPUS / "es"
# Texto desde el que se COMPILA. Por defecto, el espejo. Con CONSULTA_NORMAS_CORPUS=<carpeta> se compila desde una copia congelada
# (es/, es-vc/ y un fichero `.commit` con el sha): sirve para no depender del espejo cuando este trae erratas (ocurrió el 08-10-2026).
TEXTO = Path(os.environ["CONSULTA_NORMAS_CORPUS"]) if os.environ.get("CONSULTA_NORMAS_CORPUS") else CORPUS
# Líneas base FIJAS de las normas que no están en git (importadas a mano del DOGV): ver indice.base_fija y scripts/fija_base.py.
BASES = Path(os.environ.get("CONSULTA_NORMAS_BASES", AQUI / "lineas_base.json"))

# id interno, BOE-ID, siglas, nombre corto, modo secuencial (ver parse_norma)
NORMAS = [
    dict(id="lec",    boe="BOE-A-2000-323",   sigla="LEC",       corto="Ley de Enjuiciamiento Civil"),
    dict(id="lo1-2025", boe="BOE-A-2025-76",  sigla="LO 1/2025", corto="LO 1/2025 de eficiencia del Servicio Público de Justicia", secuencial=True),
    dict(id="lau",    boe="BOE-A-1994-26003", sigla="LAU",       corto="Ley de Arrendamientos Urbanos"),
    dict(id="lph",    boe="BOE-A-1960-10906", sigla="LPH",       corto="Ley de Propiedad Horizontal"),
    dict(id="cc",     boe="BOE-A-1889-4763",  sigla="CC",        corto="Código Civil"),
    dict(id="lopj",   boe="BOE-A-1985-12666", sigla="LOPJ",      corto="Ley Orgánica del Poder Judicial"),
    dict(id="loe",    boe="BOE-A-1999-21567", sigla="LOE",       corto="Ley de Ordenación de la Edificación"),
    dict(id="trlgdcu", boe="BOE-A-2007-20555", sigla="TRLGDCU",  corto="Ley General de Consumidores y Usuarios", previo_rdl="RDL 1/2007"),
    dict(id="d11-1995", boe="DOGV-1995-833645", sigla="D 11/1995", corto="Decreto valenciano de servicios a domicilio", dir="es-vc", dogv_id=42036),
    dict(id="ce",     boe="BOE-A-1978-31229", sigla="CE",        corto="Constitución Española"),
    # --- normas que la web comparte con LexArt (encargo N-1, 08-10-2026) ---
    # alias: formas de citarla en la búsqueda directa («1 CP»), en minúscula y sin tildes. nombres: cómo la nombra otra norma
    # («del Código Penal»), para enlazar las remisiones. anexo: encabezado desde el que empieza el texto que aprueba una
    # norma (el Decreto, el RD o el RDLeg que la aprueba va antes y se etiqueta con previo_rdl).
    dict(id="ley12-2023", boe="BOE-A-2023-12203", sigla="Ley 12/2023", corto="Ley 12/2023, por el derecho a la vivienda",
         alias="ley 12/2023|ley de vivienda|ley de la vivienda|ley por el derecho a la vivienda",
         nombres="ley 12/2023|ley por el derecho a la vivienda"),
    dict(id="lh",     boe="BOE-A-1946-2453",  sigla="LH",        corto="Ley Hipotecaria", anexo=r"TÍTULO I\. Del Registro", previo_rdl="Decreto de 8-2-1946",
         alias="lh|ley hipotecaria", nombres="ley hipotecaria|lh|decreto de 8 de febrero de 1946"),
    dict(id="trlc",   boe="BOE-A-2020-4859",  sigla="TRLC",      corto="Texto refundido de la Ley Concursal", anexo=r"TEXTO REFUNDIDO DE LA LEY CONCURSAL", previo_rdl="RDLeg 1/2020",
         alias="trlc|ley concursal|texto refundido de la ley concursal|lc|real decreto legislativo 1/2020|rdleg 1/2020",
         nombres="texto refundido de la ley concursal|real decreto legislativo 1/2020|trlc"),
    dict(id="ley5-2012", boe="BOE-A-2012-9112", sigla="Ley 5/2012", corto="Ley 5/2012, de mediación en asuntos civiles y mercantiles",
         alias="ley 5/2012|ley de mediacion", nombres="ley 5/2012|ley de mediacion en asuntos civiles y mercantiles"),
    dict(id="ljv",    boe="BOE-A-2015-7391",  sigla="LJV",       corto="Ley de la Jurisdicción Voluntaria",
         alias="ljv|ley de jurisdiccion voluntaria|ley de la jurisdiccion voluntaria|ley 15/2015",
         nombres="ley de la jurisdiccion voluntaria|ley 15/2015|ljv"),
    dict(id="egae",   boe="BOE-A-2021-4568",  sigla="EGAE",      corto="Estatuto General de la Abogacía Española (RD 135/2021)", anexo=r"ESTATUTO GENERAL DE LA ABOGAC", previo_rdl="RD 135/2021",
         alias="egae|estatuto general de la abogacia|estatuto general de la abogacia espanola|rd 135/2021|real decreto 135/2021",
         nombres="estatuto general de la abogacia espanola|estatuto general de la abogacia|real decreto 135/2021|egae"),
    dict(id="lajg",   boe="BOE-A-1996-750",   sigla="LAJG",      corto="Ley de Asistencia Jurídica Gratuita",
         alias="lajg|ley de asistencia juridica gratuita|ley 1/1996", nombres="ley de asistencia juridica gratuita|ley 1/1996|lajg"),
    dict(id="cp",     boe="BOE-A-1995-25444", sigla="CP",        corto="Código Penal",
         alias="cp|codigo penal|cod penal|ley organica 10/1995", nombres="codigo penal|ley organica 10/1995|cp"),
    dict(id="lecrim", boe="BOE-A-1882-6036",  sigla="LECrim",    corto="Ley de Enjuiciamiento Criminal", anexo=r"LEY DE ENJUICIAMIENTO CRIMINAL", previo_rdl="RD 14-9-1882", rangos_abrev=True,
         alias="lecrim|lecr|ley de enjuiciamiento criminal|enjuiciamiento criminal", nombres="ley de enjuiciamiento criminal|lecrim"),
    dict(id="lodd",   boe="BOE-A-2024-23630", sigla="LODD",      corto="Ley Orgánica 5/2024, del Derecho de Defensa",
         alias="lodd|ley organica del derecho de defensa|ley organica 5/2024|lo 5/2024|ley 5/2024",
         nombres="ley organica del derecho de defensa|ley organica 5/2024|lodd"),
    dict(id="arancel", boe="BOE-A-2024-8706", sigla="Arancel",   corto="Arancel de derechos de los profesionales de la Procura (RD 434/2024)", anexo=r"ARANCEL DE DERECHOS", previo_rdl="RD 434/2024",
         alias="arancel|arancel de la procura|arancel de procuradores|arancel procuradores|rd 434/2024|real decreto 434/2024",
         nombres="arancel de derechos de los profesionales de la procura|arancel de la procura|real decreto 434/2024"),
]

HEAD = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
ESTRUCT = re.compile(r"^(LIBRO|TÍTULO|TITULO|CAPÍTULO|CAPITULO|SECCIÓN|Sección|Subsección|SUBSECCIÓN)\b")
PREAM = re.compile(r"^(PREÁMBULO|EXPOSICIÓN DE MOTIVOS)\b", re.I)
SUF = (r"bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies|undecies|"
       r"duodecies|terdecies|quaterdecies|quindecies|sexdecies")
# Tres formas del sufijo que el BOE escribe de distintas maneras: «283 bis a)» (letra con paréntesis), «588 bis b.» (letra sin paréntesis,
# LECrim) y «624. bis.» (punto antes del bis, TRLC); y el «1º.» de los Reales Decretos antiguos.
ART = re.compile(
    rf"^Art[ií]culo\s+(\d+)[º°]?(?:(?:\.\s+|\s+)({SUF})\b)?(?:\s+(?:([a-z])(\)|(?=\s*\.))|(\d+)\b))?\s*\.?\s*(.*)$", re.I)
ART_RANGO = re.compile(r"^Art[ií]culos?\s+(\d+)\s+(a|y)\s+(\d+)\s*\.?\s*(.*)$", re.I)   # «Artículos 279 a 291», «Artículos 638 y 639» (CP)
# «Arts. 934 a 946» (LECrim): solo con la opción rangos_abrev, porque el CC trae rótulos así y su resultado no debe cambiar
ART_RANGO_ABREV = re.compile(r"^Arts?\.\s+(\d+)\s+(a|y)\s+(\d+)\s*\.?\s*(.*)$", re.I)
ART_PALABRA = re.compile(r"^Art[ií]culo\s+([a-záéíóúü]+)\s*\.\s*(.*)$", re.I)
ART_UNICO = re.compile(r"^Art[ií]culo\s+[uú]nico\s*\.?\s*(.*)$", re.I)
# El punto tras el ordinal puede faltar si el rótulo acaba ahí («Disposición adicional primera», «Disposición final» en la LECrim).
DISP = re.compile(
    r"^Disposici[oó]n\s+(adicional|transitoria|final|derogatoria)(?:\s+([^.]+?))?\s*(?:\.\s*(.*))?$", re.I)

ORD_BASE = {"primera": 1, "primero": 1, "segunda": 2, "segundo": 2, "tercera": 3, "tercero": 3,
            "cuarta": 4, "cuarto": 4, "quinta": 5, "quinto": 5, "sexta": 6, "sexto": 6,
            "septima": 7, "septimo": 7, "octava": 8, "octavo": 8, "novena": 9, "noveno": 9,
            "decima": 10, "decimo": 10, "undecima": 11, "undecimo": 11,
            "duodecima": 12, "duodecimo": 12}
ORD_DEC = {"decimo": 10, "decima": 10, "vigesimo": 20, "vigesima": 20, "trigesimo": 30,
           "trigesima": 30, "cuadragesimo": 40, "cuadragesima": 40, "quincuagesimo": 50,
           "quincuagesima": 50}


def sin_tildes(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


CARD = {"uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
        "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
        "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
        "veintiuno": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
        "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29, "treinta": 30}


def numero_en_letra(texto):
    """'veintiuno' / 'primero' -> 21 / 1 (solo palabras sueltas); None si no es número"""
    t = sin_tildes(texto.lower())
    if t in CARD:
        return CARD[t]
    if t in ORD_BASE and ORD_BASE[t] < 10:
        return ORD_BASE[t]
    return None


def ordinal(texto):
    """'vigesimoprimera' / 'trigésima segunda' / 'única' -> int | 'u' | None"""
    t = sin_tildes(texto.lower()).replace(" ", "")
    if t in ("unica", "unico"):
        return "u"
    if t.isdigit():
        return int(t)
    if t in ORD_BASE:
        return ORD_BASE[t]
    for pref, val in sorted(ORD_DEC.items(), key=lambda kv: -len(kv[0])):
        if t.startswith(pref):
            resto = t[len(pref):]
            if resto in ORD_BASE and ORD_BASE[resto] < 10:
                return val + ORD_BASE[resto]
    return None


def limpia_nota(linea):
    """'> <small>Se modifica ... [Ref. BOE-A-..#ac](https://...)</small>' -> '> Se modifica ... [Ref. BOE-A-..#ac]'"""
    t = linea
    t = re.sub(r"</?small>", "", t)
    t = re.sub(r"\[([^\]]*)\]\((?:https?://)[^)]*\)", r"[\1]", t)
    return t


def lee_norma(cfg):
    ruta = TEXTO / cfg.get("dir", "es") / f"{cfg['boe']}.md"
    raw = ruta.read_bytes()
    texto = raw.decode("utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    if not m:
        raise SystemExit(f"{ruta}: sin cabecera YAML")
    meta = {}
    for ln in m.group(1).splitlines():
        k, _, v = ln.partition(":")
        meta[k.strip()] = v.strip().strip('"')
    cuerpo = texto[m.end():]
    return raw, meta, cuerpo.split("\n")


def parse_norma(cfg, lineas):
    """Devuelve (chunks, avisos). chunk = dict(k,e,t,s,b[list de líneas])"""
    chunks, avisos = [], []
    ruta = []  # [(nivel, texto)]
    actual = None
    intro = []          # líneas tras una cabecera estructural, antes del siguiente artículo
    ultimo_num = 0
    vistos = set()
    anexo_visto = False      # opción anexo: ya se ha pasado el encabezado desde el que empieza el texto aprobado
    primero_anexo = None     # primer bloque del texto aprobado (lo anterior es del RD/Decreto que lo aprueba)

    def etiqueta_ruta():
        return " · ".join(t for _, t in ruta)

    def cierra():
        nonlocal actual
        actual = None

    def abre(k, e, t):
        nonlocal actual, intro, primero_anexo
        ch = dict(k=k, e=e, t=t, s=etiqueta_ruta(), b=list(intro), r=[x for _, x in ruta])
        intro = []
        chunks.append(ch)
        actual = ch
        if anexo_visto and primero_anexo is None:
            primero_anexo = ch

    # Cabecera previa (título, notas, "JUAN CARLOS I", etc.)
    abre("cab", "Encabezado", "", )
    chunks[-1]["s"] = ""

    for ln in lineas:
        m = HEAD.match(ln)
        if m:
            nivel, txt = len(m.group(1)), m.group(2)
            txt_plano = txt.strip("*_ ")
            if txt_plano.startswith("«") or txt_plano.startswith('"'):
                actual["b"].append(ln) if actual else intro.append(ln)
                continue
            # --- comienzo del texto aprobado (opción anexo). Si el encabezado no es estructural («TEXTO REFUNDIDO DE…»),
            # se consume como cabecera: no debe quedar colgando al final de la última disposición del RD.
            if cfg.get("anexo") and not anexo_visto and nivel <= 5 and re.match(cfg["anexo"], txt_plano, re.I):
                anexo_visto = True
                if not ESTRUCT.match(txt_plano):
                    cierra()
                    continue
            # --- artículo
            ma = ART.match(txt_plano) if nivel == 6 else None
            mr = ART_RANGO.match(txt_plano) if nivel == 6 else None
            if mr is None and nivel == 6 and cfg.get("rangos_abrev"):
                mr = ART_RANGO_ABREV.match(txt_plano)
            mp = ART_PALABRA.match(txt_plano) if nivel == 6 else None
            if mp and numero_en_letra(mp.group(1)) is None:
                mp = None
            mu = ART_UNICO.match(txt_plano) if nivel == 6 else None
            md = DISP.match(txt_plano) if nivel == 6 else None
            if mr and mr.group(2).lower() == "y" and int(mr.group(3)) != int(mr.group(1)) + 1:
                mr = None       # «Artículos 5 y 9» no es un rango: solo «N y N+1» (derogados consecutivos)
            if mr:
                ma = None
            if ma or mr or mp or mu or md:
                if mr:
                    k = f"{int(mr.group(1))}-{int(mr.group(3))}"
                    e = f"Artículos {int(mr.group(1))} {mr.group(2).lower()} {int(mr.group(3))}"
                    t = mr.group(4).strip()
                elif mp:
                    num = numero_en_letra(mp.group(1))
                    k, e, t = str(num), f"Artículo {num}", mp.group(2).strip()
                    ultimo_num = num
                elif ma:
                    num = int(ma.group(1)); suf = (ma.group(2) or "").lower().replace("á", "a")
                    extra = (ma.group(3) or ma.group(5) or "").lower()
                    if cfg.get("secuencial") and (suf or extra or num != ultimo_num + 1):
                        # cabecera de un artículo CITADO dentro de otro (norma modificadora)
                        (actual["b"] if actual else intro).append(ln)
                        continue
                    if not suf:
                        ultimo_num = num
                    partes = [str(num)] + ([suf] if suf else []) + ([extra] if extra else [])
                    k = " ".join(partes)
                    e = "Artículo " + k
                    if ma.group(3):
                        e = f"Artículo {num} {suf} {extra}{ma.group(4)}".replace("  ", " ")
                    t = ma.group(6).strip()
                elif mu:
                    k, e, t = "unico", "Artículo único", mu.group(1).strip()
                else:
                    tipo = md.group(1).lower()
                    ordtxt = (md.group(2) or "").strip()
                    n = ordinal(ordtxt) if ordtxt else "u"
                    pref = {"adicional": "da", "transitoria": "dt", "final": "df", "derogatoria": "dd"}[tipo]
                    k = f"{pref}{n}" if n is not None else f"{pref}-{sin_tildes(ordtxt.lower()).replace(' ', '-')}"
                    e = f"Disposición {tipo}" + (f" {ordtxt}" if ordtxt else "")
                    t = (md.group(3) or "").strip()
                t = t.replace("**", "").strip()
                if cfg.get("secuencial") and k in vistos:
                    (actual["b"] if actual else intro).append(ln)
                    continue
                if k in vistos:
                    avisos.append(f"clave duplicada {k!r}: se renombra")
                    i = 2
                    while f"{k}#{i}" in vistos:
                        i += 1
                    k = f"{k}#{i}"
                vistos.add(k)
                abre(k, e, t)
                continue
            # --- preámbulo / exposición de motivos
            if nivel <= 5 and PREAM.match(txt_plano):
                k = "pre"
                if k in vistos:
                    (actual["b"] if actual else intro).append(ln)
                    continue
                vistos.add(k)
                abre(k, txt_plano.capitalize() if txt_plano.isupper() else txt_plano, "")
                continue
            # --- estructura
            if nivel <= 5 and ESTRUCT.match(txt_plano):
                ruta[:] = [(n, t) for n, t in ruta if n < nivel]
                ruta.append((nivel, txt_plano))
                cierra()
                continue
            # --- otra cabecera: forma parte del texto
            (actual["b"] if actual else intro).append(ln)
        else:
            (actual["b"] if actual else intro).append(ln)
    if intro:
        chunks[-1]["b"].extend(intro)
    # recorta líneas vacías de los extremos y normaliza notas
    for ch in chunks:
        b = [limpia_nota(x) if x.startswith(">") else x.rstrip() for x in ch["b"]]
        while b and not b[0].strip():
            b.pop(0)
        while b and not b[-1].strip():
            b.pop()
        # colapsa vacías múltiples
        out = []
        for x in b:
            if not x.strip() and out and not out[-1].strip():
                continue
            out.append(x)
        ch["b"] = "\n".join(out)
    # descarta la cabecera si quedó vacía
    chunks = [c for c in chunks if c["k"] != "cab" or c["b"].strip()]
    if cfg.get("previo_rdl"):
        # Real Decreto Legislativo: lo que va antes del artículo 1 del texto refundido es del RD, no del texto
        # (su artículo único y sus disposiciones). Se etiqueta aparte para que «DF 1» no sea ambiguo.
        if cfg.get("anexo"):
            if primero_anexo is None:
                raise SystemExit(f"[{cfg['sigla']}] opción anexo: no encuentro el encabezado {cfg['anexo']!r}")
            corte = next(i for i, c in enumerate(chunks) if c is primero_anexo)
        else:
            corte = next(i for i, c in enumerate(chunks) if c["k"] == "1")
        for c in chunks[:corte]:
            if c["k"] not in ("cab", "pre"):
                c["k"] = "rd-" + c["k"]
                c["e"] = cfg["previo_rdl"] + " · " + c["e"]
        usados = {c["k"] for c in chunks[corte:]}
        avisos[:] = [a for a in avisos if "duplicada" not in a]  # ya resueltas por el prefijo rd-
        for c in chunks[corte:]:
            base = c["k"].split("#")[0]
            if "#" in c["k"] and base not in usados:
                usados.discard(c["k"]); c["k"] = base; usados.add(base)
        if cfg.get("anexo"):   # con anexo, un duplicado que sobreviva al prefijo es real: se avisa
            avisos.extend(f"clave duplicada {c['k'].split('#')[0]!r}: se renombra" for c in chunks if "#" in c["k"])
    return chunks, avisos


def verifica_sin_perdidas(cfg, lineas, chunks):
    """Cada línea de contenido de la fuente debe estar en el troceado (y viceversa)."""
    from collections import Counter

    def contenido(x):
        return limpia_nota(x) if x.startswith(">") else x.rstrip()

    fuente = Counter(contenido(x) for x in lineas if x.strip())
    # quitamos las cabeceras que se consumen (artículo/estructura/preámbulo): las reconstruimos
    consumidas = Counter()
    for ch in chunks:
        if ch["k"] == "cab":
            continue
    dest = Counter()
    for ch in chunks:
        for x in ch["b"].split("\n"):
            if x.strip():
                dest[x] += 1
    # Todo lo que haya en dest tiene que estar en fuente (con multiplicidad)
    sobran = dest - fuente
    if sobran:
        raise SystemExit(f"[{cfg['sigla']}] líneas en el troceado que no estaban en la fuente: "
                         f"{list(sobran.items())[:3]}")
    faltan = fuente - dest
    # Lo que falta deben ser solo cabeceras consumidas (líneas que empiezan por #)
    no_cabecera = {k: v for k, v in faltan.items() if not HEAD.match(k)}
    if no_cabecera:
        raise SystemExit(f"[{cfg['sigla']}] líneas de la fuente PERDIDAS: {list(no_cabecera.items())[:3]}")
    n_cab = sum(faltan.values())
    return n_cab


def rellena_fuentes_y_logo():
    def b64(p):
        return base64.b64encode(Path(p).read_bytes()).decode()
    fuentes = (
        "@font-face{font-family:'Inter';font-style:normal;font-weight:100 900;font-display:swap;"
        f"src:url(data:font/woff2;base64,{b64(AQUI/'fuentes/Inter-latin.woff2')}) format('woff2')}}\n"
        "@font-face{font-family:'Jost';font-style:normal;font-weight:100 900;font-display:swap;"
        f"src:url(data:font/woff2;base64,{b64(AQUI/'fuentes/Jost-latin.woff2')}) format('woff2')}}\n"
    )
    hon = (Path.home() / "Programación/Calculadora honorarios/index.html").read_text(encoding="utf-8")
    m = re.search(r"\.brand \.logo\{[^}]*background:url\((data:image/png;base64,[A-Za-z0-9+/=]+)\)", hon)
    if not m:
        raise SystemExit("No encuentro el logo en Calculadora honorarios/index.html")
    return fuentes, m.group(1)


def avisos_boe(normas):
    """Contraste con la API de boe.es (scripts/contraste_boe.py): -> ({sigla: {clave: [['d'] | ['f', 'AAAA-MM-DD'], ...]}}, fecha o None).
    'd' = el texto de la herramienta difiere del consolidado vigente; 'f' = reforma ya publicada que entra en vigor en esa fecha.
    Sin red (o con CONSULTA_NORMAS_SIN_BOE=1) no falla: devuelve ({}, None) y lo dice; la web entonces no muestra avisos."""
    if os.environ.get("CONSULTA_NORMAS_SIN_BOE"):
        return {}, None
    try:
        sys.path.insert(0, str(AQUI / "scripts"))
        import contraste_boe
        res = contraste_boe.contrasta(normas=normas)
    except Exception as e:
        print(f"AVISO: no he podido contrastar con boe.es ({type(e).__name__}); la web se compila SIN avisos de reforma/diferencia.")
        return {}, None
    out = {}
    for sigla, r in res["normas"].items():
        if "error" in r:
            print(f"AVISO: contraste con boe.es de {sigla} no disponible: {r['error']}")
            continue
        d = {}
        for k in r.get("distintos", []):
            d.setdefault(k, []).append(["d"])
        for k, fch in (r.get("futuras") or {}).items():
            d.setdefault(k, []).append(["f", fch])
        if d:
            out[sigla] = d
    return out, dt.date.today().isoformat()


def git_head():
    marca = TEXTO / ".commit"
    if marca.is_file():
        return marca.read_text(encoding="utf-8").strip()[:9]
    try:
        return subprocess.run(["git", "-C", str(CORPUS), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


_BASE = {}


def base_en_commit(claves_norma, sigla, commit):
    """{clave: huella} del texto de una norma en un commit del espejo, analizado con el mismo parser que el texto actual.
    None si no se puede reconstruir (commit desconocido o norma no versionada, p. ej. la importada a mano del DOGV)."""
    k = (sigla, commit)
    if k in _BASE:
        return _BASE[k]
    res = None
    try:
        cfg = claves_norma[sigla]["cfg"]
        r = subprocess.run(["git", "-C", str(CORPUS), "show", f"{commit}:{claves_norma[sigla]['ruta']}"],
                           capture_output=True, timeout=90)
        if r.returncode == 0:
            texto = r.stdout.decode("utf-8")
            m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
            if m:
                chunks, _ = parse_norma(cfg, texto[m.end():].split("\n"))
                res = indice.mapa_huellas(chunks)
    except Exception:
        res = None
    if res is None:   # norma que no vive en git: si alguien fijó su línea base a propósito, se usa; si no, sigue siendo None (prudencia)
        try:
            res = indice.base_fija(json.loads(BASES.read_text(encoding="utf-8")) if BASES.is_file() else {}, sigla)
        except Exception:
            res = None
    _BASE[k] = res
    return res


def cuenta_real(chunks):
    """(artículos, disposiciones). Artículos = los de la norma, con sus bis/ter, y los números cubiertos por los bloques
    «Artículos X a Y» (derogados) que no salgan ya sueltos; NO suma disposiciones adicionales/transitorias/derogatorias/finales
    (ni el artículo único y las disposiciones del RDL/DLeg que aprueba el texto refundido: claves rd-…)."""
    es_disp = re.compile(r"^(rd-|d[adtf])")
    sueltos, rangos, disp = [], [], 0
    for c in chunks:
        k = c["k"]
        if k in ("cab", "pre"):
            continue
        if es_disp.match(k):
            disp += 1
        elif re.match(r"^\d+-\d+$", k):
            rangos.append(k)
        else:
            sueltos.append(k)
    planos = {k for k in sueltos if re.fullmatch(r"\d+", k)}
    cubiertos = set()
    for k in rangos:
        a, z = map(int, k.split("-"))
        cubiertos |= {str(n) for n in range(a, z + 1)} - planos
    return len(sueltos) + len(cubiertos), disp


def alias_para_plantilla():
    """Textos que sustituyen las marcas @@…@@ de plantilla.html para las normas con `alias` en NORMAS (las diez primeras llevan los suyos
    escritos en la plantilla). Mismo formato que ALIAS, NOMBRES_NORMA, SAFE y RE_OTRA de la plantilla."""
    con = [c for c in NORMAS if c.get("alias")]
    solos = [c for c in con if re.fullmatch(r"[A-Za-z]+", c["sigla"])]   # siglas de una palabra (LH, CP, LECrim…)
    # SAFE: palabras que, puestas al final o al principio de una búsqueda de concepto, la limitan a esa norma. «Arancel» no: es palabra corriente.
    safe = [c for c in solos if c["id"] != "arancel"]
    return {
        "@@ALIAS_NUEVAS@@": "".join(f",\n [{json.dumps(c['id'])},{json.dumps(c['alias'])}]" for c in con),
        "@@NOMBRES_NUEVOS@@": "".join(f",[{json.dumps(c['id'])},{json.dumps(c['nombres'])}]" for c in con if c.get("nombres")),
        "@@SAFE_NUEVAS@@": "".join(f",{c['sigla'].lower()}:{json.dumps(c['sigla'].lower())}" for c in safe),
        "@@OTRA_NUEVAS@@": "".join(f"|{c['sigla'].lower()}\\b" for c in solos),
    }


def analiza(cfg):
    """Lee, trocea y verifica una norma. Es el ÚNICO camino de análisis: lo usan el build de la web y el exportador para LexArt
    (scripts/exportar_para_lexart.py), de modo que los dos ven exactamente los mismos bloques.
    -> (raw, meta, chunks, avisos, n_cabeceras_consumidas, n_articulos, n_disposiciones)"""
    raw, meta, lineas = lee_norma(cfg)
    chunks, avisos = parse_norma(cfg, lineas)
    n_cab = verifica_sin_perdidas(cfg, lineas, chunks)
    n_art, n_disp = cuenta_real(chunks)
    return raw, meta, chunks, avisos, n_cab, n_art, n_disp


def construye(solo_comprobar=False):
    datos, manifiesto, resumen, claves_norma = [], [], [], {}
    for cfg in NORMAS:
        raw, meta, chunks, avisos, n_cab, n_art, n_disp = analiza(cfg)
        claves_norma[cfg["sigla"]] = dict(id=cfg["id"], keys={c["k"] for c in chunks}, cfg=cfg, status=meta.get("status"),
                                          mapa=indice.mapa_huellas(chunks), ruta=f"{cfg.get('dir', 'es')}/{cfg['boe']}.md")
        resumen.append(f"{cfg['sigla']:10s} {n_art:5d} artículos + {n_disp:3d} disposiciones  "
                       f"({len(chunks)} bloques, {n_cab} cabeceras consumidas) "
                       f"actualizada {meta.get('last_updated','?')} {'; '.join(avisos)}")
        datos.append(dict(id=cfg["id"], boe=cfg["boe"], sigla=cfg["sigla"], corto=cfg["corto"],
                          titulo=meta.get("title", cfg["corto"]), act=meta.get("last_updated", ""),
                          est=meta.get("status", ""), url=meta.get("url_html_consolidada", ""), ca=n_art, cd=n_disp,
                          **({"dm": True} if cfg.get("alias") else {}),
                          ch=[dict(k=c["k"], e=c["e"], t=c["t"], s=c["s"], b=c["b"]) for c in chunks]))
        manifiesto.append(dict(id=cfg["id"], boe=cfg["boe"], sigla=cfg["sigla"], dir=cfg.get("dir", "es"),
                               **({"dogv_id": cfg["dogv_id"]} if cfg.get("dogv_id") else {}),
                               actualizada=meta.get("last_updated", ""),
                               sha256=hashlib.sha256(raw).hexdigest(),
                               bloques=len(chunks), articulos=n_art, disposiciones=n_disp))
    print("\n".join(resumen))
    av, av_fecha = avisos_boe([c for c in NORMAS if c["sigla"] in {d["sigla"] for d in datos}])
    for d in datos:
        if av.get(d["sigla"]):
            d["av"] = av[d["sigla"]]
    if av:
        print("Avisos de contraste con boe.es en pantalla:", {s: len(v) for s, v in av.items()})
    idx, cambios = indice.compila(Path(os.environ.get("CONSULTA_NORMAS_INDICE", AQUI / "indice")), claves_norma, lambda s, c: base_en_commit(claves_norma, s, c))
    resumen_idx = None
    if idx:
        cad = [v["v"] for v in idx["voces"] if v["es"] == "caducada"]
        prov = sum(1 for v in idx["voces"] if v["es"] == "provisional")
        resumen_idx = dict(version=idx["version"], voces=len(idx["voces"]), provisionales=prov, caducadas=cad, cambios_norma=cambios,
                           dependen={s: [v["v"] for v in idx["voces"] if s in v["nb"]] for s in sorted({s for v in idx["voces"] for s in v["nb"]})})
        print(f"Índice de conceptos {idx['version']}: {len(idx['voces'])} voces ({prov} provisionales, {len(cad)} caducadas)")
        for v in idx["voces"]:
            if v["cad"]:
                print("   caducada:", v["v"], "<-", ", ".join(f"{x.get('n', '')} {x.get('k', '')} ({x['r']}{', vigilar' if x.get('v') else ''})".strip() for x in v["cad"]))
        for sg, d in cambios.items():
            print(f"   aviso para el Armero: {sg} cambió en {len(d['articulos'])} artículo(s) que ninguna voz cita: {', '.join(d['articulos'][:12])}{' …' if len(d['articulos']) > 12 else ''}")
    # Fórmulas de sala (contenido del Armero): se valida igual que el índice; falla la compilación si una base no existe
    fx = formulas.compila(Path(os.environ.get("CONSULTA_NORMAS_FORMULAS", AQUI / "formulas")), claves_norma,
                          lambda s, c: base_en_commit(claves_norma, s, c))
    resumen_fx = None
    if fx:
        cad_fx = [f["si"] for f in fx["f"] if f["es"] == "caducada"]
        resumen_fx = dict(version=fx["version"], formulas=len(fx["f"]), provisionales=sum(1 for f in fx["f"] if f["es"] == "provisional"), caducadas=cad_fx)
        print(f"Fórmulas de sala {fx['version']}: {len(fx['f'])} fórmulas ({resumen_fx['provisionales']} provisionales, {len(cad_fx)} caducadas)")
        for f in fx["f"]:
            if f["cad"]:
                print("   caducada:", f["si"], "<-", ", ".join(f"{x.get('n', '')} {x.get('k', '')} ({x['r']})".strip() for x in f["cad"]))
        if resumen_idx is not None and cad_fx:  # el vigía ya avisa de las caducadas del índice: las de fórmulas viajan en la misma lista
            resumen_idx["caducadas"] = resumen_idx["caducadas"] + ["Fórmula de sala: " + x for x in cad_fx]
    if solo_comprobar:
        return
    hoy = dt.date.today().isoformat()
    meta_build = dict(compilado=hoy, corpus_commit=git_head(), normas=manifiesto, **({"boe_contrastado": av_fecha} if av_fecha else {}), **({"indice": resumen_idx} if resumen_idx else {}), **({"formulas": resumen_fx} if resumen_fx else {}))
    payload = json.dumps(dict(normas=datos, build=meta_build, indice=idx, formulas=fx), ensure_ascii=False, separators=(",", ":"))
    gz = gzip.compress(payload.encode("utf-8"), compresslevel=9, mtime=0)
    b64 = base64.b64encode(gz).decode()
    fuentes, logo = rellena_fuentes_y_logo()
    plantilla = (AQUI / "plantilla.html").read_text(encoding="utf-8")
    for marca, valor in alias_para_plantilla().items():
        plantilla = plantilla.replace(marca, valor)
    html = (plantilla.replace("/*@@FUENTES@@*/", fuentes)
                     .replace("@@LOGO@@", logo)
                     .replace("@@DATOS@@", b64)
                     .replace("@@COMPILADO@@", hoy))
    (AQUI / "index.html").write_text(html, encoding="utf-8")
    (AQUI / "normas.json").write_text(json.dumps(meta_build, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"index.html: {len(html)/1e6:.2f} MB  (datos sin comprimir {len(payload)/1e6:.2f} MB, gzip {len(gz)/1e6:.2f} MB)")


if __name__ == "__main__":
    construye(solo_comprobar="--comprobar" in sys.argv)
