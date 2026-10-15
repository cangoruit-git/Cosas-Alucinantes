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

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote

import requests

from .classify import TIER_BELIEF, TIER_CANDIDATE, TIER_DEFAULT, classify_text

WIKI_API = "https://es.wikipedia.org/w/api.php"
WIKI_REST = "https://es.wikipedia.org/api/rest_v1/page/summary"
UA = "CosasAlucinantes/0.1 (base vectorial de investigación; contacto: repo)"

_VERDICT_APOYA = "apoya"
_VERDICT_CONTEXTO = "contexto"
_VERDICT_CONTRA = "contradice"

_STOP = {
    "para", "por", "con", "sobre", "entre", "desde", "hacia", "contra",
    "según", "segun", "como", "más", "mas", "menos", "muy", "cada", "otra",
    "otro", "otros", "entonces", "también", "tambien", "pero", "porque",
}


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
    """Busca artículos en Wikipedia ES; devuelve [{title, snippet}]."""
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
    r.raise_for_status()
    return [
        {"title": h["title"], "snippet": re.sub(r"<[^>]+>", "", h.get("snippet", ""))}
        for h in r.json().get("query", {}).get("search", [])
        if h.get("title")
    ]


def _wikipedia_summary(title: str) -> dict | None:
    """Resumen del artículo (REST summary); None si no existe."""
    r = requests.get(
        f"{WIKI_REST}/{quote(title)}",
        headers={"Accept": "application/json", "User-Agent": UA},
        timeout=25,
    )
    if r.status_code != 200:
        return None
    d = r.json()
    url = (
        (d.get("content_urls") or {}).get("desktop", {}).get("page", "")
        or f"https://es.wikipedia.org/wiki/{quote(title)}"
    )
    return {"title": d.get("title", title), "extract": d.get("extract", ""), "url": url}


def _words(text: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-záéíóúüñ]{4,}", (text or "").lower())
        if w not in _STOP
    }


def _overlap(fragment: str, other: str) -> float:
    """Fracción de palabras del fragmento presentes en `other` (0..1)."""
    a = _words(fragment)
    if not a:
        return 0.0
    b = _words(other)
    return len(a & b) / len(a)


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
    threshold: float = 0.20,
    search_fn: SearchFn | None = None,
    summary_fn: SummaryFn | None = None,
) -> list[Evidence]:
    """Corrobora un fragmento contra fuentes públicas; devuelve evidencia.

    Veredictos por solapamiento lexicográfico fragmento <-> fuente:
    - >= 0.45 -> "apoya" (la fuente sustenta el contenido)
    - >= 0.20 -> "contexto" (menciona los mismos referentes, sin juzgar)
    - <  0.20 -> descartado (ruido)
    """
    search_fn = search_fn or _wikipedia_search
    summary_fn = summary_fn or _wikipedia_summary
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out: list[Evidence] = []
    for hit in search_fn(fragment[:80]):
        title = hit["title"]
        snippet = hit["snippet"]
        summ = summary_fn(title)
        abstract = (summ or {}).get("extract", "") or ""
        url = (summ or {}).get("url", "") or f"https://es.wikipedia.org/wiki/{quote(title)}"
        score = max(_overlap(fragment, snippet), _overlap(fragment, abstract))
        if score < threshold:
            continue
        verdict = _VERDICT_APOYA if score >= 0.45 else _VERDICT_CONTEXTO
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
    for hit in search_fn(belief_term):
        title = hit["title"]
        summ = summary_fn(title)
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


def verify_chunk(text: str) -> tuple[str, list[Evidence]]:
    """Clasifica y verifica un fragmento completo; devuelve (tier, evidencia)."""
    cls = classify_text(text)
    evidences: list[Evidence] = []
    if cls.provision == TIER_CANDIDATE:
        for frag in extract_fragments(text)[:3]:
            evidences.extend(verify_fact(frag))
            if any(e.apoya() for e in evidences):
                break  # ya hay apoyo; no gastar más consultas
    elif cls.provision == TIER_BELIEF:
        for marker in cls.markers[:2]:
            evidences.extend(verify_belief(marker))
    return resolve_tier(cls.provision, evidences), evidences
