#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
indice.py — índice jurídico de conceptos de «Consulta de normas».

CONTENIDO JURÍDICO: lo redacta y mantiene el Armero (ver docs/respuesta-armero-indice-conceptos-07-10-2026.md y
docs/indice/tanda-01-notas.md). Taller solo lo COPIA (carpeta indice/*.yaml, verbatim), lo VALIDA (que cada precepto citado
exista en la herramienta) y calcula su CADUCIDAD. Aquí no se edita ni una remisión.

CADUCIDAD (decisión del Armero, tanda-01-notas.md apartado 1): por ARTÍCULO CITADO, con el artículo ENTERO como unidad de huella
(encabezado + título + todos los apartados + notas de reforma del espejo; solo se normalizan los espacios). La línea base es el
texto del artículo en el commit del espejo con el que el Armero revisó la voz (`espejo: "legalize-es@<commit>"`); se obtiene con
`git show`, así que no hace falta guardar huellas aparte: dar de alta o revalidar una voz = cambiar su `espejo`.
Una voz queda CADUCADA si:
  a) cambia la huella de un artículo citado;
  b) un artículo citado ya no se encuentra (derogado, renumerado o «(Sin contenido)» con otro encabezado);
  c) aparece un artículo nuevo con el mismo número base que uno citado (un «22 bis» en una voz que cita el 22);
  d) cambia un artículo del campo opcional `vigilar[]`.
Un cambio en OTROS artículos de la norma NO caduca nada: genera un único aviso agregado por norma (`cambios_norma`) para el Armero.
Si no se puede reconstruir la línea base (commit desconocido, norma no versionada) la voz se marca caducada por prudencia y lo dice.
"""
import hashlib
import re
import unicodedata
from pathlib import Path

import yaml

TIPOS = {"regula": "r", "conexa": "c"}
ESTADOS = ("vigente", "provisional", "caducada")


def slug(texto):
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def extrae_yaml_md(ruta_md):
    """Devuelve el texto del primer bloque ```yaml de un .md (para copiar la muestra del Armero tal cual)."""
    txt = Path(ruta_md).read_text(encoding="utf-8")
    m = re.search(r"```yaml\n(.*?)\n```", txt, re.S)
    if not m:
        raise SystemExit(f"{ruta_md}: no hay bloque yaml")
    return m.group(1) + "\n"


def clave_articulo(articulo):
    """Clave interna de la herramienta: «da 7» -> «da7»; «22 quáter» -> «22 quater» (la herramienta no lleva tildes);
    «49 bis» y «282» quedan igual. El Armero escribe la grafía exacta del encabezado del espejo."""
    a = unicodedata.normalize("NFD", str(articulo).strip())
    a = "".join(c for c in a if unicodedata.category(c) != "Mn").lower()
    a = re.sub(r"\s+", " ", a)
    m = re.match(r"^(da|dt|df|dd)\s*(\S+)$", a)
    return (m.group(1) + m.group(2)) if m else a


def num_base(clave):
    m = re.match(r"^(\d+)", clave)
    return int(m.group(1)) if m else None


def orden_natural(clave):
    m = re.match(r"^(\d+)(?: (.*))?$", clave)
    return (0, int(m.group(1)), m.group(2) or "") if m else (1, 0, clave)


def apartado_numerico(ap):
    """Número de apartado para resaltar al abrir: «1.2.º»->1, «2.a)»->2, «3, párrafo 2.º»->3; «4.º» (ordinal) -> None."""
    if not ap:
        return None
    m = re.match(r"^(\d+)(?!\d|\.º|º|\.ª|ª)", str(ap).strip())
    return int(m.group(1)) if m else None


def huella(chunk):
    """Huella del artículo ENTERO (encabezado, título y cuerpo con las notas de reforma); solo se normalizan espacios."""
    b = chunk["b"] if isinstance(chunk["b"], str) else "\n".join(chunk["b"])
    txt = "\n".join([chunk.get("e") or "", chunk.get("t") or "", b])
    return hashlib.sha256(re.sub(r"\s+", " ", txt).strip().encode("utf-8")).hexdigest()


def mapa_huellas(chunks):
    return {c["k"]: huella(c) for c in chunks if c["k"] not in ("cab", "pre")}


def carga(dir_indice):
    """Lee indice/*.yaml en orden alfabético. Devuelve (version, aviso, voces[])."""
    version, aviso, voces = None, None, []
    for f in sorted(Path(dir_indice).glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        version = version or d.get("version_indice")
        aviso = aviso or d.get("aviso_general")
        for v in d.get("voces", []) or []:
            v["_fichero"] = f.name
            voces.append(v)
    return version, aviso, voces


def valida(voces, normas):
    """normas: {sigla: {'id':..., 'keys': set(claves de la norma)}}. Devuelve lista de errores (vacía si todo bien)."""
    err, vistos, slugs = [], set(), set()
    for v in voces:
        nom = v.get("voz")
        ctx = f"{v.get('_fichero', '?')}: «{nom}»"
        if not nom:
            err.append(f"{ctx}: falta `voz`")
            continue
        if nom in vistos or slug(nom) in slugs:
            err.append(f"{ctx}: voz duplicada")
        vistos.add(nom), slugs.add(slug(nom))
        if v.get("estado") not in ESTADOS:
            err.append(f"{ctx}: estado {v.get('estado')!r} no válido (usa {ESTADOS})")
        for campo in ("normas_base", "espejo", "revisada_el", "revisor"):
            if not v.get(campo):
                err.append(f"{ctx}: falta `{campo}`")
        for s in v.get("normas_base") or []:
            if s not in normas:
                err.append(f"{ctx}: norma_base {s!r} no existe en la herramienta")
        for r in v.get("remisiones") or []:
            if r.get("norma") not in normas:
                err.append(f"{ctx}: remisión a norma desconocida {r.get('norma')!r}")
                continue
            if r.get("tipo") not in TIPOS:
                err.append(f"{ctx}: tipo {r.get('tipo')!r} no válido en {r.get('norma')} {r.get('articulo')}")
            if clave_articulo(r.get("articulo", "")) not in normas[r["norma"]]["keys"]:
                err.append(f"{ctx}: {r['norma']} art. {r.get('articulo')!r} NO existe en el texto de la herramienta")
            if len(str(r.get("nota", ""))) > 160:
                err.append(f"{ctx}: nota demasiado larga en {r['norma']} {r.get('articulo')} ({len(str(r['nota']))} car.)")
            if r.get("norma") not in (v.get("normas_base") or []):
                err.append(f"{ctx}: cita {r['norma']} pero no está en `normas_base` (el vigía no la vigilaría)")
        for r in v.get("vigilar") or []:
            if r.get("norma") not in normas or clave_articulo(r.get("articulo", "")) not in normas[r["norma"]]["keys"]:
                err.append(f"{ctx}: `vigilar` apunta a {r.get('norma')} art. {r.get('articulo')!r}, que no existe en la herramienta")
        if v.get("fuera_de_la_herramienta") is not None and not isinstance(v["fuera_de_la_herramienta"], list):
            err.append(f"{ctx}: `fuera_de_la_herramienta` debe ser una lista")
    return err


def commit_espejo(espejo):
    m = re.search(r"@([0-9a-f]{7,40})", str(espejo or ""))
    return m.group(1) if m else None


class BaseFija(dict):
    """{clave: huella} de una línea base FIJA, con el estado oficial con el que se fijó (atributo `estado`, p. ej. «in_force»).
    Es un dict normal para todo lo demás: así `cambios_norma` y `caducidad_voz` la tratan igual que una base sacada de git."""
    estado = None


def base_fija(bases, sigla):
    """Línea base FIJA de una norma que no vive en git (importada a mano, p. ej. un decreto del DOGV): {clave: huella} o None.
    Solo existe si alguien la fijó a propósito (scripts/fija_base.py). Una norma sin entrada sigue dando None, es decir, caducidad por prudencia."""
    e = (bases or {}).get(sigla)
    h = e.get("huellas") if isinstance(e, dict) else None
    if not h:
        return None
    b = BaseFija(h)
    b.estado = e.get("status") or None
    return b


def crea_base(chunks, origen, sha256, fijada_el, status=None):
    """Entrada de lineas_base.json para una norma: huella por artículo del texto que se da por revisado, el estado oficial de su cabecera,
    de dónde sale y cuándo se fijó. Si el estado oficial cambia al reimportar, caducan las voces aunque los artículos sean iguales
    (un decreto derogado conserva su texto literal y la huella por sí sola no lo detectaría)."""
    return dict(origen=origen, sha256=sha256, fijada_el=fijada_el, status=status, huellas=mapa_huellas(chunks))


def caducidad_voz(v, normas, base_fn):
    """Lista de razones por las que la voz está caducada ([] = no caduca). Cada razón: {n: sigla, k: clave, r: código, [v: 'vigilar']}.
    Códigos: 'cambia' (a, d), 'falta' (b), 'nuevo' (c), '?' (no se pudo comprobar). base_fn(sigla, commit) -> {clave: huella} | None."""
    c = commit_espejo(v.get("espejo"))
    if not c:
        return [dict(r="?")]
    items = {}  # sigla -> {clave: via}
    for r in v.get("remisiones") or []:
        items.setdefault(r["norma"], {})[clave_articulo(r["articulo"])] = "cita"
    for r in v.get("vigilar") or []:
        items.setdefault(r["norma"], {}).setdefault(clave_articulo(r["articulo"]), "vigilar")
    razones = []
    for sigla in sorted(items):
        base = base_fn(sigla, c)
        if base is None:
            return [dict(n=sigla, r="?")]
        cur = normas[sigla]["mapa"]
        eb, ec = getattr(base, "estado", None), normas[sigla].get("status")
        if eb and ec and eb != ec:   # solo las líneas base fijas recuerdan el estado oficial; las de git no lo llevan
            razones.append(dict(n=sigla, r="estado", antes=eb, ahora=ec))
        for k in sorted(items[sigla], key=orden_natural):
            via = items[sigla][k]
            extra = {"v": "vigilar"} if via == "vigilar" else {}
            if k not in base:
                razones.append(dict(n=sigla, k=k, r="?", **extra))  # no existía en la línea base: no se puede comparar
            elif k not in cur:
                razones.append(dict(n=sigla, k=k, r="falta", **extra))
            elif cur[k] != base[k]:
                razones.append(dict(n=sigla, k=k, r="cambia", **extra))
        citados_base = {num_base(k) for k, via in items[sigla].items() if via == "cita" and num_base(k) is not None}
        for k in sorted(cur, key=orden_natural):
            if k not in base and num_base(k) in citados_base and k not in items[sigla]:
                razones.append(dict(n=sigla, k=k, r="nuevo"))
    return razones


def cambios_norma(voces, normas, base_fn):
    """Aviso agregado para el Armero: por norma de `normas_base`, los artículos que han cambiado desde la revisión de las voces
    que cuelgan de ella y que NINGUNA de esas voces cita. {sigla: {articulos: [...], voces: [...]}}. No caduca nada."""
    out = {}
    siglas = sorted({s for v in voces for s in (v.get("normas_base") or [])})
    for s in siglas:
        dep = [v for v in voces if s in (v.get("normas_base") or [])]
        citados = set()
        for v in dep:
            for lista in (v.get("remisiones") or [], v.get("vigilar") or []):
                citados |= {clave_articulo(r["articulo"]) for r in lista if r.get("norma") == s}
        alterados = set()
        for c in {commit_espejo(v.get("espejo")) for v in dep} - {None}:
            base = base_fn(s, c)
            if base is None:
                continue
            cur = normas[s]["mapa"]
            alterados |= {k for k in set(base) | set(cur) if base.get(k) != cur.get(k) and k not in ("cab", "pre")}
        libres = sorted(alterados - citados, key=orden_natural)
        if libres:
            out[s] = dict(articulos=libres, voces=[v["voz"] for v in dep])
    return out


def compila(dir_indice, normas, base_fn):
    """Valida y devuelve (diccionario compacto para el HTML, cambios_norma). normas[sigla] = {id, keys, mapa, ruta}."""
    version, aviso, voces = carga(dir_indice)
    if not voces:
        return None, {}
    err = valida(voces, normas)
    if err:
        raise SystemExit("ÍNDICE DE CONCEPTOS NO VÁLIDO:\n  - " + "\n  - ".join(err))
    out = []
    for v in voces:
        cad = caducidad_voz(v, normas, base_fn)
        efectivo = "caducada" if (cad or v["estado"] == "caducada") else v["estado"]
        out.append(dict(
            v=v["voz"], s=slug(v["voz"]), sn=v.get("sinonimos") or [], nb=v.get("normas_base") or [],
            r=[dict(n=normas[r["norma"]]["id"], k=clave_articulo(r["articulo"]), ap=str(r.get("apartado") or ""),
                    a=apartado_numerico(r.get("apartado")), t=TIPOS[r["tipo"]], nota=r.get("nota", ""))
               for r in v.get("remisiones") or []],
            nc=v.get("no_consta_en_norma") or [], fh=v.get("fuera_de_la_herramienta") or [], af=v.get("afines") or [],
            es=efectivo, eo=v["estado"], e=v["espejo"], rv=str(v["revisada_el"]), rr=v["revisor"], cad=cad))
    return dict(version=str(version or ""), aviso=aviso or "", voces=out), cambios_norma(voces, normas, base_fn)
