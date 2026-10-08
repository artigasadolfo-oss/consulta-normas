# Informe N-1 · la web «Consulta de normas» pasa de 10 a 21 normas (08-10-2026)

Rama `normas-21` (copia aislada de la web). Sin publicar. Compilada desde la copia congelada del espejo `corpus-aca28304d` (ver «Pendiente: actualizar al 7 de octubre»).

## Qué hay
- Las 11 normas del BOE que ya tenía LexArt: Ley 12/2023, LH, TRLC, Ley 5/2012, LJV, EGAE, LAJG, CP, LECrim, LODD y Arancel de la Procura. Con las 10 anteriores, 21 normas.
- Opción `anexo` en el analizador (LH, TRLC, EGAE y Arancel están dentro de la norma que las aprueba).
- Exportador `scripts/exportar_para_lexart.py` → `salida/lexart-corpus.json` (esquema `consulta-normas/lexart-corpus@1`, documentado en su cabecera y en el README). Parte de la misma función `build.analiza()` que usa la web: no hay segundo analizador.
- Pruebas nuevas (`scripts/test_nuevas.py`) y contraste con boe.es de las normas nuevas.
- `index.html`: 3,83 MB (antes 2,47 MB).

## Medido (por el asistente, no por el agente)
- Las 10 normas antiguas: mismos recuentos y mismas huellas que antes (comparación contra `HEAD:normas.json`).
- Reconstrucción sin pérdidas (`build.py --comprobar`, código 0) con las 21 normas.
- Recuentos de las 11 nuevas contra las cabeceras del espejo: cuadran; las diferencias son rangos derogados («Artículos X a Y»), bis/ter y anexos.
- `scripts/test_app.py --capturas`: **505 comprobaciones, 0 fallos** (la versión original: 504, 0 fallos).

## Cambios de test (a propósito)
1. «declinatoria de jurisdicción»: 12 resultados en vez de 8. Las 8 de la LEC siguen; las 4 nuevas están en normas añadidas (LECrim 666 y 674, Ley 5/2012 D. final 3.ª y preámbulo). El test cuenta ahora 8 de la LEC y 12 en total.
2. «artículo 5 de la Ley Hipotecaria»: antes «NO se enlaza» (la LH no estaba); ahora enlaza a `#a/lh/5`, correcto. Se añade que «artículo 5 de la Ley de Aguas» (norma que no está) sigue sin enlazar.

## Un defecto que había y se corrigió
El `index.html` que dejó el agente se construyó antes de ejecutar el contraste con boe.es: faltaban los avisos «este texto difiere del consolidado» de la LAU (art. 2, 7…). Reconstruido: vuelven los 34 de la LAU. El test lo detectó (falló el apartado 3 del art. 2 LAU).

## Pendiente
- **Actualizar al 7 de octubre**: el espejo vivo trae LEC y LAU (y Ley 12/2023) del 07-10-2026 (reforma del RDL 29/2026 y otras). La web enseña hoy LAU del 02-10 y LEC del 05-10. Actualizar caduca 26 voces del índice del Armero, que debe revisarlas.
- **Rótulos «Capítulo» pegados al texto**: `ESTRUCT` solo reconoce «CAPÍTULO»/«TÍTULO» en mayúsculas; la LECrim y el CC escriben «Capítulo I». El rótulo queda dentro del texto del artículo vecino y no en su ubicación. LexArt los quita al importar. Arreglar en origen cuando la otra sesión comitee su cambio de `ESTRUCT` (comentario del CC, sin comitear en la carpeta original).
- Nombres con que se citan «Ley Concursal», «Ley de Mediación», «Ley de Vivienda»: sin enlace de momento (seguro frente a enlace equivocado).
- Ampliar el vigilante diario de frescura a las 21 normas y a LexArt (vive en el perfil raíz).
- `eli` en el esquema de la exportación (LexArt lo deja vacío).
