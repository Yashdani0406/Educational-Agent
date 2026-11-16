"""Turns text into vectors with the local Ollama embedding model."""

import logging
import threading

import httpx

from eduagent.config import Settings

log = logging.getLogger(__name__)

WHAT_IT_DOES = "Turns pieces of text into number lists (vectors) so the app can find material by meaning."

# Whole embedding input (prefix + header + chunk), counted with the model's own tokenizer, special tokens included.
# The model's context is 2048; Ollama truncates silently (or returns HTTP 400) above it. The chunker enforces this cap.
MAX_EMBED_TOKENS = 1500
TOKENIZER_REPO = "nomic-ai/nomic-embed-text-v1.5"
TOKENIZER_REVISION = "e9b6763023c676ca8431644204f50c2b100d9aab"
BATCH_SIZE = 8
DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "
LABEL_PREFIX = "clustering: "

_DOWN = "Ollama isn't running. Start it with: ollama serve"
_TOO_LONG = "A piece of text was too long for the embedding model."


class EmbedError(Exception):
    """Embedding failed; the message is plain English."""


class TokenCounter:
    """Counts tokens like Ollama does for nomic-embed-text (special tokens included). Callable: `counter(text)`.

    The tokenizer file is fetched once into the models folder (lazily, thread-safe) and works offline afterwards.
    """

    def __init__(self, settings: Settings):
        self._cache_dir = str(settings.models_dir / "hf")
        self._tokenizer = None
        self._lock = threading.Lock()

    def count(self, text: str) -> int:
        return len(self._load().encode(text).ids)

    __call__ = count

    def _load(self):
        with self._lock:
            if self._tokenizer is None:
                self._tokenizer = self._read_tokenizer()
            return self._tokenizer

    def _read_tokenizer(self):
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        args = dict(repo_id=TOKENIZER_REPO, filename="tokenizer.json", revision=TOKENIZER_REVISION, cache_dir=self._cache_dir)
        try:
            try:
                path = hf_hub_download(**args, local_files_only=True)
            except Exception:
                log.info("Downloading the embedding tokenizer (once)")
                path = hf_hub_download(**args)
            return Tokenizer.from_file(path)
        except Exception as exc:
            raise EmbedError(
                "Couldn't download the embedding tokenizer (needed once). Check your internet connection and try again."
            ) from exc


class Embedder:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        counter=None,
    ):
        self._settings = settings
        self._count = counter or TokenCounter(settings)
        self._client = httpx.Client(base_url=settings.ollama_url, timeout=120, transport=transport)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(DOCUMENT_PREFIX, texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed(QUERY_PREFIX, [text])[0]

    def embed_labels(self, texts: list[str]) -> list[list[float]]:
        return self._embed(LABEL_PREFIX, texts)

    def _embed(self, prefix: str, texts: list[str]) -> list[list[float]]:
        if any(self._count(prefix + t) > MAX_EMBED_TOKENS for t in texts):
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
        if response.status_code == 400 and "context length" in response.text.lower():
            raise EmbedError(_TOO_LONG)
        if response.status_code != 200:
            log.warning("Ollama embed returned HTTP %s", response.status_code)
            raise EmbedError("The embedding model returned an error. Check that Ollama and the model are available.")
        try:
            embeddings = response.json()["embeddings"]
            if len(embeddings) != len(batch):
                raise ValueError("wrong number of vectors")
        except (ValueError, KeyError, TypeError) as exc:
            raise EmbedError("The embedding model sent back an answer the app couldn't read.") from exc
        return embeddings
