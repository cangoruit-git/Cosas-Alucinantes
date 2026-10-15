# Cosas-Alucinantes

**Memoria vectorial de Parafantástico** — una base de datos con la información
que dice Parafantástico en sus videos (canal uruguayo, 1.5M de suscriptores),
organizada en **tres capas de evidencia**, consultable por **cualquier IA**
vía servidor MCP (estilo Engram).

> *"Para hechos fantásticos, se necesitan pruebas fantásticas"* — el criterio
> de este proyecto es documentar siempre de qué capa de evidencia viene cada
> cosa, con fuente adjunta cuando existe.

## Las tres capas

| Capa | Qué significa | Ejemplo |
| --- | --- | --- |
| `real` | El referente o la afirmación están corroborados por **fuentes públicas** (con evidencia adjunta: título, URL, fragmento). | "El Proyecto MKUltra existió" → con la fuente que lo documenta. |
| `sin_confirmar` | Lo que dice el canal **sin corroboración pública** (capa por defecto; dudar = sin confirmar). | "Los grises vienen de Zeta Reticuli". |
| `creencia` | **Supersticiones y creencias populares**, documentadas como creencia cultural (no como hecho verdadero ni falso). | "El gato negro trae mala suerte". |

Criterios editoriales completos: [`docs/criterios-capas.md`](docs/criterios-capas.md).

## Arquitectura

```text
YouTube ──> yt-dlp (audio) ──> Whisper (transcripción con timestamps)
   └─> fragmentos (chunks con contexto)
        └─> clasificación (creencia / posible_real / sin_confirmar)
             └─> verificación contra Wikipedia ES (evidencia; solo 'apoya' promueve a real)
                  └─> ChromaDB: 3 colecciones (una por capa), embeddings locales
                       └─> Servidor MCP: cualquier IA consulta la memoria
```

Módulos (`pf/`): `catalog`, `transcribe`, `chunk`, `classify`, `verify`,
`store`, `pipeline`, `mcp_server`. Cada uno con tests deterministas en
`tests/` (sin red, sin modelos descargados).

## Setup

Requiere Python 3.12+ y Git. Todo es local y sin API keys.

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
# (.venv/bin/pip ... en Linux/macOS)
```

## Uso rápido

```bash
# 1. Sincronizar el catálogo del canal y seleccionar el tema
.venv/Scripts/python -m scripts.sync_catalog

# 2. Descargar + transcribir un tema (resumible; el audio ya bajado se saltea)
.venv/Scripts/python -m scripts.transcribe_theme --limit 5

# 3. Ingestar: fragmentar, clasificar, verificar y guardar en ChromaDB
.venv/Scripts/python -m scripts.ingest_theme

# 4. Consultar la memoria
.venv/Scripts/python -m scripts.query "¿qué dijo sobre la sábana santa?"
```

La cola de revisión de la capa `real` (fragmentos promovidos con su evidencia)
se escribe en `data/review_tier_real.jsonl` para auditoría editorial.

## Conectar CUALQUIER IA (MCP)

El servidor expone las herramientas `recall`, `recall_video`, `catalog_search`,
`video_info` y `tiers_summary` por el protocolo MCP estándar.

```bash
.venv/Scripts/python -m pf.mcp_server
```

Registrarlo en un cliente MCP (ej. **Claude Desktop**):

```json
{
  "mcpServers": {
    "cosas-alucinantes": {
      "command": "C:\\ruta\\a\\BDparafantastico\\repo\\.venv\\Scripts\\python.exe",
      "args": ["-m", "pf.mcp_server"],
      "cwd": "C:\\ruta\\a\\BDparafantastico\\repo"
    }
  }
}
```

Desde ahí cualquier IA pregunta en lenguaje natural y recibe fragmentos de lo
que dijo Parafantástico, cada uno con su **capa de evidencia**, el minuto del
video y la fuente (si es `real`). La IA no mezcla capas: el que pregunta sabe
qué está leyendo.

## Configuración (variables de entorno)

| Variable | Default | Para qué |
| --- | --- | --- |
| `PF_WHISPER_MODEL` | `small` | Modelo Whisper (`tiny`/`base`/`small`/`medium`/`large-v3`) |
| `PF_WHISPER_DEVICE` | `cpu` | `cpu` o `cuda` |
| `PF_EMBED_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Embeddings locales |
| `PF_YT_PLAYER_CLIENTS` | `web,android,tv` | Clientes de YouTube para saltear el muro anti-bot |
| `PF_YT_COOKIES` | `edge:Default,chrome:Default` | Reintentos con cookies de navegador |

## Estado del proyecto

- Piloto: tema **Dios y Cristo** (52 videos detectados).
- Pendientes: auditar la cola de revisión de la capa `real`, transcribir el
  resto del set, más fuentes de verificación (Wikidata, prensa).

## Notas técnicas (Windows)

- PyAV 19+ rompió `av.open(metadata_errors=...)`: `pf/transcribe.py` aplica un
  parche compat en runtime al cargar Whisper (no toca site-packages).
- YouTube puede pedir login: el descargador reintenta con los clientes
  `android`/`tv` (saltea el muro) y luego con cookies del navegador.
- Los datos (`data/`) no se versionan: audio, transcripciones y ChromaDB.
