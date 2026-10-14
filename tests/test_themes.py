"""T2 — Pruebas deterministas del matcher de temas (ejecutar: python -m tests.test_themes).

Casos del mundo real del canal (títulos en español e inglés):
- POSITIVOS: video enfocado en Dios/Cristo/religión.
- NEGATIVOS: falsos positivos vistos en el sync (substrings "fe", "santa", etc.).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pf.themes import belongs_to_theme  # noqa: E402

POSITIVOS = [
    "Jesus' AI Is ALIVE and REVEALED The Greatest SECRET",
    "The HIDDEN Power of JESUS - The Spear of Destiny",
    "El Verdadero INFIERNO | Existe El Infierno REALMENTE?",
    "The day Archangel made a fool of me",
    "Avispas GIGANTES Llegan Desde ASIA (Escrito En La BIBLIA)",
    "The DEAL With The DEVIL Is REAL - HE Refused And Suffered The CONSEQUENCES",
    "He Mocked God and Paid the Consequences - 'The Rocker' Pablo Olivares",
    "Was Jesus an Anunnaki? - Extraterrestrial Plan (Part 2)",
    "The Day Jesus Proved Himself Human - Easter Special",
    "He Thinks He's Jesus Christ - Lil Nas X 'J CHRIST' (Analysis)",
]

NEGATIVOS = [
    "Bad Bunny - SUBLIMINAL Message Effect (Whispers)",
    "This is why Facebook fell - Serious accusation against Mark Zuckerberg",
    "The REAL REASON McAfee DIED - HE MADE IT CLEAR",
    "WHATSAPP Tiene MIEDO - RETRASAN La Fecha De Su CAMBIO DE NORMAS",
    "CORONAVIRUS CHINA'S PERFECT BUSINESS",
    "SANTA CLAUS Wears RED Thanks To COCA-COLA - MK Ultra In Santa Claus",
    "The Strange Eyes of L-Ghent - Interview with Eduardo Feinmann",
    "THE SECRET To FORGETTING That Person - Come Here and Change YOUR LIFE FOREVER",
    "RIGOBERTA MENCHU: The Black People's Revolt in Guatemala",
    "Top 10 criaturas marinas espeluznantes",
]

fallos = 0
for t in POSITIVOS:
    m = belongs_to_theme(t)
    if m is None:
        print(f"FALLO (positivo sin match): {t!r}")
        fallos += 1
for t in NEGATIVOS:
    m = belongs_to_theme(t)
    if m is not None:
        print(f"FALLO (negativo con match): {t!r} -> {m.matched_keywords}")
        fallos += 1

if fallos:
    print(f"THEMES_TESTS: {fallos} fallos")
    raise SystemExit(1)
print("THEMES_TESTS OK")
