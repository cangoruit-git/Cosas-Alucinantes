"""T4 — Chunking: convierte una transcripción en fragmentos con contexto.

Cada chunk agrupa segmentos contiguos hasta el presupuesto de caracteres y
conserva sus timestamps (inicio/fin) para poder citar el minuto exacto del
video. Las colas de los chunks se solapan para que la búsqueda semántica no
pierda las frases cortadas por el corte.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .catalog import Video
from .transcribe import Transcript

_Seg = tuple[float, float, str]


@dataclass
class Chunk:
    """Fragmento de transcripción listo para clasificar y vectorizar."""

    video_id: str
    index: int
    start: float
    end: float
    text: str
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "meta": self.meta,
        }


def _video_meta(video: Video) -> dict:
    return {
        "title": video.title,
        "url": video.url,
        "duration_sec": video.duration_sec,
        "view_count": video.view_count,
        "upload_date": video.upload_date,
    }


def chunk_transcript(
    transcript: Transcript,
    video: Video,
    *,
    max_chars: int = 1000,
    overlap_chars: int = 120,
) -> list[Chunk]:
    """Divide los segmentos en chunks contiguos con solapamiento opcional.

    - Empaqueta segmentos hasta que agregar el siguiente superaría `max_chars`.
    - Cada chunk nuevo arranca con la cola del anterior (`overlap_chars`):
      ese texto queda duplicado a propósito (solapamiento a nivel de segmento).
    - Un segmento más largo que `max_chars` queda solo en su propio chunk.
    - La cola del solapamiento se calcula SOLO sobre los segmentos nuevos del
      pack (no sobre la cola heredada): evita bucles infinitos.
    """
    segs: list[_Seg] = [
        (s.start, s.end, " ".join(s.text.split()))
        for s in transcript.segments
        if s.text and s.text.strip()
    ]
    if not segs:
        return []

    meta = _video_meta(video)
    chunks: list[Chunk] = []
    pos = 0
    tail: list[_Seg] = []
    idx = 0
    while pos < len(segs) or tail:
        pack: list[_Seg] = list(tail) if tail else []
        tail = []
        new_added = 0
        size = sum(len(s[2]) + 1 for s in pack)
        while pos < len(segs):
            s = segs[pos]
            if pack and size + len(s[2]) + 1 > max_chars:
                break
            pack.append(s)
            size += len(s[2]) + 1
            pos += 1
            new_added += 1
        if not pack:  # segmento gigante: queda solo
            pack.append(segs[pos])
            pos += 1
            new_added += 1
        text = " ".join(s[2] for s in pack)
        chunks.append(
            Chunk(
                video_id=transcript.video_id,
                index=idx,
                start=pack[0][0],
                end=pack[-1][1],
                text=text,
                meta=meta,
            )
        )
        idx += 1
        # cola de solapamiento a partir de los segmentos NUEVOS del pack
        if overlap_chars > 0 and new_added:
            acc = 0
            for s in reversed(pack[-new_added:]):
                tail.insert(0, s)
                acc += len(s[2]) + 1
                if acc >= overlap_chars:
                    break
    return chunks
