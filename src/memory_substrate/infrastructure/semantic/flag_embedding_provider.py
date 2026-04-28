from __future__ import annotations

from functools import lru_cache


DEFAULT_SEMANTIC_MODEL = "BAAI/bge-m3"


class FlagEmbeddingProvider:
    def __init__(self, model_name: str = DEFAULT_SEMANTIC_MODEL) -> None:
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError as exc:
            raise RuntimeError(
                "Semantic search requires optional dependencies. Install with: "
                "uv sync --extra semantic"
            ) from exc
        self.model_name = model_name
        self.model = BGEM3FlagModel(model_name, use_fp16=True)

    def embed_passages(self, texts: list[str], batch_size: int = 8) -> list[list[float]]:
        output = self.model.encode(
            texts,
            batch_size=batch_size,
            max_length=8192,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return [embedding.tolist() for embedding in output["dense_vecs"]]

    def embed_query(self, query: str) -> list[float]:
        output = self.model.encode(
            [query],
            batch_size=1,
            max_length=8192,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return output["dense_vecs"][0].tolist()


@lru_cache(maxsize=4)
def get_flag_embedding_provider(model_name: str = DEFAULT_SEMANTIC_MODEL) -> FlagEmbeddingProvider:
    return FlagEmbeddingProvider(model_name)


def clear_flag_embedding_provider_cache() -> None:
    get_flag_embedding_provider.cache_clear()
