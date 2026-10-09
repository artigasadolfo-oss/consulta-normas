#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""¿Qué voces del índice de conceptos y qué fórmulas de sala cuelgan de unos artículos?

Sirve para que un aviso de cambio en una norma (diferencia con boe.es, reforma ya publicada que entrará en vigor, artículos alterados) diga
SIEMPRE a quién afecta, y no solo «han cambiado estos artículos». Cuenta lo mismo que cuenta la caducidad (`indice.caducidad_voz`): las
remisiones citadas y los artículos en `vigilar`. Solo lectura sobre indice/*.yaml y formulas/*.yaml.

Uso como módulo:  afectadas(aq, {"LAU": ["10"], "LPH": ["10"]}) -> {"LAU": {"10": [("voz", "Tácita reconducción"), ...]}, ...}
Uso suelto:       python3 scripts/voces_afectadas.py LAU:10,22 LPH:10
"""
import sys
from pathlib import Path

import yaml

AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import indice  # noqa: E402


def citas(aq):
    """Itera (tipo, nombre, fichero, {(sigla, clave)}) de cada voz y fórmula."""
    for carpeta, lista, nom, tipo in (("indice", "voces", "voz", "voz"), ("formulas", "formulas", "situacion", "fórmula")):
        for f in sorted((Path(aq) / carpeta).glob("*.yaml")):
            datos = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            for v in datos.get(lista, []) or []:
                c = set()
                for r in (v.get("remisiones") or []) + (v.get("bases") or []) + (v.get("vigilar") or []):   # voces: remisiones; fórmulas: bases
                    if r.get("norma") and r.get("articulo") is not None:
                        c.add((r["norma"], indice.clave_articulo(str(r["articulo"]))))
                yield tipo, v.get(nom, "?"), f.name, c


def afectadas(aq, cambios):
    """cambios: {sigla: [clave, ...]} -> {sigla: {clave: [(tipo, nombre), ...]}} (solo las claves con alguien que las cite)."""
    pedido = {(s, indice.clave_articulo(str(k))): (s, str(k)) for s, ks in cambios.items() for k in ks}
    res = {}
    for tipo, nombre, _, c in citas(aq):
        for par in c & set(pedido):
            s, k = pedido[par]
            res.setdefault(s, {}).setdefault(k, []).append((tipo, nombre))
    return res


def resumen(aq, cambios, max_nombres=8):
    """Frase para un aviso: «Citan estos artículos: 6 voces y 0 fórmulas (Tácita reconducción; …)». '' si nadie los cita."""
    af = afectadas(aq, cambios)
    todos = {}
    for s, d in af.items():
        for k, lst in d.items():
            for t, n in lst:
                todos[(t, n)] = True
    if not todos:
        return ""
    nv = sum(1 for t, _ in todos if t == "voz")
    nf = len(todos) - nv
    nombres = [n for _, n in todos]
    cola = f"; … (+{len(nombres) - max_nombres})" if len(nombres) > max_nombres else ""
    return f"Citan esos artículos {nv} voz/voces y {nf} fórmula(s): {'; '.join(nombres[:max_nombres])}{cola}"


if __name__ == "__main__":
    cambios = {}
    for a in sys.argv[1:]:
        s, _, ks = a.partition(":")
        cambios[s] = [k for k in ks.split(",") if k]
    r = resumen(AQUI, cambios, 50)
    print(r or "Ninguna voz ni fórmula cita esos artículos.")
