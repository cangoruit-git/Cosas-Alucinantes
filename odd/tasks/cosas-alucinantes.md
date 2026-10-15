# Cosas-Alucinantes: memoria vectorial de Parafantástico

Cerebro de memoria con la información que dice Parafantástico en sus videos, en base vectorial, consultable por cualquier IA, con 3 capas de evidencia (real / sin confirmar / creencia). Proyecto público en github.com/cangoruit-git/Cosas-Alucinantes.

## Specs

- S1 — Ingestar toda la información que dice Parafantástico en sus videos: *"quiero guardar toda la informacion de lo que dice parafantastico en sus videos"*.
- S2 — Guardarla en base vectorial como memoria para consultas: *"tenerlo guardado en una base vectorial para que sirva de memoria para que cuando te pregunte algo puedas saber lo que decia el"*.
- S3 — Tres capas separadas de evidencia: datos conectados con fuentes públicas reales, datos no confirmados, y creencias de personas supersticiosas: *"quiero conectarlo con datos reales publicos, otra parte con datos no confirmado, y otra con creencias que hay de personas supersticiosas"*.
- S4 — Arquitectura de "cerebro con recuerdos" que cualquier IA pueda conectar y leer (estilo Engram con proyectos): *"se supone que hagamos un tipo de cerebro con recuerdos para que cualquier ia pueda conectarse y leerlo, a partir de eso hablar siendo bastante parecido a lo que hace engram con los proyectos"*.
- S5 — La capa "real" exige confirmación con información pública relevante: *"para esto los datos deben estar confirmados con informacion real relevante para el tema"*.
- S6 — Arranque con un solo tema: DIOS Y CRISTO (decisión del usuario, verbatim: "dios y cristo").
- S7 — Transcripción por Whisper (audio de los videos).
- S8 — Stack: Python + ChromaDB local, embeddings multilingües locales (sin API keys).
- S9 — Repositorio: <https://github.com/cangoruit-git/Cosas-Alucinantes> (público, vacío), cuenta GitHub cangoruit-git ya autenticada.

- S10 — La memoria debe capturar lo que la IMAGEN muestra, incluido lo explícito que el audio suaviza u omite: *"aun hay un problema que es las partes sensuradas del texto pero que se pueden ver en el video de forma explicita"* (aclarado por el usuario: el caso es "lo explicito es la imagen, no el texto").
Criterio de capas (editorial, documentado en docs/criterios-capas.md):
- `real`: la afirmación o el referente existen y están corroborados por una fuente pública verificable (registros, prensa, informes, Wikipedia/Wikidata con fuente). Se marca SOLO con evidencia adjunta.
- `sin_confirmar`: afirmación del canal sin corroboración pública (por defecto, la mayoría).
- `creencia`: supersticiones, folklor y creencias populares (no verificables por diseño; se documenta su origen cultural).

## Tasks

- T1 — Setup entorno (venv, deps, ffmpeg, smoke-test imports). Specs S8-S9. Ruta: inline. Commit: `chore: scaffold proyecto Cosas-Alucinantes`.
- T2 — Módulo catálogo: lista completa de videos del canal (yt-dlp: id, título, URL, duración, fecha, descripción) → `data/catalog.sqlite`. Specs S1, S6. Ruta: inline. Commit: `feat(catalog): ingesta de catálogo del canal`.
- T3 — Módulo transcripción: descarga audio + Whisper (faster-whisper), por tema, resumible, segmentos JSON con timestamps. Specs S1, S6, S7. Ruta: inline + bash_background para el lote. Commit: `feat(transcribe): transcripción Whisper resumible`.
- T4 — Módulo chunking: fragmentos superpuestos con metadatos (video_id, título, URL, t_inicio, t_fin). Specs S1, S2. Ruta: inline. Commit: `feat(chunk): fragmentación con contexto`.
- T5 — Módulo clasificación en 3 capas con criterios documentados; clasificador por defecto + hook opcional de LLM. Specs S3. Ruta: inline. Commit: `feat(classify): capas de evidencia`.
- T6 — Módulo verificación: extracción de afirmaciones/entidades + corroboración con fuentes públicas (Wikipedia/Wikidata + web), registro de evidencia; gate de la capa `real`. Specs S3, S5. Ruta: inline + worker de revisión. Commit: `feat(verify): corroboración con fuentes públicas`.
- T7 — Módulo store: ChromaDB con 3 colecciones (real/sin_confirmar/creencia), embeddings locales, upsert. Specs S2, S8. Ruta: inline. Commit: `feat(store): base vectorial ChromaDB`.
- T8 — Servidor MCP + cliente de consulta: `recall`, `recall_video`, `catalog_search`, `tiers_summary`; cualquier IA se conecta (estilo Engram). Specs S2, S4. Ruta: inline. Commit: `feat(mcp): servidor de memoria para cualquier IA`.
- T9 — Piloto: correr el pipeline completo sobre el tema dios-cristo, verificar capa `real` con revisión. Specs S5, S6. Ruta: inline + verificación. Commit: `feat(pilot): base del tema dios-cristo`.
- T10 — Docs: README, criterios de capas, cómo conectar cualquier IA. Spec S4. Ruta: inline. Commit: `docs: README y criterios de capas`.
- T11 — Push a GitHub (decisión del usuario; cuenta cangoruit-git). Spec S9. Ruta: usuario.
- T12 — Capa visual: muestreo de fotogramas (PyAV) + etiquetado con CLIP multilingüe local; etiquetas adjuntas al fragmento por minuto y visibles en MCP. Spec S10. Ruta: inline. Commit: `feat(vision): capa visual (lo que muestra el video)`.

## Log

- L1 (2026-02-17, usuario, verbatim): "quiero guardar toda la informacion de lo que dice parafantastico en sus videos, y tenerlo guardado en una base vectorial para que sirva de memoria para que cuando te pregunte algo puedas saber lo que decia el, ademas quiero conectarlo con datos reales publicos, otra parte con datos no confirmado, y otra con creencias que hay de personas supersticiosas"
- L2 (usuario, repo): "https://github.com/cangoruit-git/Cosas-Alucinantes.git ese el repo de github, para entrar usa la cuenta de cangoruit" — repo público vacío; cuenta cangoruit-git autenticada.
- L3 (usuario, respuestas múltiple choice): Alcance = "Solo un tema primero" (tema pendiente de elegir). Texto = "Whisper (transcripción de audio)". Stack = "Python + ChromaDB local". Clasificación (custom, verbatim): "se supone que hagamos un tipo de cerebro con recuerdos para que cualquier ia pueda conectarse y leerlo, a partir de eso hablar siendo bastante parecido a lo que hace engram con los proyectos. para esto los datos deben estar confirmados con informacion real relevante para el tema"
- L4 (descripción del repo en GitHub): "informacion en base de datos vectorial sobre supersticiones o conspiraciones"
- L5 (usuario, tema del piloto, verbatim): "dios y cristo"
- L6 (usuario, estrategia de transcripción): "De a 5 primero" (validar el pipeline completo en 5 videos antes del resto).
- L7 (decisiones técnicas del entorno, T3): las cookies de navegador no se pueden desencriptar (App-Bound, bug yt-dlp #10927) y el cliente `android` de YouTube saltea el muro anti-bot; PyAV 19 rompió `metadata_errors` y `pf/transcribe.py` aplica un parche compat en runtime.
- L8 (auditoría del piloto): la 1ª pasada de la capa `real` promovía ruido ("Doblado de chapa", "Mente universal", "Tales of Vesperia"). Correcciones con tests: gate de título (`5aba8e3`), gate de ENTIDAD del tema (`ebebf89`); resultado honesto `real: 0` (el canal afirma mayormente cosas no verificables). Bugs detectados y corregidos: fragmentos huérfanos al re-ingerir (`5ee4d13`) y `_format_hit` devolviendo vacío con URLs de YouTube (`1c56a65`).
- L9 (verificación independiente, gentle-ai-verify, read-only): S1-S9 **CUMPLE**; avisos corregidos en el commit `7d515ed` (criterios-capas alineado al código real 0.55/0.25 + gates, código muerto eliminado de pipeline, sondas de regresión agregadas a los tests).

## Commits (evidencia)

- T1 scaffold: `51010ee`
- T2 catálogo + matcher: `7594e30`
- fix catalog themes: `21ce8f6`
- T4 chunking: `a5af6fe`
- T5 clasificación: `1ef3081`
- T6 verificación + criterios: `df0f1a3`
- T7 store ChromaDB: `6e7ab19`
- T8 servidor MCP (MCPServer 2.x): `2da19c4`
- T9 pipeline + script piloto: `7216823`
- T10 README: `e1ef109`
- T3 transcripción validada: `ede6d90`
- config YT (clientes/cookies): `4fa3584`
- store video_chunks: `755128b`
- query CLI: `269c85e`
- verificación endurecida (429, título, entidad): `42c0159`, `5aba8e3`, `ebebf89`
- fix huérfanos + fix MCP: `5ee4d13`, `1c56a65`
- log de spec / style: `727228f`, `16d4d80`
- L10 (usuario, requisito nuevo, verbatim): "aun hay un problema que es las partes sensuradas del texto pero que se pueden ver en el video de forma explicita" → al preguntar cuál de los casos era, eligió "Lo explicito es la imagen" (escenas gráficas que el audio cuenta suave).
