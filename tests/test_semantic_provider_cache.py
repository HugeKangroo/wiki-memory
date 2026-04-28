from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.semantic.service import SemanticChunk
from memory_substrate.infrastructure.semantic.flag_embedding_provider import FlagEmbeddingProvider, clear_flag_embedding_provider_cache
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


class FakeBgeM3FlagModel:
    calls = []

    def __init__(self, model_name: str, **kwargs) -> None:
        self.calls.append({"model_name": model_name, "kwargs": kwargs})


class FakeHuggingFaceHubModule:
    calls = []
    cached_path = "/cached/bge-m3"
    fail_cached_only = False

    @classmethod
    def snapshot_download(cls, **kwargs) -> str:
        cls.calls.append(kwargs)
        if kwargs.get("local_files_only") and cls.fail_cached_only:
            raise OSError("cached model is missing")
        return cls.cached_path


class SemanticProviderCacheTest(unittest.TestCase):
    def tearDown(self) -> None:
        FakeBgeM3FlagModel.calls = []
        FakeHuggingFaceHubModule.calls = []
        FakeHuggingFaceHubModule.fail_cached_only = False
        clear_flag_embedding_provider_cache()

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

    def test_flag_embedding_provider_uses_cached_model_before_online_fallback(self) -> None:
        with patch.dict(
            sys.modules,
            {
                "FlagEmbedding": _fake_flag_embedding_module(),
                "huggingface_hub": FakeHuggingFaceHubModule,
            },
        ):
            provider = FlagEmbeddingProvider("fake-model")

        self.assertEqual(provider.model_name, "fake-model")
        self.assertEqual(provider.model_path, "/cached/bge-m3")
        self.assertEqual(FakeHuggingFaceHubModule.calls[0]["repo_id"], "fake-model")
        self.assertEqual(FakeHuggingFaceHubModule.calls[0]["local_files_only"], True)
        self.assertEqual(len(FakeBgeM3FlagModel.calls), 1)
        self.assertEqual(FakeBgeM3FlagModel.calls[0]["model_name"], "/cached/bge-m3")
        self.assertEqual(FakeBgeM3FlagModel.calls[0]["kwargs"]["use_fp16"], True)

    def test_flag_embedding_provider_downloads_when_cache_is_missing(self) -> None:
        FakeHuggingFaceHubModule.fail_cached_only = True

        with patch.dict(
            sys.modules,
            {
                "FlagEmbedding": _fake_flag_embedding_module(),
                "huggingface_hub": FakeHuggingFaceHubModule,
            },
        ):
            provider = FlagEmbeddingProvider("fake-model")

        self.assertEqual(provider.model_name, "fake-model")
        self.assertEqual(provider.model_path, "fake-model")
        self.assertEqual(len(FakeBgeM3FlagModel.calls), 1)
        self.assertEqual(FakeBgeM3FlagModel.calls[0]["model_name"], "fake-model")


def _fake_flag_embedding_module():
    class FakeFlagEmbeddingModule:
        BGEM3FlagModel = FakeBgeM3FlagModel

    return FakeFlagEmbeddingModule()


if __name__ == "__main__":
    unittest.main()
