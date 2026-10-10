#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exportar_para_lexart.py — escribe salida/lexart-corpus.json: el corpus de normas de la web, en el formato que leerá LexArt.

No hay un segundo analizador: parte de build.analiza(), la misma función con la que build.py trocea y verifica cada norma
(prueba de reconstrucción incluida). Si cambia el analizador de la web, cambia la exportación; LexArt no vuelve a trocear nada.

Uso:   python3 scripts/exportar_para_lexart.py [--salida ruta.json]
Falla (código 1, sin dejar fichero a medias) si: la suma de bloques exportados no coincide con la que cuenta build.py, un bloque
pierde o añade líneas respecto al que analiza build.py, o normas.json (el manifiesto del último build) describe otro texto.

ESQUEMA (esquema = "consulta-normas/lexart-corpus@1"; si cambia algo incompatible, sube el número):
{
  "esquema": "consulta-normas/lexart-corpus@1",
  "compilado": "AAAA-MM-DD",            fecha de la exportación
  "corpus_commit": "<sha>",             commit del espejo del BOE con que se compiló ("" si no consta)
  "normas": [ {
      "id": "lec",                      identificador interno de la web (minúscula, con guion)
      "sigla": "LEC",                   sigla con que se cita («282 LEC»)
      "boe": "BOE-A-2000-323",          identificador BOE (o DOGV-... en la importada a mano)
      "titulo": "...",                  título oficial completo, tal como lo da el BOE
      "corto": "Ley de Enjuiciamiento Civil",   nombre llano
      "alias": ["lec", "ley de enjuiciamiento civil", ...],   formas de citarla, minúsculas y sin tildes
      "url": "https://www.boe.es/...",  texto consolidado en boe.es
      "estado": "in_force",             estado que declara el espejo
      "actualizada": "2026-10-05",      fecha de la última actualización del consolidado (la del espejo)
      "sha256": "...",                  huella del fichero fuente del espejo
      "dir": "es" | "es-vc",            carpeta del espejo
      "fuente": "texto consolidado del BOE" | "DOGV, importado a mano",
      "bloques[].posterior": OPCIONAL, solo en los artículos con una reforma ya publicada que aún no rige (el texto del bloque es la redacción VIGENTE hoy):
                                              {"fecha": "AAAA-MM-DD" (entrada en vigor), "origen": "v" (versión del BOE) | "n" (reconstruida de la nota «Téngase en cuenta…»),
                                               "parrafos": [texto limpio de la posterior], "cambios": [[[t, texto], …], …]  t: 0 igual, 1 nuevo, 2 suprimido de la vigente}.
                                              Aditivo: el esquema sigue siendo @1 y quien no lo lea no se entera.
      "contraste": {"fecha": "AAAA-MM-DD", "avisos": {"<clave>": [["d"], ["f", "AAAA-MM-DD"]]}},   contraste con la API de boe.es del día de la exportación:
                                              "d" = el texto del espejo difiere del consolidado vigente; "f" = reforma ya publicada que entra en vigor en esa fecha.
                                              Sin red la exportación FALLA (no se exporta sin avisos); --sin-contraste la fuerza y deja "contraste": null.
      "recuento": {"articulos": N, "disposiciones": M, "bloques": B},   los de build.py (artículos reales, con bis/ter y los números que
                                                                         cubren los rangos derogados; disposiciones aparte)
      "bloques": [ {                    en el orden del texto
          "clave": "282" | "3 bis" | "588 bis b" | "unico" | "da1" | "dt2" | "df-derogatoria" | "617-622" | "rd-1" | "cab" | "pre",
          "rotulo": "Artículo 282",     rótulo tal como se muestra
          "titulo": "...",              título del artículo ("" si no tiene)
          "ubicacion": ["LIBRO II...", "TÍTULO I...", "CAPÍTULO ..."],   Libro > Título > Capítulo > Sección en que está
          "tipo": "articulo" | "disposicion" | "preambulo" | "encabezado",
          "ambito": "norma" | "real_decreto",   «real_decreto» = lo que va ANTES del texto aprobado (Decreto/RD/RDLeg que aprueba la
                                                norma: artículo único, sus disposiciones...); clave con prefijo «rd-»
          "rango": [638, 639],          solo en los bloques «Artículos 638 y 639» / «Arts. 934 a 946» (derogados en bloque)
          "texto": "...",               texto del artículo en markdown tal como lo trae el espejo, SIN las notas de reforma
          "notas": ["Se modifica ... [Ref. BOE-A-...]", ...]   notas de reforma del BOE, una por elemento (el texto de la
                                                                «Redacción anterior» va dentro de su nota, con saltos de línea)
      } ]
  } ]
}
Las claves de artículo no se repiten dentro de una norma. Nada se resume ni se interpreta: es el texto del espejo, troceado.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import build  # noqa: E402

ESQUEMA = "consulta-normas/lexart-corpus@1"
RE_DISP = re.compile(r"^d[adtf]")
RE_RANGO = re.compile(r"^(\d+)-(\d+)$")
INICIO_NOTA = re.compile(r"^(Se |Téngase|Redacción|Esta modificación)")


def alias_de_plantilla():
    """Alias de las normas cuyos nombres siguen escritos en plantilla.html (las diez primeras); las demás los traen en NORMAS."""
    txt = (AQUI / "plantilla.html").read_text(encoding="utf-8")
    m = re.search(r"var ALIAS=\[(.*?)\n\];", txt, re.S)
    return {i: a.split("|") for i, a in re.findall(r"\['([a-z0-9-]+)','([^']+)'\]", m.group(1))} if m else {}


def separa_notas(b):
    """(texto, notas) a partir del cuerpo de un bloque: las líneas «> …» son notas de reforma; una continuación (la redacción anterior
    entera) se une a su nota con salto de línea, como hace LexArt hoy."""
    texto, notas, hubo_texto = [], [], False
    for ln in b.split("\n"):
        if ln.startswith(">"):
            t = re.sub(r"^>\s?", "", ln).strip()
            if not t:
                continue
            if not notas or INICIO_NOTA.match(t) or hubo_texto:
                notas.append(t)
            else:
                notas[-1] += "\n" + t
            hubo_texto = False
        else:
            if ln.strip():
                hubo_texto = True
            texto.append(ln)
    while texto and not texto[0].strip():
        texto.pop(0)
    while texto and not texto[-1].strip():
        texto.pop()
    return "\n".join(texto), notas


def lineas_no_vacias(s):
    return Counter(x.rstrip() for x in s.split("\n") if x.strip())


def bloque(c):
    k = c["k"]
    base = k[3:] if k.startswith("rd-") else k
    if k == "cab":
        tipo = "encabezado"
    elif k == "pre":
        tipo = "preambulo"
    elif RE_DISP.match(base):
        tipo = "disposicion"
    else:
        tipo = "articulo"
    texto, notas = separa_notas(c["b"])
    # el texto y las notas, juntos, son exactamente las líneas del bloque que analizó build.py (ni una más, ni una menos)
    del_bloque = Counter(re.sub(r"^>\s?", "", x).strip() if x.startswith(">") else x.rstrip() for x in c["b"].split("\n"))
    exportadas = lineas_no_vacias(texto) + Counter(y for n in notas for y in n.split("\n"))
    del_bloque.pop("", None)
    if del_bloque != exportadas:
        raise SystemExit(f"bloque {k!r}: el texto y las notas exportados no reproducen las líneas del bloque que analiza build.py")
    out = dict(clave=k, rotulo=c["e"], titulo=c["t"], ubicacion=list(c.get("r", [])), tipo=tipo,
               ambito="real_decreto" if k.startswith("rd-") else "norma", texto=texto, notas=notas)
    m = RE_RANGO.match(k)
    if m:
        out["rango"] = [int(m.group(1)), int(m.group(2))]
    return out


def exporta():
    alias_plantilla = alias_de_plantilla()
    normas, resumen = [], []
    av, av_fecha = ({}, None) if SIN_CONTRASTE else build.avisos_boe(build.NORMAS)
    if av_fecha is None and not SIN_CONTRASTE:
        raise SystemExit("no he podido contrastar con boe.es: no se exporta sin avisos de diferencia/reforma (usa --sin-contraste solo a sabiendas)")
    for cfg in build.NORMAS:
        raw, meta, chunks, avisos, n_cab, n_art, n_disp = build.analiza(cfg)
        futuras = build.aplica_futuras(cfg["sigla"], chunks)   # mismo texto por defecto que la web: la redacción VIGENTE hoy
        bloques = [bloque(c) for c in chunks]
        for b_ in bloques:   # reforma ya publicada que aún no rige: la posterior, opcional, para que LexArt pueda ofrecerla (la web ya lo hace)
            if b_["clave"] in futuras:
                f_ = futuras[b_["clave"]]
                b_["posterior"] = dict(fecha=f_["f"], origen=f_["o"], parrafos=f_["p"], cambios=f_["s"])
        claves = [b["clave"] for b in bloques]
        if len(set(claves)) != len(claves):
            repetidas = [k for k, n in Counter(claves).items() if n > 1][:5]
            raise SystemExit(f"[{cfg['sigla']}] claves repetidas en la exportación: {repetidas}")
        if len(bloques) != len(chunks):
            raise SystemExit(f"[{cfg['sigla']}] bloques exportados {len(bloques)} != bloques de build.py {len(chunks)}")
        alias = cfg["alias"].split("|") if cfg.get("alias") else alias_plantilla.get(cfg["id"], [])
        if not alias:
            raise SystemExit(f"[{cfg['sigla']}] sin alias (ni en NORMAS ni en plantilla.html)")
        normas.append(dict(
            id=cfg["id"], sigla=cfg["sigla"], boe=cfg["boe"], titulo=meta.get("title", cfg["corto"]), corto=cfg["corto"], alias=alias,
            url=meta.get("url_html_consolidada", ""), estado=meta.get("status", ""), actualizada=meta.get("last_updated", ""),
            sha256=hashlib.sha256(raw).hexdigest(), dir=cfg.get("dir", "es"),
            fuente="DOGV, importado a mano" if cfg.get("dir") == "es-vc" else "texto consolidado del BOE",
            recuento=dict(articulos=n_art, disposiciones=n_disp, bloques=len(chunks)),
            contraste=None if av_fecha is None else dict(fecha=av_fecha, avisos=av.get(cfg["sigla"], {})), bloques=bloques))
        resumen.append((cfg["sigla"], n_art, n_disp, len(bloques)))
    return dict(esquema=ESQUEMA, compilado=dt.date.today().isoformat(), corpus_commit=build.git_head(), normas=normas), resumen


def contrasta_con_manifiesto(datos):
    """El manifiesto del último build (normas.json) debe describir exactamente lo que se exporta."""
    f = AQUI / "normas.json"
    if not f.is_file():
        raise SystemExit("falta normas.json: ejecuta antes python3 build.py")
    man = {m["id"]: m for m in json.loads(f.read_text(encoding="utf-8"))["normas"]}
    for n in datos["normas"]:
        m = man.get(n["id"])
        if m is None:
            raise SystemExit(f"normas.json no tiene la norma {n['id']}: ejecuta python3 build.py")
        if m["sha256"] != n["sha256"]:
            raise SystemExit(f"normas.json es de otro texto que el de [{n['sigla']}] (huella distinta): ejecuta python3 build.py")
        r = n["recuento"]
        if (m["bloques"], m["articulos"], m["disposiciones"]) != (r["bloques"], r["articulos"], r["disposiciones"]):
            raise SystemExit(f"[{n['sigla']}] la exportación cuenta {r} y build.py {(m['bloques'], m['articulos'], m['disposiciones'])}")
    if set(man) != {n["id"] for n in datos["normas"]}:
        raise SystemExit("normas.json y la exportación no tienen las mismas normas")


SIN_CONTRASTE = False


def main():
    global SIN_CONTRASTE
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-contraste", action="store_true", help="exporta sin consultar boe.es (no recomendado)")
    ap.add_argument("--salida", default=str(AQUI / "salida" / "lexart-corpus.json"))
    a = ap.parse_args()
    SIN_CONTRASTE = a.sin_contraste
    datos, resumen = exporta()
    contrasta_con_manifiesto(datos)
    total = sum(r[3] for r in resumen)
    if total != sum(len(n["bloques"]) for n in datos["normas"]):
        raise SystemExit("la suma de bloques no coincide")
    destino = Path(a.salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    # relectura: lo escrito es lo que se cuenta
    leido = json.loads(tmp.read_text(encoding="utf-8"))
    if sum(len(n["bloques"]) for n in leido["normas"]) != total:
        raise SystemExit("la relectura del fichero no coincide con lo exportado")
    tmp.replace(destino)
    for sigla, ca, cd, nb in resumen:
        print(f"{sigla:12s} {ca:5d} artículos + {cd:3d} disposiciones  ({nb} bloques)")
    print(f"{len(resumen)} normas, {total} bloques -> {destino} ({destino.stat().st_size/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
