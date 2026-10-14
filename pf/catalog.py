"""Catálogo de videos del canal: descarga la lista con yt-dlp y la persiste en SQLite.

- `ChannelCatalog.sync()`: trae la lista plana de videos (rápida, sin descargas).
- `ChannelCatalog.enrich(ids)` : trae descripciones completas de videos puntuales.
- `ChannelCatalog.theme_videos(theme)`: selecciona videos del tema (themes.belongs_to_theme).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import yt_dlp

from . import config
from .themes import ThemeMatch, belongs_to_theme

logger = logging.getLogger(__name__)


def _safe_loads(raw: str | None) -> dict:
    """JSON robusto: devuelve {} si el dato no es JSON válido."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Fila con JSON inválido: %r", raw[:80])
        return {}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id          TEXT PRIMARY KEY,          -- id de video de YouTube
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    duration_sec INTEGER,
    view_count  INTEGER,
    upload_date TEXT,                      -- YYYYMMDD (formato YouTube)
    description TEXT,
    themes      TEXT NOT NULL DEFAULT '{}',-- JSON: {theme: {score, keywords}}
    fetched_at  TEXT
);
"""

_UPSERT_SQL = (
    "INSERT OR REPLACE INTO videos "
    "(id, title, url, duration_sec, view_count, upload_date, description, themes, fetched_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


@dataclass
class Video:
    id: str
    title: str
    url: str
    duration_sec: int | None = None
    view_count: int | None = None
    upload_date: str | None = None
    description: str = ""
    themes: dict[str, dict] | None = None

    @property
    def is_absent(self) -> bool:
        return self.duration_sec is None or self.duration_sec == 0


class ChannelCatalog:
    """Acceso al catálogo persistente del canal."""

    def __init__(self, db_path=config.CATALOG_DB):
        config.ensure_dirs()
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(_SCHEMA)  # noqa: S608 - DDL estático, sin interpolación
        self._conn.commit()

    # ── ingesta ───────────────────────────────────────────────────────────────
    def sync(self, channel_url: str = config.CHANNEL_URL) -> int:
        """Trae la lista plana de videos del canal y hace upsert. Devuelve el total."""
        opts = {
            "extract_flat": "in_playlist",
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
            info = ydl.extract_info(channel_url, download=False)
        rows: list[tuple] = []
        now = datetime.now(UTC).isoformat(timespec="seconds")
        for e in info.get("entries", []):
            if not e:
                continue
            vid = e.get("id")
            if not vid:
                continue
            title = e.get("title") or "sin título"
            rows.append(
                (
                    vid,
                    title,
                    e.get("webpage_url") or e.get("url") or f"https://www.youtube.com/watch?v={vid}",
                    e.get("duration") if e.get("duration") else None,
                    e.get("view_count") if e.get("view_count") else None,
                    e.get("upload_date") if e.get("upload_date") else None,
                    None,  # descripción: se enriquece luego
                    "[]",
                    now,
                )
            )
        self._conn.executemany(  # noqa: S608 - consulta parametrizada
            _UPSERT_SQL,
            rows,
        )
        self._conn.commit()
        return len(rows)

    def enrich(self, video_ids: list[str], max_workers: int = 8) -> int:
        """Trae descripción completa (y views/duration) para los ids dados."""
        ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        updated = 0
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
            for vid in video_ids:
                try:
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
                except Exception as exc:  # noqa: BLE001 - un video fallido no detiene el lote
                    logger.info("No se pudo enriquecer %s: %s", vid, exc)
                    continue
                if not info or not info.get("id"):
                    continue
                self._conn.execute(
                    "UPDATE videos SET description = ?, view_count = ?, duration_sec = ? WHERE id = ?",
                    (
                        (info.get("description") or "")[:4000],
                        info.get("view_count"),
                        info.get("duration"),
                        vid,
                    ),
                )
                updated += 1
        self._conn.commit()
        return updated

    # ── consulta ──────────────────────────────────────────────────────────────
    def theme_videos(self, theme: str) -> list[Video]:
        """Videos que pertenecen al tema, con su match guardado en `themes`."""
        out: list[Video] = []
        for row in self._conn.execute("SELECT * FROM videos").fetchall():
            v = self._video_from_row(row)
            m = belongs_to_theme(v.title, v.description, theme) if v.title else None
            if m:
                out.append(v)
        return out

    def all_videos(self) -> list[Video]:
        return [self._video_from_row(r) for r in self._conn.execute("SELECT * FROM videos").fetchall()]

    def get(self, video_id: str) -> Video | None:
        row = self._conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        return self._video_from_row(row) if row else None

    def save_theme_match(self, video_id: str, match: ThemeMatch) -> None:
        row = self._conn.execute("SELECT themes FROM videos WHERE id = ?", (video_id,)).fetchone()
        themes = _safe_loads(row[0]) if row else {}
        if not isinstance(themes, dict):  # filas viejas con '[]'
            themes = {}
        themes[match.theme] = {
            "score": match.score,
            "keywords": match.matched_keywords,
        }
        self._conn.execute(
            "UPDATE videos SET themes = ? WHERE id = ?", (json.dumps(themes, ensure_ascii=False), video_id)
        )
        self._conn.commit()

    # ── helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _video_from_row(row) -> Video:
        return Video(
            id=row[0],
            title=row[1],
            url=row[2],
            duration_sec=row[3],
            view_count=row[4],
            upload_date=row[5],
            description=row[6] or "",
            themes=_safe_loads(row[7]),
        )

    def close(self) -> None:
        self._conn.close()
