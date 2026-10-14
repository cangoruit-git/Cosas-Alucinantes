"""Cosas-Alucinantes: memoria vectorial de Parafantástico.

Pipeline: catálogo del canal -> transcripción Whisper -> fragmentos ->
clasificación en 3 capas (real / sin_confirmar / creencia) -> ChromaDB ->
servidor MCP para que cualquier IA consulte la memoria.
"""

__version__ = "0.1.0"
