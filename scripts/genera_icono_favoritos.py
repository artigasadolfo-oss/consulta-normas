#!/usr/bin/env python3
"""Genera apple-touch-icon.png (180x180) de Consulta de normas con el generador de ArrendArt.
Norma de favoritos (04-10-2026): fondo #FAFAFB, A gris, nombre de la app al pie, banda azul #1F5AA6."""
import importlib.util, os, pathlib, sys, tempfile

GEN = pathlib.Path.home() / "Programación/arrendart-app/tools/iconos/generar.py"
AQUI = pathlib.Path(__file__).resolve().parents[1]
tmp = tempfile.mkdtemp()
os.environ["ICONOS_SALIDA"] = tmp
os.environ["ICONOS_PUBLICO"] = tmp
spec = importlib.util.spec_from_file_location("generar", GEN)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
g.NOMBRE_APP = "NORMAS"
g.ACENTO_APP = "#1F5AA6"
g.renderizar(g.svg_favoritos("azul"), 1024, AQUI / "apple-touch-icon.png", 180)
print("ok", AQUI / "apple-touch-icon.png")
