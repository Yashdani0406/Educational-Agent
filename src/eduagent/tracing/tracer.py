"""Records every step of every request into SQLite, with secrets redacted."""

import json
import logging
import uuid
from collections.abc import Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from eduagent.db.database import Database
from eduagent.tracing.redact import redact, scrub

log = logging.getLogger(__name__)

WHAT_IT_DOES = (
    "Writes each step of a request (route choice, model call, tool call, fallback, "
    "answer) to the local database so you can see how an answer was produced. "
    "API keys are removed before anything is saved."
)

StepType = Literal[
    "route", "agent", "tool_call", "tool_result", "model_call", "fallback", "answer", "error",
    "reroute",
]

current_trace_id: ContextVar[str | None] = ContextVar("current_trace_id", default=None)


@dataclass
class TraceStep:
    trace_id: str
    seq: int
    step_type: StepType
    component: str
    inputs: Any = None
    outputs: Any = None
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    duration_ms: int | None = None


@dataclass
class Trace:
    id: str
    kind: Literal["chat", "upload"]
    label: str
    status: str
    steps: list[TraceStep] = field(default_factory=list)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Tracer:
    def __init__(self, db: Database, secrets: Sequence[str] = ()):
        self._db = db
        self._secrets = [s for s in secrets if s and s.strip()]
        self._subscribers: list[Callable[[TraceStep], None]] = []

    def _dump(self, value: Any) -> str | None:
        if value is None:
            return None
        redacted = redact(value, self._secrets)
        text = scrub(json.dumps(redacted, default=str), self._secrets)
        try:
            json.loads(text)
            return text
        except ValueError:
            pass
        # The text scrub corrupted the JSON: redact the decoded strings instead.
        try:
            decoded = json.loads(json.dumps(redacted, default=str))
            return json.dumps(redact(decoded, self._secrets))
        except (ValueError, TypeError):
            return json.dumps("[redacted: unserializable]")

    def start_trace(self, kind: Literal["chat", "upload"], label: str) -> str:
        trace_id = uuid.uuid4().hex
        with self._db.connect() as conn:
            conn.execute(
                "INSERT INTO traces(id, kind, label, started_at, status) "
                "VALUES (?, ?, ?, ?, 'running')",
                (trace_id, kind, scrub(label, self._secrets), _now()),
            )
        return trace_id

    def add_step(
        self,
        trace_id: str,
        step_type: StepType,
        component: str,
        *,
        inputs: Any = None,
        outputs: Any = None,
        model: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        duration_ms: int | None = None,
    ) -> TraceStep:
        in_json = self._dump(inputs)
        out_json = self._dump(outputs)
        step_type = scrub(step_type, self._secrets)  # type: ignore[assignment]
        component = scrub(component, self._secrets)
        model = scrub(model, self._secrets) if model is not None else None
        with self._db.connect() as conn:
            seq = conn.execute(
                "INSERT INTO trace_steps(trace_id, seq, step_type, component, input_json, "
                "output_json, model, tokens_in, tokens_out, duration_ms, created_at) "
                "SELECT ?, COALESCE(MAX(seq), 0) + 1, ?, ?, ?, ?, ?, ?, ?, ?, ? "
                "FROM trace_steps WHERE trace_id = ? RETURNING seq",
                (trace_id, step_type, component, in_json, out_json, model,
                 tokens_in, tokens_out, duration_ms, _now(), trace_id),
            ).fetchone()[0]
        step = TraceStep(
            trace_id, seq, step_type, component,
            json.loads(in_json) if in_json is not None else None,
            json.loads(out_json) if out_json is not None else None,
            model, tokens_in, tokens_out, duration_ms,
        )
        for cb in list(self._subscribers):
            try:
                cb(step)
            except Exception:
                log.exception("Trace subscriber failed")
        return step

    def end_trace(self, trace_id: str, status: Literal["ok", "error"]) -> None:
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE traces SET status = ?, ended_at = ? WHERE id = ?",
                (status, _now(), trace_id),
            )

    @staticmethod
    def _step(row) -> TraceStep:
        return TraceStep(
            row["trace_id"], row["seq"], row["step_type"], row["component"],
            json.loads(row["input_json"]) if row["input_json"] is not None else None,
            json.loads(row["output_json"]) if row["output_json"] is not None else None,
            row["model"], row["tokens_in"], row["tokens_out"], row["duration_ms"],
        )

    @staticmethod
    def _trace(row) -> Trace:
        return Trace(row["id"], row["kind"], row["label"], row["status"])

    def get_trace(self, trace_id: str) -> Trace:
        with self._db.connect() as conn:
            row = conn.execute("SELECT * FROM traces WHERE id = ?", (trace_id,)).fetchone()
            if row is None:
                raise KeyError(trace_id)
            trace = self._trace(row)
            trace.steps = [
                self._step(r)
                for r in conn.execute(
                    "SELECT * FROM trace_steps WHERE trace_id = ? ORDER BY seq", (trace_id,)
                )
            ]
        return trace

    def list_traces(self, kind: str | None = None, limit: int = 50) -> list[Trace]:
        sql = "SELECT * FROM traces"
        params: list[Any] = []
        if kind is not None:
            sql += " WHERE kind = ?"
            params.append(kind)
        sql += " ORDER BY started_at DESC, rowid DESC LIMIT ?"
        params.append(limit)
        with self._db.connect() as conn:
            return [self._trace(r) for r in conn.execute(sql, params)]

    def subscribe(self, callback: Callable[[TraceStep], None]) -> Callable[[], None]:
        self._subscribers.append(callback)

        def unsubscribe() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return unsubscribe
