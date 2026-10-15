"""T3 — Lote de transcripción de un tema: descarga audio + Whisper (resumible).

Uso:
  python -m scripts.transcribe_theme --limit 5          # top 5 del tema
  python -m scripts.transcribe_theme --ids ID1 ID2      # videos puntuales
  python -m scripts.transcribe_theme --audio-only       # solo descargar audio
"""

from __future__ import annotations

import argparse
import logging
import time

from pf.catalog import ChannelCatalog, Video
from pf.themes import PILOT_THEME
from pf.transcribe import AudioManager, Transcriber, transcript_exists

logger = logging.getLogger("transcribe_theme")


def _theme_score(v: Video, theme: str) -> int:
    """Score del video en el tema; 0 si no está (no lanza nunca)."""
    if not isinstance(v.themes, dict):
        return 0
    m = v.themes.get(theme)
    if not isinstance(m, dict):
        return 0
    try:
        return int(m.get("score", 0) or 0)
    except (TypeError, ValueError):
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Lote de transcripción del tema")
    ap.add_argument("--theme", default=PILOT_THEME)
    ap.add_argument("--limit", type=int, default=0, help="0 = todos los del tema")
    ap.add_argument("--ids", nargs="*", default=None, help="ids de video explícitos")
    ap.add_argument("--min-score", type=int, default=0)
    ap.add_argument("--audio-only", action="store_true", help="solo descargar audio")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cat = ChannelCatalog()
    try:
        vs = [v for v in cat.all_videos() if isinstance(v.themes, dict) and v.themes.get(args.theme)]
        vs.sort(key=lambda v: -_theme_score(v, args.theme))
        if args.ids:
            wanted = set(args.ids)
            vs = [v for v in vs if v.id in wanted]
        if args.min_score:
            vs = [v for v in vs if _theme_score(v, args.theme) >= args.min_score]
        if args.limit:
            vs = vs[: args.limit]
    finally:
        cat.close()

    if not vs:
        logger.error("no hay videos del tema '%s'", args.theme)
        return 2

    logger.info("lote: %d videos del tema '%s'", len(vs), args.theme)
    pending = [v for v in vs if not transcript_exists(v.id)]
    logger.info("%d ya transcritos, %d pendientes", len(vs) - len(pending), len(pending))
    if not pending:
        logger.info("nada por hacer")
        return 0

    audio = AudioManager()
    transcriber = Transcriber()
    done = failed = 0
    for v in pending:
        if transcript_exists(v.id):
            continue  # otro proceso pudo completarlo
        apath = audio.download(v)
        if apath is None:
            failed += 1
            logger.warning("[%s] sin audio descargado", v.id)
            continue
        if args.audio_only:
            logger.info("[%s] audio OK: %s", v.id, apath.name)
            continue
        t0 = time.monotonic()
        try:
            tr = transcriber.transcribe(v, apath)
        except Exception as exc:  # noqa: BLE001 - un video no detiene el lote
            failed += 1
            logger.exception("[%s] transcripción falló: %s", v.id, exc)
            continue
        tr.save()
        done += 1
        logger.info(
            "[%s] ok: %d segs, %s de audio (%ds reales)",
            v.id,
            len(tr.segments),
            _fmt(tr.audio_duration or 0.0),
            int(time.monotonic() - t0),
        )

    logger.info("fin lote: %d transcritos, %d fallos", done, failed)
    return 0 if failed == 0 else 1


def _fmt(secs: float) -> str:
    m, s = divmod(int(secs), 60)
    return f"{m}m{s:02d}s"


if __name__ == "__main__":
    raise SystemExit(main())
