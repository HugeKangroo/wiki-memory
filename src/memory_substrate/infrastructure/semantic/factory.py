from __future__ import annotations

from pathlib import Path

from memory_substrate.application.semantic.service import SemanticIndexService
from memory_substrate.infrastructure.config.repository import MemoryConfigRepository
from memory_substrate.infrastructure.semantic.lance_semantic_index import LanceSemanticIndex


def create_semantic_index_service(root: str | Path, backend: str | None = None) -> SemanticIndexService | None:
    resolved_root = Path(root)
    config = MemoryConfigRepository(resolved_root)
    requested_backend = backend or config.semantic_backend()
    if requested_backend is None:
        return None
    if requested_backend != "lancedb":
        raise ValueError(f"Unsupported semantic backend: {requested_backend}")
    model = config.semantic_model() or "BAAI/bge-m3"
    return SemanticIndexService(resolved_root, LanceSemanticIndex(resolved_root, model_name=model))
