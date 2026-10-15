"""T8 — Servidor MCP: la memoria de Parafantástico para CUALQUIER IA.

Cualquier cliente MCP (Claude Desktop, Pi, Cursor, etc.) se conecta y
consulta lo que dijo Parafantástico, con cada fragmento en su capa de
evidencia: `real` (con fuente), `sin_confirmar` o `creencia`.

Ejecutar:  .venv/Scripts/python -m pf.mcp_server
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.mcpserver import MCPServer  # type: ignore

from .catalog import ChannelCatalog
from .store import SearchHit, VectorStore

server = MCPServer(
    "Cosas-Alucinantes",
    description=(
        "Memoria de Parafantástico: consulta lo que dijo en sus videos, "
        "con cada fragmento en su capa de evidencia (real / sin_confirmar / creencia)."
    ),
)

_store: VectorStore | None = None
_TIERS = ("real", "sin_confirmar", "creencia")
_TIER_HELP = "una de: todas | real | sin_confirmar | creencia"


def get_store() -> VectorStore:
    """Carga perezosa del store (el embedding model tarda en cargar)."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def _safe_int(value: Any, default: int = 5) -> int:
    """Convierte a int sin lanzar: clientes MCP pueden mandar cualquier cosa."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ts(seconds: float) -> str:
    m, s = divmod(int(seconds or 0), 60)
    return f"{m:02d}:{s:02d}"


def _evidence_summary(meta: dict) -> str:
    raw = meta.get("evidence", "") or ""
    if not raw:
        return ""
    try:
        items = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ""
    lines = []
    for e in items[:2]:
        lines.append(f"    fuente: {e.get('title')} ({e.get('verdict')}) {e.get('url')}")
    return "\n".join(lines) or ""


def _format_hit(h: SearchHit) -> str:
    m = h.metadata
    t = m.get("title", "?")
    url = m.get("url", "")
    ts = _ts(h.metadata.get("start", 0))
    text = " ".join(h.document.split())[:260]
    return (
        f"[{h.tier}] {t} (en {ts}) score={h.score}\n"
        f"  {text}\n"
        f"  https://www.youtube.com/watch?v={m.get('video_id', '')}"
        f"{'&t=' + str(int(float(m.get('start', 0)))) if m.get('start') is not None else ''}\n"
        + (_evidence_summary(m) + "\n" if _evidence_summary(m) else "")
        + f"  URL: {url}" if url and not url.startswith("https://www.youtube.com") else ""
    ).rstrip()


# ── herramientas MCP ──────────────────────────────────────────────────────────


@server.tool()
def recall(query: str, tier: str = "todas", k: int = 5) -> str:
    """Busca en la memoria de Parafantástico y devuelve fragmentos con su capa de evidencia.

    - query: pregunta en lenguaje natural (ej. 'qué dijo sobre la sábana santa?').
    - tier: filtra por capa de evidencia ('real', 'sin_confirmar', 'creencia' o 'todas').
    - k: cantidad de resultados (1-15).
    """
    if tier != "todas" and tier not in _TIERS:
        return f"tier inválido: {tier}. Usá {_TIER_HELP}."
    k = max(1, min(_safe_int(k, 5), 15))
    vstore = get_store()
    hits = vstore.query(query, tier=None if tier == "todas" else tier, k=k)
    if not hits:
        return "Sin resultados en la memoria."
    return f"Memoria de Parafantástico ({len(hits)} fragmentos, capa={tier}):\n\n" + "\n\n".join(
        _format_hit(h) for h in hits
    )


@server.tool()
def recall_video(video_id: str, tier: str = "todas") -> str:
    """Devuelve todos los fragmentos guardados de un video (id de YouTube)."""
    if tier != "todas" and tier not in _TIERS:
        return f"tier inválido: {tier}. Usá {_TIER_HELP}."
    vstore = get_store()
    chunks = vstore.video_chunks(video_id, None if tier == "todas" else tier)
    if not chunks:
        return f"Sin fragmentos guardados para {video_id} (capa: {tier})."
    title = chunks[0].metadata.get("title", "?")
    body = "\n".join(f"  [{_ts(c.metadata.get('start', 0))}] ({c.tier}) {c.document[:220]}" for c in chunks)
    return f"Video {video_id} — {title} — {len(chunks)} fragmentos:\n{body}"


@server.tool()
def catalog_search(q: str, theme: str | None = None, limit: int = 10) -> str:
    """Busca videos del canal por texto en título/descripción (catálogo base)."""
    limit = max(1, min(_safe_int(limit, 10), 50))
    cat = ChannelCatalog()
    try:
        ql = q.lower()
        out = []
        for v in cat.all_videos():
            if ql in v.title.lower() or ql in (v.description or "").lower():
                if theme and (not isinstance(v.themes, dict) or theme not in v.themes):
                    continue
                dur = f"{v.duration_sec // 60}m" if v.duration_sec else "?"
                out.append(f"[{v.id}] ({dur}) {v.title}\n  {v.url}")
                if len(out) >= limit:
                    break
    finally:
        cat.close()
    if not out:
        return f"Sin videos que coincidan con {q!r}."
    return f"Catálogo ({len(out)} videos):\n" + "\n".join(out)


@server.tool()
def video_info(video_id: str) -> str:
    """Metadatos de un video + estado de su fragmentación en la memoria."""
    cat = ChannelCatalog()
    try:
        v = cat.get(video_id)
    finally:
        cat.close()
    if v is None:
        return f"El video {video_id} no está en el catálogo."
    vstore = get_store()
    chunks = vstore.video_chunks(video_id)
    by_tier: dict[str, int] = {}
    for c in chunks:
        by_tier[c.tier] = by_tier.get(c.tier, 0) + 1
    return (
        f"{v.title}\n{v.url}\n"
        f"subido: {v.upload_date or '?'} | {v.duration_sec // 60 if v.duration_sec else '?'} min | "
        f"vistas: {v.view_count or '?'}\n"
        f"en memoria: {len(chunks)} fragmentos {by_tier or '(vacío)'}"
    )


@server.tool()
def tiers_summary() -> str:
    """Resumen de cuántos fragmentos hay en cada capa de evidencia."""
    counts = get_store().counts()
    total = sum(counts.values())
    return (
        "Memoria de Cosas-Alucinantes:\n"
        + "\n".join(f"  {tier}: {counts.get(tier, 0)} fragmentos" for tier in _TIERS)
        + f"\n  TOTAL: {total}"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    server.run()
