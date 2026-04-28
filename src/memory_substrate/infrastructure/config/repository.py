from __future__ import annotations

from pathlib import Path
from typing import Any

from memory_substrate.infrastructure.storage.fs_utils import read_json, write_json
from memory_substrate.infrastructure.storage.paths import StoragePaths


VALID_GRAPH_BACKENDS = {"file", "kuzu"}
VALID_SEMANTIC_BACKENDS = {"lancedb"}
DEFAULT_SEMANTIC_MODEL = "BAAI/bge-m3"


class MemoryConfigRepository:
    """File-backed root configuration for optional memory-substrate defaults."""

    def __init__(self, root: str | Path) -> None:
        self.paths = StoragePaths(root)

    def get(self) -> dict[str, Any]:
        if not self.paths.config_path.exists():
            return {"graph": {}, "semantic": {}}
        config = read_json(self.paths.config_path)
        config.setdefault("graph", {})
        config.setdefault("semantic", {})
        return config

    def set_graph_backend(self, backend: str) -> dict[str, Any]:
        if backend not in VALID_GRAPH_BACKENDS:
            raise ValueError(f"Unsupported graph backend: {backend}")
        config = self.get()
        config["graph"]["backend"] = backend
        write_json(self.paths.config_path, config)
        return config

    def graph_backend(self) -> str | None:
        backend = self.get().get("graph", {}).get("backend")
        return str(backend) if backend else None

    def set_semantic_backend(self, backend: str, model: str = DEFAULT_SEMANTIC_MODEL) -> dict[str, Any]:
        if backend not in VALID_SEMANTIC_BACKENDS:
            raise ValueError(f"Unsupported semantic backend: {backend}")
        config = self.get()
        config["semantic"]["backend"] = backend
        config["semantic"]["model"] = model
        write_json(self.paths.config_path, config)
        return config

    def semantic_backend(self) -> str | None:
        backend = self.get().get("semantic", {}).get("backend")
        return str(backend) if backend else None

    def semantic_model(self) -> str | None:
        model = self.get().get("semantic", {}).get("model")
        return str(model) if model else None
