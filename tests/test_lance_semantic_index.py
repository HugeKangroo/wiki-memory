from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.semantic.service import SemanticChunk
from memory_substrate.infrastructure.semantic.lance_semantic_index import LanceSemanticIndex


class FakeEmbeddingProvider:
    def embed_passages(self, texts: list[str], batch_size: int = 8) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._vector(query)

    def _vector(self, text: str) -> list[float]:
        lower = text.lower()
        return [
            1.0 if "codex" in lower else 0.0,
            1.0 if "dogfood" in lower else 0.0,
            1.0 if "graph" in lower or "kuzu" in lower else 0.0,
            1.0 if "duplicate" in lower else 0.0,
        ]


class LanceSemanticIndexTest(unittest.TestCase):
    def test_rebuild_and_search_roundtrip_with_fake_embeddings(self) -> None:
        pytest.importorskip("lancedb")
        with tempfile.TemporaryDirectory() as tmp:
            index = LanceSemanticIndex(tmp, model_name="fake", embedding_provider=FakeEmbeddingProvider())
            result = index.rebuild(
                [
                    SemanticChunk(
                        object_id="know:dogfood",
                        chunk_id="know:dogfood#object",
                        object_type="knowledge",
                        kind="dogfood",
                        title="Codex can call memory-substrate MCP",
                        summary="Dogfood verified MCP access.",
                        text="Codex dogfood can call memory-substrate MCP.",
                        status="candidate",
                        scope_refs=["scope:dogfood"],
                    ),
                    SemanticChunk(
                        object_id="know:kuzu",
                        chunk_id="know:kuzu#object",
                        object_type="knowledge",
                        kind="decision",
                        title="Kuzu graph backend",
                        summary="Kuzu remains local graph backend.",
                        text="Kuzu is the local graph backend.",
                        status="active",
                        scope_refs=["scope:memory-substrate"],
                    ),
                ]
            )

            hits = index.search("Codex dogfood MCP", limit=2)

            self.assertEqual(result["chunk_count"], 2)
            self.assertEqual(hits[0]["object_id"], "know:dogfood")
            self.assertEqual(hits[0]["chunk_id"], "know:dogfood#object")


if __name__ == "__main__":
    unittest.main()
