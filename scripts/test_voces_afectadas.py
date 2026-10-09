#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de scripts/voces_afectadas.py: qué voces y fórmulas cuelgan de unos artículos. Carpetas temporales, sin red."""
import sys
import tempfile
from pathlib import Path

import yaml

AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI / "scripts"))
import voces_afectadas as V  # noqa: E402

fallos = []


def caso(n, cond, det=""):
    print(("  ok   " if cond else "  FALLA ") + n + ("" if cond else f"  -> {det}"))
    if not cond:
        fallos.append(n)


with tempfile.TemporaryDirectory() as tmp:
    aq = Path(tmp)
    (aq / "indice").mkdir(); (aq / "formulas").mkdir()
    (aq / "indice/t.yaml").write_text(yaml.safe_dump({"voces": [
        {"voz": "Cita el 10", "remisiones": [{"norma": "LAU", "articulo": "10", "apartado": "3", "tipo": "regula", "nota": "n"}]},
        {"voz": "Vigila el 10", "remisiones": [{"norma": "LAU", "articulo": "1"}], "vigilar": [{"norma": "LAU", "articulo": "10"}]},
        {"voz": "Cita el 10 de la LPH", "remisiones": [{"norma": "LPH", "articulo": "10"}]},
        {"voz": "Cita el 10 bis", "remisiones": [{"norma": "LAU", "articulo": "10 bis"}]},
        {"voz": "Cita la da 12", "remisiones": [{"norma": "LAU", "articulo": "da 12"}]},
    ]}, allow_unicode=True), encoding="utf-8")
    (aq / "formulas/f.yaml").write_text(yaml.safe_dump({"formulas": [
        {"situacion": "Fórmula con base LEC 22", "bases": [{"norma": "LEC", "articulo": "22", "apartado": "4"}]},
        {"situacion": "Fórmula que solo vigila LEC 22", "bases": [{"norma": "LEC", "articulo": "421"}], "vigilar": [{"norma": "LEC", "articulo": "22"}]},
        {"situacion": "Otra", "bases": [{"norma": "LEC", "articulo": "222"}]},
    ]}, allow_unicode=True), encoding="utf-8")
    a = V.afectadas(aq, {"LAU": ["10"]})
    caso("encuentra quien cita el artículo (con o sin apartado) y quien lo vigila", sorted(n for _, n in a["LAU"]["10"]) == ["Cita el 10", "Vigila el 10"], a)
    caso("no confunde el 10 con el 10 bis, ni la LAU con la LPH", all("bis" not in n and "LPH" not in n for _, n in a["LAU"]["10"]), a)
    caso("una disposición («da 12») se encuentra por su clave", V.afectadas(aq, {"LAU": ["da 12"]}) == {"LAU": {"da 12": [("voz", "Cita la da 12")]}}, V.afectadas(aq, {"LAU": ["da 12"]}))
    f = V.afectadas(aq, {"LEC": ["22"]})
    caso("las FÓRMULAS cuentan, por `bases` y por `vigilar` (usan `bases`, no `remisiones`)", sorted(n for _, n in f["LEC"]["22"]) == ["Fórmula con base LEC 22", "Fórmula que solo vigila LEC 22"], f)
    caso("lo que nadie cita no aparece", V.afectadas(aq, {"LAU": ["999"], "CC": ["1"]}) == {}, V.afectadas(aq, {"LAU": ["999"]}))
    r = V.resumen(aq, {"LAU": ["10"], "LEC": ["22"]})
    caso("el resumen cuenta voces y fórmulas por separado y nombra a todas", r.startswith("Citan esos artículos 2 voz/voces y 2 fórmula(s)") and "Cita el 10" in r and "Fórmula con base LEC 22" in r, r)
    caso("el resumen es vacío si nadie los cita (para no meter ruido en el aviso)", V.resumen(aq, {"CC": ["1"]}) == "")
    r2 = V.resumen(aq, {"LAU": ["10"], "LEC": ["22"]}, max_nombres=2)
    caso("el resumen se acorta con «…(+n)» cuando hay muchas", "(+2)" in r2, r2)

print(f"\n{'TODO VERDE' if not fallos else 'FALLOS: ' + str(fallos)}")
sys.exit(1 if fallos else 0)
