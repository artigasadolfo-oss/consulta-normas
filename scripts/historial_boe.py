#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
historial_boe.py — redacciones sucesivas de cada artículo según la API de datos abiertos del BOE (texto consolidado): «¿qué decía el artículo X el día D?».

Para LexArt (biblioteca de normas, selector de fecha): un contrato de 01-10-2018 se juzga con la LAU de esa fecha, no con la de hoy.

REGLA DE SELECCIÓN (la misma que usa el contraste con boe.es, calibrada el 07-10-2026 contra la página oficial de la LEC en 855 artículos): entre las versiones que
YA rigen en la fecha D, la de mayor `fecha_publicacion` (el BOE las ordena por publicación, no por vigencia: una sentencia del TC publicada después puede regir antes).

TRAMPA (10-10-2026): las últimas versiones de una cadena de reales decretos-ley llegan SIN `fecha_vigencia`. Tratarlas como «vigentes desde siempre» hace que la LAU 10
al 01-10-2018 salga con la redacción de 2026. Se toma como fecha de efectos la de PUBLICACIÓN y el tramo se marca `incierta` (cota inferior: no rige antes de publicarse).

LÍMITES (se muestran al usuario): (1) es el texto vigente EN esa fecha; no resuelve el régimen transitorio (disposiciones transitorias de cada reforma), que decide el jurista.
(2) Las reformas anunciadas solo en una nota «Téngase en cuenta…» no son versiones; para el futuro está `contraste_boe.futuras_detalle`.
(3) No existe una URL oficial «texto a fecha» con la que cotejar (`act.php?p=` y la ruta ELI devuelven el texto actual); se valida con coherencia interna y con hechos jurídicos conocidos.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contraste_boe as cb  # noqa: E402


def _efectos(v):
    """(AAAAMMDD desde el que rige, incierta). Sin `fecha_vigencia` -> la de publicación, y es incierta."""
    vig = v.get("fecha_vigencia") or ""
    if vig:
        return vig, False
    return (v.get("fecha_publicacion") or "00000000"), True


def _iso(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def _dia_antes(d):
    return (dt.date(int(d[:4]), int(d[4:6]), int(d[6:])) - dt.timedelta(days=1)).strftime("%Y%m%d")


def version_a_fecha(versiones, d):
    """versiones: [(efectos, incierta, idx, elemento <version>)]; d: AAAAMMDD -> la que rige en d (None si el artículo aún no existía)."""
    ok = [x for x in versiones if x[0] <= d]
    return max(ok, key=lambda x: (x[3].get("fecha_publicacion") or "00000000", x[0], x[2])) if ok else None


def tramos_bloque(b, clave, hoy=None):
    """Tramos de vigencia de un <bloque> de la API, hasta `hoy` (lo posterior es una reforma futura, no historia):
    [{desde: 'AAAA-MM-DD', hasta: 'AAAA-MM-DD' | None (el vigente), norma: 'BOE-A-…', titulo, parrafos: [...], incierta: bool, sk: esqueleto}].
    Tramos consecutivos con el MISMO texto se funden (una reforma que no toca este artículo no abre tramo)."""
    hoy_s = (hoy or dt.date.today()).strftime("%Y%m%d")
    vs = [(*_efectos(v), i, v) for i, v in enumerate(b.findall("version"))]
    tr = []
    for d in sorted({x[0] for x in vs if x[0] <= hoy_s}):
        x = version_a_fecha(vs, d)
        if x is None:
            continue
        v = x[3]
        sk = cb.esqueleto(cb.texto_version(v, clave))
        if tr and tr[-1]["sk"] == sk:
            continue
        rot, ps = cb._parrafos_version(v)
        titulo = cb.sin_rotulo(rot, clave).strip() if rot else ""
        tr.append(dict(desde=d, norma=v.get("id_norma"), titulo=titulo, parrafos=ps, incierta=x[1], sk=sk))
    for a, b2 in zip(tr, tr[1:]):
        a["hasta"] = _dia_antes(b2["desde"])
    if tr:
        tr[-1]["hasta"] = None
    for t in tr:
        t["desde"] = _iso(t["desde"])
        if t["hasta"]:
            t["hasta"] = _iso(t["hasta"])
    return tr


def historial(xml_texto, hoy=None):
    """{clave: [tramos]} de todos los preceptos de la norma. Misma clave que usa el contraste (bloques_boe)."""
    out, vistos = {}, set()
    for b in cb.ET.fromstring(xml_texto).iter("bloque"):
        if b.get("tipo") != "precepto":
            continue
        k = cb._clave_bloque(b)
        if not k or k in vistos:
            continue
        vistos.add(k)
        t = tramos_bloque(b, k, hoy)
        if t:
            out[k] = t
    return out


def a_fecha(tramos, fecha_iso):
    """Tramo vigente en `fecha_iso` ('AAAA-MM-DD') o None si el artículo aún no existía."""
    sel = None
    for t in tramos:
        if t["desde"] <= fecha_iso and (t["hasta"] is None or fecha_iso <= t["hasta"]):
            sel = t
    return sel


def para_exportar(tr):
    """Forma compacta para la exportación a LexArt: todos los tramos; el vigente SIN párrafos (ya va en el texto del bloque)."""
    out = []
    for i, t in enumerate(tr):
        d = dict(desde=t["desde"], hasta=t["hasta"], norma=t["norma"], titulo=t["titulo"])
        if t["incierta"]:
            d["incierta"] = True
        if t["hasta"] is not None:
            d["parrafos"] = t["parrafos"]
        out.append(d)
    return out
