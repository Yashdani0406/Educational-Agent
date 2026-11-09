import logging
from datetime import UTC, datetime

import litellm
import pytest
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from google.genai.errors import ClientError
from pydantic import SecretStr

from eduagent.config import Settings
from eduagent.db.database import Database
from eduagent.models.quota import QuotaTracker
from eduagent.models.router import ModelRouter
from eduagent.models.routed_llm import (
    TRACE_FIELD_CAP,
    RoutedLlm,
    is_daily_quota_exhausted,
    is_rate_limit,
    summarize_request,
)
from eduagent.tracing.tracer import Tracer, current_trace_id

LIMIT = 10


class FakeLlm(BaseLlm):
    reply: str = "ok"
    error: BaseException | None = None
    function_call: types.FunctionCall | None = None
    seen_models: list[str] = []

    async def generate_content_async(self, llm_request, stream=False):
        self.seen_models.append(llm_request.model)
        if self.error is not None:
            raise self.error
        if self.function_call is not None:
            parts = [types.Part(function_call=self.function_call)]
        else:
            parts = [types.Part(text=self.reply)]
        yield LlmResponse(
            content=types.Content(role="model", parts=parts),
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=7, candidates_token_count=3
            ),
            finish_reason=types.FinishReason.STOP,
        )


def rate_limit_error():
    return ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})


def quota_error(quota_id):
    return ClientError(429, {"error": {
        "code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED",
        "details": [{
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [{"quotaId": quota_id}],
        }],
    }})


PER_DAY = "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
PER_MINUTE = "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"


class Env:
    def __init__(self, tmp_path, mode="split", gemini=None, qwen=None):
        self.db = Database(tmp_path / "study.db")
        self.db.migrate()
        self.quota = QuotaTracker(self.db, LIMIT, lambda: datetime(2026, 11, 7, 12, tzinfo=UTC))
        settings = Settings(
            _env_file=None, gemini_api_key=SecretStr("k"), routing_mode=mode,
            gemini_model="gem", qwen_model="qw", data_dir=tmp_path,
        )
        self.tracer = Tracer(self.db)
        self.gemini = gemini or FakeLlm(model="gem", reply="from gemini", seen_models=[])
        self.qwen = qwen or FakeLlm(model="ollama_chat/qw", reply="from qwen", seen_models=[])
        self.llm = RoutedLlm(
            model="routed", job="chat", router=ModelRouter(settings, self.quota),
            quota=self.quota, tracer=self.tracer, gemini=self.gemini, qwen=self.qwen,
        )
        self.trace_id = self.tracer.start_trace("chat", "t")

    def steps(self):
        return self.tracer.get_trace(self.trace_id).steps


def request(text="what is overfitting?", **kw):
    return LlmRequest(
        model="x",
        contents=[types.Content(role="user", parts=[types.Part(text=text)])],
        **kw,
    )


async def run(env, req=None, *, traced=True):
    token = current_trace_id.set(env.trace_id if traced else None)
    try:
        return [r async for r in env.llm.generate_content_async(req or request())]
    finally:
        current_trace_id.reset(token)


def text_of(responses):
    return responses[0].content.parts[0].text


async def test_gemini_success_counts_quota(tmp_path, caplog):
    env = Env(tmp_path)
    with caplog.at_level(logging.INFO):
        out = await run(env)
    assert text_of(out) == "from gemini"
    assert env.quota.remaining() == LIMIT - 1
    step = env.steps()[0]
    assert (step.step_type, step.model, step.tokens_in, step.tokens_out) == ("model_call", "gem", 7, 3)
    assert env.gemini.seen_models == ["gem"]
    assert any("model=gem tokens=7/3 ms=" in r.getMessage() for r in caplog.records)


async def test_rate_limit_falls_back_and_exhausts(tmp_path, caplog):
    env = Env(tmp_path, gemini=FakeLlm(model="gem", error=quota_error(PER_DAY)))
    with caplog.at_level(logging.INFO):
        out = await run(env)
    assert text_of(out) == "from qwen"
    assert env.quota.is_available() is False
    assert [s.step_type for s in env.steps()] == ["fallback", "model_call"]
    assert env.steps()[0].component == "model_router"
    assert env.steps()[0].outputs["error"] == "ClientError"
    assert env.qwen.seen_models == ["ollama_chat/qw"]
    assert any(
        r.levelno == logging.WARNING
        and r.getMessage().startswith("gemini failed (ClientError: ")
        and r.getMessage().endswith("), falling back to qwen")
        for r in caplog.records
    )


@pytest.mark.parametrize("error", [quota_error(PER_MINUTE), rate_limit_error()])
async def test_per_minute_429_falls_back_without_exhausting(tmp_path, error):
    env = Env(tmp_path, gemini=FakeLlm(model="gem", error=error))
    out = await run(env)
    assert text_of(out) == "from qwen"
    assert env.quota.is_available() is True


def test_is_daily_quota_exhausted():
    assert is_daily_quota_exhausted(quota_error(PER_DAY))
    assert not is_daily_quota_exhausted(quota_error(PER_MINUTE))
    assert not is_daily_quota_exhausted(rate_limit_error())
    assert not is_daily_quota_exhausted(ConnectionError("down"))
    assert is_daily_quota_exhausted(
        ClientError(429, {"error": {"message": "exceeded GenerateRequestsPerDay quota"}})
    )
    assert is_daily_quota_exhausted(
        litellm.RateLimitError("GenerateRequestsPerDayPerProjectPerModel", "gemini", "m")
    )
    assert not is_daily_quota_exhausted(litellm.RateLimitError("slow down", "ollama", "qw"))


async def test_non_rate_limit_error_falls_back_without_exhausting(tmp_path):
    env = Env(tmp_path, gemini=FakeLlm(model="gem", error=ConnectionError("down")))
    out = await run(env)
    assert text_of(out) == "from qwen"
    assert env.quota.is_available() is True


async def test_qwen_error_propagates(tmp_path):
    env = Env(tmp_path, mode="all_qwen", qwen=FakeLlm(model="qw", error=RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        await run(env)


async def test_no_trace_no_steps_but_works(tmp_path):
    env = Env(tmp_path)
    assert text_of(await run(env, traced=False)) == "from gemini"
    assert env.steps() == []


async def test_model_call_records_request_and_response(tmp_path):
    env = Env(tmp_path)
    req = LlmRequest(
        model="x",
        contents=[
            types.Content(role="user", parts=[types.Part(text="what is overfitting?")]),
            types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(
                name="search_material", response={"chunks": ["c1"]}))]),
        ],
        config=types.GenerateContentConfig(
            system_instruction="Be brief",
            tools=[types.Tool(function_declarations=[types.FunctionDeclaration(
                name="search_material", description="d")])],
        ),
    )
    await run(env, req)
    step = env.steps()[0]
    assert step.inputs["system_instruction"] == "Be brief"
    assert step.inputs["tools"] == ["search_material"]
    msgs = step.inputs["messages"]
    assert {"text": "what is overfitting?"} in msgs[0]["parts"]
    assert {"function_response": {"name": "search_material", "response": {"chunks": ["c1"]}}} in msgs[1]["parts"]
    assert step.outputs["text"] == "from gemini"
    assert step.outputs["finish_reason"] is not None


async def test_model_call_records_function_call_output(tmp_path):
    fake = FakeLlm(model="gem", function_call=types.FunctionCall(name="search_material", args={"query": "x"}))
    env = Env(tmp_path, gemini=fake)
    await run(env)
    assert env.steps()[0].outputs["function_calls"] == [
        {"name": "search_material", "args": {"query": "x"}}
    ]


async def test_trace_fields_truncated(tmp_path):
    env = Env(tmp_path)
    await run(env, request("a" * 50_000))
    text = env.steps()[0].inputs["messages"][0]["parts"][0]["text"]
    assert text.endswith("[truncated 30000 chars]")
    assert text.startswith("a" * TRACE_FIELD_CAP)
    assert len(text) <= TRACE_FIELD_CAP + len("… [truncated 30000 chars]")


async def test_fallback_step_includes_request(tmp_path):
    env = Env(tmp_path, gemini=FakeLlm(model="gem", error=rate_limit_error()))
    await run(env)
    fb = env.steps()[0]
    assert fb.step_type == "fallback"
    assert fb.inputs["messages"][0]["parts"] == [{"text": "what is overfitting?"}]


def test_is_rate_limit():
    assert is_rate_limit(rate_limit_error())
    assert is_rate_limit(RuntimeError("RESOURCE_EXHAUSTED: x"))
    assert not is_rate_limit(ConnectionError("down"))
    assert is_rate_limit(litellm.RateLimitError("slow", "ollama", "qw"))


def test_summarize_request_without_config():
    out = summarize_request(LlmRequest(model="x", contents=[]))
    assert out == {"system_instruction": None, "messages": [], "tools": []}


def test_build_routed_llm_wires_real_models(tmp_path):
    from eduagent.models.routed_llm import build_routed_llm

    env = Env(tmp_path)
    settings = Settings(_env_file=None, gemini_api_key=SecretStr("k"), data_dir=tmp_path)
    llm = build_routed_llm("light", settings, env.llm.router, env.quota, env.tracer)
    assert llm.gemini.model == settings.gemini_model
    assert llm.qwen.model == f"ollama_chat/{settings.qwen_model}"


async def test_qwen_direct_gets_ollama_chat_model(tmp_path):
    env = Env(tmp_path, mode="all_qwen")
    await run(env, traced=False)
    assert env.qwen.seen_models == ["ollama_chat/qw"]
    assert env.gemini.seen_models == []


async def test_qwen_think_is_stripped_but_gemini_is_untouched(tmp_path):
    env = Env(tmp_path, mode="all_qwen", qwen=FakeLlm(model="ollama_chat/qw", reply="<think>x</think> hello"))
    assert text_of(await run(env)) == "hello"
    assert env.steps()[0].outputs["text"] == "hello"
    (tmp_path / "g").mkdir()
    env = Env(tmp_path / "g", gemini=FakeLlm(model="gem", reply="<think>x</think> hi"))
    assert text_of(await run(env, traced=False)) == "<think>x</think> hi"


@pytest.mark.parametrize("key", ["k", None])
def test_build_routed_llm_gives_gemini_a_timeout(tmp_path, key):
    from eduagent.models.routed_llm import GEMINI_TIMEOUT_S, build_routed_llm

    env = Env(tmp_path)
    settings = Settings(
        _env_file=None, gemini_api_key=SecretStr(key) if key else None, data_dir=tmp_path
    )
    llm = build_routed_llm("light", settings, env.llm.router, env.quota, env.tracer)
    assert GEMINI_TIMEOUT_S == 30
    http_options = llm.gemini.client_kwargs["http_options"]
    assert http_options.timeout == 30_000  # HttpOptions.timeout is in milliseconds
    if key:  # building a real client needs a key; proves ADK keeps our timeout
        assert llm.gemini.api_client._api_client._http_options.timeout == 30_000


async def test_gemini_timeout_falls_back_with_message(tmp_path, caplog):
    err = TimeoutError("read timed out after 30s")
    env = Env(tmp_path, gemini=FakeLlm(model="gem", error=err))
    with caplog.at_level(logging.WARNING):
        out = await run(env)
    assert text_of(out) == "from qwen"
    assert env.quota.is_available() is True
    assert env.steps()[0].outputs == {
        "error": "TimeoutError", "message": "read timed out after 30s",
    }
    assert any(
        r.getMessage() == "gemini failed (TimeoutError: read timed out after 30s), falling back to qwen"
        for r in caplog.records
    )


async def test_fallback_message_truncated_to_200_chars(tmp_path, caplog):
    env = Env(tmp_path, gemini=FakeLlm(model="gem", error=RuntimeError("x" * 500)))
    with caplog.at_level(logging.WARNING):
        await run(env)
    assert env.steps()[0].outputs["message"] == "x" * 200
    assert any("x" * 200 + ")" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("use_gpu, expected", [(False, {"num_gpu": 0}), (True, {})])
def test_build_routed_llm_qwen_cpu_option(tmp_path, use_gpu, expected):
    from eduagent.models.routed_llm import build_routed_llm

    env = Env(tmp_path)
    settings = Settings(
        _env_file=None, gemini_api_key=SecretStr("k"), data_dir=tmp_path, ollama_use_gpu=use_gpu
    )
    llm = build_routed_llm("light", settings, env.llm.router, env.quota, env.tracer)
    extra = {k: v for k, v in llm.qwen._additional_args.items() if k == "num_gpu"}
    assert extra == expected


def test_gemini_key_never_appears_in_reprs(tmp_path):
    from eduagent.agents.tutor import build_tutor
    from eduagent.models.routed_llm import build_routed_llm

    env = Env(tmp_path)
    key = "AIzaFAKEKEY123"
    settings = Settings(_env_file=None, gemini_api_key=SecretStr(key), data_dir=tmp_path)
    llm = build_routed_llm("light", settings, env.llm.router, env.quota, env.tracer)
    for obj in (llm, llm.gemini, build_tutor(llm)):
        assert key not in repr(obj)
