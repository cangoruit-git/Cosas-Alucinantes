"""T5 — Clasificación de fragmentos en capas de evidencia.

Tres capas (ver docs/criterios-capas.md):
- `creencia`     : superstición / folklor / creencia popular (no verificable
                   por diseño; se documenta su existencia cultural).
- `posible_real` : candidato a la capa `real` (referentes verificables con
                   fuentes públicas). SOLO la verificación (T6) lo promueve.
- `sin_confirmar`: lo demás — afirmación sin corroboración pública.

Clasificación CONSERVADORA por diseño: dudar es `sin_confirmar`, nunca
inventar evidencia. El criterio editorial final es del usuario (revisión).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .chunk import Chunk
from .themes import _hit, _norm

TIER_BELIEF = "creencia"
TIER_CANDIDATE = "posible_real"
TIER_DEFAULT = "sin_confirmar"

# Señales de contenido supersticioso / folklor (palabra completa, es+en)
_SUPERSTICION = [
    "mala suerte", "bad luck", "gato negro", "black cat", "martes 13",
    "viernes 13", "friday 13", "mal de ojo", "evil eye", "amuleto", "amulets",
    "talismán", "talisman", "horóscopo", "horoscope", "espejo roto", "broken mirror",
    "lechuza", "gualicho", "mufa", "curandero", "curandera", "pombero", "duende",
    "duendes", "fantasma", "ghost", "fantasmas", "bruja", "witch", "brujas",
    "hechizo", "spell", "hechizos", "maleficio", "espíritu", "espiritus",
    "spirit", "alma en pena", "maldición", "maldicion", "curse", "energía negativa",
    "energia negativa", "negative energy", "amuletos de la suerte", "sal gorda",
    "limpieza espiritual", "espiritual cleansing", "mala vibra", "mufas",
]

# Marcas de discurso presentacional: "se dice que...", "la leyenda cuenta..."
_PRESENTACIONAL = [
    "se dice que", "dicen que", "cuentan que", "según la creencia",
    "según las creencias", "los supersticiosos", "creencias populares",
    "la leyenda dice", "la leyenda cuenta", "las leyendas dicen", "se cree que",
    "la gente cree", "algunos creen", "los antiguos creían", "antiguos creian",
    "en mi pueblo", "mi abuela", "las abuelas", "popular belief", "folk belief",
    "superstición", "supersticion", "superstitions", "creencia popular",
    "creencias de la gente",
]

# Referentes del mundo real verificables (entidades, organismos, evidencia)
_REFERENTES = [
    "informe", "report", "documento", "document", "expediente", "fbi", "cia",
    "nasa", "pentágono", "pentagon", "gobierno", "government", "archivo",
    "archives", "registros", "records", "estudio", "study", "científico",
    "cientifico", "científicos", "científica", "scientist", "investigación",
    "investigacion", "investigation", "forense", "forensic", "testimonio",
    "testimony", "declaración", "declaracion", "evidencia", "evidence", "prueba",
    "pruebas", "fotos", "fotografía", "fotografia", "fotografías", "grabación",
    "grabacion", "recording", "video", "cámara", "camara", "camera", "radar",
    "satélite", "satellite", "sensores", "sensores", "datos", "data",
    "estadísticas", "estadisticas", "statistics", "censura", "desclasificado",
    "declassified", "ley", "law", "tribunal", "court", "juicio", "trial",
    "historiador", "historians", "arqueólogo", "arqueologo", "arqueólogos",
    "archeologist", "paleontólogo", "paleontologo", "museo", "museum",
    "universidad", "university", "laboratorio", "laboratory", "autopsia",
    "autopsy", "análisis", "analisis", "analysis",
]

_YEAR_RE = re.compile(r"\b(18|19|20)\d{2}\b")


@dataclass
class Classification:
    """Resultado de la clasificación de un fragmento."""

    provision: str
    reasons: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)


def classify_text(text: str) -> Classification:
    """Clasifica un texto SIN clasificar (conservadora)."""
    if not text or not text.strip():
        return Classification(TIER_DEFAULT, ["texto vacío"])

    t = _norm(text)
    sup_hits = [k for k in _SUPERSTICION if _hit(t, _norm(k))]
    pres_hits = [k for k in _PRESENTACIONAL if _hit(t, _norm(k))]
    ref_hits = [k for k in _REFERENTES if _hit(t, _norm(k))]
    years = _YEAR_RE.findall(text)

    if sup_hits and (pres_hits or len(sup_hits) >= 2):
        return Classification(
            TIER_BELIEF,
            reasons=["marcas de superstición + presentación folklor"],
            markers=sup_hits + pres_hits,
        )

    if len(ref_hits) >= 2 or (ref_hits and years):
        return Classification(
            TIER_CANDIDATE,
            reasons=["referentes del mundo real verificables"],
            markers=ref_hits + [f"año:{y}" for y in years],
        )

    return Classification(TIER_DEFAULT, reasons=["sin corroboración pública"])


def classify_chunk(chunk: Chunk) -> Classification:
    """Clasifica un chunk (texto + contexto de tema)."""
    return classify_text(chunk.text)
