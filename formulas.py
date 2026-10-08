#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
formulas.py — «Fórmulas de sala» de Consulta de normas (objeciones, impugnaciones y protestas).

El CONTENIDO jurídico (fórmulas, bases, avisos) lo redacta y mantiene el ARMERO; taller solo lo copia (formulas/*.yaml, verbatim), lo
VALIDA (cada base debe existir en el texto de la herramienta; si no, falla la compilación) y calcula la CADUCIDAD con el mismo criterio
que el índice de conceptos: por ARTÍCULO citado, con el artículo entero como huella, contra el commit del espejo con que lo revisó el
Armero. Reutiliza indice.py: cada fórmula se trata como una «voz» cuya situación es su nombre y cuyas bases son sus remisiones.
"""
from pathlib import Path

import yaml

import indice

MOMENTOS = {"audiencia_previa": "Audiencia previa", "juicio": "Juicio", "vista_verbal": "Vista del verbal"}


def carga(dir_formulas):
    """Lee formulas/*.yaml en orden alfabético -> (version, aviso, formulas[])."""
    version, aviso, fs = None, None, []
    for f in sorted(Path(dir_formulas).glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        version = version or d.get("version_formulas")
        aviso = aviso or d.get("aviso_general")
        for x in d.get("formulas", []) or []:
            x["_fichero"] = f.name
            fs.append(x)
    return version, aviso, fs


def a_voz(f):
    """Fórmula -> pseudo-voz del índice (para reutilizar la validación y la caducidad)."""
    bases = f.get("bases") or []
    vig = f.get("vigilar") or []
    return dict(
        voz=f.get("situacion"), estado=f.get("estado"), espejo=f.get("espejo"), revisada_el=f.get("revisada_el"), revisor=f.get("revisor"),
        normas_base=sorted({b.get("norma") for b in bases + vig if b.get("norma")}),
        remisiones=[dict(norma=b.get("norma"), articulo=b.get("articulo", ""), apartado=b.get("apartado"), tipo="regula", nota="") for b in bases],
        vigilar=vig, _fichero=f.get("_fichero"))


def valida(formulas, normas):
    """Devuelve la lista de errores (vacía si todo bien)."""
    err, slugs = [], set()
    for f in formulas:
        nom = f.get("situacion")
        ctx = f"{f.get('_fichero', '?')}: «{nom}»"
        if not nom:
            err.append(f"{ctx}: falta `situacion`")
            continue
        if indice.slug(nom) in slugs:
            err.append(f"{ctx}: situación duplicada")
        slugs.add(indice.slug(nom))
        if not str(f.get("grupo") or "").strip():
            err.append(f"{ctx}: falta `grupo`")
        if not str(f.get("formula") or "").strip():
            err.append(f"{ctx}: falta `formula`")
        elif len(str(f["formula"])) > 600:
            err.append(f"{ctx}: `formula` demasiado larga ({len(str(f['formula']))} car.; debe poder decirse en sala)")
        m = f.get("momento")
        if not isinstance(m, list) or not m or any(x not in MOMENTOS for x in m):
            err.append(f"{ctx}: `momento` debe ser una lista con valores de {sorted(MOMENTOS)}")
        for campo in ("pide", "aviso"):
            if f.get(campo) is not None and not isinstance(f[campo], str):
                err.append(f"{ctx}: `{campo}` debe ser texto")
        for campo in ("bases", "no_consta_en_norma"):
            if f.get(campo) is not None and not isinstance(f[campo], list):
                err.append(f"{ctx}: `{campo}` debe ser una lista")
        if not (f.get("bases") or f.get("no_consta_en_norma")):
            err.append(f"{ctx}: debe tener al menos una `base` o una entrada en `no_consta_en_norma`")
        for b in f.get("bases") or []:
            if not isinstance(b, dict) or not b.get("norma") or not b.get("articulo"):
                err.append(f"{ctx}: base mal formada {b!r} (necesita `norma` y `articulo`)")
    if err:
        return err
    # las comprobaciones comunes (estado, campos obligatorios, que cada artículo exista, vigilar) las hace el índice
    out = []
    for f in formulas:
        for e in indice.valida([a_voz(f)], normas):
            if not (f.get("bases") or f.get("vigilar")) and "falta `normas_base`" in e:
                continue  # una fórmula de uso forense, sin base en norma, no necesita normas_base
            out.append(e)
    return out


def compila(dir_formulas, normas, base_fn):
    """Valida y devuelve (dict compacto para el HTML | None). normas[sigla] = {id, keys, mapa, ruta}."""
    version, aviso, fs = carga(dir_formulas)
    if not fs:
        return None
    err = valida(fs, normas)
    if err:
        raise SystemExit("FÓRMULAS DE SALA NO VÁLIDAS:\n  - " + "\n  - ".join(err))
    out = []
    for f in fs:
        v = a_voz(f)
        cad = indice.caducidad_voz(v, normas, base_fn)
        efectivo = "caducada" if (cad or f["estado"] == "caducada") else f["estado"]
        out.append(dict(
            s=indice.slug(f["situacion"]), si=f["situacion"], g=str(f["grupo"]).strip(), m=list(f["momento"]),
            f=str(f["formula"]).strip(), p=(f.get("pide") or "").strip(), av=(f.get("aviso") or "").strip(),
            b=[dict(n=normas[b["norma"]]["id"], k=indice.clave_articulo(b["articulo"]), ap=str(b.get("apartado") or ""),
                    a=indice.apartado_numerico(b.get("apartado"))) for b in f.get("bases") or []],
            nc=f.get("no_consta_en_norma") or [], es=efectivo, eo=f["estado"], rv=str(f["revisada_el"]), rr=f["revisor"], cad=cad))
    return dict(version=str(version or ""), aviso=aviso or "", momentos=MOMENTOS, f=out)
