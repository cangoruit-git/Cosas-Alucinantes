"""T12 — Capa visual: lo que el video MUESTRA (no solo lo que dice).

- `iter_frames()`: muestrea fotogramas con PyAV (sin ffmpeg binario).
- `ClipTagger`: etiqueta imágenes contra un vocabulario curado en español con
  CLIP multilingüe local (sin API keys): el encoder de imagen (`clip-ViT-B-32`)
  y el de texto (`clip-ViT-B-32-multilingual-v1`) comparten espacio.
- `visual_notes()`: notas por minuto (tiempo + etiquetas con score).
- `tags_for_window()`: etiquetas que caen en la ventana temporal de un chunk,
  para adjuntarlas al fragmento y que la memoria sepa qué se VE además de
  qué se dice (incluido lo gráfico que el audio suaviza).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Vocabulario curado para este canal: lo gráfico, lo religioso, las "pruebas"
# y los recursos visuales frecuentes (documentales con clips de película/CGI).
ETIQUETAS: list[str] = [
    # contenido explícito / gráfico
    "una escena violenta con sangre",
    "una herida o mutilación explícita",
    "un cadáver o un cuerpo sin vida",
    "un arma blanca o una lanza",
    "una ejecución o una crucifixión",
    "una persona sufriendo o torturada",
    # imaginería religiosa
    "una figura religiosa o de Jesús",
    "una virgen o imagen mariana",
    "una iglesia o catedral",
    "una cruz o símbolo cristiano",
    "un objeto religioso o reliquia",
    # pruebas / documentos
    "un documento o captura de texto",
    "un titular de diario o revista",
    "un mapa o un plano",
    "una fotografía histórica en blanco y negro",
    "un gráfico o infografía",
    "un cartel con texto grande en pantalla",
    # escenas y elementos
    "un rostro humano en primer plano",
    "una multitud de personas",
    "un cielo nocturno o estrellas",
    "un objeto volador o una nave",
    "un paisaje natural",
    "un edificio o una ciudad",
    "un laboratorio o experimento",
    "un símbolo ocultista o masónico",
    # estilo
    "una animación o gráfico por computadora",
    "una escena de película o recreación histórica",
]

TaggerFn = Callable[[Any], list[tuple[str, float]]]


@dataclass
class VisualNote:
    """Lo que se ve en un instante del video."""

    t: float
    tags: list[tuple[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"t": round(self.t, 2), "tags": [(n, round(s, 3)) for n, s in self.tags]}


def iter_frames(
    video_path: Path | str,
    *,
    every_sec: float = 20.0,
    max_frames: int = 60,
) -> Iterator[tuple[float, Any]]:
    """Genera (tiempo_en_segundos, imagen PIL) muestreando el video cada `every_sec`."""
    import av  # import tardío: dependencia pesada solo cuando se usa

    container = av.open(str(video_path))
    try:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        next_at = 0.0
        emitted = 0
        for frame in container.decode(stream):
            if emitted >= max_frames:
                break
            t = float(frame.pts * stream.time_base) if frame.pts is not None else 0.0
            if t + 1e-6 >= next_at:
                yield t, frame.to_image()
                emitted += 1
                next_at = t + every_sec
    finally:
        container.close()


class ClipTagger:
    """Etiquetador CLIP multilingüe local (imagen + etiquetas en español)."""

    def __init__(
        self,
        image_model: str = "clip-ViT-B-32",
        text_model: str = "clip-ViT-B-32-multilingual-v1",
        etiquetas: list[str] | None = None,
    ):
        from sentence_transformers import SentenceTransformer

        logger.info("cargando CLIP (%s + %s)...", image_model, text_model)
        self.image_model = SentenceTransformer(image_model)
        self.text_model = SentenceTransformer(text_model)
        self.etiquetas = etiquetas or ETIQUETAS
        self._text_emb = self.text_model.encode(self.etiquetas, convert_to_tensor=True)

    def __call__(self, image: Any) -> list[tuple[str, float]]:
        from sentence_transformers import util

        img_emb = self.image_model.encode([image], convert_to_tensor=True)
        sims = util.cos_sim(img_emb, self._text_emb)[0]
        pares = [(self.etiquetas[i], float(sims[i])) for i in range(len(self.etiquetas))]
        pares.sort(key=lambda p: -p[1])
        return pares


def visual_notes(
    video_path: Path | str,
    tagger: TaggerFn,
    *,
    every_sec: float = 20.0,
    max_frames: int = 60,
    top_k: int = 4,
    min_score: float = 0.22,
) -> list[VisualNote]:
    """Notas visuales del video: por cada fotograma, sus `top_k` etiquetas relevantes."""
    notas: list[VisualNote] = []
    for t, image in iter_frames(video_path, every_sec=every_sec, max_frames=max_frames):
        try:
            pares = tagger(image)
        except Exception as exc:  # noqa: BLE001 - un frame no rompe el video
            logger.warning("frame @%.0fs sin etiquetas: %s", t, exc)
            continue
        relevantes = [(n, s) for n, s in pares[:top_k] if s >= min_score]
        notas.append(VisualNote(t=round(t, 1), tags=relevantes))
    logger.info("notas visuales: %d fotogramas con etiquetas", len(notas))
    return notas


def tags_for_window(
    notas: list[VisualNote],
    start: float,
    end: float,
    *,
    min_score: float = 0.22,
    max_tags: int = 5,
) -> list[dict]:
    """Etiquetas de los fotogramas que caen en [start, end], agregadas por score.

    Devuelve [{tag, score, t}] ordenado por score, para adjuntar al fragmento.
    """
    acumulado: dict[str, tuple[float, float]] = {}
    for nota in notas:
        if start - 0.5 <= nota.t <= end + 0.5:
            for nombre, score in nota.tags:
                if score < min_score:
                    continue
                prev = acumulado.get(nombre)
                if prev is None or score > prev[0]:
                    acumulado[nombre] = (score, nota.t)
    orden = sorted(acumulado.items(), key=lambda kv: -kv[1][0])[:max_tags]
    return [{"tag": n, "score": round(s, 3), "t": round(t, 1)} for n, (s, t) in orden]


def load_notes(path: Path | str) -> list[VisualNote]:
    """Carga notas visuales cacheadas (JSON) si existen."""
    import json

    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [VisualNote(t=n["t"], tags=[(a, b) for a, b in n["tags"]]) for n in data]


def save_notes(notas: list[VisualNote], path: Path | str) -> Path:
    """Guarda las notas visuales de un video (caché resumible)."""
    import json

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([n.to_dict() for n in notas], ensure_ascii=False, indent=1), encoding="utf-8")
    return p
