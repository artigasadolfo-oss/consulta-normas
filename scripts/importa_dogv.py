#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
importa_dogv.py — Convierte una disposición guardada en ~/Documents/iA/LEYES/DOGV/ (texto verbatim del DOGV)
en un fichero del corpus consolidado (legalize-es/es-vc/<CVE>.md) con el MISMO formato que el resto:
cabecera YAML + «# título» + cabeceras «######» de artículo/disposición.

Pensado para normas valencianas que SOLO salen en el DOGV (no en el BOE) y que no están en el espejo.
Cada norma importada así NO se actualiza sola: el vigía (vigila_consulta_normas.py) consulta su estado en la API
del DOGV y avisa si deja de constar VIGENTE o aparece una consolidación.

Ajustes sobre el texto del DOGV (se declaran en la propia cabecera del fichero):
  - se añaden las marcas de estructura (######) y se quita la cabecera de grupo «DISPOSICIONES FINALES»;
  - la «Ñ» MAYÚSCULA dentro de una palabra en minúsculas (defecto de digitalización del DOGV: «tamaÑo») pasa a «ñ».
Todo lo demás es literal.

Uso:  python3 importa_dogv.py "<fichero de la carpeta DOGV>" [--destino <carpeta es-vc>] [--estado VIGENTE]
"""
import argparse, datetime as dt, re, sys
from pathlib import Path

ES_VC = Path.home() / "Documents/iA/LEYES/legalize-es/es-vc"
ART = re.compile(r"^Art[ií]culo\s+(\S+?)\.\s")
GRUPO = re.compile(r"^DISPOSICIONES\s+(ADICIONALES|TRANSITORIAS|FINALES|DEROGATORIAS)\s*$")
TIPO = {"ADICIONALES": "adicional", "TRANSITORIAS": "transitoria", "FINALES": "final", "DEROGATORIAS": "derogatoria"}
ORDINAL = re.compile(r"^(Única|Unica|Primera|Segunda|Tercera|Cuarta|Quinta|Sexta|Séptima|Septima|Octava|Novena|Décima|Decima)\s*$")
ENE = re.compile(r"(?<=[a-záéíóúü])Ñ(?=[a-záéíóúü])")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fichero")
    ap.add_argument("--destino", default=str(ES_VC))
    ap.add_argument("--estado", default="VIGENTE", help="estado verificado en el portal (VIGENTE/DEROGADA)")
    a = ap.parse_args()
    txt = Path(a.fichero).read_text(encoding="utf-8")
    cab, _, cuerpo = txt.partition("\n---\n")
    meta = {}
    for ln in cab.splitlines():
        k, _, v = ln.partition(":")
        meta[k.strip()] = v.strip()
    m_id = re.search(r"/disposicion/(\d+)", meta.get("Fuente", ""))
    cve = meta.get("Referencia oficial (CVE)", "")
    if not (m_id and cve):
        sys.exit("La cabecera del fichero no trae Fuente/CVE: guárdalo con `dogv.py texto --id N --guardar`.")
    lineas = [l.rstrip() for l in cuerpo.split("\n")]
    while lineas and not lineas[0].strip():
        lineas.pop(0)
    titulo_dogv = lineas[0].strip()
    titulo = re.sub(r"\.$", "", re.sub(r"^DECRETO", "Decreto", titulo_dogv))
    cuerpo_l = lineas[1:]
    sale, tipo, n_ene = [f"# {titulo}", ""], None, 0
    for ln in cuerpo_l:
        if not ln.strip():
            continue
        nuevo, k = ENE.subn("ñ", ln)
        n_ene += k
        ln = nuevo
        mg = GRUPO.match(ln.strip())
        if mg:
            tipo = TIPO[mg.group(1)]
            continue
        if tipo and ORDINAL.match(ln.strip()):
            sale += [f"###### Disposición {tipo} {ln.strip().lower()}.", ""]
            continue
        if ART.match(ln):
            sale += [f"###### {ln.strip()}", ""]
            continue
        sale += [ln.strip(), ""]
    fecha_pub = re.search(r"/datos/(\d{4})/(\d{2})/(\d{2})/", meta.get("PDF oficial", ""))
    pub = "-".join(fecha_pub.groups()) if fecha_pub else ""
    oficial = re.search(r"Decreto\s+(\d+/\d+),\s+de\s+(\d+)\s+de\s+(\w+)", titulo)
    hoy = dt.date.today().isoformat()
    yaml = [
        "---",
        f'title: "{titulo}"',
        f'identifier: "{cve}"',
        'country: "es"',
        'rank: "decreto"',
        f'publication_date: "{pub}"',
        f'last_updated: "{pub}"',
        f'status: "{"in_force" if a.estado == "VIGENTE" else "repealed"}"',
        f'source: "{meta.get("Permalink", "")}"',
        'department: "Comunitat Valenciana"',
        'jurisdiction: "es-vc"',
        f'pdf_url: "{meta.get("PDF oficial", "")}"',
        f'official_number: "{oficial.group(1) if oficial else ""}"',
        'official_journal: "Diari Oficial de la Generalitat Valenciana"',
        'consolidation_status: "No consolidada (solo existe la redacción original)"',
        'scope: "Autonómico"',
        f'url_html_consolidada: "{meta.get("Permalink", "")}"',
        f'dogv_id: "{m_id.group(1)}"',
        f'estado_verificado: "{a.estado} según el portal legislativo del DOGV, consultado el {hoy}"',
        f'nota_local: "Importada a mano el {hoy} desde la API oficial del DOGV (no procede del espejo legalize-es y no se actualiza sola). '
        'Ajustes sobre el texto del DOGV: marcas de estructura (######); cabecera de grupo DISPOSICIONES FINALES suprimida; '
        f'{n_ene} «Ñ» mayúsculas dentro de palabra pasadas a «ñ» (defecto de digitalización). Resto literal."',
        "---",
        "",
    ]
    destino = Path(a.destino) / f"{cve}.md"
    destino.write_text("\n".join(yaml + sale).rstrip() + "\n", encoding="utf-8")
    print(f"escrito {destino}  ({len(sale)//2} bloques; {n_ene} Ñ corregidas)")


if __name__ == "__main__":
    main()
