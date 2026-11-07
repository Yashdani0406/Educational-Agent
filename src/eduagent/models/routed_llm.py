"""The one place every LLM call passes through: routing, quota, fallback, tracing."""

import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

import litellm
from google.adk.models import BaseLlm, Gemini, LiteLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from google.genai.errors import ClientError

from eduagent.config import Settings
from eduagent.models.quota import QuotaTracker
from eduagent.models.router import JobKind, ModelRouter
from eduagent.tracing.tracer import Tracer, current_trace_id

log = logging.getLogger(__name__)

WHAT_IT_DOES = (
    "Sends every model request to Gemini or the local Qwen model as the router "
    "decides, switches to Qwen if Gemini fails, and records exactly what the model "
    "was sent and replied."
)

TRACE_FIELD_CAP = 20_000


def is_rate_limit(exc: BaseException) -> bool:
    if isinstance(exc, ClientError) and exc.code == 429:
        return True
    if isinstance(exc, litellm.RateLimitError):
        return True
    return "RESOURCE_EXHAUSTED" in str(exc)


def _cap(value: Any) -> Any:
    """Cut every string longer than TRACE_FIELD_CAP, recursively."""
    if isinstance(value, str):
        extra = len(value) - TRACE_FIELD_CAP
        return value if extra <= 0 else f"{value[:TRACE_FIELD_CAP]}… [truncated {extra} chars]"
    if isinstance(value, dict):
        return {k: _cap(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_cap(v) for v in value]
    return value


def _render_part(part: types.Part) -> dict:
    if part.function_call:
        fc = part.function_call
        return {"function_call": {"name": fc.name, "args": fc.args}}
    if part.function_response:
        fr = part.function_response
        return {"function_response": {"name": fr.name, "response": fr.response}}
    return {"text": part.text}


def _system_text(instruction: Any) -> str | None:
    if instruction is None:
        return None
    if isinstance(instruction, str):
        return instruction
    parts = getattr(instruction, "parts", None)
    if parts is None:
        return str(instruction)
    return "\n".join(p.text for p in parts if p.text)


def summarize_request(llm_request: LlmRequest) -> dict:
    config = llm_request.config
    tools: list[str] = []
    for tool in (config.tools if config else None) or []:
        tools += [d.name for d in tool.function_declarations or [] if d.name]
    return {
        "system_instruction": _system_text(config.system_instruction) if config else None,
        "messages": [
            {"role": c.role, "parts": [_render_part(p) for p in c.parts or []]}
            for c in llm_request.contents
        ],
        "tools": tools,
    }


def summarize_response(responses: list[LlmResponse]) -> dict:
    texts: list[str] = []
    calls: list[dict] = []
    finish = None
    for r in responses:
        for p in (r.content.parts if r.content and r.content.parts else []):
            if p.function_call:
                calls.append({"name": p.function_call.name, "args": p.function_call.args})
            elif p.text and not p.thought:
                texts.append(p.text)
        if r.finish_reason is not None:
            finish = getattr(r.finish_reason, "name", str(r.finish_reason))
    return {
        "text": "".join(texts) if texts else None,
        "function_calls": calls,
        "finish_reason": finish,
    }


class RoutedLlm(BaseLlm):
    """Wraps a Gemini and a Qwen model; agents see one transparent model."""

    job: JobKind
    router: ModelRouter
    quota: QuotaTracker
    tracer: Tracer
    gemini: BaseLlm
    qwen: BaseLlm

    async def _call(
        self, llm: BaseLlm, label: str, llm_request: LlmRequest, stream: bool
    ) -> list[LlmResponse]:
        # Collected before yielding so any error arrives before output (chat is non-streaming in v1).
        # The delegate's own id (e.g. "ollama_chat/qwen3:4b") must reach it; ADK's LiteLlm
        # prefers llm_request.model over its own. `label` is only for logs and the trace.
        request = llm_request.model_copy(update={"model": llm.model})
        started = time.perf_counter()
        responses = [r async for r in llm.generate_content_async(request, stream=stream)]
        ms = int((time.perf_counter() - started) * 1000)
        usage = next((r.usage_metadata for r in reversed(responses) if r.usage_metadata), None)
        tokens_in = usage.prompt_token_count if usage else None
        tokens_out = usage.candidates_token_count if usage else None
        log.info("model=%s tokens=%s/%s ms=%d", label, tokens_in, tokens_out, ms)
        trace_id = current_trace_id.get()
        if trace_id:
            self.tracer.add_step(
                trace_id, "model_call", "model_router",
                inputs=_cap(summarize_request(request)),
                outputs=_cap(summarize_response(responses)),
                model=label, tokens_in=tokens_in, tokens_out=tokens_out, duration_ms=ms,
            )
        return responses

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        choice = self.router.choose(self.job)
        log.debug("model request: %s", summarize_request(llm_request))
        if choice.provider == "gemini":
            self.quota.record_request()
            try:
                responses = await self._call(self.gemini, choice.model_id, llm_request, stream)
            except Exception as e:
                if is_rate_limit(e):
                    self.quota.mark_exhausted()
                log.warning("gemini failed (%s), falling back to qwen", type(e).__name__)
                trace_id = current_trace_id.get()
                if trace_id:
                    self.tracer.add_step(
                        trace_id, "fallback", "model_router",
                        inputs=_cap(summarize_request(llm_request)),
                        outputs={"error": type(e).__name__},
                        model=choice.model_id,
                    )
                label = self.qwen.model.removeprefix("ollama_chat/")
                responses = await self._call(self.qwen, label, llm_request, stream)
        else:
            responses = await self._call(self.qwen, choice.model_id, llm_request, stream)
        for response in responses:
            yield response


def build_routed_llm(
    job: JobKind, settings: Settings, router: ModelRouter, quota: QuotaTracker, tracer: Tracer
) -> RoutedLlm:
    key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
    # ADK's Gemini forwards client_kwargs to google.genai.Client, so the key is passed explicitly.
    gemini = Gemini(
        model=settings.gemini_model,
        client_kwargs={"api_key": key} if key.strip() else None,
    )
    qwen = LiteLlm(
        model=f"ollama_chat/{settings.qwen_model}",
        api_base=settings.ollama_url,
        think=False,
    )
    return RoutedLlm(
        model=f"routed/{job}", job=job, router=router, quota=quota, tracer=tracer,
        gemini=gemini, qwen=qwen,
    )
