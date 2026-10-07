#!/usr/bin/env python3
"""Pruebas del motor del índice (indice.py): validación y caducidad POR ARTÍCULO CITADO (criterio del Armero). Sin git ni disco:
la línea base se inyecta como función. Uso: python3 scripts/test_indice.py"""
import sys
from pathlib import Path
AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import indice

fallos = []
def caso(nombre, cond, detalle=""):
    print(("  ok   " if cond else "  FALLA ") + nombre + ("" if cond else f"  -> {detalle}"))
    if not cond:
        fallos.append(nombre)

H = lambda s: indice.huella(dict(e=s, t="", b=""))
def norma(**arts):  # {clave: texto} -> estructura de la norma
    return dict(id="x", keys=set(arts), mapa={k: H(v) for k, v in arts.items()}, ruta="es/X.md")
def voz(cita, espejo="legalize-es@abc1234", vigilar=(), base=("LEC",)):
    return dict(voz="V", espejo=espejo, normas_base=list(base), vigilar=[dict(norma="LEC", articulo=a) for a in vigilar],
                remisiones=[dict(norma="LEC", articulo=a, tipo="regula", nota="n") for a in cita])
def base_de(**arts):
    m = {k: H(v) for k, v in arts.items()}
    return lambda s, c: m if c == "abc1234" else None

print("[caducidad por artículo citado — reglas a), b), c), d) del Armero]")
N0 = dict(a22="22 v1", a23="23 v1", a63="63 v1")  # texto en la línea base
B = base_de(**{"22": "22 v1", "23": "23 v1", "63": "63 v1"})
hoy = norma(**{"22": "22 v1", "23": "23 v1", "63": "63 v1"})
caso("nada cambió -> no caduca", indice.caducidad_voz(voz(["22", "63"]), {"LEC": hoy}, B) == [])
hoy = norma(**{"22": "22 v2", "23": "23 v1", "63": "63 v1"})
r = indice.caducidad_voz(voz(["22", "63"]), {"LEC": hoy}, B)
caso("a) cambia un artículo citado -> caduca y nombra cuál", r == [dict(n="LEC", k="22", r="cambia")], str(r))
r = indice.caducidad_voz(voz(["63"]), {"LEC": hoy}, B)
caso("cambia el 22 pero la voz solo cita el 63 -> NO caduca (el caso de la LEC de hoy)", r == [], str(r))
hoy = norma(**{"22": "22 v1", "63": "63 v1"})
r = indice.caducidad_voz(voz(["23"]), {"LEC": hoy}, B)
caso("b) un artículo citado ya no se encuentra -> caduca (falta)", r == [dict(n="LEC", k="23", r="falta")], str(r))
hoy = norma(**{"22": "22 v1", "22 bis": "nuevo", "23": "23 v1", "63": "63 v1"})
r = indice.caducidad_voz(voz(["22"]), {"LEC": hoy}, B)
caso("c) aparece un «22 bis» y la voz cita el 22 -> caduca (nuevo)", r == [dict(n="LEC", k="22 bis", r="nuevo")], str(r))
hoy = norma(**{"22": "22 v1", "63 bis": "nuevo", "23": "23 v1", "63": "63 v1"})
caso("c) un «63 bis» nuevo NO caduca una voz que solo cita el 22", indice.caducidad_voz(voz(["22"]), {"LEC": hoy}, B) == [])
hoy = norma(**{"22": "22 v1", "23": "23 v2", "63": "63 v1"})
r = indice.caducidad_voz(voz(["22"], vigilar=["23"]), {"LEC": hoy}, B)
caso("d) cambia un artículo de `vigilar[]` -> caduca y lo marca como vigilado", r == [dict(n="LEC", k="23", r="cambia", v="vigilar")], str(r))
caso("d) si el artículo de `vigilar[]` no cambia -> no caduca", indice.caducidad_voz(voz(["22"], vigilar=["63"]), {"LEC": norma(**{"22": "22 v1", "23": "23 v1", "63": "63 v1"})}, B) == [])
hoy = norma(**{"22": "22 v1", "23": "23 v1", "63": "63 v1"})
caso("línea base irreconstruible (commit desconocido) -> caduca por prudencia ('?')", indice.caducidad_voz(voz(["22"], espejo="legalize-es@deadbeef0"), {"LEC": hoy}, B) == [dict(n="LEC", r="?")])
caso("espejo ausente o mal formado -> caduca por prudencia ('?')", indice.caducidad_voz(voz(["22"], espejo="legalize-es"), {"LEC": hoy}, B) == [dict(r="?")])
caso("artículo que no existía en la línea base -> no se puede comparar ('?'), no se da por bueno", indice.caducidad_voz(voz(["99"]), {"LEC": norma(**{"99": "x"})}, B) == [dict(n="LEC", k="99", r="?")])
hoy = norma(**{"22": "22 v2", "23": "23 v1", "63": "63 v2"})
r = indice.caducidad_voz(voz(["22", "63"]), {"LEC": hoy}, B)
caso("varios artículos cambiados -> una razón por cada uno", [x["k"] for x in r] == ["22", "63"], str(r))

print("[aviso agregado para el Armero: cambios en artículos que ninguna voz cita]")
v1, v2 = voz(["22"]), dict(voz("63"), voz="W") if False else dict(voz(["63"]), voz="W")
hoy = norma(**{"22": "22 v1", "23": "23 v2", "63": "63 v1", "24": "nuevo"})
c = indice.cambios_norma([v1, v2], {"LEC": hoy}, B)
caso("artículo no citado que cambia + artículo nuevo -> un solo aviso por norma con ambos y con todas las voces", c == {"LEC": dict(articulos=["23", "24"], voces=["V", "W"])}, str(c))
hoy = norma(**{"22": "22 v2", "23": "23 v1", "63": "63 v1"})
caso("lo que cambia y SÍ cita alguna voz no va en el aviso (ya la caduca)", indice.cambios_norma([v1, v2], {"LEC": hoy}, B) == {})
caso("sin cambios -> sin aviso", indice.cambios_norma([v1], {"LEC": norma(**{"22": "22 v1", "23": "23 v1", "63": "63 v1"})}, B) == {})
hoy = norma(**{"22": "22 v1", "23": "23 v1"})
caso("artículo no citado derogado también se avisa", indice.cambios_norma([v1], {"LEC": hoy}, B) == {"LEC": dict(articulos=["63"], voces=["V"])})
caso("orden natural de artículos (2, 10, 22 bis, 22 ter)", sorted(["22 ter", "10", "2", "22 bis"], key=indice.orden_natural) == ["2", "10", "22 bis", "22 ter"])

print("[huella: el artículo entero, notas incluidas, sin ruido de espacios]")
base = dict(e="Artículo 22", t="Título", b="1. Texto.\n\n> <small>Nota de reforma</small>")
caso("misma sustancia con otros espacios/saltos -> misma huella", indice.huella(base) == indice.huella(dict(base, b="1.   Texto.\n\n\n> <small>Nota de reforma</small>")))
caso("cambia el texto -> otra huella", indice.huella(base) != indice.huella(dict(base, b="1. Texto distinto.\n\n> <small>Nota de reforma</small>")))
caso("cambia SOLO una nota de reforma -> otra huella (el Armero la incluye)", indice.huella(base) != indice.huella(dict(base, b="1. Texto.\n\n> <small>Otra nota</small>")))
caso("cambia el título -> otra huella", indice.huella(base) != indice.huella(dict(base, t="Otro título")))
caso("body como lista o como texto da la misma huella", indice.huella(dict(base, b=["1. Texto.", "", "> <small>Nota de reforma</small>"])) == indice.huella(base))

print("[validación]")
N = {"A": dict(id="a", keys={"1", "2", "da7", "49 bis", "22 quater"}, ruta="es/A.md"), "B": dict(id="b", keys={"1"}, ruta="es/B.md")}
ok = dict(voz="Ok", estado="provisional", espejo="legalize-es@abc1234", revisada_el="2026-10-07", revisor="armero", normas_base=["A"],
          remisiones=[dict(norma="A", articulo="da 7", tipo="regula", nota="n"), dict(norma="A", articulo="49 bis", tipo="conexa", nota="n"),
                      dict(norma="A", articulo="22 quáter", tipo="regula", nota="n")])
caso("voz correcta (da 7, 49 bis y «22 quáter» con tilde, como lo escribe el Armero)", indice.valida([ok], N) == [], str(indice.valida([ok], N)))
def con(**c): x = dict(ok); x.update(c); return x
e = indice.valida([con(remisiones=[dict(norma="A", articulo="999", tipo="regula", nota="n")])], N)
caso("artículo inexistente -> error que lo nombra", any("999" in x and "NO existe" in x for x in e), str(e))
caso("norma desconocida en una remisión -> error", any("desconocida" in x for x in indice.valida([con(remisiones=[dict(norma="ZZ", articulo="1", tipo="regula", nota="n")])], N)))
caso("remisión a una norma que no está en normas_base -> error (el vigía no la vigilaría)", any("normas_base" in x for x in indice.valida([con(remisiones=[dict(norma="B", articulo="1", tipo="regula", nota="n")])], N)))
caso("norma_base desconocida -> error", any("norma_base" in x for x in indice.valida([con(normas_base=["ZZ"])], N)))
caso("tipo no válido -> error", any("tipo" in x for x in indice.valida([con(remisiones=[dict(norma="A", articulo="1", tipo="menciona", nota="n")])], N)))
caso("estado no válido -> error", any("estado" in x for x in indice.valida([con(estado="bueno")], N)))
caso("voz duplicada -> error", any("duplicada" in x for x in indice.valida([ok, dict(ok)], N)))
caso("falta revisor -> error", any("revisor" in x for x in indice.valida([con(revisor="")], N)))
caso("nota de más de 160 caracteres -> error", any("larga" in x for x in indice.valida([con(remisiones=[dict(norma="A", articulo="1", tipo="regula", nota="x" * 161)])], N)))
caso("`vigilar` a un artículo inexistente -> error", any("vigilar" in x for x in indice.valida([con(vigilar=[dict(norma="A", articulo="500")])], N)))
caso("`vigilar` y `fuera_de_la_herramienta` (campos nuevos del Armero) se aceptan", indice.valida([con(vigilar=[dict(norma="A", articulo="2")], fuera_de_la_herramienta=["Reglamento (UE) 1215/2012"])], N) == [])
caso("`fuera_de_la_herramienta` que no es lista -> error (no se cae la voz entera en silencio)", any("lista" in x for x in indice.valida([con(fuera_de_la_herramienta="texto")], N)))

print("[utilidades]")
caso("clave_articulo: «da 7»->da7, «DT 2»->dt2, «22 quáter»->«22 quater», «49 bis» y «282» intactos", [indice.clave_articulo(x) for x in ("da 7", "DT 2", "22 quáter", "49 bis", "282")] == ["da7", "dt2", "22 quater", "49 bis", "282"])
casos = {"1": 1, "1.2.º": 1, "2.a)": 2, "3, párrafo 2.º": 3, "4.º": None, "2.º": None, "": None, None: None, "1.7.º": 1, "10": 10, "5.ª": None, "1.1.ª": 1}
caso("apartado_numerico (ordinales «4.º», «5.ª» no son apartado)", all(indice.apartado_numerico(k) == x for k, x in casos.items()), str({k: indice.apartado_numerico(k) for k in casos}))
caso("slug: «Requisito de procedibilidad (MASC)» -> requisito-de-procedibilidad-masc", indice.slug("Requisito de procedibilidad (MASC)") == "requisito-de-procedibilidad-masc")

print(f"\n{'TODO VERDE' if not fallos else 'FALLOS: ' + str(fallos)}")
sys.exit(1 if fallos else 0)
