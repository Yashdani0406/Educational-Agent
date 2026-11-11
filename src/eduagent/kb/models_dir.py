"""Keeps every downloaded model under the models folder instead of the user cache."""

import os

from eduagent.config import Settings

WHAT_IT_DOES = "Points the model libraries at the app's own models folder so nothing is downloaded to the user's cache."


def configure_model_dirs(settings: Settings) -> None:
    """Create the models folder and point model libraries at it (an existing setting wins)."""
    models = settings.models_dir
    models.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(models / "hf"))
    os.environ.setdefault("FASTEMBED_CACHE_PATH", str(models / "fastembed"))
    os.environ.setdefault("DOCLING_ARTIFACTS_PATH", str(models / "docling"))
