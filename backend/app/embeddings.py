"""
Singleton wrapper around fastembed's TextEmbedding model.
Uses BAAI/bge-small-en-v1.5 — 384 dimensions, ~45 MB download, runs on CPU.
Model is cached to ~/.cache/fastembed after first download.
"""
import asyncio
from typing import Sequence

_model = None
EMBEDDING_DIM = 384
MODEL_NAME = "BAAI/bge-small-en-v1.5"


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(MODEL_NAME)
    return _model


def embed_sync(texts: Sequence[str]) -> list[list[float]]:
    """Synchronous embedding — returns list of float vectors."""
    model = _get_model()
    return [v.tolist() for v in model.embed(texts)]


async def embed(texts: Sequence[str]) -> list[list[float]]:
    """Async-safe embedding — runs in thread pool to avoid blocking the event loop."""
    return await asyncio.to_thread(embed_sync, texts)


async def embed_one(text: str) -> list[float]:
    results = await embed([text])
    return results[0]


def vec_to_pg(v: list[float]) -> str:
    """Convert a float list to the Postgres vector literal format: '[0.1,0.2,...]'"""
    return "[" + ",".join(f"{x:.8f}" for x in v) + "]"
