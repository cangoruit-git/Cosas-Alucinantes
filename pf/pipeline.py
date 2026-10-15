"""T9 — Pipeline de ingesta: transcripción -> fragmentos -> capas -> base vectorial.

`ingest_video()` une chunking (T4), clasificación (T5), verificación (T6) y
almacenamiento (T7). Es idempotente: re-ingestar el mismo video actualiza los
fragmentos en vez de duplicarlos.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from . import config
from .catalog import Video
from .chunk import Chunk, chunk_transcript
from .classify import TIER_CANDIDATE, classify_text
from .transcribe import Transcript
from .verify import Evidence, resolve_tier, verify_chunk

logger = logging.getLogger(__name__)

VerifyFn = Callable[[str], tuple[str, list[Evidence]]]


@runtime_checkable
class StoreLike(Protocol):
    """Lo único que el pipeline necesita del store (inyectable y testeable)."""

    def upsert_chunk(self, chunk: Chunk, tier: str, evidences: list[Evidence] | None = None) -> str: ...

    def delete_video(self, video_id: str) -> int: ...


@dataclass
class IngestReport:
    """Resumen de la ingesta de un video."""

    video_id: str
    chunks: int = 0
    tiers: dict[str, int] = field(default_factory=dict)
    promoted_to_real: int = 0
    evidence_items: int = 0
    real_samples: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "chunks": self.chunks,
            "tiers": self.tiers,
            "promoted_to_real": self.promoted_to_real,
            "evidence_items": self.evidence_items,
            "real_samples": self.real_samples,
        }


def ingest_video(
    transcript: Transcript,
    video: Video,
    store: StoreLike,
    *,
    verify_fn: VerifyFn = verify_chunk,
    skip_verify: bool = False,
    max_chars: int = config.CHUNK_MAX_CHARS,
    overlap_chars: int = config.CHUNK_OVERLAP_CHARS,
) -> IngestReport:
    """Fragmenta, clasifica, verifica y guarda un video en la base vectorial."""
    report = IngestReport(video_id=transcript.video_id)
    # re-ingerir = REEMPLAZAR: sin esto, un fragmento que cambia de capa queda
    # huérfano en la colección anterior (el id incluye la capa)
    store.delete_video(transcript.video_id)
    for chunk in chunk_transcript(transcript, video, max_chars=max_chars, overlap_chars=overlap_chars):
        if skip_verify:
            provision = classify_text(chunk.text).provision
            # sin verificación, un candidato no puede ser 'real': queda sin_confirmar
            tier = provision if provision != TIER_CANDIDATE else "sin_confirmar"
            evidences: list[Evidence] = []
        else:
            tier, evidences = verify_fn(chunk.text)
        store.upsert_chunk(chunk, tier, evidences or None)
        report.chunks += 1
        report.tiers[tier] = report.tiers.get(tier, 0) + 1
        report.evidence_items += len(evidences)
        if tier == "real":
            report.promoted_to_real += 1
            if len(report.real_samples) < 5:
                report.real_samples.append(
                    {
                        "chunk_index": chunk.index,
                        "start": chunk.start,
                        "end": chunk.end,
                        "text": chunk.text[:220],
                        "evidence": [e.to_dict() for e in evidences[:2]],
                    }
                )
    logger.info(
        "video %s: %d fragmentos en capas %s (%d a 'real', %d evidencias)",
        report.video_id,
        report.chunks,
        report.tiers,
        report.promoted_to_real,
        report.evidence_items,
    )
    return report


def resolve_without_verify(provision: str) -> str:
    """Capa final sin verificación: candidato CAE a sin_confirmar."""
    return resolve_tier(provision, [])
