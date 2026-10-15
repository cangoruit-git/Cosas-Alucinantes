"""T6 — Pruebas deterministas de verificación (sin red; fetchers falsos).

Cobertura:
- evidencia que apoya -> posible_real promueve a real
- sin evidencia -> permanece sin_confirmar
- contexto (solapamiento medio) NO promueve
- verificación de creencias documenta el término folklor
- extract_fragments corta oraciones largas
"""

from __future__ import annotations

from pf.classify import TIER_BELIEF, TIER_CANDIDATE, TIER_DEFAULT
from pf.verify import extract_fragments, resolve_tier, verify_belief, verify_fact

_SNIPPET_MKULTRA = (
    "El Proyecto MKUltra fue un programa clandestino de la CIA de "
    "experimentación con control mental, documentado por el Congreso."
)
_SUMMARY_MKULTRA = _SNIPPET_MKULTRA + " Investigaciones de 1977 desclasificadas."

_SNIPPET_GRISES = (
    "En la ufología, los grises son una raza alienígena descrita con "
    "piel gris y grandes ojos negros."
)
_SNIPPET_GATO = "El gato negro es considerado de mala suerte en varias culturas."
_SUMMARY_GATO = "El gato negro es considerado de mala suerte en varias culturas europeas."


def fake_search(term: str) -> list[dict]:
    t = term.lower()
    if "mkultra" in t or "control mental" in t:
        return [{"title": "Proyecto MKUltra", "snippet": _SNIPPET_MKULTRA}]
    if "gato negro" in t:
        return [{"title": "Gato negro (superstición)", "snippet": _SNIPPET_GATO}]
    if "grises" in t or "raza alienígena" in t:
        return [{"title": "Grises (ufología)", "snippet": _SNIPPET_GRISES}]
    return []


def fake_summary(title: str) -> dict | None:
    if "MKUltra" in title:
        return {"title": title, "extract": _SUMMARY_MKULTRA, "url": f"https://es.wikipedia.org/wiki/{title}"}
    if "Gato negro" in title:
        return {"title": title, "extract": _SUMMARY_GATO, "url": f"https://es.wikipedia.org/wiki/{title}"}
    if "Grises" in title:
        return {"title": title, "extract": _SNIPPET_GRISES, "url": f"https://es.wikipedia.org/wiki/{title}"}
    return None


fallos = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global fallos
    if not cond:
        print(f"FALLO: {name} {detail}")
        fallos += 1


# 1. MKUltra: la fuente sustenta el contenido -> apoya -> real
frag = "El proyecto MKUltra fue un programa de la CIA de control mental documentado por el congreso"
ev = verify_fact(frag, search_fn=fake_search, summary_fn=fake_summary)
check("mkultra: hay evidencia", len(ev) >= 1, f"got {len(ev)}")
check("mkultra: veredicto apoya", bool(ev and ev[0].apoya()), f"got {[e.verdict for e in ev]}")
check("mkultra: promueve a real", resolve_tier(TIER_CANDIDATE, ev) == "real")

# 2. sin evidencia -> sin_confirmar (busca y no encuentra)
ev2 = verify_fact(
    "las piedras lunares se curvaron ante el ruido",
    search_fn=fake_search,
    summary_fn=fake_summary,
)
check("sin evidencia: no promueve", resolve_tier(TIER_CANDIDATE, ev2) == TIER_DEFAULT, f"got {ev2}")

# 3. contexto (solapamiento bajo-medio) NO promueve
frag3 = "hay un expediente sobre el tema y unos registros del museo"
ev3 = verify_fact(frag3, search_fn=fake_search, summary_fn=fake_summary)
check("contexto/sin apoyo: no promueve", resolve_tier(TIER_CANDIDATE, ev3) == TIER_DEFAULT)

# 4. creencia: documenta el término folklor y mantiene la capa
ev4 = verify_belief("gato negro", search_fn=fake_search, summary_fn=fake_summary)
check("creencia: documento cultural", len(ev4) >= 1 and "Gato negro" in ev4[0].title, f"got {ev4}")
check("creencia: mantiene capa", resolve_tier(TIER_BELIEF, ev4) == TIER_BELIEF)

# 5. extract_fragments
long_text = "Primera oración con contenido de investigación. " * 3 + "Segunda oración corta."
frags = extract_fragments(long_text, max_len=60, limit=4)
check("fragments: más de uno", len(frags) >= 2, f"got {len(frags)}")
check("fragments: ninguno supera max", all(len(f) <= 60 for f in frags))

# 6. evidencia serializable
d = ev[0].to_dict() if ev else {}
check("evidence.to_dict", bool(d.get("source") == "wikipedia" and d.get("url")), f"got {d}")

if fallos:
    print(f"VERIFY_TESTS: {fallos} fallos")
    raise SystemExit(1)
print("VERIFY_TESTS OK")
