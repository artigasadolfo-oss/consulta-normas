# Consulta de normas · Artigas Abogados

Herramienta de consulta rápida de normas para vistas y juicios. Un único `index.html` con los textos
incrustados: funciona abriéndolo como archivo local, **sin conexión**, y también publicado en GitHub Pages.

## Qué hace

- **Artículo directo**: `282 LEC`, `art. 18.3 de la LPH`, `1902 cc`, `5 lo 1/2025`, `da 1 lec`,
  `63-65 lec` (varios seguidos), `63, 65 lec`. Con `21` a secas lo muestra en todas las normas.
  `18.3` resalta el apartado 3.
- **Concepto**: cualquier palabra o frase (`declinatoria de jurisdicción`). Devuelve los artículos cuyo texto o
  título la contienen, ordenados por relevancia, con el término resaltado. Filtro por norma.
  Es búsqueda **textual**: no interpreta ni resume.
- **Enlaces entre artículos**: «artículo 63 de esta Ley» salta a ese artículo. Solo se enlaza cuando el destino
  es seguro; si la frase remite a otra norma que no está aquí, queda sin enlace.
- Teclado: `/` buscador, `↑ ↓` lista, `Enter` abrir, `← →` artículo anterior/siguiente,
  `1`-`9` abrir resultado, `Esc`. Móvil: menú, lista y lector en pantallas separadas.
- Copiar (cita + texto + fecha de consolidación), notas de reforma del BOE (ocultas por defecto), tamaño de letra,
  enlace al BOE, recientes.

Normas incluidas: LEC, LO 1/2025, LAU, LPH, Código Civil, LOPJ, Ley 38/1999 de Ordenación de la Edificación (LOE),
RDL 1/2007 (texto refundido de la Ley General de Consumidores y Usuarios, TRLGDCU), Decreto 11/1995
del Gobierno Valenciano de prestación de servicios a domicilio (D 11/1995, solo en el DOGV, importado a mano) y Constitución.
(La LOPDGDD se retiró el 07-10-2026 a petición de Adolfo; la Ley valenciana 3/2004 de calidad de la edificación se probó y se descartó.)

El número de artículos de cada norma se muestra en su cabecera y en la portada (no en el menú, para dejar sitio al título completo); es el de **artículos reales** (con sus bis/ter, y los números que cubren los bloques derogados «Artículos X a Y»); las disposiciones adicionales, transitorias, derogatorias y finales se cuentan aparte («867 artículos · 49 disposiciones»).

## Favoritos

Bloque «Favoritos» arriba del menú (resaltado en ocre): los **artículos que fijas** con la estrella de la barra del lector
(o la tecla `F`), y las **5 normas más consultadas** (sin contador visible). Al estrenar, las 5 normas son LEC, LO 1/2025, LAU,
LPH y Cciv; pasan a ordenarse solas por uso. Cada artículo abierto suma una consulta a su norma. Todo se guarda solo en el
dispositivo (`localStorage`: `normas.fav`, `normas.uso`), no viaja a ningún sitio y no se comparte entre dispositivos.
«Restablecer favoritos» (al final de la portada) borra ambas cosas.

## Origen y fidelidad del texto

Sale del corpus `legalize-es` (espejo del BOE consolidado) que ya mantiene el vigilante diario del BOE:
`~/Documents/iA/LEYES/legalize-es`. `build.py` trocea cada norma en artículos y **falla** si se pierde o sobra
una sola línea respecto a la fuente. El texto **no tiene valor oficial**: contrastar con boe.es antes de citar
literalmente (la propia página lo dice).

## Regenerar

```
cd ~/Programación/"Consulta de normas"
python3 build.py                                   # regenera index.html y normas.json
env -u PYTHONPATH python3.12 scripts/test_app.py   # 76 pruebas en Chromium real
env -u PYTHONPATH python3.12 scripts/test_offline.py
```

Para añadir una norma: una línea en `NORMAS` de `build.py` (BOE-ID, siglas) y, si tiene alias propios,
en `ALIAS` y `NOMBRES_NORMA` de `plantilla.html`.

## Vigía

`~/.hermes/scripts/vigila_consulta_normas.py` (cron `30edd99dd0d1`, diario 10:45, tras el vigilante del BOE de las 10:34)
compara la huella de cada fichero del corpus con la de `normas.json`. Silencio si todo coincide; aviso con las normas
afectadas y el comando de arriba si alguna cambió; **error visible** (nunca silencio) si no puede comprobar.
Test: `~/.hermes/scripts/tests/test_vigila_consulta_normas.py`.

**Normas importadas a mano del DOGV** (las que no están en el espejo, p. ej. el Decreto 11/1995): se guardan con
`dogv.py texto --id N --guardar` (carpeta `~/Documents/iA/LEYES/DOGV/`, texto verbatim) y se convierten con
`python3 scripts/importa_dogv.py "<fichero>"` en `legalize-es/es-vc/<CVE>.md` (queda SIN versionar en el clon git). No se
actualizan solas, así que su entrada en `build.py` lleva `dogv_id` y el vigía consulta cada día su estado en la API del
DOGV: avisa si deja de constar VIGENTE, si hay una modificación pendiente o si aparece una consolidación.

## Offline

- Archivo local: abrir `index.html` (funciona sin red; las fuentes van incrustadas).
- Publicada: `sw.js` guarda la página en la primera visita; después abre sin red. En iPhone/iPad:
  Compartir → Añadir a pantalla de inicio.
- Los datos van comprimidos (gzip + base64) y se descomprimen en el navegador (Safari 16.4+ / Chrome 80+).

## Pendiente de decisión

Un índice **jurídico** de conceptos («declinatoria → arts. 63 a 65 y 39») sería criterio del bot Armero, no de este
perfil técnico. La búsqueda actual es solo textual.
