"""Turns text into vectors with the local Ollama embedding model."""

import logging

import httpx

from eduagent.config import Settings

log = logging.getLogger(__name__)

WHAT_IT_DOES = "Turns pieces of text into number lists (vectors) so the app can find material by meaning."

MAX_EMBED_CHARS = 4500  # about 1,500 tokens of prose; the chunker enforces it (Ollama truncates silently otherwise)
BATCH_SIZE = 8
DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "
LABEL_PREFIX = "clustering: "

_DOWN = "Ollama isn't running. Start it with: ollama serve"
_TOO_LONG = "A piece of text was too long for the embedding model."


class EmbedError(Exception):
    """Embedding failed; the message is plain English."""


class Embedder:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self._settings = settings
        self._client = httpx.Client(base_url=settings.ollama_url, timeout=120, transport=transport)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(DOCUMENT_PREFIX, texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed(QUERY_PREFIX, [text])[0]

    def embed_labels(self, texts: list[str]) -> list[list[float]]:
        return self._embed(LABEL_PREFIX, texts)

    def _embed(self, prefix: str, texts: list[str]) -> list[list[float]]:
        if any(len(t) > MAX_EMBED_CHARS for t in texts):
            raise EmbedError(_TOO_LONG)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = [prefix + t for t in texts[start : start + BATCH_SIZE]]
            vectors.extend(self._post(batch))
        return vectors

    def _post(self, batch: list[str]) -> list[list[float]]:
        # No num_ctx: limits were measured with the model's own 2048-token context.
        body: dict = {"model": self._settings.embed_model, "input": batch, "truncate": False}
        if not self._settings.ollama_use_gpu:
            body["options"] = {"num_gpu": 0}  # the 2 GB GPU crashed Ollama on CUDA init
        try:
            response = self._client.post("/api/embed", json=body)
        except httpx.ConnectError as exc:
            raise EmbedError(_DOWN) from exc
        except httpx.HTTPError as exc:
            raise EmbedError("The embedding model didn't answer. Check that Ollama is running.") from exc
        if response.status_code == 400 and any(w in response.text.lower() for w in ("context", "length")):
            raise EmbedError(_TOO_LONG)
        if response.status_code != 200:
            log.warning("Ollama embed returned HTTP %s", response.status_code)
            raise EmbedError("The embedding model returned an error. Check that Ollama and the model are available.")
        return response.json()["embeddings"]
