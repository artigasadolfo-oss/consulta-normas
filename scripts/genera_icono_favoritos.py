#!/usr/bin/env python3.12
"""Genera apple-touch-icon.png (180x180) de Consulta de normas con el PATRÓN DE LAS CALCULADORAS.

Procedimiento (skill webs-despacho, Regla 2): se parte del icono de «Calculadora de plazos» (mismo monograma:
barras, «A», guion ocre, fondo #FAFAFB, esquinas transparentes), se borra SOLO la franja del nombre y se
compone «NORMAS» con la misma letra (Geist Medium), cuerpo, color y espaciado, calibrados contra el propio
«PLAZOS» original. Se verifica que la zona del monograma queda idéntica al original.

Uso:  env -u PYTHONPATH python3.12 scripts/genera_icono_favoritos.py [--calibrar]
Necesita Geist-500.ttf (https://fonts.googleapis.com/css2?family=Geist:wght@500, formato truetype) en
$GEIST_TTF o en scripts/Geist-500.ttf.
"""
import itertools, os, pathlib, sys
from PIL import Image, ImageChops, ImageDraw, ImageFont

AQUI = pathlib.Path(__file__).resolve().parents[1]
BASE = pathlib.Path.home() / "Programación/Calculadora de plazos/apple-touch-icon.png"
TTF = pathlib.Path(os.environ.get("GEIST_TTF", AQUI / "scripts/Geist-500.ttf"))
BG, INK = (250, 250, 251, 255), (32, 36, 41)
BANDA = (126, 153)        # filas que contienen el nombre (y nada más): y 132-147 en el original
SS = 8                    # supersampling


def borra_banda(im):
    im = im.copy()
    d = ImageDraw.Draw(im)
    d.rectangle([4, BANDA[0], 175, BANDA[1]], fill=BG)
    return im


def render(texto, size, track, base_y, cx=90.0):
    """Capa RGBA de 180x180 con el texto (tinta INK) centrado en cx, línea base en base_y."""
    font = ImageFont.truetype(str(TTF), int(round(size * SS)))
    advs = [font.getlength(ch) for ch in texto]
    xs, x = [], 0.0
    for a in advs:
        xs.append(x)
        x += a + track * SS
    izq = font.getbbox(texto[0], anchor="ls")[0]
    der = xs[-1] + font.getbbox(texto[-1], anchor="ls")[2]
    ancho = der - izq
    x0 = cx * SS - ancho / 2 - izq
    lienzo = Image.new("L", (180 * SS, 180 * SS), 0)
    dr = ImageDraw.Draw(lienzo)
    for ch, xi in zip(texto, xs):
        dr.text((x0 + xi, base_y * SS), ch, font=font, fill=255, anchor="ls")
    mascara = lienzo.resize((180, 180), Image.Resampling.LANCZOS)
    capa = Image.new("RGBA", (180, 180), INK + (0,))
    capa.putalpha(mascara)
    return capa


def compone(base_borrada, texto, size, track, base_y):
    return Image.alpha_composite(base_borrada, render(texto, size, track, base_y))


def error(a, b):
    """Diferencia media absoluta en la franja del nombre."""
    r = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).crop((0, BANDA[0], 180, BANDA[1]))
    return sum(r.convert("L").getdata()) / (180 * (BANDA[1] - BANDA[0]))


def calibra(orig):
    limpio = borra_banda(orig)
    mejor = None
    for size, track, by in itertools.product([x / 4 for x in range(72, 100)], [x / 4 for x in range(4, 18)],
                                             [x / 2 for x in range(284, 298)]):
        e = error(compone(limpio, "PLAZOS", size, track, by), orig)
        if mejor is None or e < mejor[0]:
            mejor = (e, size, track, by)
    return mejor


def main():
    if not TTF.is_file():
        sys.exit(f"Falta la fuente {TTF}")
    orig = Image.open(BASE).convert("RGBA")
    e, size, track, by = calibra(orig)
    print(f"calibración sobre PLAZOS: error medio {e:.3f}/255  cuerpo {size}px  espaciado {track}px  línea base y={by}")
    if "--calibrar" in sys.argv:
        scratch = pathlib.Path(os.environ.get("TMPDIR", "/tmp"))
        lado = Image.new("RGBA", (360, 180), (255, 255, 255, 255))
        lado.paste(orig, (0, 0)); lado.paste(compone(borra_banda(orig), "PLAZOS", size, track, by), (180, 0))
        lado.save(scratch / "calibracion_plazos.png")
        print("comparación original | reproducción:", scratch / "calibracion_plazos.png")
        return
    out = compone(borra_banda(orig), "NORMAS", size, track, by)
    destino = AQUI / "apple-touch-icon.png"
    out.save(destino)
    # verificación: la zona del monograma (y < 126) debe quedar IDÉNTICA al original
    dif = ImageChops.difference(orig.crop((0, 0, 180, BANDA[0])), out.crop((0, 0, 180, BANDA[0]))).getbbox()
    print("monograma idéntico al original:", dif is None)
    print("ok", destino)
    if dif is not None:
        sys.exit(1)


if __name__ == "__main__":
    main()
