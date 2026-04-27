from __future__ import annotations

from pathlib import Path

from .file_graph_backend import FileGraphBackend
from .kuzu_graph_backend import KuzuGraphBackend


def create_graph_backend(root: str | Path, backend: str | None):
    """Create an optional graph backend by name."""
    if backend is None:
        return None
    if backend == "file":
        return FileGraphBackend(root)
    if backend == "kuzu":
        return KuzuGraphBackend(root)
    raise ValueError(f"Unsupported graph backend: {backend}")
