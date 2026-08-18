"""Embedding providers.

Deliberately pluggable: the deployment target is undecided, so nothing here may
assume a specific cloud. Three implementations ship:

* ``hash``   - deterministic character n-gram hashing. No network, no model
               download, works offline and in CI. This is the default so the
               stack boots anywhere; its similarity is lexical-ish, not truly
               semantic, so switch to ``local`` before any quality evaluation.
* ``local``  - sentence-transformers multilingual model (Arabic + English).
* ``voyage`` - hosted embeddings via Voyage AI.

Anthropic does not serve an embeddings endpoint, which is why the LLM provider
and the embedding provider are configured independently.
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from functools import lru_cache

from app.core.config import get_settings

_TOKEN = re.compile(r"\w+", re.UNICODE)


class EmbeddingProvider(ABC):
    name: str = "base"

    def __init__(self, dim: int) -> None:
        self.dim = dim

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


def _l2_normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return vector
    return [v / norm for v in vector]


class HashingEmbeddings(EmbeddingProvider):
    """Offline deterministic embeddings over word tokens and character 3-grams."""

    name = "hash"

    def _features(self, text: str) -> list[str]:
        lowered = (text or "").lower()
        tokens = _TOKEN.findall(lowered)
        features = list(tokens)
        squashed = " ".join(tokens)
        features.extend(squashed[i : i + 3] for i in range(max(0, len(squashed) - 2)))
        return features

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dim
            for feature in self._features(text):
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "big") % self.dim
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[index] += sign
            out.append(_l2_normalise(vector))
        return out


class LocalSentenceTransformerEmbeddings(EmbeddingProvider):
    name = "local"

    def __init__(self, dim: int, model_name: str) -> None:
        super().__init__(dim)
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "EMBEDDING_PROVIDER=local requires `pip install sentence-transformers`"
            ) from exc
        self._model = SentenceTransformer(model_name)
        actual = int(self._model.get_sentence_embedding_dimension())
        if actual != dim:
            raise RuntimeError(
                f"EMBEDDING_DIM={dim} does not match model '{model_name}' (dim={actual}). "
                "Update EMBEDDING_DIM and re-create the vector columns."
            )

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - needs model
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, v)) for v in vectors]


class VoyageEmbeddings(EmbeddingProvider):
    name = "voyage"

    def __init__(self, dim: int, api_key: str, model_name: str) -> None:
        super().__init__(dim)
        self._api_key = api_key
        self._model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - needs network
        import httpx

        response = httpx.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"input": texts, "model": self._model_name},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda d: d["index"])]


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    provider = settings.embedding_provider.lower()
    if provider == "local":
        return LocalSentenceTransformerEmbeddings(settings.embedding_dim, settings.embedding_model)
    if provider == "voyage":
        if not settings.voyage_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=voyage requires VOYAGE_API_KEY")
        return VoyageEmbeddings(settings.embedding_dim, settings.voyage_api_key, settings.embedding_model)
    return HashingEmbeddings(settings.embedding_dim)
