"""Decides which model (Gemini or local Qwen) handles each kind of job."""

import logging
from dataclasses import dataclass
from typing import Literal

from eduagent.config import Settings
from eduagent.models.quota import QuotaTracker

log = logging.getLogger(__name__)

WHAT_IT_DOES = (
    "Chooses between Gemini and the local Qwen model for each job, based on the "
    "routing setting and how much Gemini quota is left."
)

JobKind = Literal["chat", "heavy", "light"]


@dataclass(frozen=True)
class ModelChoice:
    provider: Literal["gemini", "qwen"]
    model_id: str
    reason: str


class ModelRouter:
    def __init__(self, settings: Settings, quota: QuotaTracker):
        self._settings = settings
        self._quota = quota

    @property
    def qwen_model_id(self) -> str:
        return self._settings.qwen_model

    def _qwen(self, reason: str) -> ModelChoice:
        return ModelChoice("qwen", self._settings.qwen_model, reason)

    def _gemini_or_qwen(self, reason: str) -> ModelChoice:
        if self._quota.is_available():
            return ModelChoice("gemini", self._settings.gemini_model, reason)
        return self._qwen("gemini quota exhausted")

    def choose(self, job: JobKind) -> ModelChoice:
        mode = self._settings.effective_routing_mode
        if mode == "all_qwen":
            choice = self._qwen("mode")
        elif mode == "all_gemini":
            choice = self._gemini_or_qwen("mode")
        elif job == "light":
            choice = self._qwen("job split")
        else:
            choice = self._gemini_or_qwen("job split")
        log.info("route job=%s -> %s (%s)", job, choice.model_id, choice.reason)
        return choice
