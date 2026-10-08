#!/usr/bin/env python3
"""Pruebas del motor de las fórmulas de sala (formulas.py). Sin git ni disco: la línea base se inyecta. Uso: python3 scripts/test_formulas.py"""
import sys
from pathlib import Path
AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import formulas, indice

fallos = []
def caso(n, c, d=""):
    print(("  ok   " if c else "  FALLA ") + n + ("" if c else f"  -> {d}"))
    if not c: fallos.append(n)

H = lambda s: indice.huella(dict(e=s, t="", b=""))
def norma(**arts):
    return dict(id="lec", keys=set(arts), mapa={k: H(v) for k, v in arts.items()}, ruta="es/X.md")
N = {"LEC": norma(**{"302": "t302", "303": "t303", "368": "t368", "22 bis": "t22b"})}
B = lambda s, c: {"302": H("t302"), "303": H("t303"), "368": H("t368")} if c == "abc1234" else None
ok = dict(situacion="Pregunta con valoración", grupo="Interrogatorio de parte", momento=["juicio"],
          formula="«Con la venia, Señoría: la pregunta incorpora una valoración.»", pide="Que se tenga por no formulada.",
          aviso="Si no se formula la objeción en el acto, no cabe después.",
          bases=[dict(norma="LEC", articulo="302", apartado="1"), dict(norma="LEC", articulo="303")],
          estado="vigente", espejo="legalize-es@abc1234", revisada_el="2026-10-08", revisor="armero")
def con(**c): x = dict(ok); x.update(c); return x
def errs(*fs): return formulas.valida(list(fs), N)

print("[validación]")
caso("fórmula correcta -> sin errores", errs(ok) == [], str(errs(ok)))
caso("base a un artículo inexistente -> error que lo nombra", any("999" in e and "NO existe" in e for e in errs(con(bases=[dict(norma="LEC", articulo="999")]))))
caso("norma desconocida -> error", any("desconocida" in e for e in errs(con(bases=[dict(norma="ZZ", articulo="1")]))))
caso("momento no válido -> error", any("momento" in e for e in errs(con(momento=["vista"]))))
caso("momento vacío o no lista -> error", any("momento" in e for e in errs(con(momento=[]))) and any("momento" in e for e in errs(con(momento="juicio"))))
caso("falta fórmula -> error", any("formula" in e for e in errs(con(formula=""))))
caso("fórmula demasiado larga para decirla en sala -> error", any("demasiado larga" in e for e in errs(con(formula="x" * 601))))
caso("falta grupo -> error", any("grupo" in e for e in errs(con(grupo=""))))
caso("sin bases y sin «no consta en norma» -> error", any("al menos una" in e for e in errs(con(bases=[]))))
caso("sin bases pero con «no consta en norma» (uso forense) -> válida", errs(con(bases=[], no_consta_en_norma=["Práctica forense"])) == [])
caso("situación duplicada -> error", any("duplicada" in e for e in errs(ok, dict(ok))))
caso("estado no válido -> error", any("estado" in e for e in errs(con(estado="bueno"))))
caso("falta revisor -> error", any("revisor" in e for e in errs(con(revisor=""))))
caso("base mal formada (sin artículo) -> error", any("mal formada" in e for e in errs(con(bases=[dict(norma="LEC")]))))
caso("`vigilar` a un artículo inexistente -> error", any("vigilar" in e for e in errs(con(vigilar=[dict(norma="LEC", articulo="500")]))))

print("[compilación y caducidad por artículo citado]")
r = formulas.compila(AQUI / "formulas_inexistente", N, B)
caso("sin carpeta o sin fórmulas -> None", r is None)
v = formulas.a_voz(ok)
caso("la pseudo-voz deriva `normas_base` de las bases y vigilar", v["normas_base"] == ["LEC"] and len(v["remisiones"]) == 2 and v["remisiones"][0]["apartado"] == "1")
caso("nada cambió -> no caduca", indice.caducidad_voz(v, N, B) == [])
N2 = {"LEC": norma(**{"302": "t302 NUEVO", "303": "t303", "368": "t368"})}
r = indice.caducidad_voz(v, N2, B)
caso("cambia un artículo citado -> caduca y nombra cuál", r == [dict(n="LEC", k="302", r="cambia")], str(r))
N3 = {"LEC": norma(**{"302": "t302", "303": "t303", "368": "t368 NUEVO"})}
caso("cambia un artículo NO citado -> no caduca", indice.caducidad_voz(v, N3, B) == [])

print("[carga desde disco (carpeta temporal) y salida compacta]")
import tempfile, yaml
with tempfile.TemporaryDirectory() as tmp:
    (Path(tmp) / "a.yaml").write_text(yaml.safe_dump(dict(version_formulas="0.1", aviso_general="Orientativo.", formulas=[ok]), allow_unicode=True), encoding="utf-8")
    out = formulas.compila(tmp, N, B)
    f = out["f"][0]
    caso("compila: versión, aviso y momentos", out["version"] == "0.1" and out["aviso"] == "Orientativo." and "juicio" in out["momentos"])
    caso("compila: slug, bases con apartado numérico, estado efectivo", f["s"] == "pregunta-con-valoracion" and f["b"][0] == dict(n="lec", k="302", ap="1", a=1) and f["es"] == "vigente", str(f))
    N4 = {"LEC": norma(**{"302": "t302 NUEVO", "303": "t303", "368": "t368"})}
    caso("compila: si cambia un artículo citado, la fórmula sale caducada", formulas.compila(tmp, N4, B)["f"][0]["es"] == "caducada")
    (Path(tmp) / "b.yaml").write_text(yaml.safe_dump(dict(formulas=[con(situacion="Otra situación", bases=[dict(norma="LEC", articulo="999")])]), allow_unicode=True), encoding="utf-8")
    try:
        formulas.compila(tmp, N, B); caso("compila: una base inexistente FALLA la compilación", False, "no falló")
    except SystemExit as e:
        caso("compila: una base inexistente FALLA la compilación", "FÓRMULAS DE SALA NO VÁLIDAS" in str(e) and "999" in str(e))

print(f"\n{'TODO VERDE' if not fallos else 'FALLOS: ' + str(fallos)}")
sys.exit(1 if fallos else 0)
