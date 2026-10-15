"""T6 — Verificación contra fuentes públicas (Wikipedia/Wikidata).

Semántica honesta de las capas (ver docs/criterios-capas.md):
- `real`: la afirmación o su referente están documentados en fuentes públicas
  verificables. La EVidencia adjunta cita título, URL y fragmento de la fuente.
- `sin_confirmar`: sin corroboración pública.
- `creencia`: superstición/folklor; se documenta su existencia cultural, nunca
  se afirma como hecho.

Promoción: `posible_real` -> `real` SOLO si al menos una evidencia veredicta
"apoya" con solapamiento suficiente. Nada es "real" sin evidencia adjunta.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from urllib.parse import quote

import requests

from .classify import TIER_BELIEF, TIER_CANDIDATE, TIER_DEFAULT, classify_text
from .themes import _hit, _norm

logger = logging.getLogger(__name__)

WIKI_API = "https://es.wikipedia.org/w/api.php"
WIKI_REST = "https://es.wikipedia.org/api/rest_v1/page/summary"
UA = "CosasAlucinantes/0.1 (base vectorial de investigación; contacto: repo)"

_VERDICT_APOYA = "apoya"
_VERDICT_CONTEXTO = "contexto"
_VERDICT_CONTRA = "contradice"

_STOP = {
    "para",
    "por",
    "con",
    "sobre",
    "entre",
    "desde",
    "hacia",
    "contra",
    "según",
    "segun",
    "como",
    "más",
    "mas",
    "menos",
    "muy",
    "cada",
    "otra",
    "otro",
    "otros",
    "entonces",
    "también",
    "tambien",
    "pero",
    "porque",
    "todo",
    "todos",
    "toda",
    "todas",
    "esta",
    "este",
    "esto",
    "estas",
    "estos",
    "ser",
    "son",
    "era",
    "fue",
    "han",
    "haber",
    "hacer",
    "hacen",
    "dice",
    "dicen",
    "decir",
    "cuando",
    "donde",
    "luego",
    "mismo",
    "misma",
    "nuestro",
    "nuestra",
    "tema",
    "temas",
    "caso",
    "casos",
    "forma",
    "parte",
    "nivel",
    "vez",
    "veces",
    "puede",
    "además",
    "ademas",
    "manera",
    "año",
    "años",
    "cosa",
    "cosas",
    "mucha",
    "mucho",
    "muchos",
    "ahora",
    "siempre",
    "nunca",
    "cual",
    "cuales",
    "modo",
    "través",
    "traves",
}

# Umbrales del veredicto (solapamiento de palabras DISTINTIVAS)
_APOYA_OVERLAP = 0.55
_CONTEXTO_OVERLAP = 0.25


@dataclass
class Evidence:
    """Una corroboración puntual de una afirmación contra una fuente."""

    claim: str
    source: str
    title: str
    url: str
    snippet: str
    verdict: str
    abstract: str = ""
    score: float = 0.0
    queried_at: str = ""

    def to_dict(self) -> dict:
        return {
            "claim": self.claim,
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "verdict": self.verdict,
            "abstract": self.abstract,
            "score": self.score,
            "queried_at": self.queried_at,
        }

    def apoya(self) -> bool:
        return self.verdict == _VERDICT_APOYA


SearchFn = Callable[[str], list[dict]]
SummaryFn = Callable[[str], dict | None]


def _wikipedia_search(term: str, limit: int = 3) -> list[dict]:
    """Busca artículos en Wikipedia ES; devuelve [{title, snippet}].

    Política cortés: throttle entre requests y un reintento con backoff ante
    429. Ante cualquier fallo devuelve [] (nunca rompe el lote).
    """
    for attempt in range(2):
        try:
            time.sleep(0.4)  # throttle: no bombardear la API
            r = requests.get(
                WIKI_API,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": term,
                    "srlimit": limit,
                    "format": "json",
                    "utf8": 1,
                },
                headers={"User-Agent": UA},
                timeout=25,
            )
            if r.status_code == 429 and attempt == 0:
                time.sleep(5)
                continue
            r.raise_for_status()
            return [
                {"title": h["title"], "snippet": re.sub(r"<[^>]+>", "", h.get("snippet", ""))}
                for h in r.json().get("query", {}).get("search", [])
                if h.get("title")
            ]
        except Exception as exc:  # noqa: BLE001 - degradar, no romper el lote
            logger.warning("wikipedia search falló (%s): %s", term[:40], exc)
    return []


def _wikipedia_summary(title: str) -> dict | None:
    """Resumen del artículo (REST summary); None si no existe o falla."""
    for attempt in range(2):
        try:
            time.sleep(0.4)  # throttle
            r = requests.get(
                f"{WIKI_REST}/{quote(title)}",
                headers={"Accept": "application/json", "User-Agent": UA},
                timeout=25,
            )
            if r.status_code == 429 and attempt == 0:
                time.sleep(5)
                continue
            if r.status_code != 200:
                return None
            d = r.json()
            url = (d.get("content_urls") or {}).get("desktop", {}).get(
                "page", ""
            ) or f"https://es.wikipedia.org/wiki/{quote(title)}"
            return {"title": d.get("title", title), "extract": d.get("extract", ""), "url": url}
        except Exception as exc:  # noqa: BLE001 - degradar, no romper el lote
            logger.warning("wikipedia summary falló (%s): %s", title, exc)
    return None


def _words(text: str) -> set[str]:
    """Palabras DISTINTIVAS (>= 6 letras) sin términos de alta frecuencia."""
    return {w for w in re.findall(r"[a-záéíóúüñ]{6,}", (text or "").lower()) if w not in _STOP}


def _overlap(fragment: str, other: str) -> float:
    """Fracción de palabras del fragmento presentes en `other` (0..1)."""
    a = _words(fragment)
    if not a:
        return 0.0
    b = _words(other)
    return len(a & b) / len(a)


def _title_gate(fragment: str, title: str) -> bool:
    """El título del artículo comparte con el fragmento al menos un token distintivo.

    Mata falsos positivos tipo "Doblado de chapa" para un fragmento sobre chatbots:
    aunque compartan vocabulario común, el ARTÍCULO no trata de lo mismo.
    """
    a = {w for w in re.findall(r"[a-záéíóúüñ]{4,}", (fragment or "").lower()) if w not in _STOP}
    b = {w for w in re.findall(r"[a-záéíóúüñ]{4,}", (title or "").lower()) if w not in _STOP}
    return bool(a & b)


def _entity_gate(fragment: str, title: str, entities: Collection[str]) -> bool:
    """Una ENTIDAD DEL TEMA aparece en el fragmento Y en el título del artículo.

    Es el gate fuerte: para hablar de corroboración, la fuente tiene que tratar
    del sujeto específico (Sábana Santa, Vaticano, Jesús...), no de un concepto
    genérico que comparte vocabulario ("Mente universal", "Ultra-Humanidad").
    """
    tf = _norm(fragment)
    tt = _norm(title)
    for e in entities:
        ne = _norm(e)
        if ne and _hit(tf, ne) and _hit(tt, ne):
            return True
    return False


def extract_fragments(text: str, max_len: int = 160, limit: int = 8) -> list[str]:
    """Oraciones del texto recortadas a `max_len` (candidatas a verificar)."""
    frags: list[str] = []
    for s in re.split(r"(?<=[.!?])\s+", text):
        s = " ".join(s.split())
        if not s:
            continue
        while len(s) > max_len:
            cut = s.rfind(" ", 0, max_len)
            if cut <= 0:
                frags.append(s[:max_len])
                s = s[max_len:].strip()
                break
            frags.append(s[:cut])
            s = s[cut:].strip()
        if s:
            frags.append(s)
        if len(frags) >= limit:
            break
    return frags


def verify_fact(
    fragment: str,
    *,
    max_evidence: int = 3,
    search_fn: SearchFn | None = None,
    summary_fn: SummaryFn | None = None,
    entities: Collection[str] | None = None,
) -> list[Evidence]:
    """Corrobora un fragmento contra fuentes públicas; devuelve evidencia.

    Veredictos por solapamiento de palabras DISTINTIVAS fragmento <-> fuente:
    - >= 0.55 Y gate de título (y, si se pasan `entities`, gate de entidad del
      tema: la entidad debe estar en el fragmento Y en el título) -> "apoya"
    - >= 0.25 -> "contexto" (menciona referentes, sin sustentar)
    - <  0.25 -> descartado (ruido)
    """
    search_fn = search_fn or _wikipedia_search
    summary_fn = summary_fn or _wikipedia_summary
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out: list[Evidence] = []
    try:
        hits = search_fn(fragment[:80])
    except Exception as exc:  # noqa: BLE001 - degradar, no romper el lote
        logger.warning("verificación sin fuentes (%s): %s", fragment[:40], exc)
        return out
    for hit in hits:
        title = hit["title"]
        snippet = hit["snippet"]
        try:
            summ = summary_fn(title)
        except Exception as exc:  # noqa: BLE001 - degradar, no romper el lote
            logger.debug("sin resumen para %s: %s", title, exc)
            summ = None
        abstract = (summ or {}).get("extract", "") or ""
        url = (summ or {}).get("url", "") or f"https://es.wikipedia.org/wiki/{quote(title)}"
        score = max(_overlap(fragment, snippet), _overlap(fragment, abstract))
        if score < _CONTEXTO_OVERLAP:
            continue
        if score >= _APOYA_OVERLAP and _title_gate(fragment, title):
            if entities is None or _entity_gate(fragment, title, entities):
                verdict = _VERDICT_APOYA
            else:
                verdict = _VERDICT_CONTEXTO
        else:
            verdict = _VERDICT_CONTEXTO
        out.append(
            Evidence(
                claim=fragment,
                source="wikipedia",
                title=title,
                url=url,
                snippet=snippet[:300],
                abstract=abstract[:400],
                verdict=verdict,
                score=round(score, 2),
                queried_at=now,
            )
        )
        if len(out) >= max_evidence:
            break
    return out


def verify_belief(
    belief_term: str,
    *,
    max_evidence: int = 2,
    search_fn: SearchFn | None = None,
    summary_fn: SummaryFn | None = None,
) -> list[Evidence]:
    """Documenta la existencia cultural de una creencia (capa `creencia`)."""
    search_fn = search_fn or _wikipedia_search
    summary_fn = summary_fn or _wikipedia_summary
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out: list[Evidence] = []
    try:
        hits = search_fn(belief_term)
    except Exception as exc:  # noqa: BLE001 - degradar, no romper el lote
        logger.warning("doc de creencia sin fuentes (%s): %s", belief_term, exc)
        return out
    for hit in hits:
        title = hit["title"]
        try:
            summ = summary_fn(title)
        except Exception as exc:  # noqa: BLE001 - degradar, no romper el lote
            logger.debug("sin resumen para %s: %s", title, exc)
            summ = None
        abstract = (summ or {}).get("extract", "") or ""
        if not abstract:
            continue
        url = (summ or {}).get("url", "") or f"https://es.wikipedia.org/wiki/{quote(title)}"
        out.append(
            Evidence(
                claim=belief_term,
                source="wikipedia",
                title=title,
                url=url,
                snippet=hit["snippet"][:300],
                abstract=abstract[:400],
                verdict=_VERDICT_CONTEXTO,
                score=1.0,  # documento cultural de la creencia
                queried_at=now,
            )
        )
        if len(out) >= max_evidence:
            break
    return out


def resolve_tier(provision: str, evidences: list[Evidence]) -> str:
    """Capa final tras la verificación (promoción SOLO con evidencia que apoya)."""
    if provision == TIER_CANDIDATE:
        if any(e.apoya() for e in evidences):
            return "real"
        return TIER_DEFAULT
    if provision == TIER_BELIEF:
        return TIER_BELIEF
    return provision


def verify_chunk(
    text: str, entities: Collection[str] | None = None
) -> tuple[str, list[Evidence]]:
    """Clasifica y verifica un fragmento completo; devuelve (tier, evidencia)."""
    cls = classify_text(text)
    evidences: list[Evidence] = []
    if cls.provision == TIER_CANDIDATE:
        for frag in extract_fragments(text)[:3]:
            evidences.extend(verify_fact(frag, entities=entities))
            if any(e.apoya() for e in evidences):
                break  # ya hay apoyo; no gastar más consultas
    elif cls.provision == TIER_BELIEF:
        for marker in cls.markers[:2]:
            evidences.extend(verify_belief(marker))
    return resolve_tier(cls.provision, evidences), evidences
