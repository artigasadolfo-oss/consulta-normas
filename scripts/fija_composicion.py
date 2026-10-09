#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fija la LÍNEA BASE de una COMPOSICIÓN de texto (scripts/compone_corpus.py) y le da un identificador.

Qué hace: calcula la huella de cada artículo de las normas del BOE tal como las compila la herramienta con CONSULTA_NORMAS_CORPUS=<composición>
y las guarda en lineas_base.json -> `_composiciones` -> <ident>. El identificador es hexadecimal (10 cifras, sha256 de los ficheros de la
composición) para que el Armero lo escriba como cualquier commit: `espejo: "legalize-es@<ident>"`. Una voz revisada contra la composición
caduca solo si luego cambia un artículo que cita (o el estado oficial de la norma), igual que con un commit de git.
También deja el identificador en `.commit` de la composición y copia su `composicion.json` a la raíz del repositorio (procedencia auditable).

ES UN ACTO DELIBERADO: fijar la base equivale a decir «las voces revisadas con este identificador se revisaron contra ESTE texto».
Es idempotente: si el identificador ya consta, no cambia nada.

Uso: CONSULTA_NORMAS_CORPUS=<composición> python3 scripts/fija_composicion.py [--descripcion "texto"]
"""
import datetime as dt
import hashlib
import json
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import build  # noqa: E402
import indice  # noqa: E402


def main(argv):
    if build.TEXTO == build.CORPUS:
        print("Falta CONSULTA_NORMAS_CORPUS=<carpeta de la composición>: esto no se hace sobre el espejo vivo.")
        return 2
    desc = argv[argv.index("--descripcion") + 1] if "--descripcion" in argv else "composición de texto"
    huellas_fich, normas = [], {}
    for cfg in build.NORMAS:
        if cfg.get("dir", "es") != "es":
            continue   # las importadas a mano (DOGV) tienen su propia línea base por sigla
        raw, meta, lineas = build.lee_norma(cfg)
        chunks, _ = build.parse_norma(cfg, lineas)
        huellas_fich.append(f"{cfg['sigla']}:{hashlib.sha256(raw).hexdigest()}")
        normas[cfg["sigla"]] = dict(status=meta.get("status") or None, sha256=hashlib.sha256(raw).hexdigest(), huellas=indice.mapa_huellas(chunks))
    ident = hashlib.sha256("\n".join(sorted(huellas_fich)).encode()).hexdigest()[:10]
    comp = json.loads((build.TEXTO / "composicion.json").read_text(encoding="utf-8")) if (build.TEXTO / "composicion.json").is_file() else {}
    bases = json.loads(build.BASES.read_text(encoding="utf-8")) if build.BASES.is_file() else {}
    previa = (bases.get("_composiciones") or {}).get(ident)
    bases.setdefault("_composiciones", {})[ident] = previa or dict(
        descripcion=desc, fijada_el=dt.date.today().isoformat(), base=comp.get("base", ""), origen=comp.get("origen", ""),
        sustituciones=comp.get("sustituciones", []), normas=normas)
    build.BASES.write_text(json.dumps(bases, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (build.TEXTO / ".commit").write_text(ident + "\n", encoding="utf-8")
    if (build.TEXTO / "composicion.json").is_file():
        shutil.copyfile(build.TEXTO / "composicion.json", AQUI / "composicion_corpus.json")
    print(f"composición {ident}: {'ya constaba' if previa else 'fijada'} ({sum(len(n['huellas']) for n in normas.values())} huellas en {len(normas)} normas)")
    print(f"Armero: espejo: \"legalize-es@{ident}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
