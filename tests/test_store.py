"""T7 — Pruebas deterministas del store (ChromaDB temporal + embedding fake).

Cobertura:
- upsert en 3 colecciones (una por capa) con metadatos y evidencia
- queries por capa y globales; el texto exacto es el vecino más cercano
- upsert repetido no duplica; remove_chunk borra; counts exactos
"""

from __future__ import annotations

import gc
import hashlib
import shutil
import tempfile
from pathlib import Path

from pf.chunk import Chunk
from pf.store import VectorStore
from pf.verify import Evidence


class FakeEmbedding:
    """Embedding determinista por hash: textos idénticos -> vectores idénticos."""

    default_space = None
    supported_spaces = None

    def name(self) -> str:
        return "fake"

    def __call__(self, input):
        docs = input if isinstance(input, list) else [input]
        return [[b / 255 for b in hashlib.sha256(d.encode()).digest()[:16]] for d in docs]

    def embed_query(self, input):
        docs = input if isinstance(input, list) else [input]
        return self.__call__(docs)

    def embed_documents(self, input):
        return self.__call__(input)

    def embed_with_retries(self, input):
        return self.__call__(input)

    @staticmethod
    def build_from_config(_config):  # pragma: no cover - API de chromadb
        return FakeEmbedding()


EVID = Evidence(
    claim="el informe del FBI de 1947",
    source="wikipedia",
    title="Caso Roswell",
    url="https://es.wikipedia.org/wiki/Caso_Roswell",
    snippet="El caso Roswell ...",
    verdict="apoya",
)


def _chunk(idx: int, text: str) -> Chunk:
    return Chunk(
        video_id="v1",
        index=idx,
        start=float(idx),
        end=float(idx) + 1.0,
        text=text,
        meta={
            "title": "Video de prueba",
            "url": "https://example.com/v1",
            "duration_sec": 300,
            "view_count": 10,
            "upload_date": "20240101",
        },
    )


fallos = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global fallos
    if not cond:
        print(f"FALLO: {name} {detail}")
        fallos += 1


tmp = tempfile.mkdtemp(prefix="pf-store-test-")
try:
    store = VectorStore(path=Path(tmp), embed_fn=FakeEmbedding())

    store.upsert_chunk(_chunk(0, "los grises son una raza gris"), "sin_confirmar")
    store.upsert_chunk(_chunk(1, "el gato negro trae mala suerte según la creencia"), "creencia")
    store.upsert_chunk(_chunk(2, "el informe del FBI de 1947 documenta el caso roswell"), "real", [EVID])

    # 1. counts por capa
    c = store.counts()
    check("counts", c == {"real": 1, "sin_confirmar": 1, "creencia": 1}, f"got {c}")

    # 2. query por capa devuelve solo esa capa
    hits = store.query("el gato negro trae mala suerte según la creencia", tier="creencia")
    check(
        "query creencia 1 hit",
        len(hits) == 1 and hits[0].tier == "creencia",
        f"got {len(hits)} {[h.tier for h in hits]}",
    )

    # 3. el texto exacto es el vecino más cercano (distancia mínima)
    hits = store.query("los grises son una raza gris")
    check(
        "query global top = sin_confirmar",
        bool(hits) and hits[0].tier == "sin_confirmar",
        f"got {hits[0].clip() if hits else None}",
    )

    # 4. la evidencia viaja en los metadatos del fragmento real
    hits = store.query("el informe del FBI de 1947 documenta el caso roswell", tier="real")
    meta = hits[0].metadata if hits else {}
    check(
        "query real con evidencia",
        bool(hits) and "wikipedia" in meta.get("evidence", ""),
        f"got {meta.get('evidence') if hits else None}",
    )

    # 5. upsert repetido no duplica
    store.upsert_chunk(_chunk(0, "los grises son una raza gris"), "sin_confirmar")
    check("upsert no duplica", store.counts()["sin_confirmar"] == 1, f"got {store.counts()}")

    # 6. remove_chunk borra
    store.remove_chunk("creencia", "v1", 1)
    check("remove_chunk", store.counts()["creencia"] == 0, f"got {store.counts()}")

    # 7. chunk_count por video suma todas las capas
    check("chunk_count", store.chunk_count("v1") == 2, f"got {store.chunk_count('v1')}")

    del store
    gc.collect()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print(f"STORE_TESTS: {fallos} fallos")
    raise SystemExit(1)
print("STORE_TESTS OK")
