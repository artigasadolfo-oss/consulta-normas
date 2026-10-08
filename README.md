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

Normas incluidas (21): LEC, LO 1/2025, LAU, LPH, Código Civil, LOPJ, Ley 38/1999 de Ordenación de la Edificación (LOE),
RDL 1/2007 (texto refundido de la Ley General de Consumidores y Usuarios, TRLGDCU), Decreto 11/1995
del Gobierno Valenciano de prestación de servicios a domicilio (D 11/1995, solo en el DOGV, importado a mano), Constitución y,
añadidas el 08-10-2026 para compartir fuente con LexArt: Ley 12/2023 (vivienda), Ley Hipotecaria (LH), Texto refundido de la Ley Concursal
(TRLC), Ley 5/2012 (mediación), Ley de la Jurisdicción Voluntaria (LJV), Estatuto General de la Abogacía (EGAE, RD 135/2021),
Ley de Asistencia Jurídica Gratuita (LAJG), Código Penal (CP), Ley de Enjuiciamiento Criminal (LECrim), LO 5/2024 del Derecho de Defensa (LODD)
y Arancel de la Procura (RD 434/2024).
(La LOPDGDD se retiró el 07-10-2026 a petición de Adolfo; la Ley valenciana 3/2004 de calidad de la edificación se probó y se descartó.)

El número de artículos de cada norma se muestra en su cabecera y en la portada (no en el menú, para dejar sitio al título completo); es el de **artículos reales** (con sus bis/ter, y los números que cubren los bloques derogados «Artículos X a Y»); las disposiciones adicionales, transitorias, derogatorias y finales se cuentan aparte («867 artículos · 49 disposiciones»).

## Favoritos

Bloque «Favoritos» arriba del menú (en ocre). Lo fijas tú, a mano, y queda en el orden en que lo fijas:

- **Normas:** estrella a la derecha de cada norma de la lista «Normas».
- **Artículos:** estrella «Favorito» de la barra del lector, o tecla `F`. El artículo **no** sale suelto: cuelga de su norma
  (si la norma no estaba fijada, aparece en Favoritos por él). Los artículos de una norma se muestran **ordenados por número**
  y con su título como descripción; la flecha de la norma los pliega o despliega, y pulsar la norma abre su índice y los despliega.
- No hay contador ni orden por uso. Todo se guarda solo en el dispositivo (`localStorage`: `normas.fav`, `normas.favx`).
  «Restablecer favoritos» (al final de la portada) lo vacía.

## Índice de conceptos (en construcción; NO publicado)

Pantalla `#i` («Índice de conceptos» en el menú): voces jurídicas con los preceptos que las **regulan**, los de **conexión doctrinal**
(no textual), lo que **no consta en norma** y lo que **rige fuera de la herramienta**. El **contenido lo redacta y mantiene el
Armero** (carpeta `indice/*.yaml`, copiada tal cual de sus entregas con `scripts/copia_muestra_armero.py`); taller solo lo valida y
lo muestra. `build.py` falla si una remisión apunta a un artículo que no existe. El buscador ofrece la voz sobre los resultados.

**Caducidad (criterio del Armero):** una voz caduca por **artículo citado**: si cambia el texto entero de un artículo que cita (con sus
notas de reforma), si desaparece, si aparece un «N bis» junto a uno citado, o si cambia uno de su lista `vigilar`. La referencia es el
texto del commit del espejo con que la revisó (`espejo: "legalize-es@..."`). Los cambios en artículos no citados no caducan nada:
el vigía avisa al Adolfo, una sola vez por conjunto, para que se lo reenvíe al Armero. Pruebas: `scripts/test_indice.py`.

**Nunca hagas `git pull` a mano en el espejo** (`~/Documents/iA/LEYES/legalize-es`): lo hace el cron de las 10:34 y su vigilante compara
el `HEAD` de antes y después; si lo adelantas, pierde los avisos. Para mirar el origen: `git fetch` y `git diff HEAD @{u}`.

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

Para añadir una norma: una línea en `NORMAS` de `build.py` (BOE-ID, siglas) y, si tiene alias propios, el campo `alias` (formas de
citarla, separadas por `|`, en minúscula y sin tildes) y `nombres` (cómo la nombran otras normas, para enlazar las remisiones): `build.py`
los vuelca en `ALIAS`, `NOMBRES_NORMA`, `SAFE` y `RE_OTRA` de la plantilla. Las diez primeras llevan los suyos escritos a mano en `plantilla.html`.
Opciones del analizador (por norma): `secuencial` (LO 1/2025), `previo_rdl` (etiqueta del RD/Decreto que aprueba el texto refundido o la norma),
`anexo` (regex del encabezado desde el que empieza el texto aprobado: lo anterior es del RD y sus bloques llevan la clave `rd-…`; sin `anexo`,
el corte es el primer artículo 1), `rangos_abrev` (reconoce «Arts. 934 a 946», LECrim). El analizador entiende además «Artículo 624. bis.»,
«588 bis b.», «1º.», «Artículos 638 y 639» y «Disposición adicional primera» sin punto. Las disposiciones, el preámbulo y el encabezado de las
normas con `alias` enlazan solo con nombre explícito de la ley (en ellas el texto citado suele ser de otra ley).

## Exportación para LexArt

`python3 scripts/exportar_para_lexart.py` (después de `python3 build.py`) escribe `salida/lexart-corpus.json` (carpeta ignorada por git). Parte de
`build.analiza()`, la misma función que usa el build de la web: LexArt no vuelve a trocear nada. Falla si la suma de bloques no coincide con la que
cuenta `build.py` / `normas.json`, si una clave se repite o si un bloque pierde líneas. Esquema `consulta-normas/lexart-corpus@1`
(documentado entero en la cabecera del script): por norma `id, sigla, boe, titulo, corto, alias[], url, estado, actualizada, sha256, dir, fuente,
recuento{articulos, disposiciones, bloques}` y `bloques[]` con `clave, rotulo, titulo, ubicacion[], tipo (articulo|disposicion|preambulo|encabezado),
ambito (norma|real_decreto), rango?, texto, notas[]`. Incluye la Constitución y el D 11/1995 (`fuente: "DOGV, importado a mano"`).
Pruebas: `env -u PYTHONPATH python3.12 scripts/test_nuevas.py`.

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
