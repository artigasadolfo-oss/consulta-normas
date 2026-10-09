#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de scripts/revisa_voces.py (la puerta que valida lo que devuelve el Armero). Sin llamar al Armero ni a la red: todo en carpetas temporales."""
import sys
import tempfile
from pathlib import Path

import yaml

AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI / "scripts"))
import revisa_voces as R  # noqa: E402

fallos = []


def caso(n, cond, det=""):
    print(("  ok   " if cond else "  FALLA ") + n + ("" if cond else f"  -> {det}"))
    if not cond:
        fallos.append(n)


def voz(n, espejo="legalize-es@aaaaaaaaaa", nota="n"):
    return {"voz": n, "espejo": espejo, "remisiones": [{"norma": "LAU", "articulo": "10", "tipo": "regula", "nota": nota}]}


with tempfile.TemporaryDirectory() as tmp:
    aq = Path(tmp)
    (aq / "indice").mkdir(); (aq / "formulas").mkdir()
    orig = [voz("A"), voz("B"), voz("C")]
    (aq / "indice/t.yaml").write_text(yaml.safe_dump({"voces": orig}, allow_unicode=True), encoding="utf-8")
    (aq / "formulas/f.yaml").write_text(yaml.safe_dump({"formulas": [{"situacion": "S1", "espejo": "x"}]}, allow_unicode=True), encoding="utf-8")
    print("[localiza: cada caducada a su fichero]")
    grupos, perdidas = R.localiza([("voces", "A", "LAU 10 (cambia)"), ("voces", "C", "LAU 10 (cambia)"), ("formulas", "S1", "LEC 22"), ("voces", "Z", "x")], aq)
    caso("agrupa por fichero (voces en indice/, fórmulas en formulas/)", set(grupos) == {"indice/t.yaml", "formulas/f.yaml"} and [n for n, _ in grupos["indice/t.yaml"]] == ["A", "C"], grupos)
    caso("lo que no encuentra se devuelve aparte, no se pierde en silencio", perdidas == ["Z"], perdidas)
    print("[valida: la puerta del resultado del Armero]")
    obj = [("A", "r"), ("C", "r")]

    def salida(nombre, voces):
        p = aq / nombre
        p.write_text(yaml.safe_dump({"voces": voces}, allow_unicode=True), encoding="utf-8")
        return p
    bien = [voz("A", "legalize-es@f14d07aa91", "nota nueva"), voz("B"), voz("C", "legalize-es@f14d07aa91")]
    caso("fichero correcto -> válido", R.valida("indice/t.yaml", obj, salida("ok.yaml", bien), "f14d07aa91", aq) == (True, "ok"))
    ok, m = R.valida("indice/t.yaml", obj, salida("orden.yaml", [bien[1], bien[0], bien[2]]), "f14d07aa91", aq)
    caso("cambia el orden o los nombres -> rechazado", not ok and "nombres" in m, m)
    ok, m = R.valida("indice/t.yaml", obj, salida("sinesp.yaml", [voz("A", "legalize-es@aaaaaaaaaa"), voz("B"), bien[2]]), "f14d07aa91", aq)
    caso("una voz afectada sin el espejo nuevo -> rechazado", not ok and "sin el espejo" in m, m)
    ok, m = R.valida("indice/t.yaml", obj, salida("tocada.yaml", [bien[0], voz("B", nota="TOCADA"), bien[2]]), "f14d07aa91", aq)
    caso("el Armero toca una voz que no estaba en la lista -> rechazado", not ok and "no estaba en la lista" in m, m)
    ok, m = R.valida("indice/t.yaml", obj, aq / "no_existe.yaml", "f14d07aa91", aq)
    caso("fichero ausente o ilegible -> rechazado sin reventar", not ok and "ilegible" in m, m)
    (aq / "roto.yaml").write_text("voces: [", encoding="utf-8")
    ok, m = R.valida("indice/t.yaml", obj, aq / "roto.yaml", "f14d07aa91", aq)
    caso("YAML roto -> rechazado", not ok, m)

    print("[trabaja: de extremo a extremo con un Armero simulado]")
    comp = aq / "comp"; comp.mkdir(); (comp / ".commit").write_text("f14d07aa91\n")
    rv = R.Revision("prueba", "motivo de prueba", comp, aq, hoy="2026-10-09")

    def armero_bueno(texto, ruta, nombre_log):
        assert "motivo de prueba" in texto and "f14d07aa91" in texto and "«A» — cambian: LAU 10" in texto and "«B»" not in texto.split("## Tu tarea")[1].split("Para cada una")[0]
        (rv.rev / "t.yaml").write_text(yaml.safe_dump({"voces": bien}, allow_unicode=True), encoding="utf-8")
        return 0, 1.0
    rv.armero = armero_bueno
    r = rv.trabaja("indice/t.yaml", [("A", "LAU 10 (cambia)"), ("C", "LAU 10 (cambia)")])
    caso("encargo bien formado (motivo, ident y solo las voces de la lista) y resultado válido", r[1] is True and (rv.rev / "t.yaml").is_file(), r)
    def armero_malo(texto, ruta, nombre_log):
        (rv.rev / "t.yaml").write_text(yaml.safe_dump({"voces": [voz("A"), voz("B", nota="TOCADA"), voz("C")]}, allow_unicode=True), encoding="utf-8")
        return 0, 1.0
    rv.armero = armero_malo
    r = rv.trabaja("indice/t.yaml", [("A", "x"), ("C", "x")])
    caso("resultado inválido -> rechazado y apartado en rechazadas/ (no queda donde se integra)", r[1] is False and not (rv.rev / "t.yaml").exists() and (rv.rev / "rechazadas/t.yaml").is_file(), r)
    rv.armero = lambda *a: (1, 1.0)
    r = rv.trabaja("indice/t.yaml", [("A", "x")])
    caso("el Armero no entrega nada -> fallo explícito (sin fichero)", r[1] is False and r[2] == "sin fichero", r)

print(f"\n{'TODO VERDE' if not fallos else 'FALLOS: ' + str(fallos)}")
sys.exit(1 if fallos else 0)
