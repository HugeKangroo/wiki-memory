from __future__ import annotations

from pathlib import Path
from typing import Any

from memory_substrate.infrastructure.storage.fs_utils import read_json, write_json
from memory_substrate.infrastructure.storage.paths import StoragePaths


VALID_GRAPH_BACKENDS = {"file", "kuzu"}
VALID_SEMANTIC_BACKENDS = {"lancedb"}
VALID_WIKI_PROJECTION_FORMATS = {"obsidian"}
DEFAULT_SEMANTIC_MODEL = "BAAI/bge-m3"


class MemoryConfigRepository:
    """File-backed root configuration for optional memory-substrate defaults."""

    def __init__(self, root: str | Path) -> None:
        self.paths = StoragePaths(root)

    def get(self) -> dict[str, Any]:
        if not self.paths.config_path.exists():
            return {"graph": {}, "semantic": {}, "wiki_projection": {}}
        config = read_json(self.paths.config_path)
        config.setdefault("graph", {})
        config.setdefault("semantic", {})
        config.setdefault("wiki_projection", {})
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

    def set_wiki_projection(self, *, path: str, format: str = "obsidian") -> dict[str, Any]:
        if format not in VALID_WIKI_PROJECTION_FORMATS:
            raise ValueError(f"Unsupported wiki projection format: {format}")
        config = self.get()
        config["wiki_projection"] = {
            "path": str(Path(path).expanduser().resolve()),
            "format": format,
        }
        write_json(self.paths.config_path, config)
        return config

    def wiki_projection(self) -> dict[str, str] | None:
        config = self.get().get("wiki_projection", {})
        path = config.get("path")
        format = config.get("format")
        if not path or not format:
            return None
        return {"path": str(path), "format": str(format)}
