"""T12 — Lote visual: captura lo que los videos MUESTRAN (no solo lo que dicen).

Para cada video del tema con transcripción:
1. asegura el archivo de video (`data/video/<id>.mp4`; baja video+audio si falta),
2. muestrea fotogramas y los etiqueta con CLIP multilingüe local,
3. cachea las notas en `data/visual/<id>.json` (resumible: si existe, se saltea).

La ingesta (`ingest_theme`) adjunta esas notas a los fragmentos por minuto, así
la memoria sabe qué se VE además de qué se dice (incluido lo gráfico que el
audio suaviza).

Uso:
  python -m scripts.visual_theme --limit 5
  python -m scripts.visual_theme --ids AAAA BBBB
  python -m scripts.visual_theme                  # todos los transcritos del tema
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import yt_dlp  # type: ignore

from pf import config
from pf.catalog import ChannelCatalog, Video
from pf.themes import PILOT_THEME
from pf.transcribe import load_transcript
from pf.vision import ClipTagger, save_notes, visual_notes

logger = logging.getLogger("visual_theme")

VIDEO_DIR = config.DATA / "video"
NOTES_DIR = config.DATA / "visual"

_FORMATO = "worstvideo[height<=480]+worstaudio/worstvideo[height<=480]/worst"


def _descargar_video(video: Video) -> Path | None:
    """Baja el video (con audio) probando los clientes anti-bot en orden."""
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    for client in [c.strip() for c in config.YT_PLAYER_CLIENTS.split(",") if c.strip()]:
        opts: dict = {
            "format": _FORMATO,
            "outtmpl": str(VIDEO_DIR / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 3,
        }
        if client != "web":
            opts["extractor_args"] = {"youtube": {"player_client": [client]}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
                ydl.extract_info(video.url, download=True)
        except Exception as exc:  # noqa: BLE001 - se prueba el siguiente cliente
            logger.debug("[%s] cliente %s falló: %s", video.id, client, str(exc)[:140])
            continue
        files = [p for p in VIDEO_DIR.glob(f"{video.id}.*") if p.suffix in (".mp4", ".mkv", ".webm")]
        if files:
            logger.info("[%s] video OK vía %s: %s", video.id, client, files[0].name)
            return files[0]
    logger.warning("[%s] no se pudo bajar el video", video.id)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Lote visual del tema (lo que se ve)")
    ap.add_argument("--theme", default=PILOT_THEME)
    ap.add_argument("--limit", type=int, default=0, help="0 = todos")
    ap.add_argument("--ids", nargs="*", default=None, help="ids puntuales")
    ap.add_argument("--every-sec", type=float, default=20.0, help="muestreo de fotogramas")
    ap.add_argument("--max-frames", type=int, default=60)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cat = ChannelCatalog()
    try:
        videos = [v for v in cat.all_videos() if isinstance(v.themes, dict) and v.themes.get(args.theme)]
        videos = [v for v in videos if load_transcript(v.id) is not None]
        if args.ids:
            wanted = set(args.ids)
            videos = [v for v in videos if v.id in wanted]
        if args.limit:
            videos = videos[: args.limit]
    finally:
        cat.close()

    pendientes = [v for v in videos if not (NOTES_DIR / f"{v.id}.json").exists()]
    logger.info("lote visual: %d videos transcritos, %d pendientes", len(videos), len(pendientes))
    if not pendientes:
        logger.info("nada por hacer (notas ya cacheadas)")
        return 0

    tagger = ClipTagger()  # carga los modelos CLIP una sola vez
    hechos = fallos = 0
    for v in pendientes:
        video_path = next(
            (p for p in VIDEO_DIR.glob(f"{v.id}.*") if p.suffix in (".mp4", ".mkv", ".webm")), None
        )
        if video_path is None:
            video_path = _descargar_video(v)
        if video_path is None:
            fallos += 1
            continue
        notas = visual_notes(
            video_path, tagger, every_sec=args.every_sec, max_frames=args.max_frames
        )
        save_notes(notas, NOTES_DIR / f"{v.id}.json")
        hechos += 1
        top = [n for nota in notas for n, _ in nota.tags][:6]
        logger.info("[%s] %d fotogramas etiquetados | ejemplos: %s", v.id, len(notas), ", ".join(top))

    logger.info("fin lote visual: %d videos con notas, %d fallos", hechos, fallos)
    return 0 if fallos == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
