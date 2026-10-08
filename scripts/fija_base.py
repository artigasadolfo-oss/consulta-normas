#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fija la LÍNEA BASE de una norma que no vive en git (importada a mano, p. ej. el Decreto 11/1995 del DOGV).

Qué hace: calcula la huella de cada artículo del texto que la herramienta compila AHORA y la guarda en lineas_base.json.
Para qué: el índice de conceptos marca una voz «caducada» si un artículo que cita ha cambiado desde su revisión. Con las normas del BOE
la revisión se reconstruye desde git; con una norma importada a mano no hay commit, y sin línea base la voz sale caducada por prudencia.

ES UN ACTO DELIBERADO, no automático: fijar la base equivale a decir «las voces que citan esta norma se revisaron contra ESTE texto».
Eso lo confirma quien revisó la voz (el Armero); taller solo guarda la huella. Si luego se reimporta la norma y un artículo citado
cambia, la voz vuelve a caducar. Para cambiar la base hay que volver a ejecutar esto a propósito.

Uso:  CONSULTA_NORMAS_CORPUS=<carpeta> python3 scripts/fija_base.py "D 11/1995" [--origen "texto"]
"""
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import build
import indice


def main(argv):
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    sigla = argv[0]
    origen = argv[argv.index("--origen") + 1] if "--origen" in argv else None
    cfg = next((c for c in build.NORMAS if c["sigla"] == sigla), None)
    if not cfg:
        print(f"Norma desconocida: {sigla!r}. Las de build.NORMAS son: {[c['sigla'] for c in build.NORMAS]}")
        return 1
    if cfg.get("dogv_id") is None:
        print(f"{sigla} es una norma del BOE: su línea base sale de git, no se fija a mano. Solo las importadas del DOGV llevan línea base fija.")
        return 1
    raw, _meta, lineas = build.lee_norma(cfg)
    chunks, _avisos = build.parse_norma(cfg, lineas)
    sha = hashlib.sha256(raw).hexdigest()
    ruta = f"{cfg.get('dir', 'es')}/{cfg['boe']}.md"
    bases = json.loads(build.BASES.read_text(encoding="utf-8")) if build.BASES.is_file() else {}
    entrada = indice.crea_base(chunks, origen or f"{ruta} (DOGV id {cfg['dogv_id']}), importado a mano; sin versión en git", sha, dt.date.today().isoformat(), status=_meta.get("status"))
    previa = bases.get(sigla)
    bases[sigla] = entrada
    build.BASES.write_text(json.dumps(bases, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{sigla}: línea base fijada con {len(entrada['huellas'])} artículos; texto sha256 {sha[:16]}…")
    if previa:
        cambian = sorted(k for k in set(previa["huellas"]) | set(entrada["huellas"]) if previa["huellas"].get(k) != entrada["huellas"].get(k))
        print("Sustituye a la anterior (" + previa.get("fijada_el", "?") + "). Artículos distintos respecto a la anterior: " + (", ".join(cambian) if cambian else "ninguno"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
