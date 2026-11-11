"""Keeps every downloaded model under the models folder instead of the user cache."""

import logging
import os

from eduagent.config import Settings

log = logging.getLogger(__name__)

WHAT_IT_DOES = "Points the model libraries at the app's own models folder so nothing is downloaded to the user's cache."


def configure_model_dirs(settings: Settings) -> None:
    """Create the models folder and point model libraries at it, replacing any value already set."""
    models = settings.models_dir
    models.mkdir(parents=True, exist_ok=True)
    for name, folder in (("HF_HOME", "hf"), ("FASTEMBED_CACHE_PATH", "fastembed"), ("DOCLING_ARTIFACTS_PATH", "docling")):
        target = str(models / folder)
        old = os.environ.get(name)
        if old and old != target:
            log.info("Overriding %s (%s) so models stay in %s", name, old, models)
        os.environ[name] = target
