"""T5 — Pruebas deterministas de la clasificación en capas (python -m tests.test_classify).

Casos:
- superstición + discurso folklor -> creencia
- referentes verificables + año -> posible_real
- afirmación sin señales -> sin_confirmar
- el conservadurismo: dudar -> sin_confirmar, nunca inventar 'real'
"""

from __future__ import annotations

from pf.classify import (
    TIER_BELIEF,
    TIER_CANDIDATE,
    TIER_DEFAULT,
    classify_text,
)

CASOS_CREENCIA = [
    "se dice que un gato negro cruzando tu camino trae mala suerte y por eso la gente evita pajarl... nada que ver, pero los supersticiosos tiran sal gorda al hombro",  # noqa: E501
    "mi abuela contaba que la lechuza canta anunciando una muerte, una creencia popular de los pueblos",
    "según la creencia, romper un espejo trae siete años de mala suerte, una superstición muy extendida",
]

CASOS_CANDIDATO = [
    "el informe del FBI de 1947 sobre el incidente de Roswell fue desclasificado y los registros muestran dos globos",  # noqa: E501
    "los documentos desclasificados de la CIA, el estudio forense y las grabaciones del 2019 respaldan la investigación",  # noqa: E501
    "el análisis de laboratorio y la autopsia realizada por el médico forense figuran en los archivos del museo",  # noqa: E501
]

CASOS_DEFAULT = [
    "los grises se comunican telepáticamente y vienen de un planeta lejano para observar a la humanidad",
    "el sepulcro de Cristo habría sido trasladado por seres de otra dimensión en el año del gran eclipse",
    "la energía de las pirámides curaría enfermedades según algunos relatos antiguos del canal",
]

fallos = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global fallos
    if not cond:
        print(f"FALLO: {name} {detail}")
        fallos += 1


for i, t in enumerate(CASOS_CREENCIA):
    c = classify_text(t)
    check(f"creencia {i}", c.provision == TIER_BELIEF, f"got {c.provision} markers={c.markers}")

for i, t in enumerate(CASOS_CANDIDATO):
    c = classify_text(t)
    check(f"candidato {i}", c.provision == TIER_CANDIDATE, f"got {c.provision} markers={c.markers}")

for i, t in enumerate(CASOS_DEFAULT):
    c = classify_text(t)
    check(f"default {i}", c.provision == TIER_DEFAULT, f"got {c.provision} markers={c.markers}")

# conservadurismo: ningún caso de default puede ser 'real'
check("nunca real directo", all(classify_text(t).provision != "real" for t in CASOS_CREENCIA + CASOS_DEFAULT))

if fallos:
    print(f"CLASSIFY_TESTS: {fallos} fallos")
    raise SystemExit(1)
print("CLASSIFY_TESTS OK")
