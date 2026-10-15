"""T7 — Base vectorial en ChromaDB con tres colecciones (una por capa).

- Colecciones: `pf_real`, `pf_sin_confirmar`, `pf_creencia` — una por capa.
- Embeddings multilingües locales (sentence-transformers, sin API keys).
- Metadatos: video_id, título, URL, timestamps, evidencia (JSON) y capa.
- El id de cada fragmento incluye la capa: reclasificar = borrar + re-insertar.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chromadb  # type: ignore
from chromadb.utils import embedding_functions  # type: ignore

from . import config
from .chunk import Chunk
from .verify import Evidence  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)

# chromadb acepta cualquier callable que embe(r) documentos; el tipo oficial es
# su protocolo EmbeddingFunction, así que tipamos libre para no pelear con los stubs.
EmbedFn = Callable[[list[str]], list[list[float]]]

_META_KEYS = (
    "video_id",
    "title",
    "url",
    "duration_sec",
    "view_count",
    "upload_date",
    "chunk_index",
    "start",
    "end",
    "tier",
    "evidence",
)


def _clean_meta(meta: dict) -> dict:
    """ChromaDB exige str/int/float/bool (nada de None ni dicts)."""
    out: dict[str, int | float | str | bool] = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)) and not isinstance(v, bool):
            if isinstance(v, float) and (v != v):  # NaN
                continue
            out[k] = v
        elif isinstance(v, bool):
            out[k] = v
        else:
            out[k] = str(v)
    return out


def doc_id(tier: str, video_id: str, chunk_index: int) -> str:
    return f"{tier}:{video_id}:{chunk_index}"


@dataclass
class SearchHit:
    """Resultado de búsqueda semántica con su capa y metadatos."""

    tier: str
    distance: float
    document: str
    metadata: dict
    score: float = field(default=0.0)  # 1 - distancia normalizada (mayor = mejor)

    def clip(self) -> str:
        return f"[{self.tier}][{self.metadata.get('title', '?')}] {self.document[:200]}"


class VectorStore:
    """Acceso a las colecciones vectoriales por capa."""

    def __init__(self, path: Path = config.CHROMA_DIR, embed_fn: EmbedFn | None = None):
        config.ensure_dirs()
        self.client = chromadb.PersistentClient(path=str(path))
        if embed_fn is None:
            self.embed_fn: Any = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=config.EMBED_MODEL
            )
        else:
            self.embed_fn: Any = embed_fn
        self.collections = {
            tier: self.client.get_or_create_collection(
                name=f"pf_{tier}",
                embedding_function=self.embed_fn,  # type: ignore[arg-type]
            )
            for tier in config.TIERS
        }

    # ── escritura ─────────────────────────────────────────────────────────────
    def upsert_chunk(
        self,
        chunk: Chunk,
        tier: str,
        evidences: list[Evidence] | None = None,
    ) -> str:
        """Inserta (o actualiza) un fragmento en la colección de su capa."""
        if tier not in self.collections:
            raise ValueError(f"capa desconocida: {tier}")
        meta = _clean_meta(
            {
                **chunk.meta,
                "video_id": chunk.video_id,
                "chunk_index": chunk.index,
                "start": chunk.start,
                "end": chunk.end,
                "tier": tier,
                "evidence": json.dumps([e.to_dict() for e in evidences], ensure_ascii=False)
                if evidences
                else "",
            }
        )
        idx = doc_id(tier, chunk.video_id, chunk.index)
        self.collections[tier].upsert(ids=[idx], documents=[chunk.text], metadatas=[meta])
        return idx

    def remove_chunk(self, tier: str, video_id: str, chunk_index: int) -> None:
        """Borra un fragmento de una colección (para reclasificar)."""
        self.collections[tier].delete(ids=[doc_id(tier, video_id, chunk_index)])

    # ── lectura ───────────────────────────────────────────────────────────────
    def query(
        self,
        text: str,
        *,
        tier: str | None = None,
        k: int = config.QUERY_DEFAULT_K,
        where: dict | None = None,
    ) -> list[SearchHit]:
        """Busca en la(s) colección(es); devuelve hits ordenados por distancia."""
        tiers = [tier] if tier else list(config.TIERS)
        per = max(1, k)
        hits: list[SearchHit] = []
        for t in tiers:
            col = self.collections[t]
            res = col.query(query_texts=[text], n_results=per, where=where)  # type: ignore[arg-type]
            ids = (res.get("ids") or [[]])[0]
            docs = (res.get("documents") or [[]])[0]
            dists = (res.get("distances") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]
            for i, _ in enumerate(ids):
                dist = float(dists[i]) if dists else 1.0
                hits.append(
                    SearchHit(
                        tier=t,
                        distance=dist,
                        document=docs[i] if docs else "",
                        metadata=dict(metas[i]) if metas else {},
                        score=round(1.0 - dist, 3),
                    )
                )
        hits.sort(key=lambda h: h.distance)
        return hits[:k]

    def counts(self) -> dict[str, int]:
        return {tier: self.collections[tier].count() for tier in config.TIERS}

    def chunk_count(self, video_id: str) -> int:
        total = 0
        for col in self.collections.values():
            r = col.get(where={"video_id": video_id})
            total += len(r.get("ids", []) or [])
        return total

    def video_chunks(self, video_id: str, tier: str | None = None) -> list[SearchHit]:
        """Todos los fragmentos de un video (ordenados por índice), con su capa."""
        tiers = [tier] if tier else list(config.TIERS)
        out: list[SearchHit] = []
        for t in tiers:
            r = self.collections[t].get(where={"video_id": video_id})
            ids = r.get("ids") or []
            docs = r.get("documents") or []
            metas = r.get("metadatas") or []
            for i, _ in enumerate(ids):
                out.append(
                    SearchHit(
                        tier=t,
                        distance=0.0,
                        document=docs[i] if docs else "",
                        metadata=dict(metas[i]) if metas else {},
                    )
                )
        out.sort(key=lambda h: int(h.metadata.get("chunk_index", 0) or 0))
        return out

    def delete_video(self, video_id: str) -> int:
        """Borra TODOS los fragmentos de un video, en todas las capas.

        Re-ingerir un video lo REEMPLAZA: sin esto, un fragmento que cambia de
        capa queda huérfano en la colección anterior (id distinto por capa).
        """
        removed = 0
        for col in self.collections.values():
            r = col.get(where={"video_id": video_id})
            ids = r.get("ids") or []
            if ids:
                col.delete(ids=list(ids))
                removed += len(ids)
        return removed
