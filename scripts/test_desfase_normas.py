#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de las correcciones del 10-10-2026 («desfase de las normas»): texto citado dentro de las disposiciones y comparador con el BOE.
Todo con texto sintético y sin red.
Uso: python3 scripts/test_desfase_normas.py            (sabotaje: copiar build.py / contraste_boe.py antiguos en una carpeta y apuntar APP_DIR)"""
import os
import sys
from pathlib import Path

AQUI = Path(os.environ.get("APP_DIR") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / "scripts"))
import build  # noqa: E402
import contraste_boe as C  # noqa: E402

fallos = []


def caso(nombre, cond, detalle=""):
    print(("  ok   " if cond else "  FALLA ") + nombre + ("" if cond else f"  -> {detalle}"))
    if not cond:
        fallos.append(nombre)


def parsea(texto, **extra):
    cfg = dict(id="x", boe="BOE-A-0000-0", sigla="X", corto="X", **extra)
    chunks, _ = build.parse_norma(cfg, texto.split("\n"))
    return {c["k"]: c for c in chunks}


def cuerpo(c):
    return c["b"] if isinstance(c["b"], str) else "\n".join(c["b"])


LEY = """###### Artículo 1. Uno.

Texto uno.

###### Disposición final undécima. Modificación de la Ley del Notariado.

Uno. Se introduce un nuevo Título VII, con el siguiente contenido:

## «TÍTULO VII. Intervención de los Notarios

### CAPÍTULO I. Reglas generales

    Artículo 49.

    Los Notarios intervendrán en los expedientes especiales.

### Sección 2.ª De la celebración

    Artículo 50.

    Texto citado del 50.

###### Disposición final duodécima. Modificación de la Ley Hipotecaria.

Uno. El párrafo primero del artículo 14 queda redactado como sigue.

###### Disposición final decimotercera. Entrada en vigor.

Texto trece.
"""

print("[parser: un rótulo de estructura DENTRO de una disposición es texto citado, no estructura de la norma]")
ch = parsea(LEY)
caso("df11 conserva el rótulo «CAPÍTULO I» y el texto citado del Título VII", "CAPÍTULO I. Reglas generales" in cuerpo(ch["df11"]) and "Los Notarios intervendrán" in cuerpo(ch["df11"]) and "Texto citado del 50" in cuerpo(ch["df11"]), cuerpo(ch["df11"])[:300])
caso("df12 NO arrastra el texto citado de la df11", "Notarios intervendrán" not in cuerpo(ch["df12"]) and "párrafo primero del artículo 14" in cuerpo(ch["df12"]), cuerpo(ch["df12"])[:300])
caso("df12 y df13 no heredan un «Capítulo» falso en su ubicación", all("CAPÍTULO I" not in (ch[k].get("s") or "") and "Sección 2" not in (ch[k].get("s") or "") for k in ("df12", "df13")), str({k: ch[k].get("s") for k in ("df12", "df13")}))
caso("df13 sigue siendo su propia disposición", "Texto trece." in cuerpo(ch["df13"]), cuerpo(ch["df13"]))
# control: la estructura propia de la norma, entre artículos, SIGUE siendo estructura
ctl = parsea("###### Artículo 1. Uno.\n\nTexto.\n\n### CAPÍTULO II. Otro\n\n###### Artículo 2. Dos.\n\nTexto dos.\n")
caso("control: un «CAPÍTULO» entre artículos sigue abriendo estructura (no se traga como texto)", "CAPÍTULO II" in (ctl["2"].get("s") or "") and "CAPÍTULO II" not in cuerpo(ctl["1"]), str(ctl["2"].get("s")))
# control: las normas con RD de aprobación delante (previo_rdl): tras las disposiciones del RD empieza el texto aprobado
rd = parsea("###### Disposición final única. Entrada en vigor.\n\nTexto del RD.\n\n## TÍTULO I. Del texto aprobado\n\n###### Artículo 1. Uno.\n\nTexto uno.\n", previo_rdl="RD 1/2000")
caso("control: con previo_rdl, el TÍTULO que sigue a la disposición del RD SÍ es estructura", "TÍTULO I" in (rd["1"].get("s") or "") and "TÍTULO I" not in cuerpo(rd["rd-dfu"]), str(rd["1"].get("s")))

print("[comparador con el BOE: qué entra en el «esqueleto» del espejo]")
def esp(k, texto, e="Artículo " ):
    return dict(k=k, e=(e + k if e.endswith(" ") else e), t="", b=texto.split("\n"), s="", r=[])

art = esp("517", "Penas del art. 515 <sup>(*)</sup>:\n\n> (*) La remisión al 515 se entiende hecha a los actuales números 1 a 4. [Ref. BOE-A-2015-3439#aunico](https://www.boe.es/x)\n\n> <small>Se modifica por la LO 4/2000.</small>")
r = C.bloques_espejo([art])["517"]
caso("art.: la nota al pie «(*)» del BOE SÍ cuenta (sin la URL del enlace)", "laremisional515seentiendehecha" in r and "boe" in r and "httpswww" not in r, r)
caso("art.: las notas de reforma («> <small>Se modifica…») NO cuentan", "semodificaporlalo" not in r, r)
disp = esp("df4", "Texto.\n\n> (*) Táchese lo que no proceda.", e="Disposición final cuarta")
caso("disp.: una nota «(*)» de un anexo NO cuenta (TRLGDCU df4: «Táchese lo que no proceda» no es texto del BOE)", "tachese" not in C.bloques_espejo([dict(disp, k="df4")])["df4"], C.bloques_espejo([dict(disp, k="df4")])["df4"])
d11 = esp("df11", "Se introduce un Título VII:\n\n## «TÍTULO VII. Intervención de los Notarios\n\n### CAPÍTULO I. Reglas generales\n\n### Redacción anterior de algo\n\nArtículo 49.", e="Disposición final undécima")
r = C.bloques_espejo([d11])["df11"]
caso("disp.: los rótulos de estructura citados («TÍTULO VII», «CAPÍTULO I») SÍ cuentan (el BOE los trae como párrafos)", "tituloviiintervenciondelosnotarios" in r and "capituloireglasgenerales" in r, r)
caso("disp.: un encabezado que no es estructura («Redacción anterior…») sigue fuera", "redaccionanterior" not in r, r)
a2 = esp("5", "Texto cinco.\n\n### CAPÍTULO III. Otro\n\nMás texto.")
r = C.bloques_espejo([a2])["5"]
caso("art.: un rótulo de capítulo dentro de un artículo sigue fuera (es ruido del espejo)", "capituloiii" not in r and "mastexto" in r, r)

print(f"\n{'TODO VERDE' if not fallos else 'FALLOS: ' + str(fallos)}")
sys.exit(1 if fallos else 0)
