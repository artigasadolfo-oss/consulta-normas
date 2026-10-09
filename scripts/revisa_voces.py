#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Revisión por el Armero de las voces/fórmulas CADUCADAS de «Consulta de normas» (un encargo por fichero).

Cuándo se usa: cuando el texto compilado cambia (nueva composición, actualización del espejo, reforma que entra en vigor) y `build.py --comprobar`
da voces o fórmulas «caducadas» (un artículo que citan ha cambiado desde que se revisaron). Es el paso que convierte «cambio detectado» en
«voces revisadas».

Qué hace: lista las caducadas, las agrupa por fichero (indice/*.yaml, formulas/*.yaml) y lanza un `hermes chat` del perfil `armero` por fichero
(3 a la vez). El Armero escribe el fichero COMPLETO revisado en docs/revision-<etiqueta>/ y sus notas; taller valida (mismos nombres y orden, las
no afectadas intactas, `espejo` nuevo en las afectadas). NO integra nada: el resultado se prueba aparte (copia de trabajo + batería) y solo se
publica con visto bueno de Adolfo. El contenido jurídico es del Armero; este script no lo juzga.

Uso:  CONSULTA_NORMAS_CORPUS=<composición> python3 scripts/revisa_voces.py --etiqueta rdl28-art10 --motivo "texto del porqué" [--solo-fichero indice/tanda-06.yaml]
      [--plan]   (solo lista el plan, sin llamar al Armero)
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

AQ = Path(__file__).resolve().parents[1]
HERMES_ARMERO = Path.home() / ".hermes/profiles/armero"

ENCARGO = """# Encargo de taller al Armero: revisar voces cuyo texto citado ha cambiado ({etiqueta})

Fecha: {hoy}. Remite: taller. Sin datos de clientes ni de expedientes.

## Qué ha pasado
{motivo}

El texto del que se compila es la **composición `{ident}`** (carpeta `{comp}`; es lo que muestra la herramienta). Por eso las voces/fórmulas que citan
los artículos cambiados aparecen «caducadas»: el texto cambió desde que las revisaste.

## Tu tarea (SOLO el fichero `{fichero}`)
Voces/fórmulas de ese fichero que debes revisar, con los artículos que han cambiado:

{lista}

Para cada una:
1. **Lee cada artículo citado en el texto actual** (`{comp}/es/<BOE-A-...>.md`; LAU `BOE-A-1994-26003`, LEC `BOE-A-2000-323`, CC `BOE-A-1889-4763`,
   LPH `BOE-A-1960-10906`, LO 1/2025 `BOE-A-2025-76`, LOPJ `BOE-L-1985-12666`/ver el fichero). Comprueba que **cada apartado citado existe con ese número**.
2. Corrige `nota`, `apartado`, `tipo`, `vigilar` y el texto de la voz donde haga falta. Las notas describen el texto **vigente hoy**; si algo depende de una
   reforma que aún no rige, ponlo como aviso con su fecha, sin presentarlo como vigente.
3. Pon `espejo: "legalize-es@{ident}"` y `revisada_el: "{hoy}"` en las revisadas. `revisor: armero`.
4. **Estado:** `provisional` lo que dependa de una norma no convalidada o de una reforma futura con el aviso que ya usas; `vigente` el resto. Decides tú.
5. Puedes añadir remisiones a artículos nuevos de la norma; **no crees voces nuevas** (si crees que falta una, dilo en las notas).
6. Las voces del fichero que NO están en la lista **no se tocan**: cópialas literalmente (incluido su `espejo` antiguo).

## Formato y límites
- Mismo YAML que el fichero actual (clave `{clave}:`, mismos campos). **Mismos nombres, mismo orden, mismo número** de elementos. Sin campos nuevos.
  Conserva los comentarios de cabecera, cambiando la línea de «Espejo» para decir que las revisadas lo son contra `legalize-es@{ident}`.
- Precepto citado = precepto leído. No cites de memoria.
- No abras carpetas de expedientes ni de clientes. No toques `legal-esp`. No hagas pull/fetch/checkout/reset en el espejo.

## Dónde dejar la respuesta (SOLO estos ficheros, en {revdir})
- `{salida}` — el fichero **completo** ya revisado. Escríbelo con `write_file` cuando lo tengas.
- `{salida_notas}` — qué has cambiado voz a voz (una línea cada una) y lo que dejas dudoso para Adolfo.
"""


def caducadas(aq=AQ):
    r = subprocess.run([sys.executable, "build.py", "--comprobar"], capture_output=True, text=True, cwd=aq, timeout=900)
    seccion, res = "voces", []
    for ln in r.stdout.splitlines():
        if ln.startswith("Fórmulas de sala"):
            seccion = "formulas"
        m = re.match(r"^\s+caducada: (.*?) <- (.*)$", ln)
        if m:
            res.append((seccion, m.group(1), m.group(2)))
    return res


def localiza(res, aq=AQ):
    """{ruta_relativa: [(nombre, razones)]}, [nombres sin localizar]. Busca cada nombre en indice/*.yaml (voz) o formulas/*.yaml (situacion)."""
    grupos, perdidas, cache = {}, [], {}
    ficheros = {"voces": sorted((aq / "indice").glob("*.yaml")), "formulas": sorted((aq / "formulas").glob("*.yaml"))}
    for sec, nombre, razones in res:
        clave, lista = ("voz", "voces") if sec == "voces" else ("situacion", "formulas")
        hallado = None
        for f in ficheros[sec]:
            if f not in cache:
                cache[f] = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            if any(x.get(clave) == nombre for x in cache[f].get(lista, [])):
                hallado = f
                break
        if hallado:
            grupos.setdefault(str(hallado.relative_to(aq)), []).append((nombre, razones))
        else:
            perdidas.append(nombre)
    return grupos, perdidas


def valida(fich_rel, objetivos, salida, ident, aq=AQ):
    """(ok, motivo). Mismos elementos y orden; los no afectados idénticos; los afectados con el espejo nuevo."""
    clave, nom = ("formulas", "situacion") if fich_rel.startswith("formulas/") else ("voces", "voz")
    try:
        orig = yaml.safe_load((aq / fich_rel).read_text(encoding="utf-8"))[clave]
        nuevo = yaml.safe_load(Path(salida).read_text(encoding="utf-8"))[clave]
    except Exception as e:
        return False, f"YAML ilegible o sin clave: {e}"
    if [x[nom] for x in orig] != [x[nom] for x in nuevo]:
        return False, "los nombres u orden no coinciden con el fichero original"
    obj = {n for n, _ in objetivos}
    for a, b in zip(orig, nuevo):
        if a[nom] in obj:
            if f"@{ident}" not in str(b.get("espejo", "")):
                return False, f"«{a[nom][:50]}» sin el espejo nuevo"
        elif a != b:
            return False, f"se ha tocado «{a[nom][:50]}», que no estaba en la lista"
    return True, "ok"


class Revision:
    def __init__(self, etiqueta, motivo, comp, aq=AQ, hoy=None):
        self.etiqueta, self.motivo, self.comp, self.aq = etiqueta, motivo, Path(comp), Path(aq)
        self.ident = (self.comp / ".commit").read_text().strip()
        self.hoy = hoy or dt.date.today().isoformat()
        self.rev = self.aq / "docs" / f"revision-{etiqueta}"
        self.rev.mkdir(parents=True, exist_ok=True)
        self.logf = self.rev / "piloto.log"

    def log(self, m):
        l = f"[{dt.datetime.now():%H:%M:%S}] {m}"
        print(l, flush=True)
        with open(self.logf, "a", encoding="utf-8") as f:
            f.write(l + "\n")

    def armero(self, texto, ruta, nombre_log):
        ruta.write_text(texto, encoding="utf-8")
        q = f"Lee el encargo de taller en {ruta} y ejecútalo hasta el final. No abras carpetas de expedientes ni de clientes."
        env = {**os.environ, "HERMES_HOME": str(HERMES_ARMERO)}
        t0 = time.time()
        try:
            r = subprocess.run(["hermes", "chat", "-Q", "--max-turns", "90", "-q", q], capture_output=True, text=True, timeout=45 * 60, env=env, cwd=self.aq)
            (self.rev / nombre_log).write_text((r.stdout or "") + (r.stderr or ""), encoding="utf-8")
            return r.returncode, time.time() - t0
        except subprocess.TimeoutExpired:
            return "tiempo", time.time() - t0

    def trabaja(self, fich_rel, objetivos):
        nombre = Path(fich_rel).name
        clave = "formulas" if fich_rel.startswith("formulas/") else "voces"
        salida, notas = self.rev / nombre, self.rev / (Path(nombre).stem + "-notas.md")
        if salida.exists():
            salida.unlink()
        lista = "\n".join(f"- «{n}» — cambian: {r}" for n, r in objetivos)
        txt = ENCARGO.format(etiqueta=self.etiqueta, hoy=self.hoy, motivo=self.motivo, ident=self.ident, comp=self.comp, fichero=fich_rel, lista=lista,
                             clave=clave, revdir=self.rev, salida=salida, salida_notas=notas)
        rc, seg = self.armero(txt, self.rev / f"encargo-{Path(nombre).stem}.md", f"armero-{Path(nombre).stem}.log")
        if not salida.is_file():
            self.log(f"{nombre}: el Armero no entregó fichero (rc={rc}, {seg / 60:.0f} min)")
            return nombre, False, "sin fichero"
        ok, motivo = valida(fich_rel, objetivos, salida, self.ident, self.aq)
        self.log(f"{nombre}: {'VALIDADO' if ok else 'RECHAZADO: ' + motivo} ({len(objetivos)} elementos, rc={rc}, {seg / 60:.0f} min)")
        if not ok:
            (self.rev / "rechazadas").mkdir(exist_ok=True)
            salida.rename(self.rev / "rechazadas" / nombre)
        return nombre, ok, motivo


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiqueta", required=True)
    ap.add_argument("--motivo", required=True)
    ap.add_argument("--solo-fichero", action="append", default=[])
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--paralelo", type=int, default=3)
    a = ap.parse_args(argv)
    corpus = os.environ.get("CONSULTA_NORMAS_CORPUS")
    if not corpus or not (Path(corpus) / ".commit").is_file():
        print("Falta CONSULTA_NORMAS_CORPUS=<composición con .commit> (no se revisa contra el espejo vivo).")
        return 2
    rv = Revision(a.etiqueta, a.motivo, corpus)
    rv.log(f"== revisión «{a.etiqueta}» (composición {rv.ident}) ==")
    res = caducadas()
    grupos, perdidas = localiza(res)
    if a.solo_fichero:
        grupos = {k: v for k, v in grupos.items() if k in a.solo_fichero}
    rv.log(f"{len(res)} caducadas; {len(grupos)} ficheros en el plan; sin localizar: {perdidas}")
    (rv.rev / "plan.json").write_text(json.dumps({k: [list(x) for x in v] for k, v in grupos.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.plan or not grupos:
        for k, v in grupos.items():
            print(" ", k, [n for n, _ in v])
        return 0
    resultados = []
    with cf.ThreadPoolExecutor(max_workers=a.paralelo) as ex:
        futs = {ex.submit(rv.trabaja, f, o): f for f, o in grupos.items()}
        for fu in cf.as_completed(futs):
            try:
                resultados.append(fu.result())
            except Exception as e:
                rv.log(f"{futs[fu]}: EXCEPCIÓN {type(e).__name__}: {e}")
                resultados.append((futs[fu], False, str(e)))
    ok = [r[0] for r in resultados if r[1]]
    rv.log(f"== fin: {len(ok)} validados de {len(grupos)}. Rechazados/sin fichero: {[r[0] for r in resultados if not r[1]]} ==")
    return 0 if len(ok) == len(grupos) else 1


if __name__ == "__main__":
    sys.exit(main())
