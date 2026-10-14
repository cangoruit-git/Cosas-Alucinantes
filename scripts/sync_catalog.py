"""T2 — Sincroniza el catálogo del canal y selecciona los videos del tema.

Uso: .venv/Scripts/python -m scripts.sync_catalog [--theme dios-cristo]
"""

from __future__ import annotations

import argparse

from pf.catalog import ChannelCatalog
from pf.themes import PILOT_THEME, belongs_to_theme

TM = PILOT_THEME


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", default=TM)
    args = ap.parse_args()

    cat = ChannelCatalog()
    try:
        n = cat.sync()
        print(f"catálogo: {n} videos sincronizados")

        # selección por título (sin descripción todavía)
        matches = []
        for v in cat.all_videos():
            m = belongs_to_theme(v.title, "", args.theme)
            if m:
                cat.save_theme_match(v.id, m)  # queda registrado qué keywords matchearon
                matches.append((v, m))
        print(f"tema '{args.theme}': {len(matches)} candidatos por título")

        # enriquecer con descripción para confirmar / ampliar
        cand: dict[str, object] = {v.id: (v, m) for v, m in matches}
        enriched_count = cat.enrich(list(cand))
        print(f"enriquecidos: {enriched_count} descripciones")

        # re-evaluar con descripción
        confirmed = []
        for v, _m in matches:
            m2 = belongs_to_theme(v.title, v.description, args.theme)
            if m2:
                cat.save_theme_match(v.id, m2)
                confirmed.append((v, m2))

        print(f"confirmados con descripción: {len(confirmed)}")
        for v, m in sorted(confirmed, key=lambda x: -(x[1].score or 0)):
            dur = f"{v.duration_sec // 60}m" if v.duration_sec else "?"
            print(f"  [{v.id}] ({dur}) score={m.score} title={v.title!r}")
        return 0
    finally:
        cat.close()


if __name__ == "__main__":
    raise SystemExit(main())
