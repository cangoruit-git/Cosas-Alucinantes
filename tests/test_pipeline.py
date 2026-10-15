"""T9 — Pruebas deterministas del pipeline de ingesta (store y verificación fake).

Cobertura:
- cada segmento largo es un chunk propio: la capa la decide la verificación
- 'posible_real' SIN apoyo cae a sin_confirmar (nunca inventa 'real')
- las evidencias viajan con el fragmento
- re-ingesta idempotente (upsert no duplica)
- skip_verify: sin red, sin 'real'
"""

from __future__ import annotations

from pf.catalog import Video
from pf.pipeline import ingest_video
from pf.transcribe import Segment, Transcript
from pf.verify import Evidence

VIDEO = Video(
    id="t1",
    title="Video de prueba",
    url="https://www.youtube.com/watch?v=t1",
    duration_sec=300,
    upload_date="20240101",
)

_TEXTOS = [
    "el proyecto MKUltra fue un programa de la CIA de control mental documentado por el congreso "
    "y reconocido por informes oficiales de la época.",
    "según la creencia popular se dice que un gato negro cruzando el camino trae mala suerte "
    "y por eso los supersticiosos hacen ciertos rituales.",
    "los grises se comunican telepáticamente desde un planeta lejano según los relatos "
    "que cuenta el canal sobre avistamientos.",
    "hay un informe del FBI que menciona el caso roswell solo como contexto histórico "
    "y los registros del museo lo catalogan así.",
]

_EVIDENCIAS = {
    "mkultra": Evidence(
        claim="proyecto mkultra", source="wikipedia", title="Proyecto MKUltra",
        url="https://es.wikipedia.org/wiki/Proyecto_MKUltra", snippet="...", verdict="apoya",
    ),
    "gato": Evidence(
        claim="gato negro", source="wikipedia", title="Gato negro (superstición)",
        url="https://es.wikipedia.org/wiki/Gato_negro_(superstición)", snippet="...", verdict="contexto",
    ),
    "roswell": Evidence(
        claim="informe fbi", source="wikipedia", title="Caso Roswell",
        url="https://es.wikipedia.org/wiki/Caso_Roswell", snippet="...", verdict="contexto",
    ),
}


class FakeVStore:
    """Graba cada ingesta sin tocar ChromaDB (cumple la interfaz StoreLike)."""

    def __init__(self):
        self.upserts: list[tuple[str, str, list[Evidence] | None]] = []

    def upsert_chunk(self, chunk, tier, evidences=None) -> str:
        self.upserts.append((chunk.video_id, tier, evidences))
        return f"{tier}:{chunk.video_id}:{chunk.index}"


def _tr(texts: list[str]) -> Transcript:
    segs = []
    t = 0.0
    for s in texts:
        dur = len(s) / 8.0
        segs.append(Segment(t, t + dur, s))
        t += dur
    return Transcript("t1", t, segs, "test")


def fake_verify(text: str) -> tuple[str, list[Evidence]]:
    low = text.lower()
    if "mkultra" in low:
        return ("real", [_EVIDENCIAS["mkultra"]])
    if "gato negro" in low:
        return ("creencia", [_EVIDENCIAS["gato"]])
    if "informe" in low and "fbi" in low:
        return ("sin_confirmar", [_EVIDENCIAS["roswell"]])
    return ("sin_confirmar", [])


fallos = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global fallos
    if not cond:
        print(f"FALLO: {name} {detail}")
        fallos += 1


# 1. distribución de capas y evidencias (sin overlap; max=300 -> cada texto = un chunk)
store = FakeVStore()
report = ingest_video(
    _tr(_TEXTOS), VIDEO, store, verify_fn=fake_verify, overlap_chars=0, max_chars=150
)
tiers = [u[1] for u in store.upserts]
check("4 chunks", len(store.upserts) == 4, f"got {len(store.upserts)}")
check("hay real con evidencia", tiers.count("real") == 1, f"tiers: {tiers}")
check("hay creencia", tiers.count("creencia") == 1, f"tiers: {tiers}")
check("contexto no promueve", tiers.count("sin_confirmar") == 2, f"tiers: {tiers}")
first_ev = store.upserts[0][2]
check("evidencia viaja con mkultra", bool(first_ev) and "wikipedia" in first_ev[0].url)
check(
    "report tiers",
    report.tiers == {"real": 1, "creencia": 1, "sin_confirmar": 2},
    f"report: {report.tiers}",
)
check("report promovidos", report.promoted_to_real == 1)
check("report samples", len(report.real_samples) == 1 and bool(report.real_samples[0]["evidence"]))

# 2. skip_verify: un candidato no puede ser real
store2 = FakeVStore()
tr2 = _tr(["el informe del FBI de 1947 documenta el caso con registros del museo"])
ingest_video(tr2, VIDEO, store2, verify_fn=fake_verify, skip_verify=True)
check("skip_verify nunca real", store2.upserts[0][1] == "sin_confirmar", f"got {store2.upserts[0][1]}")

# 3. idempotencia: re-ingerir el mismo video genera la misma cantidad por vuelta
store3 = FakeVStore()
ingest_video(_tr(_TEXTOS), VIDEO, store3, verify_fn=fake_verify, overlap_chars=0, max_chars=150)
ingest_video(_tr(_TEXTOS), VIDEO, store3, verify_fn=fake_verify, overlap_chars=0, max_chars=150)
check(
    "re-ingesta genera la misma cantidad",
    len(store3.upserts) == 8,
    f"got {len(store3.upserts)}",
)

# 4. transcript vacío -> reporte sin fragmentos
r = ingest_video(Transcript("t1", 0.0, [], "test"), VIDEO, FakeVStore(), verify_fn=fake_verify)
check("transcript vacío: 0 chunks", r.chunks == 0, f"got {r.chunks}")

if fallos:
    print(f"PIPELINE_TESTS: {fallos} fallos")
    raise SystemExit(1)
print("PIPELINE_TESTS OK")
