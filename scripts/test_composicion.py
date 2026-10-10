#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de la COMPOSICIÓN de texto (scripts/compone_corpus.py) y de su base compuesta (indice.base_compuesta + build.base_en_commit).
Todo en carpetas y repositorios temporales: no toca el espejo, la copia congelada ni lineas_base.json reales.
Uso: python3 scripts/test_composicion.py [ruta_compone_corpus.py]   (el argumento sirve para el sabotaje)"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import build  # noqa: E402
import indice  # noqa: E402

SCRIPT = sys.argv[1] if len(sys.argv) > 1 else str(AQUI / "scripts/compone_corpus.py")
fallos = []


def caso(nombre, cond, detalle=""):
    print(("  ok   " if cond else "  FALLA ") + nombre + ("" if cond else f"  -> {detalle}"))
    if not cond:
        fallos.append(nombre)


def sh(*a, cwd=None):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, (a, r.stderr)
    return r.stdout.strip()


def ruta_nueva(boe):
    return f"es/{hashlib.sha1(boe.encode()).hexdigest()[:2]}/{boe}.md"


LAU, LEC, CC = "BOE-A-1994-26003", "BOE-A-2000-323", "BOE-A-1889-4763"
CAB = '---\ntitle: "T"\nidentifier: "{b}"\npublication_date: "1994-11-25"\n{extra}status: "in_force"\n---\n'

print("[compone_corpus: sustituye solo lo previsto, limpia el escape del formato nuevo y no toca la copia base]")
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp)
    base, espejo, out = t / "base", t / "espejo", t / "out"
    (base / "es").mkdir(parents=True)
    (base / ".commit").write_text("aca28304d\n")
    # copia base (formato antiguo, sin escapes)
    viejo = {
        LAU: CAB.format(b=LAU, extra='last_updated: "2026-10-02"\n') + "###### Artículo 1. Viejo.\n\n1. Texto viejo de la LAU.\n",
        LEC: CAB.format(b=LEC, extra='last_updated: "2026-10-05"\n') + "###### Artículo 21. Uno.\n\nTexto 21 viejo.\n\n###### Artículo 22. Dos.\n\nTexto 22 VIEJO.\n\n"
             "###### Artículo 22 bis. Bis.\n\nTexto 22 bis viejo.\n\n### CAPÍTULO II. Otro\n\n###### Artículo 685. Seis.\n\nTexto 685 VIEJO.\n\n###### Artículo 686. Siete.\n\nTexto 686 viejo.\n",
        CC: CAB.format(b=CC, extra='last_updated: "2025-01-03"\n') + "###### Artículo 395. A.\n\nTexto 395.\n\n###### Artículo 396. B.\n\nlos elemento de cierre.\n\n###### Artículo 397. C.\n\nTexto 397.\n",
    }
    for boe, txt in viejo.items():
        (base / "es" / f"{boe}.md").write_text(txt, encoding="utf-8")
    # espejo en formato nuevo: subcarpeta = 2 primeros caracteres del SHA-1; escapes de markdown; sin last_updated pero con source_updated_at
    sh("git", "init", "-q", str(espejo))
    nuevo = {
        LAU: CAB.format(b=LAU, extra='source_updated_at: "2026-10-07T12:24:33Z"\n') + "###### Artículo 1. Nuevo.\n\n1\\. Texto nuevo de la LAU (\\*vigente\\*).\n\n2\\. Segundo apartado.\n",
        LEC: CAB.format(b=LEC, extra="") + "###### Artículo 21. Uno.\n\nTexto 21 CON ERRATA del espejo.\n\n###### Artículo 22. Dos.\n\n1\\. Texto 22 NUEVO.\n\n6\\. Apartado nuevo.\n\n"
             "###### Artículo 685. Seis.\n\nTexto 685 NUEVO.\n",
        CC: CAB.format(b=CC, extra="") + "###### Artículo 395. A.\n\nTexto 395 CON ERRATA.\n\n###### Artículo 396. B.\n\nlos elementos de cierre.\n",
    }
    for boe, txt in nuevo.items():
        p = espejo / ruta_nueva(boe)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8")
    sh("git", "-C", str(espejo), "add", ".")
    sh("git", "-C", str(espejo), "-c", "user.email=t@l", "-c", "user.name=t", "commit", "-q", "-m", "[bootstrap] x")
    sha = sh("git", "-C", str(espejo), "rev-parse", "--short", "HEAD")
    r = subprocess.run([sys.executable, SCRIPT, "--base", str(base), "--mirror", str(espejo), "--origen", sha, "--out", str(out), "--fecha", "LEC=2026-10-07"],
                       capture_output=True, text=True)
    caso("el script termina bien", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
    lau, lec, cc = [(out / "es" / f"{b}.md").read_text(encoding="utf-8") for b in (LAU, LEC, CC)]
    caso("LAU: sustituida entera por la de la fuente nueva", "Texto nuevo de la LAU" in lau and "Texto viejo" not in lau, lau[-200:])
    caso("LAU: SIN barras de escape de markdown («1\\.» -> «1.», «\\*» -> «*»)", "\\" not in lau and "1. Texto nuevo de la LAU (*vigente*)." in lau, lau[-200:])
    caso("LAU: last_updated sale de source_updated_at (el formato nuevo no lo trae)", 'last_updated: "2026-10-07"' in lau, lau[:200])
    caso("LEC: el artículo 22 es el nuevo (con su apartado 6)", "Texto 22 NUEVO." in lec and "6. Apartado nuevo." in lec and "22 VIEJO" not in lec, lec)
    caso("LEC: el 685 es el nuevo", "Texto 685 NUEVO." in lec and "685 VIEJO" not in lec, lec)
    caso("LEC: el 21 NO se sustituye (la fuente nueva trae errata en él)", "Texto 21 viejo." in lec and "ERRATA" not in lec, lec)
    caso("LEC: el 22 bis, el 686 y la cabecera de capítulo siguen intactos", "Texto 22 bis viejo." in lec and "### CAPÍTULO II. Otro" in lec and "Texto 686 viejo." in lec, lec)
    caso("LEC: last_updated puesto con --fecha", 'last_updated: "2026-10-07"' in lec and "2026-10-05" not in lec, lec[:200])
    caso("CC: solo el 396 cambia (el 395 de la fuente nueva trae errata y no entra)", "los elementos de cierre." in cc and "Texto 395." in cc and "ERRATA" not in cc, cc)
    caso("la copia BASE no se ha tocado (clonefile/hardlink no escribe a través)", all((base / "es" / f"{b}.md").read_text(encoding="utf-8") == viejo[b] for b in viejo))
    comp = json.loads((out / "composicion.json").read_text(encoding="utf-8"))
    alcances = [(s["norma"], s["alcance"]) for s in comp["sustituciones"]]
    caso("composicion.json registra cada sustitución con su procedencia", ("LAU", "norma completa") in alcances and ("LEC", "art. 22") in alcances and ("LEC", "art. 685") in alcances
         and ("CC", "art. 396") in alcances and comp["origen"] == sha and comp["base"] == "aca28304d", str(comp)[:400])
    caso("cada sustitución lleva huella antes y después, y son distintas", all(s.get("antes") != s.get("despues") for s in comp["sustituciones"] if "antes" in s))
    r2 = subprocess.run([sys.executable, SCRIPT, "--base", str(base), "--mirror", str(espejo), "--origen", sha, "--out", str(out)], capture_output=True, text=True)
    caso("no sobrescribe una composición existente", r2.returncode != 0 and "ya existe" in (r2.stdout + r2.stderr), r2.stdout + r2.stderr)

print("[compone_corpus --solo: se apila sobre una composición anterior sin rehacer lo ya compuesto (Ley 12/2023 entera, LECrim 999)]")
L12, LECR = "BOE-A-2023-12203", "BOE-A-1882-6036"
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp)
    base, espejo, out = t / "base", t / "espejo", t / "out"
    (base / "es").mkdir(parents=True)
    (base / ".commit").write_text("10ec58cc2a\n")
    anterior_comp = {"creada": "x", "base": "aca28304d", "origen": "a5e9eecce6", "sustituciones": [dict(norma="LAU", boe=LAU, alcance="norma completa", antes="a", despues="b")]}
    (base / "composicion.json").write_text(json.dumps(anterior_comp), encoding="utf-8")
    viejo = {
        LAU: CAB.format(b=LAU, extra='last_updated: "2026-10-07"\n') + "###### Artículo 1. LAU ya compuesta.\n\nTexto LAU compuesta.\n",
        L12: CAB.format(b=L12, extra='last_updated: "2026-10-05"\n') + "###### Artículo 3. Defs.\n\nTexto 3 VIEJO.\n\n###### Disposición transitoria cuarta. Régimen.\n\ndt4 VIEJA.\n",
        LECR: CAB.format(b=LECR, extra='last_updated: "2026-04-09"\n') + "###### Artículo 998. Antes.\n\nTexto 998.\n\n###### Artículo 999. Ejecución.\n\n1. Texto 999.\n\nDISPOSICIÓN ADICIONAL\n\nResto de la numeración antigua.\n\n###### Artículo 1000. Después.\n\nTexto 1000.\n",
    }
    for boe, txt in viejo.items():
        (base / "es" / f"{boe}.md").write_text(txt, encoding="utf-8")
    sh("git", "init", "-q", str(espejo))
    nuevo = {
        LAU: CAB.format(b=LAU, extra='source_updated_at: "2026-10-09T00:00:00Z"\n') + "###### Artículo 1. LAU del origen NUEVO.\n\nNO debe entrar: ya estaba compuesta.\n",
        L12: CAB.format(b=L12, extra='source_updated_at: "2026-10-08T00:00:00Z"\n') + "###### Artículo 3. Defs.\n\nTexto 3 NUEVO\\.\n\n###### Disposición transitoria cuarta. Régimen.\n\ndt4 NUEVA.\n",
        LECR: CAB.format(b=LECR, extra="") + "###### Artículo 998. Antes.\n\nTexto 998 CON ERRATA.\n\n###### Artículo 999. Ejecución.\n\n1\\. Texto 999.\n\n###### Artículo 1000. Después.\n\nTexto 1000 CON ERRATA.\n",
    }
    for boe, txt in nuevo.items():
        pp = espejo / ruta_nueva(boe)
        pp.parent.mkdir(parents=True, exist_ok=True)
        pp.write_text(txt, encoding="utf-8")
    sh("git", "-C", str(espejo), "add", ".")
    sh("git", "-C", str(espejo), "-c", "user.email=t@l", "-c", "user.name=t", "commit", "-q", "-m", "[bootstrap] y")
    sha2 = sh("git", "-C", str(espejo), "rev-parse", "--short", "HEAD")
    r = subprocess.run([sys.executable, SCRIPT, "--base", str(base), "--mirror", str(espejo), "--origen", sha2, "--out", str(out), "--solo", "Ley 12/2023,LECrim"], capture_output=True, text=True)
    caso("--solo: el script termina bien", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
    lau, l12, lecr = [(out / "es" / f"{b}.md").read_text(encoding="utf-8") for b in (LAU, L12, LECR)]
    caso("--solo: la LAU ya compuesta NO se rehace con el origen nuevo", "Texto LAU compuesta." in lau and "NO debe entrar" not in lau, lau[-200:])
    caso("--solo: Ley 12/2023 sustituida entera y sin barras de escape", "Texto 3 NUEVO." in l12 and "dt4 NUEVA." in l12 and "VIEJ" not in l12 and "\\" not in l12, l12[-200:])
    caso("--solo: LECrim solo cambia el 999 (quita la DISPOSICIÓN ADICIONAL suelta); el 998 y el 1000 de la fuente con errata NO entran",
         "DISPOSICIÓN ADICIONAL" not in lecr and "Resto de la numeración antigua" not in lecr and "Texto 998." in lecr and "Texto 1000." in lecr and "ERRATA" not in lecr, lecr)
    comp = json.loads((out / "composicion.json").read_text(encoding="utf-8"))
    alc = [(x["norma"], x["alcance"]) for x in comp["sustituciones"]]
    caso("--solo: composicion.json conserva la procedencia anterior y añade la nueva",
         comp["base"] == "aca28304d" and comp["origen"] == "a5e9eecce6" and ("LAU", "norma completa") in alc and ("Ley 12/2023", "norma completa") in alc and ("LECrim", "art. 999") in alc
         and comp.get("origenes_adicionales") == [dict(origen=sha2, siglas=["Ley 12/2023", "LECrim"], sobre="10ec58cc2a")], str(comp)[:500])

print("[base compuesta: las voces revisadas contra la composición no caducan por comparar con un commit que no existe]")
bases = {"_composiciones": {"597314599f": {"normas": {"LEC": {"status": "in_force", "huellas": {"22": "h22", "685": "h685"}}}}}}
b = indice.base_compuesta(bases, "597314599f", "LEC")
caso("base_compuesta: devuelve las huellas y el estado oficial", b == {"22": "h22", "685": "h685"} and b.estado == "in_force", str(b))
caso("base_compuesta: identificador o norma desconocidos -> None", indice.base_compuesta(bases, "deadbeef00", "LEC") is None and indice.base_compuesta(bases, "597314599f", "LAU") is None
     and indice.base_compuesta({}, "597314599f", "LEC") is None and indice.base_compuesta(None, "x", "LEC") is None)
H = lambda s: indice.huella(dict(e=s, t="", b=""))
with tempfile.TemporaryDirectory() as tmp:
    f = Path(tmp) / "lb.json"
    f.write_text(json.dumps({"_composiciones": {"597314599f": {"normas": {"LEC": {"status": "in_force", "huellas": {"22": H("texto 22"), "685": H("texto 685")}}}}}}), encoding="utf-8")
    anterior = build.BASES
    build.BASES = f
    build._BASE.clear()
    try:
        r = build.base_en_commit({"LEC": {"cfg": {}, "ruta": "es/X.md"}}, "LEC", "597314599f")
        caso("build.base_en_commit: un identificador de composición resuelve sin pasar por git", r == {"22": H("texto 22"), "685": H("texto 685")}, str(r))
        v = dict(voz="V", espejo="legalize-es@597314599f", normas_base=["LEC"], vigilar=[], remisiones=[dict(norma="LEC", articulo="22", tipo="regula", nota="n")])
        hoy = dict(id="x", keys={"22", "685"}, mapa={"22": H("texto 22"), "685": H("texto 685")}, ruta="es/X.md", status="in_force")
        base_fn = lambda s, c: build.base_en_commit({"LEC": {"cfg": {}, "ruta": "es/X.md"}}, s, c)
        caso("voz revisada contra la composición y texto igual -> NO caduca", indice.caducidad_voz(v, {"LEC": hoy}, base_fn) == [])
        cambia = dict(hoy, mapa={"22": H("texto 22 REFORMADO"), "685": H("texto 685")})
        rr = indice.caducidad_voz(v, {"LEC": cambia}, base_fn)
        caso("... y si luego cambia un artículo que cita -> caduca y lo nombra (la protección sigue)", rr == [dict(n="LEC", k="22", r="cambia")], str(rr))
    finally:
        build.BASES = anterior
        build._BASE.clear()

print(f"\n{'TODO VERDE' if not fallos else 'FALLOS: ' + str(fallos)}")
sys.exit(1 if fallos else 0)
