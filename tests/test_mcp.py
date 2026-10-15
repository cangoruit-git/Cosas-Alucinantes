"""T8 — Pruebas del servidor MCP (store fake, sin modelo de embeddings).

Cobertura:
- las tools devuelven formato correcto con sus capas y evidencia
- validación de tier y límites de k
- el catálogo responde strings (sin importar el estado de la base local)
"""

from __future__ import annotations

import json

import pf.mcp_server as mcp_mod
from pf.store import SearchHit

_EVID = json.dumps(
    [
        {
            "title": "Sábana Santa",
            "verdict": "apoya",
            "url": "https://es.wikipedia.org/wiki/Sábana_Santa",
        }
    ],
    ensure_ascii=False,
)


class FakeVStore:
    """Store falsa: respuestas deterministas por tool."""

    def query(self, text, *, tier=None, k=5):
        return [
            SearchHit(
                tier="real",
                distance=0.05,
                document="fragmento de prueba sobre la sábana santa y su análisis forense",
                metadata={
                    "video_id": "abc123",
                    "title": "Video de prueba",
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "start": 65.0,
                    "evidence": _EVID,
                },
            )
        ]

    def video_chunks(self, video_id, tier=None):
        return [
            SearchHit(
                tier="sin_confirmar",
                distance=0.0,
                document="primer fragmento del video",
                metadata={
                    "video_id": video_id,
                    "title": "Video de prueba",
                    "chunk_index": 0,
                    "start": 0.0,
                    "url": "https://x",
                },
            )
        ]

    def counts(self):
        return {"real": 2, "sin_confirmar": 5, "creencia": 3}


fallos = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global fallos
    if not cond:
        print(f"FALLO: {name} {detail}")
        fallos += 1


mcp_mod._store = FakeVStore()  # sin cargar el modelo de embeddings

# 1. recall básico: capa, título, evidencia
out = mcp_mod.recall("qué dijo sobre la sábana santa?")
check("recall: header memoria", "Memoria de Parafantástico" in out, out[:80])
check("recall: capa visible", "[real]" in out, out[:120])
check("recall: CUERPO del fragmento visible", "fragmento de prueba" in out, out[:200])
check("recall: link con minuto", "watch?v=abc123&t=65" in out, out[:200])
check("recall: evidencia visible", "Sábana Santa" in out and "apoya" in out, out[:200])

# 2. tier inválido devuelve error claro
check("recall tier inválido", "tier inválido" in mcp_mod.recall("x", tier="falso"))

# 3. k fuera de rango no rompe
out = mcp_mod.recall("x", k=0)
check("recall k=0 no rompe", isinstance(out, str) and len(out) > 0)

# 4. recall_video
out = mcp_mod.recall_video("abc123")
check("recall_video: título y fragmentos", "Video de prueba" in out and "fragmento" in out, out[:120])

# 5. tiers_summary
out = mcp_mod.tiers_summary()
check("tiers_summary: total", "TOTAL: 10" in out, out)

# 6. catalog_search y video_info devuelven strings (cualquier estado de la base)
out = mcp_mod.catalog_search("JESUS")
check("catalog_search string", isinstance(out, str) and len(out) > 0, out[:80])
out = mcp_mod.video_info("BeHrOOzpTNg")
check("video_info string", isinstance(out, str) and len(out) > 0, out[:80])

# 7. el servidor está registrado con ciclo de vida MCP
check("server registrado", hasattr(mcp_mod.server, "run") and hasattr(mcp_mod.server, "tool"))

if fallos:
    print(f"MCP_TESTS: {fallos} fallos")
    raise SystemExit(1)
print("MCP_TESTS OK")
