"""Configuración central del proyecto (rutas, canal, modelos)."""

from __future__ import annotations

import os
from pathlib import Path

# ── Rutas canónicas ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
AUDIO_DIR = DATA / "audio"
TRANSCRIPTS_DIR = DATA / "transcripts"
CHROMA_DIR = DATA / "chroma"
CATALOG_DB = DATA / "catalog.sqlite"
REVIEW_QUEUE = DATA / "review_queue.jsonl"

# ── Canal ────────────────────────────────────────────────────────────────────
CHANNEL_URL = "https://www.youtube.com/@parafantastico/videos"
CHANNEL_HANDLE = "@parafantastico"
CHANNEL_ID = "UCDELrgcBAh9hAKfZc_B-CCQ"

# ── Capas de evidencia ───────────────────────────────────────────────────────
TIERS = ("real", "sin_confirmar", "creencia")
TIER_REAL = "real"
TIER_UNCONFIRMED = "sin_confirmar"
TIER_BELIEF = "creencia"
# La clasificación automática puede marcar "posible_real"; solo verificación
# con evidencia pública lo promueve a "real".
TIER_POSSIBLE_REAL = "posible_real"

# ── Whisper (transcripción) ──────────────────────────────────────────────────
WHISPER_MODEL = os.environ.get("PF_WHISPER_MODEL", "small")  # tiny/base/small/medium/large-v3
WHISPER_LANG = "es"
WHISPER_DEVICE = os.environ.get("PF_WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_BEAM_SIZE = 5

# ── Embeddings (locales, sin API keys) ───────────────────────────────────────
EMBED_MODEL = os.environ.get("PF_EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

# ── Chunking ─────────────────────────────────────────────────────────────────
CHUNK_TARGET_CHARS = 700
CHUNK_MAX_CHARS = 1000
CHUNK_OVERLAP_CHARS = 120

# ── Búsqueda ──────────────────────────────────────────────────────────────────
QUERY_DEFAULT_K = 5

# ── YouTube: reintentos con cookies de navegador (anti-bot) ───────────────────
# Formato: browser[:profile] separados por coma. Se prueban en orden tras un
# fallo anónimo. Requiere sesión iniciada de YouTube en ese navegador.
YT_COOKIES_BROWSERS = os.environ.get("PF_YT_COOKIES", "edge:Default,chrome:Default")

# ── YouTube: clientes de reproducción (anti-bot, sin cookies) ────────────────
# "web" es el sitio; "android"/"tv" usan los clientes móvil/consola y suelen
# saltear el muro "Sign in to confirm you're not a bot" (probado: android OK).
YT_PLAYER_CLIENTS = os.environ.get("PF_YT_PLAYER_CLIENTS", "web,android,tv")


def ensure_dirs() -> None:
    """Crea los directorios de datos si no existen."""
    for d in (DATA, AUDIO_DIR, TRANSCRIPTS_DIR, CHROMA_DIR):
        d.mkdir(parents=True, exist_ok=True)
