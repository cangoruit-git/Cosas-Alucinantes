"""Consulta CLI de la memoria (el mismo motor que el servidor MCP, sin MCP).

Uso:
  python -m scripts.query "¿qué dijo sobre la sábana santa?"
  python -m scripts.query "¿qué dijo sobre Jesús?" --tier real
  python -m scripts.query "apocalipsis" --k 8
"""

from __future__ import annotations

import argparse
import logging

from pf.mcp_server import recall  # type: ignore[import-not-found]


def main() -> int:
    ap = argparse.ArgumentParser(description="Consulta la memoria de Parafantástico")
    ap.add_argument("query", help="pregunta en lenguaje natural")
    ap.add_argument("--tier", default="todas", help="todas | real | sin_confirmar | creencia")
    ap.add_argument("--k", type=int, default=5, help="cantidad de fragmentos (1-15)")
    args = ap.parse_args()

    # silenciar logs de terceros (huggingface/httpx) para que la respuesta se lea
    logging.basicConfig(level=logging.ERROR)
    for noisy in (
        "httpx",
        "httpcore",
        "urllib3",
        "huggingface_hub",
        "sentence_transformers",
        "chromadb",
    ):
        logging.getLogger(noisy).setLevel(logging.ERROR)
    print(recall(args.query, tier=args.tier, k=args.k))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
