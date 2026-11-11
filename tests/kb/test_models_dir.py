import os

from eduagent.config import Settings
from eduagent.kb.models_dir import configure_model_dirs


def test_overrides_existing_cache_variables(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HOME", "C:/Users/someone/.cache/huggingface")
    monkeypatch.setenv("FASTEMBED_CACHE_PATH", "x")  # registers the restore for the variables we set
    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", "x")
    settings = Settings(_env_file=None, models_dir=tmp_path / "models")
    configure_model_dirs(settings)
    assert os.environ["HF_HOME"] == str(tmp_path / "models" / "hf")
    assert os.environ["FASTEMBED_CACHE_PATH"] == str(tmp_path / "models" / "fastembed")
    assert os.environ["DOCLING_ARTIFACTS_PATH"] == str(tmp_path / "models" / "docling")
    assert (tmp_path / "models").is_dir()
