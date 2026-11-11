import httpx
import pytest
from pydantic import SecretStr

from eduagent.config import Settings
from eduagent.launcher import preflight

NOT_RUNNING = "Ollama isn't running. Start it with: ollama serve"
UNEXPECTED = "Ollama answered with something unexpected (check OLLAMA_URL in .env)."
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


@pytest.mark.parametrize(
    "error, expected",
    [
        (ValueError("not json"), UNEXPECTED),
        (KeyError("models"), UNEXPECTED),
        (TypeError("bad"), UNEXPECTED),
        (httpx.InvalidURL("bad"), NOT_RUNNING),
    ],
)
def test_preflight_survives_malformed_tags(error, expected):
    def odd():
        raise error

    assert expected in preflight(make(), odd)


def test_main_adds_chroma_warning(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from eduagent import launcher

    seen = SimpleNamespace(warnings=[])
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "preflight", lambda *a: [])
    monkeypatch.setattr(launcher, "build_services", lambda s: seen)
    monkeypatch.setattr(launcher, "configure_model_dirs", lambda s: None)
    monkeypatch.setattr(launcher, "apply_theme", lambda: None)
    monkeypatch.setattr(launcher, "register_pages", lambda s: None)
    monkeypatch.setattr(launcher.ui, "run", lambda **kw: None)
    stops = []
    monkeypatch.setattr(launcher.app, "on_shutdown", stops.append)

    fake = None

    class FakeChroma:
        def __init__(self, settings):
            nonlocal fake
            fake = self

        def start(self):
            return "Chroma broke"

        def stop(self):
            pass

    monkeypatch.setattr(launcher, "ChromaServer", FakeChroma)
    launcher.main()
    assert "Chroma broke" in seen.warnings
    assert stops == [fake.stop]


def test_main_stops_chroma_if_startup_fails(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from eduagent import launcher

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "preflight", lambda *a: [])
    monkeypatch.setattr(launcher, "configure_model_dirs", lambda s: None)
    monkeypatch.setattr(launcher.app, "on_shutdown", lambda f: None)

    def boom(settings):
        raise RuntimeError("db broke")

    monkeypatch.setattr(launcher, "build_services", boom)
    calls = []

    class FakeChroma:
        def __init__(self, settings):
            pass

        def start(self):
            return None

        def stop(self):
            calls.append("stop")

    monkeypatch.setattr(launcher, "ChromaServer", FakeChroma)
    with pytest.raises(RuntimeError, match="db broke"):
        launcher.main()
    assert calls == ["stop"]
