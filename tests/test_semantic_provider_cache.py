from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.semantic.service import SemanticChunk
from memory_substrate.infrastructure.semantic.flag_embedding_provider import clear_flag_embedding_provider_cache
from memory_substrate.infrastructure.semantic.lance_semantic_index import LanceSemanticIndex


class FakeLanceDbModule:
    def __init__(self) -> None:
        self.connections = []

    def connect(self, path: str):
        connection = FakeLanceDbConnection()
        self.connections.append((path, connection))
        return connection


class FakeLanceDbConnection:
    def create_table(self, name: str, data, mode: str) -> None:
        self.created = {"name": name, "data": list(data), "mode": mode}


class CountingEmbeddingProvider:
    def __init__(self) -> None:
        self.passages_calls = 0

    def embed_passages(self, texts: list[str], batch_size: int = 8) -> list[list[float]]:
        self.passages_calls += 1
        return [[1.0] for _ in texts]


class SemanticProviderCacheTest(unittest.TestCase):
    def test_lance_index_loads_default_provider_lazily_and_reuses_process_cache(self) -> None:
        provider = CountingEmbeddingProvider()
        factory_calls = []
        fake_lancedb = FakeLanceDbModule()

        def provider_factory(model_name: str):
            factory_calls.append(model_name)
            return provider

        chunk = SemanticChunk(
            object_id="know:x",
            chunk_id="know:x#object",
            object_type="knowledge",
            kind="fact",
            title="Cached semantic provider",
            summary="",
            text="Cached semantic provider text.",
            status="active",
            scope_refs=[],
        )

        with (
            patch.dict(sys.modules, {"lancedb": fake_lancedb}),
            patch(
                "memory_substrate.infrastructure.semantic.flag_embedding_provider.FlagEmbeddingProvider",
                side_effect=provider_factory,
            ),
        ):
            clear_flag_embedding_provider_cache()
            first = LanceSemanticIndex("/tmp/cache-test", model_name="fake-model")
            second = LanceSemanticIndex("/tmp/cache-test", model_name="fake-model")

            self.assertEqual(factory_calls, [])

            first.rebuild([chunk])
            second.rebuild([chunk])
            clear_flag_embedding_provider_cache()

        self.assertEqual(factory_calls, ["fake-model"])
        self.assertEqual(provider.passages_calls, 2)


if __name__ == "__main__":
    unittest.main()
