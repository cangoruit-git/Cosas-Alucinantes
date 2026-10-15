# Criterios de capas de evidencia

Contrato editorial de **Cosas-Alucinantes**. Toda la información de los videos
de Parafantástico se clasifica en una de tres capas. El criterio es del
proyecto (documentado acá), la clasificación automática es un **punto de
partida**, y la revisión editorial del humano es la autoridad final.

## Las tres capas

| Capa | Definición | Ejemplo |
| --- | --- | --- |
| `real` | La afirmación o su referente están documentados en fuentes públicas verificables (prensa, informes, registros, Wikipedia con fuentes, organismos). SIEMPRE con evidencia adjunta (título, URL, fragmento). | "El Proyecto MKUltra existió: la CIA reconoció los experimentos de control mental" — con evidencia del informe del Senado/artículo. |
| `sin_confirmar` | Afirmación del canal sin corroboración pública. **Capa por defecto**: dudar es `sin_confirmar`. | "Los grises vienen de Zeta Reticuli". |
| `creencia` | Superstición, folklor o creencia popular. No es verificable como hecho; se documenta su existencia cultural (no se afirma que sea falsa ni verdadera). | "El gato negro trae mala suerte" — documentado como creencia popular. |

## Cómo se decide

1. **Clasificación automática** (`pf/classify.py`):
   - `creencia` solo con señales supersticiosas fuertes (marcas + discurso
     folklor: "se dice que", "mi abuela", "los supersticiosos"...).
   - `posible_real` solo con referentes verificables claros (informe, FBI,
     CIA, forense, año, archivos...). Es un CANDIDATO, nunca `real` aún.
   - Todo lo demás → `sin_confirmar`.
   - **Regla de oro**: nunca inventar evidencia; la duda siempre es
     `sin_confirmar`.
2. **Verificación** (`pf/verify.py`): para candidatos, busca fuentes públicas
   (Wikipedia ES por ahora; Wikidata/prensa próximos). Veredictos por
   solapamiento con la fuente:
   - `apoya` (>= 0.45): la fuente sustenta el contenido → promueve a `real`.
   - `contexto` (0.20–0.45): la fuente menciona los referentes sin sustentar
     la afirmación → se queda en `sin_confirmar` (la evidencia viaja con él).
   - sin solapamiento → se descarta el ruido.
3. **Revisión editorial** (humano): el piloto genera un reporte de la capa
   `real` con su evidencia para auditoría. El humano puede corregir cualquier
   fragmento (reclasificar). Las correcciones se guardan en la base y ganan a
   la clasificación automática.

## Qué NO hace este sistema

- No afirma que una creencia sea falsa ni verdadera: la documenta como
  creencia popular (con fuente cultural).
- No promueve nada a `real` sin evidencia adjunta citada.
- No mezcla capas en las respuestas: una consulta devuelve cada fragmento con
  su capa y su evidencia, para que quien pregunta sepa qué está leyendo.