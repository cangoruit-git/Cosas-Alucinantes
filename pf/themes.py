"""Temas del canal y matcher de videos por título/descripción.

El matcher es transparente y auditable: registra qué keywords matchearon.
Coincidencia con límite de palabra (nunca subcadenas: "fe" no matchea "effect").

Reglas editoriales (decididas en T2 con casos reales del canal):
1. keyword núcleo en el TÍTULO -> aceptado directo (el video habla del tema).
2. >= 3 keywords núcleo solo en descripción -> aceptado (muy temático).
3. keyword genérica en título Y >= 2 hits (núcleo o genéricas) en descripción -> aceptado.
4. cualquier otro caso -> fuera del tema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Tema piloto decidido por el usuario (L5). El catálogo puede crecer con más temas.
PILOT_THEME = "dios-cristo"

_DIOS_CRISTO_DESC = (
    "Religión, cristianismo, figuras bíblicas, profecías, milagros, apariciones y misterios de la fe."
)

# `keywords` = núcleo: indica foco directo en el tema (español E inglés: los
# títulos del canal suelen estar en inglés).
# `keywords_genericas` = términos amplios (nombres, conceptos cotidianos) que
# solos no alcanzan, pero apoyan una señal fuerte.
THEMES: dict[str, dict] = {
    "dios-cristo": {
        "nombre": "Dios y Cristo",
        "descripcion": _DIOS_CRISTO_DESC,
        "keywords": [
            "jesús",
            "jesus",
            "cristo",
            "christ",
            "jesucristo",
            "dios",
            "god",
            "biblia",
            "bible",
            "evangelio",
            "gospel",
            "evangelios",
            "religión",
            "religion",
            "religioso",
            "religiosos",
            "religiosa",
            "católico",
            "católica",
            "catolicismo",
            "cristiano",
            "cristiana",
            "cristiandad",
            "cristianismo",
            "vaticano",
            "vatican",
            "apocalipsis",
            "apocalypse",
            "apocalíptico",
            "apocaliptico",
            "profecía",
            "profecia",
            "prophecy",
            "profético",
            "profetico",
            "mesías",
            "mesias",
            "messiah",
            "arcángel",
            "arcangel",
            "archangel",
            "demonio",
            "demonios",
            "satanás",
            "satanas",
            "satan",
            "satánico",
            "satanico",
            "satanic",
            "diablo",
            "devil",
            "infierno",
            "hell",
            "resurrección",
            "resurreccion",
            "resurrection",
            "milagro",
            "milagros",
            "miracle",
            "iglesia",
            "church",
            "exorcismo",
            "exorcism",
            "exorcista",
            "anticristo",
            "antichrist",
            "segunda venida",
            "rapto",
            "rapture",
            "sábana santa",
            "sabana santa",
            "tierra santa",
            "arca de noé",
            "arca de noe",
            "noah",
            "noé",
            "noe",
            "moisés",
            "moises",
            "moses",
            "sodoma",
            "sodom",
            "gomorra",
            "evangelio de judas",
            "evangelio de tomás",
            "evangelio de tomas",
            "apóstol",
            "apostol",
            "apóstoles",
            "apostles",
            "apostle",
            "revelación",
            "revelacion",
            "antiguo testamento",
            "nuevo testamento",
            "génesis",
            "genesis",
            "éxodo",
            "exodo",
            "exodus",
            "salmo",
            "salmos",
            "profeta",
            "profetas",
            "prophet",
            "endemoniado",
            "sepulcro",
            "jerusalén",
            "jerusalen",
            "jerusalem",
            "belén",
            "belen",
            "nazareno",
            "nazareth",
            "fátima",
            "fatima",
            "lourdes",
            "guadalupe",
            "virgen de",
            "papa francisco",
            "predicador",
            "predicadores",
            "jesuita",
            "jesuitas",
            "misa",
            "oración",
            "oracion",
            "prayer",
            "amen",
            "hallelujah",
            "aleluya",
            "pentecostés",
            "pentecostes",
            "bautismo",
            "baptism",
            "santidad",
            "santísima",
            "santísimo",
            "divinidad",
            "trinidad",
            "espíritu santo",
            "espiritu santo",
            "pacto con el diablo",
            "pacto con dios",
            "santo grial",
            "maná",
            "mana",
            "diez mandamientos",
            "tablas de la ley",
            "serpiente del edén",
            "edén",
            "eden",
            "paraíso perdido",
            "paraiso perdido",
        ],
        "keywords_genericas": [
            "fe",
            "papa",
            "maría",
            "maria",
            "ángel",
            "angel",
            "ángeles",
            "angels",
            "cruz",
            "cross",
            "cielo",
            "heaven",
            "paraíso",
            "paraiso",
            "santa",
            "santo",
            "santos",
            "saints",
            "pedro",
            "peter",
            "pablo",
            "paul",
            "david",
            "santiago",
            "adán",
            "adan",
            "eva",
            "juan",
            "magdalena",
            "bautista",
            "santuario",
            "cura",
            "curas",
            "sacerdote",
            "sacerdotes",
            "monje",
            "monjes",
            "monja",
            "monjas",
            "capilla",
            "catedral",
            "comunión",
            "comunion",
            "confesión",
            "confesion",
            "666",
            "número de la bestia",
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
    """Normaliza para comparar: lower, sin acentos, espacios colapsados."""
    if not text:
        return ""
    text = text.lower()
    for a, b in ("áa", "ée", "íi", "óo", "úu", "üu", "ñn"):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text)).strip()


def _hit(text: str, keyword_norm: str) -> bool:
    """¿El keyword aparece como palabra completa en el texto normalizado?"""
    if not keyword_norm:
        return False
    return re.search(r"(?<![a-z0-9])" + re.escape(keyword_norm) + r"(?![a-z0-9])", text) is not None


def _count_hits(
    title: str, desc: str, keywords: list[str]
) -> tuple[int, int, int, int, list[str], list[str]]:
    """Cuenta hits por clase y campo: (core_title, weak_title, core_desc, weak_desc, matched, fields)."""
    t = _norm(title)
    d = _norm(desc)
    core_title = weak_title = core_desc = weak_desc = 0
    matched: list[str] = []
    fields: list[str] = []
    for kw in keywords:
        nkw = _norm(kw)
        hit_t = _hit(t, nkw)
        hit_d = bool(d) and _hit(d, nkw)
        if not hit_t and not hit_d:
            continue
        if kw not in matched:
            matched.append(kw)
        if hit_t:
            if "titulo" not in fields:
                fields.append("titulo")
        if hit_d:
            if "descripcion" not in fields:
                fields.append("descripcion")
    return core_title, weak_title, core_desc, weak_desc, matched, fields


def match_theme(video_title: str, video_description: str = "", theme: str = PILOT_THEME) -> ThemeMatch:
    """Cuenta hits por clase y campo; devuelve el match con trazabilidad."""
    th = THEMES[theme]
    core_title, weak_title, core_desc, weak_desc, matched, fields = _count_hits(
        video_title, video_description, th["keywords"] + th["keywords_genericas"]
    )
    score = core_title * 3 + weak_title * 1 + core_desc * 2 + weak_desc * 1
    return ThemeMatch(theme=theme, score=score, matched_keywords=matched, fields_hit=fields)


def belongs_to_theme(
    video_title: str, video_description: str = "", theme: str = PILOT_THEME
) -> ThemeMatch | None:
    """Reglas editoriales: devuelve el match si el video pertenece al tema."""
    if not video_title:
        return None
    th = THEMES[theme]
    all_kw = th["keywords"] + th["keywords_genericas"]
    nkw_core = {_norm(k) for k in th["keywords"]}
    t = _norm(video_title)
    d = _norm(video_description)
    core_title = weak_title = core_desc = weak_desc = 0
    matched: list[str] = []
    fields: list[str] = []
    for kw in all_kw:
        nkw = _norm(kw)
        hit_t = _hit(t, nkw)
        hit_d = bool(d) and _hit(d, nkw)
        if not hit_t and not hit_d:
            continue
        is_core = nkw in nkw_core
        if hit_t:
            if is_core:
                core_title += 1
            else:
                weak_title += 1
            if "titulo" not in fields:
                fields.append("titulo")
        if hit_d:
            if is_core:
                core_desc += 1
            else:
                weak_desc += 1
            if "descripcion" not in fields:
                fields.append("descripcion")
        if kw not in matched:
            matched.append(kw)

    # ── reglas editoriales ───────────────────────────────────────────────────
    if core_title >= 1:
        pass
    elif core_desc >= 3:
        pass
    elif weak_title >= 1 and (core_desc + weak_desc) >= 2:
        pass
    else:
        return None

    score = core_title * 3 + weak_title * 1 + core_desc * 2 + weak_desc * 1
    return ThemeMatch(theme=theme, score=score, matched_keywords=matched, fields_hit=fields)
