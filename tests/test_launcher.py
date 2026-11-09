import httpx
from pydantic import SecretStr

from eduagent.config import Settings
from eduagent.launcher import preflight

NO_KEY = "No GEMINI_API_KEY in .env — running everything on Qwen."


def make(key: str | None = "k", **kw) -> Settings:
    return Settings(_env_file=None, gemini_api_key=SecretStr(key) if key else None, **kw)


def models(*names: str):
    return lambda: list(names)


def test_preflight_all_good():
    assert preflight(make(), models("qwen3:4b-instruct", "nomic-embed-text:latest")) == []


def test_preflight_ollama_down():
    def down():
        raise httpx.ConnectError("refused")

    assert preflight(make(), down) == ["Ollama isn't running. Start it with: ollama serve"]


def test_preflight_missing_model():
    warnings = preflight(make(), models("nomic-embed-text:latest"))
    assert warnings == ["Model qwen3:4b-instruct not found. Run: ollama pull qwen3:4b-instruct"]


def test_preflight_missing_embed_model():
    warnings = preflight(make(), models("qwen3:4b-instruct"))
    assert warnings == ["Model nomic-embed-text not found. Run: ollama pull nomic-embed-text"]


def test_preflight_explicit_latest_tag_matches():
    s = make(embed_model="nomic-embed-text:latest")
    assert preflight(s, models("qwen3:4b-instruct", "nomic-embed-text:latest")) == []


def test_preflight_no_key():
    ok = models("qwen3:4b-instruct", "nomic-embed-text:latest")
    assert preflight(make(key=None), ok) == [NO_KEY]
    assert preflight(make(key="  "), ok) == [NO_KEY]
