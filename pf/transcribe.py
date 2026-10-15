"""T3 — Descarga de audio y transcripción Whisper (resumible).

- `AudioManager.download(video_id, url)`: audio-only con yt-dlp (sin ffmpeg
  binario: baja m4a/opus directo; faster-whisper decodifica con PyAV).
- `Transcriber.transcribe(video_id)`: transcribe con faster-whisper, guarda
  segmentos JSON con timestamps. Resumible: si el JSON ya existe, no re-transcribe.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import yt_dlp  # type: ignore

from . import config
from .catalog import Video

logger = logging.getLogger(__name__)

_DL_OPTS: dict[str, object] = {
    "format": "bestaudio/best",
    "outtmpl": str(config.AUDIO_DIR / "%(id)s.%(ext)s"),
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "retries": 5,
    "socket_timeout": 30,
}


def _parse_cookie_candidates(spec: str) -> list[tuple[str, str | None, None, None]]:
    """ "edge:Default,chrome" -> [("edge", "Default", None, None), ("chrome", None, None, None)]."""
    out: list[tuple[str, str | None, None, None]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        browser, _, profile = part.partition(":")
        out.append((browser, profile or None, None, None))
    return out


_COOKIE_CANDIDATES = _parse_cookie_candidates(config.YT_COOKIES_BROWSERS)


def _client_opts(client: str) -> dict[str, object]:
    """Opciones para un cliente de reproducción ("web" = sin override)."""
    opts = dict(_DL_OPTS)
    if client != "web":
        opts["extractor_args"] = {"youtube": {"player_client": [client]}}
    return opts


def _download_attempts() -> list[tuple[str, dict[str, object]]]:
    """Intentos en orden: clientes anónimos -> cookies de navegador."""
    attempts = [
        (f"anónimo:{c.strip()}", _client_opts(c.strip()))
        for c in config.YT_PLAYER_CLIENTS.split(",")
        if c.strip()
    ]
    for browser, profile, _keyring, _container in _COOKIE_CANDIDATES:
        label = f"cookies:{browser}:{profile or 'default'}"
        attempts.append((label, {**_DL_OPTS, "cookiesfrombrowser": (browser, profile, None, None)}))
    return attempts


_MODEL = None


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    video_id: str
    audio_duration: float | None
    segments: list[Segment]
    model: str

    def save(self) -> Path:
        payload = {
            "video_id": self.video_id,
            "model": self.model,
            "audio_duration": self.audio_duration,
            "segments": [{"start": s.start, "end": s.end, "text": s.text} for s in self.segments],
        }
        path = transcript_path(self.video_id)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        return path


class AudioManager:
    """Descarga el audio de un video (una sola vez por video)."""

    def __init__(self, audio_dir: Path = config.AUDIO_DIR):
        self.audio_dir = audio_dir

    def download(self, video: Video, force: bool = False) -> Path | None:
        existing = list(self.audio_dir.glob(f"{video.id}.*"))
        if existing and not force:
            return existing[0]
        # orden de intentos: clientes anónimos (web/android/tv) -> cookies
        attempts = _download_attempts()
        last_exc: Exception | None = None
        for label, opts in attempts:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
                    ydl.extract_info(video.url, download=True)
                files = list(self.audio_dir.glob(f"{video.id}.*"))
                if files:
                    if not force:
                        logger.info("[%s] audio OK vía %s: %s", video.id, label, files[0].name)
                    return files[0]
            except Exception as exc:  # noqa: BLE001 - un fallo de descarga no detiene el lote
                last_exc = exc
                logger.debug("[%s] intento %s falló: %s", video.id, label, str(exc)[:300])
        logger.warning("Fallo descarga %s (último intento): %s", video.id, last_exc or "sin error")
        return None


def transcript_path(video_id: str) -> Path:
    return config.TRANSCRIPTS_DIR / f"{video_id}.json"


def transcript_exists(video_id: str) -> bool:
    return transcript_path(video_id).exists()


def load_transcript(video_id: str) -> Transcript | None:
    path = transcript_path(video_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("transcripción corrupta %s: %s", video_id, exc)
        return None
    segs = [Segment(s["start"], s["end"], s["text"]) for s in data.get("segments", [])]
    return Transcript(data["video_id"], data.get("audio_duration"), segs, data.get("model", "?"))


def _patch_av_open_compat() -> None:
    """PyAV 19+ rompió `av.open(..., metadata_errors=...)` (usado por faster-whisper).

    Wrapper en runtime: descarta el kwarg no soportado y delega en el open real.
    """
    import av  # import tardío: solo cuando faster-whisper está por cargarse

    if getattr(av.open, "_fw_compat", False):
        return
    _orig = av.open

    def _compat_open(file, *args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig(file, *args, **kwargs)

    _compat_open._fw_compat = True  # type: ignore[attr-defined]
    av.open = _compat_open  # type: ignore[assignment]


def _get_model():
    """Singleton perezoso del modelo Whisper (carga una sola vez por proceso)."""
    global _MODEL
    if _MODEL is None:
        _patch_av_open_compat()  # PyAV 19 rompió metadata_errors
        from faster_whisper import (
            WhisperModel,  # type: ignore[import-not-found]  # import tardío: setup pesado
        )

        logger.info(
            "cargando modelo Whisper %s (%s, %s)...",
            config.WHISPER_MODEL,
            config.WHISPER_DEVICE,
            config.WHISPER_COMPUTE_TYPE,
        )
        _MODEL = WhisperModel(
            config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE_TYPE,
        )
    return _MODEL


class Transcriber:
    """Transcribe un audio ya descargado y guarda el JSON de segmentos."""

    def __init__(self) -> None:
        self.model = _get_model()

    def transcribe(self, video: Video, audio_path: Path) -> Transcript:
        logger.info("transcribiendo %s (%s)...", video.id, audio_path.name)
        t0 = time.monotonic()
        segments, info = self.model.transcribe(
            str(audio_path),
            language=config.WHISPER_LANG,
            beam_size=config.WHISPER_BEAM_SIZE,
            vad_filter=True,
        )
        raw = [(seg.start, seg.end, seg.text.strip()) for seg in segments if seg.text and seg.text.strip()]
        dur = info.duration if info is not None else audio_path.stat().st_size
        tr = Transcript(video.id, dur, [Segment(s, e, t) for s, e, t in raw], config.WHISPER_MODEL)
        elapsed = time.monotonic() - t0
        logger.info(
            "%s: %d segmentos, %s de audio en %.0fs",
            video.id,
            len(raw),
            _fmt_secs(dur or 0.0),
            elapsed,
        )
        return tr


def _fmt_secs(secs: float) -> str:
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"
