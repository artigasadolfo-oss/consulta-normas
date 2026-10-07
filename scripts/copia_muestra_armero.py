#!/usr/bin/env python3
"""Copia VERBATIM lo que entrega el Armero a indice/: la muestra (bloque yaml de su respuesta) y las tandas docs/indice/tanda-*.yaml.
Uso: python3 scripts/copia_muestra_armero.py. No edita nada: si el YAML del Armero es inválido, lo dirá build.py."""
import shutil, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import indice
(AQUI / "indice").mkdir(exist_ok=True)
md = AQUI / "docs/respuesta-armero-indice-conceptos-07-10-2026.md"
(AQUI / "indice/muestra.yaml").write_text(indice.extrae_yaml_md(md), encoding="utf-8")
print("indice/muestra.yaml  <-", md.name)
for t in sorted((AQUI / "docs/indice").glob("tanda-*.yaml")):
    shutil.copyfile(t, AQUI / "indice" / t.name)
    print(f"indice/{t.name}  <- docs/indice/{t.name}")
