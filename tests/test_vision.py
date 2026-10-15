"""T12 — Pruebas deterministas de la capa visual (video sintético + tagger falso).

No descarga modelos: el CLIP real se usa solo en el lote (integración).

Cobertura:
- muestreo de fotogramas de un video real (sintético) con tiempos crecientes
- etiquetado con umbral (se filtran scores bajos)
- agregación por ventana de tiempo (lo que se VE en el minuto del fragmento)
- caché de notas: guardar/cargar roundtrip
"""

from __future__ import annotations

import tempfile
from fractions import Fraction
from pathlib import Path

import av
from PIL import Image

from pf.vision import VisualNote, iter_frames, load_notes, save_notes, tags_for_window, visual_notes


def _video_sintetico(path: Path, segundos: int = 6, fps: int = 2) -> Path:
    """Crea un video real (mpeg4) con colores que cambian, para probar el muestreo."""
    container = av.open(str(path), mode="w")
    stream = container.add_stream("mpeg4", rate=fps)
    stream.width, stream.height = 64, 64
    stream.pix_fmt = "yuv420p"
    total = segundos * fps
    for i in range(total):
        img = Image.new("RGB", (64, 64), ((i * 37) % 255, 60, 120))
        frame = av.VideoFrame.from_image(img)
        frame.pts = i
        frame.time_base = Fraction(1, fps)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    return path


def tagger_falso(_imagen) -> list[tuple[str, float]]:
    """Tagger determinista: siempre las mismas etiquetas (una por debajo del umbral)."""
    return [
        ("una escena violenta con sangre", 0.61),
        ("una figura religiosa o de Jesús", 0.44),
        ("una animación o gráfico por computadora", 0.10),  # < 0.22 -> se filtra
    ]


fallos = 0


def check(nombre: str, cond: bool, detalle: str = "") -> None:
    global fallos
    if not cond:
        print(f"FALLO: {nombre} {detalle}")
        fallos += 1


tmp = Path(tempfile.mkdtemp(prefix="pf-vision-"))
try:
    video = _video_sintetico(tmp / "v.mp4", segundos=6, fps=2)

    # 1. muestreo: al menos 3 fotogramas con tiempos crecientes
    frames = list(iter_frames(video, every_sec=2.0, max_frames=10))
    check("muestrea >= 3 fotogramas", len(frames) >= 3, f"got {len(frames)}")
    tiempos = [t for t, _ in frames]
    check("tiempos crecientes", tiempos == sorted(tiempos), f"got {tiempos}")
    check("imagen PIL", isinstance(frames[0][1], Image.Image))

    # 2. etiquetado con umbral: la etiqueta de 0.10 se filtra
    notas = visual_notes(video, tagger_falso, every_sec=2.0, max_frames=5, top_k=3, min_score=0.22)
    check("notas generadas", len(notas) >= 2, f"got {len(notas)}")
    todas = [n for nota in notas for n, _ in nota.tags]
    check("filtra scores bajos", "una animación o gráfico por computadora" not in todas)
    check("conserva scores altos", "una escena violenta con sangre" in todas)

    # 3. agregación por ventana: el chunk [0,4] ve las etiquetas del minuto
    ventana = tags_for_window(notas, 0.0, 4.0, max_tags=3)
    nombres = [v["tag"] for v in ventana]
    check("ventana trae etiquetas", len(ventana) >= 1, f"got {ventana}")
    check("ventana ordenada por score", nombres[:1] == ["una escena violenta con sangre"], f"got {nombres}")
    check("ventana con t y score", all("t" in v and "score" in v for v in ventana))

    # 4. ventana sin fotogramas -> vacío
    check("ventana vacía", tags_for_window(notas, 900.0, 960.0) == [])

    # 5. caché roundtrip
    destino = save_notes(notas, tmp / "notas" / "v.json")
    recargadas = load_notes(destino)
    check("roundtrip cantidad", len(recargadas) == len(notas))
    check("roundtrip tags", recargadas[0].tags == notas[0].tags, f"{recargadas[0].tags} vs {notas[0].tags}")
    check("load_notes inexistente -> []", load_notes(tmp / "no-existe.json") == [])

    # 6. VisualNote serializable
    d = VisualNote(t=1.0, tags=[("x", 0.5)]).to_dict()
    check("to_dict", d["t"] == 1.0 and d["tags"][0][0] == "x")
finally:
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print(f"VISION_TESTS: {fallos} fallos")
    raise SystemExit(1)
print("VISION_TESTS OK")
