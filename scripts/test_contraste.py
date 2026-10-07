#!/usr/bin/env python3
"""Pruebas del contraste con boe.es (scripts/contraste_boe.py). XML sintético con la forma real de la API del BOE: sin red."""
import datetime as dt
import sys
from pathlib import Path
AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI)); sys.path.insert(0, str(AQUI / "scripts"))
import contraste_boe as c

fallos = []
def caso(n, cond, det=""):
    print(("  ok   " if cond else "  FALLA ") + n + ("" if cond else f"  -> {det}"))
    if not cond: fallos.append(n)

def ver(vig, pub, texto, id_norma="X", extra=""):
    return f'<version id_norma="{id_norma}" fecha_publicacion="{pub}" fecha_vigencia="{vig}"><p class="articulo">{texto[0]}</p>' + "".join(f'<p class="parrafo">{t}</p>' for t in texto[1:]) + extra + "</version>"
def doc(*bloques):
    return "<response><data><texto>" + "".join(bloques) + "</texto></data></response>"
def bloque(id_, titulo, *versiones, tipo="precepto"):
    return f'<bloque id="{id_}" tipo="{tipo}" titulo="{titulo}">' + "".join(versiones) + "</bloque>"
HOY = dt.date(2026, 10, 7)

print("[versión vigente: la de MAYOR PUBLICACIÓN entre las ya en vigor, no la de mayor vigencia ni la última del documento]")
xml = doc(bloque("a1", "Artículo 1",
    ver("20010108", "20000108", ["Artículo 1. Objeto.", "Texto original."]),
    ver("20250403", "20250103", ["Artículo 1. Objeto.", "Texto reformado en 2025."]),
    ver("20250228", "20250228", ["Artículo 1. Objeto.", "Texto tras sentencia del TC."])))   # publicada DESPUÉS, vigente ANTES: es la buena
vig, fut = c.bloques_boe(xml, HOY)
caso("elige la publicada más tarde (caso art. 439 LEC y STC 26/2025)", vig["1"] == c.esqueleto("Objeto. Texto tras sentencia del TC."), vig)
caso("sin reformas futuras -> sin aviso temprano", fut == {})

print("[reformas que entran en vigor mañana: aviso temprano]")
xml = doc(bloque("a22", "Artículo 22",
    ver("20250403", "20250103", ["Artículo 22. Terminación.", "1. Texto."]),
    ver("20261008", "20261007", ["Artículo 22. Terminación.", "1. Texto.", "6. Apartado nuevo."])))
vig, fut = c.bloques_boe(xml, HOY)
caso("el texto de HOY es el antiguo", vig["22"] == c.esqueleto("Terminación. 1. Texto."))
caso("avisa de la reforma del 08-10-2026 como futura", fut == {"22": "2026-10-08"}, fut)
vig2, fut2 = c.bloques_boe(xml, dt.date(2026, 10, 8))
caso("el día que entra en vigor pasa a ser el vigente y deja de ser futura", vig2["22"].endswith(c.esqueleto("6. Apartado nuevo.")) and fut2 == {})
xml = doc(bloque("a5", "Artículo 5", ver("20250101", "20250101", ["Artículo 5. X.", "Igual."]), ver("20270101", "20261201", ["Artículo 5. X.", "Igual."])))
caso("versión futura con el mismo texto -> no es aviso", c.bloques_boe(xml, HOY)[1] == {})

print("[claves y texto: el atributo `titulo` va en letra; el primer párrafo lleva la cifra]")
xml = doc(bloque("aquintobis", "Artículo quinto bis", ver("20250101", "20250101", ["Artículo 5 bis.", "Texto."])),
          bloque("ada1", "Disposición adicional primera", ver("20250101", "20250101", ["Disposición adicional primera. Algo.", "Texto da."])),
          bloque("a31", "Artículo treinta y uno", ver("20250101", "20250101", ["Artículo 31.", "Texto 31."])),
          bloque("a283", "Artículo 283 bis a)", ver("20250101", "20250101", ["Artículo 283 bis a).", "Texto 283."])))
vig, _ = c.bloques_boe(xml, HOY)
caso("«Artículo quinto bis» -> clave «5 bis»", "5 bis" in vig, list(vig))
caso("«Disposición adicional primera» -> da1", "da1" in vig, list(vig))
caso("«Artículo treinta y uno» -> 31", "31" in vig, list(vig))
caso("«283 bis a)» -> «283 bis a» (como el espejo)", "283 bis a" in vig, list(vig))
caso("clave_de_titulo: «Art 1» (CC) -> 1; «Artículo único» -> unico", c.clave_de_titulo("Art 1") == "1" and c.clave_de_titulo("Artículo único") == "unico")

print("[ruido que NO debe contar]")
a = c.esqueleto("Artículo 22 quáter. Plazo. 1.º Dentro de «cinco» días — art. 3.")
caso("tildes, signos, comillas, ordinales y espacios no cuentan", a == c.esqueleto("articulo 22 quater plazo 1 dentro de cinco dias art 3"))
caso("una cifra distinta SÍ cuenta", c.esqueleto("plazo de cinco días") != c.esqueleto("plazo de diez días"))
caso("una palabra distinta SÍ cuenta (padres / progenitores)", c.esqueleto("los padres que pretendan") != c.esqueleto("los progenitores que pretendan"))
caso("fórmula promulgatoria final del espejo se ignora", c.esqueleto("Texto final. Por tanto, mando a todos los españoles, particulares y autoridades…") == c.esqueleto("Texto final."))
xml = doc(bloque("a1", "Artículo 1", ver("20250101", "20250101", ["Artículo 1. T.", "Texto con ordinal 1.<sup>a</sup> y nota."], extra='<blockquote><p class="nota_pie">Se modifica por X.</p></blockquote>')))
caso("`<sup>a</sup>` = ª y las notas de reforma (blockquote) no cuentan", c.bloques_boe(xml, HOY)[0]["1"] == c.esqueleto("T. Texto con ordinal 1.ª y nota."))
chunks = [dict(k="1", e="Artículo 1", t="T.", b="Texto con ordinal 1.<sup>a</sup> y nota.\n\n> <small>Se modifica por X.</small>\n\n> Redacción anterior:\n\n###### \"Artículo 1. Viejo.\n\n> texto viejo\n")]
caso("el espejo: sin notas «>», sin rótulo «Redacción anterior» y sin el rótulo del artículo", c.bloques_espejo(chunks)["1"] == c.esqueleto("T. Texto con ordinal 1.ª y nota."), c.bloques_espejo(chunks))

print("[comparación]")
B = {"1": "aaa", "2": "bbb", "3": "ccc", "4": "ddd"}; E = {"1": "aaa", "2": "XXX", "3": "ccc", "9": "zzz"}
r = c.compara(B, E)
caso("distintos / solo boe / solo espejo", r["distintos"] == ["2"] and r["solo_boe"] == ["4"] and r["solo_espejo"] == ["9"] and r["comparados"] == 3, r)
con = {"2": [c.sha("bbb"), c.sha("XXX"), "motivo"], "_solo_boe": ["4"]}
r = c.compara(B, E, con)
caso("una diferencia conocida (huellas de ambos textos) se acepta", r["distintos"] == [] and r["aceptadas"] == 1 and r["solo_boe"] == [], r)
r = c.compara(B, dict(E, **{"2": "YYY"}), con)
caso("si cambia el texto del espejo, la excepción deja de valer y vuelve a avisar", r["distintos"] == ["2"], r)
r = c.compara(dict(B, **{"2": "NUEVO"}), E, con)
caso("si cambia el texto de boe.es, la excepción también deja de valer", r["distintos"] == ["2"], r)

print(f"\n{'TODO VERDE' if not fallos else 'FALLOS: ' + str(fallos)}")
sys.exit(1 if fallos else 0)
