from __future__ import annotations

import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from memory_substrate.application.semantic.service import SemanticChunk
from memory_substrate.infrastructure.semantic.flag_embedding_provider import DEFAULT_SEMANTIC_MODEL, get_flag_embedding_provider


class LanceSemanticIndex:
    backend_name = "lancedb"
    table_name = "semantic_chunks"

    def __init__(self, root: str | Path, model_name: str = DEFAULT_SEMANTIC_MODEL, embedding_provider=None) -> None:
        try:
            import lancedb
        except ImportError as exc:
            raise RuntimeError(
                "Semantic search requires optional dependencies. Install with: "
                "uv sync --extra semantic"
            ) from exc
        self.root = Path(root)
        self.index_root = self.root / "memory" / "indexes" / "semantic_lancedb"
        self.model_name = model_name
        self._embedding_provider = embedding_provider
        self.lancedb = lancedb

    @property
    def embedding_provider(self):
        if self._embedding_provider is None:
            self._embedding_provider = get_flag_embedding_provider(self.model_name)
        return self._embedding_provider

    def rebuild(self, chunks: list[SemanticChunk]) -> dict:
        if self.index_root.exists():
            shutil.rmtree(self.index_root)
        self.index_root.mkdir(parents=True, exist_ok=True)
        db = self.lancedb.connect(str(self.index_root))
        if not chunks:
            return {"backend": self.backend_name, "model": self.model_name, "chunk_count": 0}
        vectors = self.embedding_provider.embed_passages([chunk.text for chunk in chunks])
        rows = [{**asdict(chunk), "vector": vector} for chunk, vector in zip(chunks, vectors, strict=True)]
        db.create_table(self.table_name, data=rows, mode="overwrite")
        return {"backend": self.backend_name, "model": self.model_name, "chunk_count": len(chunks)}

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        table = self._open_table()
        if table is None:
            return []
        query_vector = self.embedding_provider.embed_query(query)
        rows = (
            table.search(query_vector)
            .distance_type("cosine")
            .select(
                [
                    "object_id",
                    "chunk_id",
                    "object_type",
                    "kind",
                    "title",
                    "status",
                    "scope_refs",
                    "summary",
                    "text",
                    "_distance",
                ]
            )
            .limit(limit)
            .to_list()
        )
        return [
            {
                "object_id": row["object_id"],
                "chunk_id": row["chunk_id"],
                "distance": row.get("_distance", row.get("distance", 1.0)),
            }
            for row in rows
        ]

    def count_chunks(self) -> int:
        table = self._open_table()
        if table is None:
            return 0
        counter = getattr(table, "count_rows", None)
        if callable(counter):
            return int(counter())
        return len(table.to_list())

    def _open_table(self):
        if not self.index_root.exists():
            return None
        db = self.lancedb.connect(str(self.index_root))
        if hasattr(db, "list_tables"):
            response = db.list_tables()
            table_names = response.tables
        else:
            table_names = db.table_names()
        if self.table_name not in table_names:
            return None
        return db.open_table(self.table_name)
