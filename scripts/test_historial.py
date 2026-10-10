#!/usr/bin/env python3
"""Pruebas de scripts/historial_boe.py (redacciones sucesivas de cada artículo). XML sintético con la forma real de la API del BOE: sin red."""
import datetime as dt
import sys
from pathlib import Path
AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI)); sys.path.insert(0, str(AQUI / "scripts"))
import historial_boe as h
import contraste_boe as c

fallos = []
def caso(n, cond, det=""):
    print(("  ok   " if cond else "  FALLA ") + n + ("" if cond else f"  -> {det}"))
    if not cond: fallos.append(n)

def ver(vig, pub, parrafos, id_norma="X"):
    return (f'<version id_norma="{id_norma}" fecha_publicacion="{pub}" fecha_vigencia="{vig}"><p class="articulo">{parrafos[0]}</p>'
            + "".join(f'<p class="parrafo">{t}</p>' for t in parrafos[1:]) + "</version>")
def doc(*b): return "<response><data><texto>" + "".join(b) + "</texto></data></response>"
def bloque(i, t, *v): return f'<bloque id="{i}" tipo="precepto" titulo="{t}">' + "".join(v) + "</bloque>"
HOY = dt.date(2026, 10, 10)

print("[tramos de vigencia: desde / hasta contiguos, el último abierto]")
xml = doc(bloque("a9", "Artículo 9",
    ver("19950101", "19941125", ["Artículo 9. Plazo mínimo.", "1. Cinco años."], "BOE-A-1994-26003"),
    ver("20130606", "20130605", ["Artículo 9. Plazo mínimo.", "1. Tres años."], "BOE-A-2013-5941"),
    ver("20190306", "20190305", ["Artículo 9. Plazo mínimo.", "1. Cinco años otra vez."], "BOE-A-2019-3108")))
t = h.historial(xml, HOY)["9"]
caso("tres tramos", len(t) == 3, t)
caso("desde/hasta contiguos (el día anterior al siguiente)", [(x["desde"], x["hasta"]) for x in t] == [("1995-01-01", "2013-06-05"), ("2013-06-06", "2019-03-05"), ("2019-03-06", None)], [(x["desde"], x["hasta"]) for x in t])
caso("cada tramo lleva su norma y su texto sin rótulo", t[1]["norma"] == "BOE-A-2013-5941" and t[1]["parrafos"] == ["1. Tres años."] and t[1]["titulo"] == "Plazo mínimo.", t[1])
caso("a_fecha: un contrato de 01-10-2018 se rige por el texto de 2013", h.a_fecha(t, "2018-10-01")["parrafos"] == ["1. Tres años."])
caso("a_fecha: el día exacto de la reforma ya rige la nueva y la víspera la anterior",
     h.a_fecha(t, "2019-03-06")["parrafos"] == ["1. Cinco años otra vez."] and h.a_fecha(t, "2019-03-05")["parrafos"] == ["1. Tres años."])
caso("a_fecha: antes de que existiera el artículo -> None (no existía)", h.a_fecha(t, "1994-12-31") is None)

print("[orden por PUBLICACIÓN, no por vigencia (caso LEC 439: sentencia del TC publicada después y vigente antes)]")
xml = doc(bloque("a1", "Artículo 1",
    ver("20010108", "20000108", ["Artículo 1. Objeto.", "Texto original."]),
    ver("20250403", "20250103", ["Artículo 1. Objeto.", "Texto reformado en 2025."]),
    ver("20250228", "20250228", ["Artículo 1. Objeto.", "Texto tras sentencia del TC."])))
t = h.historial(xml, HOY)["1"]
caso("tras el 28-02-2025 rige la sentencia y el 03-04-2025 NO abre tramo (la publicada después manda)", [(x["desde"], x["parrafos"][0]) for x in t] == [("2001-01-08", "Texto original."), ("2025-02-28", "Texto tras sentencia del TC.")], t)
caso("coincide con la regla del contraste (misma versión vigente hoy)", t[-1]["sk"] == c.bloques_boe(xml, HOY)[0]["1"], (t[-1]["sk"], c.bloques_boe(xml, HOY)[0]))

print("[versión SIN fecha de vigencia (cadena de RDL, caso LAU 10): no rige antes de publicarse]")
xml = doc(bloque("a10", "Artículo 10",
    ver("19950101", "19941125", ["Artículo 10. Prórroga.", "1. Texto de 1994."]),
    ver("20130606", "20130605", ["Artículo 10. Prórroga.", "1. Texto de 2013: tres años."]),
    ver("", "20261007", ["Artículo 10. Prórroga.", "1. Texto de 2026 sin vigencia."])))
t = h.historial(xml, HOY)["10"]
caso("al 01-10-2018 rige el de 2013 (NO el de 2026, que no tiene fecha de vigencia)", h.a_fecha(t, "2018-10-01")["parrafos"] == ["1. Texto de 2013: tres años."], t)
caso("el tramo sin vigencia arranca el día de su publicación y se marca incierto", t[-1]["desde"] == "2026-10-07" and t[-1]["incierta"] is True and not t[0]["incierta"], t)
vs_ing = [((v.get("fecha_vigencia") or "00000000"), k, v) for k, v in enumerate(c.ET.fromstring(xml).iter("version"))]
ingenua = max([x for x in vs_ing if x[0] <= "20181001"], key=lambda x: (x[2].get("fecha_publicacion"), x[0], x[1]))[2]
caso("control del caso: la regla ingenua (vigencia vacía = desde siempre) SÍ daría la redacción de 2026 al 01-10-2018", "2026" in ingenua.findall("p")[1].text, ingenua.findall("p")[1].text)

print("[reformas que no tocan este artículo, artículo nuevo, reformas futuras]")
xml = doc(bloque("a5", "Artículo 5",
    ver("20000101", "19991231", ["Artículo 5. X.", "Igual."], "N1"),
    ver("20100101", "20091231", ["Artículo 5. X.", "Igual."], "N2"),      # reforma de otra cosa: mismo texto
    ver("20200101", "20191231", ["Artículo 5. X.", "Cambia."], "N3"),
    ver("20270101", "20261201", ["Artículo 5. X.", "Futuro."], "N4")),    # futura respecto a HOY
    bloque("a6", "Artículo 6", ver("20180101", "20171231", ["Artículo 6. Nuevo.", "Apareció en 2018."])))
hh = h.historial(xml, HOY)
caso("dos versiones consecutivas con el mismo texto forman UN tramo", [(x["desde"], x["hasta"]) for x in hh["5"]] == [("2000-01-01", "2019-12-31"), ("2020-01-01", None)], hh["5"])
caso("la reforma futura NO es historia (la cubre contraste_boe.futuras_detalle)", all("Futuro" not in " ".join(x["parrafos"]) for x in hh["5"]))
caso("un artículo nuevo no existe antes de su fecha", h.a_fecha(hh["6"], "2017-12-31") is None and h.a_fecha(hh["6"], "2018-01-01")["parrafos"] == ["Apareció en 2018."])
caso("el día que entra en vigor la futura pasa a ser el último tramo", h.a_fecha(h.historial(xml, dt.date(2027, 1, 1))["5"], "2027-01-01")["parrafos"] == ["Futuro."])

print("[norma con RD de aprobación delante (LH, TRLC): la clave repetida es del RD la primera vez y de la norma la segunda]")
xml_rd = doc(bloque("rd1", "Artículo 1", ver("19460101", "19460101", ["Artículo 1.", "Del RD: aprueba el texto."])),
          bloque("l1", "Artículo 1", ver("19460101", "19460101", ["Artículo 1.", "De la Ley: texto propio."]), ver("20000101", "19991231", ["Artículo 1.", "De la Ley: reformado."])),
          bloque("l2", "Artículo 2", ver("19460101", "19460101", ["Artículo 2.", "Solo de la Ley."])))
hr = h.historial(xml_rd, HOY, rd_duplicados=True)
caso("la primera aparición pasa a «rd-1» y la segunda queda como «1»", sorted(hr) == ["1", "2", "rd-1"] and hr["rd-1"][0]["parrafos"] == ["Del RD: aprueba el texto."] and hr["1"][-1]["hasta"] is None, sorted(hr))
caso("el historial de «1» es el de la norma (2 tramos), no el del RD", len(hr["1"]) == 2 and hr["1"][0]["parrafos"] == ["De la Ley: texto propio."], hr["1"])
caso("coincide con las claves y el vigente de bloques_boe con la misma opción", {k: v[-1]["sk"] for k, v in hr.items()} == c.bloques_boe(xml_rd, HOY, rd_duplicados=True)[0])
caso("sin la opción la segunda aparición no pisa a la primera (como en el contraste)", sorted(h.historial(xml_rd, HOY)) == ["1", "2"] and h.historial(xml_rd, HOY)["1"][0]["parrafos"] == ["Del RD: aprueba el texto."])

print("[exportación compacta]")
ex = h.para_exportar(h.historial(xml, HOY)["5"])
caso("los tramos cerrados llevan el texto y el vigente NO (ya va en el bloque)", "parrafos" in ex[0] and "parrafos" not in ex[-1] and ex[-1]["hasta"] is None, ex)
caso("sin tramos inciertos no aparece la marca", all("incierta" not in x for x in ex))

print(f"\n{'TODO VERDE' if not fallos else 'FALLOS: ' + str(fallos)}")
sys.exit(1 if fallos else 0)
