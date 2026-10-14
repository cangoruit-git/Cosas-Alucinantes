"""Temas del canal y matcher de videos por título/descripción.

Cada tema define keywords; un video pertenece al tema si acumula hits
sobre el título y la descripción. El matcher es transparente: guarda qué
keywords matchearon para poder auditar la selección.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Tema piloto decidido por el usuario (L5). El catálogo puede crecer con más temas.
PILOT_THEME = "dios-cristo"

THEMES: dict[str, dict] = {
    "dios-cristo": {
        "nombre": "Dios y Cristo",
        "descripcion": "Religión, cristianismo, figuras bíblicas, profecías, milagros, apariciones y misterios de la fe.",
        "keywords": [
            "dios", "cristo", "jesús", "jesus", "biblia", "evangelio", "evangelios",
            "religión", "religion", "religioso", "religiosa", "católico", "católica",
            "catolicismo", "cristiano", "cristiana", "cristiandad", "vaticano",
            "apocalipsis", "profecía", "profecia", "profético", "mesías", "mesias",
            "arcángel", "arcangel", "ángel", "angel", "ángeles", "demonio", "demonios",
            "satanás", "satanas", "diablo", "infierno", "paraíso", "paraiso", "cielo",
            "resurrección", "resurreccion", "milagro", "milagros", "fe", "cruz",
            "virgen", "maría", "maria", "guadalupe", "lourdes", "fátima", "fatima",
            "santo", "santa", "santos", "iglesia", "papa", "jerusalén", "jerusalen",
            "belén", "belen", "nacimiento", "sepulcro", "sábana santa", "sabana santa",
            "turín", "turin", "arca de noé", "arca de noe", "noé", "noe", "moisés",
            "moises", "david", "goliat", "sodoma", "gomorra", "maná", "mana",
            "elías", "elias", "salomón", "salomon", "judas", "pedro", "pablo",
            "maría magdalena", "maria magdalena", "evangelio de judas", "evangelio de tomás",
            "evangelio de tomas", "apóstol", "apostol", "apóstoles", "apostoles",
            "revelación", "revelacion", "apocalíptico", "apocaliptico", "antiguo testamento",
            "nuevo testamento", "éxodo", "exodo", "génesis", "genesis", "salmo", "salmos",
            "mezquita", "cristiandad", "deuteronomio", "profeta", "profetas", "endemoniado",
            "exorcismo", "exorcista", "estigma", "estigmas", "curación por fe", "curacion por fe",
        ],
    },
}


@dataclass
class ThemeMatch:
    """Resultado del matcher de tema sobre un video."""

    theme: str
    score: int
    matched_keywords: list[str] = field(default_factory=list)
    fields_hit: list[str] = field(default_factory=list)


def _norm(text: str) -> str:
    """Normaliza para comparación: lower, sin acentos, sin signos raros."""
    if not text:
        return ""
    text = text.lower()
    accents = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "ü": "u", "ñ": "n",
    }
    for a, b in accents.items():
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9 ]+", " ", text)


def match_theme(video_title: str, video_description: str = "", theme: str = PILOT_THEME) -> ThemeMatch:
    """Marca un video para un tema según keywords (score + qué matcheó)."""
    t = _norm(video_title)
    d = _norm(video_description)
    th = THEMES[theme]
    matched: list[str] = []
    fields_hit: list[str] = []
    for kw in th["keywords"]:
        nkw = _norm(kw)
        hit_title = nkw in t
        hit_desc = bool(d) and nkw in d
        if hit_title or hit_desc:
            matched.append(kw)
            if hit_title and "titulo" not in fields_hit:
                fields_hit.append("titulo")
            if hit_desc and "descripcion" not in fields_hit:
                fields_hit.append("descripcion")
    score = len(matched) + (2 if "titulo" in fields_hit else 0)
    return ThemeMatch(theme=theme, score=score, matched_keywords=matched, fields_hit=fields_hit)


MIN_SCORE_TITLE_HIT = 1  # con hit en título alcanza score alto (2+)
MIN_SCORE_DESC_ONLY = 3  # solo con varios hits en descripción


def belongs_to_theme(video_title: str, video_description: str = "", theme: str = PILOT_THEME) -> ThemeMatch | None:
    """Devuelve el match si el video pertenece al tema, si no None."""
    m = match_theme(video_title, video_description, theme)
    if "titulo" in m.fields_hit and m.score >= MIN_SCORE_TITLE_HIT:
        return m
    if m.score >= MIN_SCORE_DESC_ONLY:
        return m
    return None
