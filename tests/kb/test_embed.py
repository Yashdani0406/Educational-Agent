import json

import httpx
import pytest

from eduagent.config import Settings
from eduagent.kb.embed import MAX_EMBED_TOKENS, Embedder, EmbedError, TokenCounter


def make(handler, counter=len, **overrides):
    """Embedder with a fake counter (one token per character) so nothing is downloaded."""
    settings = Settings(_env_file=None, **overrides)
    return Embedder(settings, transport=httpx.MockTransport(handler), counter=counter)


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
    room = MAX_EMBED_TOKENS - len("search_query: ")  # the prefix counts too
    with pytest.raises(EmbedError, match="too long"):
        emb.embed_documents(["ok", "x" * MAX_EMBED_TOKENS])
    with pytest.raises(EmbedError, match="too long"):
        emb.embed_query("x" * (room + 1))
    assert seen == []
    emb.embed_query("x" * room)  # exactly 1,500 tokens is fine
    assert len(seen) == 1


def test_http_400_context_error_becomes_too_long_message():
    def handler(request):
        return httpx.Response(400, json={"error": "the input length exceeds the context length"})

    with pytest.raises(EmbedError, match="A piece of text was too long for the embedding model."):
        make(handler).embed_query("hi")


@pytest.mark.parametrize("payload", [{"embeddings": [[1.0], [2.0]]}, {"nope": 1}, {"embeddings": None}])
def test_malformed_200_becomes_embed_error(payload):
    def handler(request):
        return httpx.Response(200, json=payload)

    with pytest.raises(EmbedError, match="couldn't read"):
        make(handler).embed_query("hi")


def test_undecodable_200_becomes_embed_error():
    def handler(request):
        return httpx.Response(200, content=b"not json")

    with pytest.raises(EmbedError, match="couldn't read"):
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


def test_tokenizer_failure_is_plain_english(tmp_path, monkeypatch):
    import huggingface_hub

    def boom(**kwargs):
        raise OSError("no network")

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", boom)
    counter = TokenCounter(Settings(_env_file=None, models_dir=tmp_path))
    with pytest.raises(EmbedError, match="Couldn't download the embedding tokenizer"):
        counter.count("hi")


# Samples written for these tests (not course material).
PROSE = (
    "A decision tree learns by asking a sequence of yes or no questions about the data. "
    "At every step it looks for the question that separates the examples into the purest groups it can find, "
    "and then repeats the process inside each group until the groups are small or perfectly sorted. "
)
CODE = '''def gini(labels):
    counts = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    total = len(labels)
    return 1.0 - sum((c / total) ** 2 for c in counts.values())
'''
TABLE = "| 0.4821 | 17.093 | 0.0031 | 233 | 9.8e-05 |\n"
LATEX = (
    r"\hat{\beta} = (X^{\top}X)^{-1}X^{\top}y, \quad "
    r"\sum_{i=1}^{n} \frac{(y_i - \hat{y}_i)^2}{\sigma^2} \le \alpha_{0.05}" + "\n"
)
SAMPLES = {"prose": PROSE, "code": CODE, "table": TABLE, "latex": LATEX}
DOCUMENT = "search_document: "


def fit_to_tokens(sample: str, counter, prefix: str, low: int = 1400, high: int = 1500) -> str:
    """Repeat the sample until the prefixed text counts between low and high tokens."""
    text = ""
    while counter(prefix + text + sample) <= high:
        text += sample
    assert low <= counter(prefix + text) <= high
    return text


def ollama_token_count(settings: Settings, text: str) -> int:
    body = {"model": settings.embed_model, "input": [text], "truncate": False, "options": {"num_gpu": 0}}
    reply = httpx.post(f"{settings.ollama_url}/api/embed", json=body, timeout=120)
    assert reply.status_code == 200, reply.text
    return reply.json()["prompt_eval_count"]


@pytest.mark.models
@pytest.mark.ollama
def test_live_counter_matches_ollama():
    from eduagent.kb.models_dir import configure_model_dirs

    settings = Settings(_env_file=None)
    configure_model_dirs(settings)
    counter = TokenCounter(settings)
    for name, sample in SAMPLES.items():
        text = DOCUMENT + sample
        ours, theirs = counter(text), ollama_token_count(settings, text)
        print(f"\n{name}: counter={ours} ollama={theirs}")
        assert ours == theirs
    assert any((settings.models_dir / "hf").rglob("tokenizer.json"))


@pytest.mark.models
@pytest.mark.ollama
@pytest.mark.parametrize("name", ["prose", "table"])
def test_live_embed_dims(name):
    from eduagent.kb.models_dir import configure_model_dirs

    settings = Settings(_env_file=None)
    configure_model_dirs(settings)
    counter = TokenCounter(settings)
    text = fit_to_tokens(SAMPLES[name], counter, DOCUMENT)
    emb = Embedder(settings, counter=counter)
    [doc] = emb.embed_documents([text])
    assert len(doc) == 768 and all(isinstance(v, float) for v in doc)
    used = ollama_token_count(settings, DOCUMENT + text)
    print(f"\nlive embed {name}: {len(text)} chars, counted {counter(DOCUMENT + text)}, ollama {used}")
    assert 1400 <= used <= 1500
    assert len(emb.embed_query("what is a decision tree")) == 768
    assert len(emb.embed_labels(["Decision trees"])[0]) == 768
