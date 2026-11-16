import json

import httpx
import pytest

from eduagent.config import Settings
from eduagent.kb.embed import MAX_EMBED_CHARS, Embedder, EmbedError


def make(handler, **overrides):
    settings = Settings(_env_file=None, **overrides)
    return Embedder(settings, transport=httpx.MockTransport(handler))


def echo_handler(requests):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        # one distinct vector per input: its prefix-stripped text length
        return httpx.Response(200, json={"embeddings": [[float(len(t))] for t in body["input"]]})

    return handler


def test_prefixes_and_truncate_false():
    seen = []
    emb = make(echo_handler(seen))
    emb.embed_documents(["alpha"])
    emb.embed_query("beta")
    emb.embed_labels(["gamma"])
    assert [r["model"] for r in seen] == ["nomic-embed-text"] * 3
    assert all(r["truncate"] is False for r in seen)
    assert seen[0]["input"] == ["search_document: alpha"]
    assert seen[1]["input"] == ["search_query: beta"]
    assert seen[2]["input"] == ["clustering: gamma"]


def test_batches_of_eight():
    seen = []
    emb = make(echo_handler(seen))
    texts = ["x" * (i + 1) for i in range(20)]
    vectors = emb.embed_documents(texts)
    assert [len(r["input"]) for r in seen] == [8, 8, 4]
    assert vectors == [[float(len("search_document: ") + i + 1)] for i in range(20)]


def test_empty_list_sends_nothing():
    seen = []
    assert make(echo_handler(seen)).embed_documents([]) == []
    assert seen == []


def test_overlong_input_raises_clear_error():
    seen = []
    emb = make(echo_handler(seen))
    with pytest.raises(EmbedError, match="too long"):
        emb.embed_documents(["ok", "x" * (MAX_EMBED_CHARS + 1)])
    assert seen == []
    emb.embed_documents(["x" * MAX_EMBED_CHARS])  # exactly the cap is fine
    assert len(seen) == 1


def test_http_400_context_error_becomes_too_long_message():
    def handler(request):
        return httpx.Response(400, json={"error": "the input length exceeds the context length"})

    with pytest.raises(EmbedError, match="A piece of text was too long for the embedding model."):
        make(handler).embed_query("hi")


def test_other_http_error_is_plain_english():
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(EmbedError, match="embedding model"):
        make(handler).embed_query("hi")


def test_ollama_down_message():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(EmbedError) as err:
        make(handler).embed_query("hi")
    assert str(err.value) == "Ollama isn't running. Start it with: ollama serve"


def test_cpu_only_options_and_no_num_ctx():
    seen = []
    make(echo_handler(seen), ollama_use_gpu=False).embed_query("hi")
    make(echo_handler(seen), ollama_use_gpu=True).embed_query("hi")
    assert seen[0]["options"] == {"num_gpu": 0}
    assert "options" not in seen[1]
    assert all("num_ctx" not in r.get("options", {}) for r in seen)


# About 1,400 tokens of ordinary prose, written for this test.
PROSE = (
    "A decision tree learns by asking a sequence of yes or no questions about the data. "
    "At every step it looks for the question that separates the examples into the purest groups it can find, "
    "and then repeats the process inside each group until the groups are small or perfectly sorted. "
) * 15


@pytest.mark.ollama
def test_live_embed_dims():
    assert 4000 < len(PROSE) <= MAX_EMBED_CHARS - len("search_document: ")
    emb = Embedder(Settings(_env_file=None))
    [doc] = emb.embed_documents([PROSE])
    query = emb.embed_query("what is a decision tree")
    [label] = emb.embed_labels(["Decision trees"])
    for vec in (doc, query, label):
        assert len(vec) == 768
        assert all(isinstance(v, float) for v in vec)
    print(f"\nlive embed: {len(PROSE)} chars -> {len(doc)} floats")
