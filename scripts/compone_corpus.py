#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compone la copia de texto desde la que se COMPILA «Consulta de normas».

Parte de la copia congelada (`corpus-aca28304d`) y sustituye SOLO lo que el contraste con el BOE ha dado por mejor en otra fuente
(recomendación del Armero, 08-10-2026; decisión de Adolfo, 09-10-2026: texto vigente de la LAU tras el RDL 29/2026):
  - LAU completa  <- origen nuevo del espejo (legalize v0.4), que coincide con el BOE en toda la norma;
  - LEC arts. 22 y 685 y CC art. 396 <- esa misma fuente, artículo a artículo (el resto de la LEC de esa fuente trae versiones equivocadas).
Cada sustitución queda en `composicion.json` (sha256 del bloque antes y después). Nada se inventa: son bloques copiados verbatim del espejo
(solo se quitan las barras de escape de markdown del formato nuevo: «1\\.» -> «1.»). Solo lectura sobre el espejo (`git show`).
Si el RDL 29/2026 se derogara, el contraste diario con la API del BOE lo detectará y habrá que recomponer sin estas sustituciones.

Uso: python3 scripts/compone_corpus.py --base DIR --mirror REPO --origen SHA --out DIR [--fecha SIGLA=AAAA-MM-DD ...]
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

NORMAS = {  # sigla -> (identificador BOE, carpeta en el formato nuevo del espejo: 2 primeros caracteres del SHA-1 del identificador)
    "LAU": "BOE-A-1994-26003", "LEC": "BOE-A-2000-323", "CC": "BOE-A-1889-4763",
    "Ley 12/2023": "BOE-A-2023-12203", "LECrim": "BOE-A-1882-6036",
}
# 10-10-2026: Ley 12/2023 completa (el espejo congelado no traía el RDL 29/2026: art. 3 y dt 4.ª) y LECrim art. 999 (el congelado le pegaba una
# «DISPOSICIÓN ADICIONAL» de la numeración antigua). Ambas, con --base = la composición anterior, --origen = el commit del clon nuevo y --solo.
SUSTITUCIONES = {"LAU": "todo", "LEC": ["22", "685"], "CC": ["396"], "Ley 12/2023": "todo", "LECrim": ["999"]}
ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")   # barra + puntuación ASCII (escape de markdown)


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


def ruta_nueva(boe):
    return f"es/{hashlib.sha1(boe.encode()).hexdigest()[:2]}/{boe}.md"


def git_show(mirror, sha_, ruta):
    r = subprocess.run(["git", "-C", str(mirror), "show", f"{sha_}:{ruta}"], capture_output=True, timeout=180)
    if r.returncode != 0:
        raise SystemExit(f"git show {sha_}:{ruta} falló: {r.stderr.decode()[:200]}")
    return r.stdout.decode("utf-8")


def limpia(t):
    return ESCAPE.sub(r"\1", t)


def bloque(lineas, num):
    """(inicio, fin) del bloque del artículo `num` (cabecera de nivel 6 hasta la siguiente cabecera de cualquier nivel)."""
    pat = re.compile(rf"^#{{6}}\s+Art[ií]culo\s+{re.escape(num)}\s*(?:\.|$)")
    ini = [i for i, ln in enumerate(lineas) if pat.match(ln)]
    if len(ini) != 1:
        raise SystemExit(f"artículo {num}: {len(ini)} cabeceras (se esperaba 1)")
    i = ini[0]
    j = next((k for k in range(i + 1, len(lineas)) if re.match(r"^#{1,6}\s", lineas[k])), len(lineas))
    return i, j


def pon_fecha(t, fecha):
    """Fija last_updated en la cabecera YAML (la sustituye o la añade tras publication_date)."""
    m = re.match(r"^(---\n)(.*?)(\n---\n)", t, re.S)
    if not m:
        raise SystemExit("sin cabecera YAML")
    cab = m.group(2)
    if re.search(r"^last_updated:", cab, re.M):
        cab = re.sub(r"^last_updated:.*$", f'last_updated: "{fecha}"', cab, flags=re.M)
    else:
        cab = re.sub(r"^(publication_date:.*)$", rf'\1\nlast_updated: "{fecha}"', cab, count=1, flags=re.M)
    return m.group(1) + cab + m.group(3) + t[m.end():]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True); ap.add_argument("--mirror", required=True); ap.add_argument("--origen", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--fecha", action="append", default=[])
    ap.add_argument("--solo", default="", help="siglas separadas por comas: solo estas sustituciones (para apilar sobre una composición ya hecha)")
    a = ap.parse_args()
    base, mirror, out = Path(a.base), Path(a.mirror), Path(a.out)
    fechas = dict(x.split("=", 1) for x in a.fecha)
    if out.exists():
        raise SystemExit(f"{out} ya existe: no se sobrescribe")
    r = subprocess.run(["cp", "-cR", str(base), str(out)], capture_output=True)   # APFS clonefile: instantáneo y sin duplicar 670 MB
    if r.returncode != 0:
        shutil.copytree(base, out, copy_function=lambda s, d: __import__("os").link(s, d))
    solo = [x.strip() for x in a.solo.split(",") if x.strip()]
    previa = json.loads((base / "composicion.json").read_text(encoding="utf-8")) if (solo and (base / "composicion.json").is_file()) else None
    if previa:   # se apila sobre una composición anterior: se conserva su procedencia y se añade la nueva
        reg = dict(creada=dt.datetime.now().isoformat(timespec="seconds"), base=previa["base"], origen=previa["origen"], sustituciones=list(previa["sustituciones"]),
                   origenes_adicionales=list(previa.get("origenes_adicionales", [])) + [dict(origen=a.origen, siglas=solo, sobre=(base / ".commit").read_text().strip() if (base / ".commit").is_file() else "")])
    else:
        reg = dict(creada=dt.datetime.now().isoformat(timespec="seconds"), base=(base / ".commit").read_text().strip() if (base / ".commit").is_file() else "",
                   origen=a.origen, sustituciones=[])
    for sigla, boe in NORMAS.items():
        if solo and sigla not in solo:
            continue
        if not solo and sigla in ("Ley 12/2023", "LECrim"):
            continue   # sin --solo se reproduce la composición del 09-10-2026 (LAU, LEC 22 y 685, CC 396)
        destino = out / "es" / f"{boe}.md"
        if destino.is_symlink() or destino.stat().st_nlink > 1:   # no tocar el fichero compartido con la copia base
            txt = destino.read_text(encoding="utf-8"); destino.unlink(); destino.write_text(txt, encoding="utf-8")
        viejo = destino.read_text(encoding="utf-8")
        nuevo = limpia(git_show(mirror, a.origen, ruta_nueva(boe)))
        quehacer = SUSTITUCIONES[sigla]
        if quehacer == "todo":
            # el formato nuevo no trae last_updated: se pone la fecha de la fuente (source_updated_at) salvo que se indique otra
            f = fechas.get(sigla) or (re.search(r'^source_updated_at:\s*"?(\d{4}-\d\d-\d\d)', nuevo, re.M) or [0, ""])[1]
            texto = pon_fecha(nuevo, f) if f else nuevo
            reg["sustituciones"].append(dict(norma=sigla, boe=boe, alcance="norma completa", antes=sha(viejo), despues=sha(texto), last_updated=f))
        else:
            lv, ln = viejo.split("\n"), nuevo.split("\n")
            for num in quehacer:
                i, j = bloque(lv, num); p, q = bloque(ln, num)
                antes, despues = "\n".join(lv[i:j]), "\n".join(ln[p:q])
                lv[i:j] = ln[p:q]
                reg["sustituciones"].append(dict(norma=sigla, boe=boe, alcance=f"art. {num}", antes=sha(antes), despues=sha(despues)))
            texto = "\n".join(lv)
            if fechas.get(sigla):
                texto = pon_fecha(texto, fechas[sigla]); reg["sustituciones"].append(dict(norma=sigla, boe=boe, alcance="last_updated", despues=fechas[sigla]))
        destino.write_text(texto, encoding="utf-8")
    (out / "composicion.json").write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in reg["sustituciones"]:
        print(f"  {s['norma']:11s} {s['alcance']:16s} {s.get('antes', '-')} -> {s.get('despues')}")
    print("OK:", out)


if __name__ == "__main__":
    sys.exit(main())
