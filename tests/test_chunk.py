"""T4 — Pruebas deterministas del chunking (python -m tests.test_chunk)."""

from __future__ import annotations

from pf.catalog import Video
from pf.chunk import chunk_transcript
from pf.transcribe import Segment, Transcript

VIDEO = Video(
    id="abc123",
    title="El misterio del sepulcro",
    url="https://www.youtube.com/watch?v=abc123",
    duration_sec=600,
    view_count=1000,
    upload_date="20240101",
)

def _tr(segments: list[tuple[float, float, str]]) -> Transcript:
    return Transcript(
        video_id="abc123",
        audio_duration=600.0,
        segments=[Segment(s, e, t) for s, e, t in segments],
        model="test",
    )


# 10 segmentos de ~90 caracteres: superan el max de 400 -> varios chunks
BIG_SEGS = [(i * 10.0, i * 10.0 + 9.0, ("palabra " * 9).strip()) for i in range(10)]

fallos = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global fallos
    if not cond:
        print(f"FALLO: {name} {detail}")
        fallos += 1


# 1. un solo video corto -> un único chunk, texto = unión, timestamps bien
tr_small = _tr([(0.0, 2.5, "hola"), (2.5, 5.0, "mundo")])
chunks = chunk_transcript(tr_small, VIDEO, max_chars=400, overlap_chars=0)
check("video corto = 1 chunk", len(chunks) == 1, f"got {len(chunks)}")
check("texto unido", chunks[0].text == "hola mundo", chunks[0].text)
check("start/end", chunks[0].start == 0.0 and chunks[0].end == 5.0)

# 2. video largo -> varios chunks, ninguno supera max_chars
# 10 segmentos de ~71 chars con max=190 -> ~5 chunks
chunks = chunk_transcript(_tr(BIG_SEGS), VIDEO, max_chars=190, overlap_chars=0)
check("varios chunks", len(chunks) >= 3, f"got {len(chunks)}")
check("max_chars respeta: todos <= 190", all(len(c.text) <= 190 for c in chunks))
check(
    "orden de timestamps",
    all(chunks[i].start <= chunks[i].end for i in range(len(chunks))),
)

# 3. overlap: los chunks con overlap solapan en el tiempo (rango [start,end])
chunks_ov = chunk_transcript(_tr(BIG_SEGS), VIDEO, max_chars=190, overlap_chars=60)
check("con overlap hay más chunks o igual", len(chunks_ov) >= len(chunks))
if len(chunks_ov) > 1:
    overlaps = sum(1 for i in range(len(chunks_ov) - 1) if chunks_ov[i + 1].start < chunks_ov[i].end)
    check("el solapamiento comparte rango de tiempo", overlaps >= 1, f"{overlaps} solapamientos")

# 4. metadatos de video presentes en cada chunk
check("meta title", all(c.meta.get("title") == VIDEO.title for c in chunks))
check("meta url", all(c.meta.get("url") == VIDEO.url for c in chunks))
check("meta upload_date", all(c.meta.get("upload_date") == "20240101" for c in chunks))

# 5. segmento gigante solo: no revienta ni se parte a medias
seg_gigante = _tr([(0.0, 10.0, "x" * 900)])
chunks = chunk_transcript(seg_gigante, VIDEO, max_chars=400, overlap_chars=0)
check("segmento gigante = 1 chunk", len(chunks) == 1, f"got {len(chunks)}")
check("segmento gigante intacto", chunks[0].text == "x" * 900)

if fallos:
    print(f"CHUNK_TESTS: {fallos} fallos")
    raise SystemExit(1)
print("CHUNK_TESTS OK")
