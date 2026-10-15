"""T9 — Ingesta del piloto: transcripciones -> fragmentos -> capas -> ChromaDB.

Para cada video con transcripción descargada:
1. fragmenta 2. clasifica + verifica contra fuentes públicas (Wikipedia ES) 3. guarda.

Genera la cola de revisión de la capa `real` (data/review_tier_real.jsonl):
cada fragmento promovido con su evidencia, para auditoría editorial humana.

Uso:
  python -m scripts.ingest_theme                 # todo lo transcrito del tema
  python -m scripts.ingest_theme --ids AAAA BBBB # videos puntuales
  python -m scripts.ingest_theme --skip-verify   # sin red (nunca 'real')
"""

from __future__ import annotations

import argparse
import json
import logging

from pf import config
from pf.catalog import ChannelCatalog
from pf.pipeline import ingest_video  # type: ignore[import-not-found]
from pf.store import VectorStore  # type: ignore[import-not-found]
from pf.themes import PILOT_THEME, THEMES
from pf.transcribe import load_transcript
from pf.verify import verify_chunk

logger = logging.getLogger("ingest_theme")

REVIEW_FILE = config.DATA / "review_tier_real.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingesta del tema en la base vectorial")
    ap.add_argument("--theme", default=PILOT_THEME)
    ap.add_argument("--ids", nargs="*", default=None, help="ids de video puntuales")
    ap.add_argument("--skip-verify", action="store_true", help="sin verificación (sin red)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cat = ChannelCatalog()
    try:
        videos = [v for v in cat.all_videos() if isinstance(v.themes, dict) and v.themes.get(args.theme)]
        if args.ids:
            wanted = set(args.ids)
            videos = [v for v in videos if v.id in wanted]
    finally:
        cat.close()

    store = VectorStore()
    entities = list(THEMES.get(args.theme, {}).get("keywords", []))

    def verify_with_entities(text: str):
        """Verificación con gate de ENTIDAD del tema (su sujeto específico)."""
        return verify_chunk(text, entities=entities)

    reviews: list[dict] = []
    ingestidos = 0
    for v in videos:
        tr = load_transcript(v.id)
        if tr is None:
            logger.info("[%s] sin transcripción todavía — se saltea", v.id)
            continue
        report = ingest_video(tr, v, store, skip_verify=args.skip_verify, verify_fn=verify_with_entities)
        ingestidos += 1
        logger.info(
            "[%s] %d fragmentos: %s",
            v.id,
            report.chunks,
            ", ".join(f"{k}={n}" for k, n in sorted(report.tiers.items())),
        )
        for sample in report.real_samples:
            reviews.append(
                {
                    "video_id": v.id,
                    "video_title": v.title,
                    "video_url": v.url,
                    **sample,
                }
            )

    if reviews:
        with REVIEW_FILE.open("w", encoding="utf-8") as fh:
            for r in reviews:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        logger.info("cola de revisión capa 'real': %d fragmentos -> %s", len(reviews), REVIEW_FILE)
    else:
        logger.info("sin fragmentos 'real' en esta pasada (la cola queda vacía)")

    counts = store.counts()
    total = sum(counts.values())
    logger.info("piloto: %d videos ingestados; memoria total=%d", ingestidos, total)
    for tier, n in counts.items():
        logger.info("  %s: %d", tier, n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
