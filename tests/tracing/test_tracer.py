import json

import pytest

from eduagent.db.database import Database
from eduagent.tracing import Tracer, current_trace_id, redact


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "study.db")
    d.migrate()
    return d


def test_steps_ordered(db):
    t = Tracer(db)
    tid = t.start_trace("chat", "hi")
    for s in ("route", "model_call", "answer"):
        t.add_step(tid, s, "c")
    tr = t.get_trace(tid)
    assert [s.seq for s in tr.steps] == [1, 2, 3]
    assert tr.status == "running"


def test_secret_values_redacted_in_steps(db):
    t = Tracer(db, secrets=["AIzaSECRET"])
    tid = t.start_trace("chat", "x")
    inputs = {
        "q": "x AIzaSECRET y",
        "api_key": "abc",
        "nested": [{"Authorization": "Bearer z"}],
    }
    step = t.add_step(tid, "tool_call", "c", inputs=inputs, outputs="AIzaSECRET")
    expected = {
        "q": "x [redacted] y",
        "api_key": "[redacted]",
        "nested": [{"Authorization": "[redacted]"}],
    }
    assert step.inputs == expected
    assert step.outputs == "[redacted]"
    assert t.get_trace(tid).steps[0].inputs == expected
    with db.connect() as conn:
        text = " ".join(
            str(v) for r in conn.execute("SELECT * FROM trace_steps") for v in tuple(r)
        )
    assert "AIzaSECRET" not in text
    assert inputs["q"] == "x AIzaSECRET y"  # original untouched


def test_key_name_matching_is_by_full_name():
    data = {"max_tokens": 5, "prompt_token_count": 7, "keyword": "x"}
    assert redact(data, []) == data
    out = redact(
        {"api_key": 1, "Authorization": 2, "token": 3, "x-api-key": 4, "apiKey": 5,
         "access_token": 6, "client_secret": 7, "PASSWORD": 8},
        [],
    )
    assert out["api_key"] == out["Authorization"] == out["token"] == "[redacted]"
    assert out["x-api-key"] == out["access_token"] == out["client_secret"] == "[redacted]"
    assert out["PASSWORD"] == "[redacted]"


def test_empty_secrets_ignored(db):
    assert redact("hello", [""]) == "hello"
    assert redact("hello", ["  "]) == "hello"
    t = Tracer(db, secrets=[""])
    tid = t.start_trace("chat", "x")
    s = t.add_step(tid, "route", "c", inputs={"q": "hello"})
    assert s.inputs == {"q": "hello"}


def test_redact_tuples_and_depth():
    out = redact(("a S b", {"k": ["S"]}), ["S"])
    assert out == ("a [redacted] b", {"k": ["[redacted]"]})


def test_subscribers_notified_and_unsubscribe(db):
    t = Tracer(db)
    tid = t.start_trace("chat", "x")
    got = []
    unsub = t.subscribe(got.append)
    t.add_step(tid, "route", "c")
    unsub()
    t.add_step(tid, "answer", "c")
    assert [s.seq for s in got] == [1]


def test_failing_subscriber_does_not_break(db):
    t = Tracer(db)
    tid = t.start_trace("chat", "x")
    got = []

    def boom(step):
        raise RuntimeError("bad")

    t.subscribe(boom)
    t.subscribe(got.append)
    step = t.add_step(tid, "route", "c")
    assert got == [step]
    assert len(t.get_trace(tid).steps) == 1


def test_end_trace_sets_status(db):
    t = Tracer(db)
    tid = t.start_trace("chat", "x")
    t.end_trace(tid, "ok")
    tr = t.get_trace(tid)
    assert tr.status == "ok"
    with db.connect() as conn:
        assert conn.execute("SELECT ended_at FROM traces").fetchone()[0] is not None


def test_get_trace_unknown(db):
    with pytest.raises(KeyError):
        Tracer(db).get_trace("nope")


def test_list_traces_filters_kind(db):
    t = Tracer(db)
    a = t.start_trace("chat", "a")
    b = t.start_trace("upload", "b")
    c = t.start_trace("chat", "c")
    t.add_step(a, "route", "c")
    assert [x.id for x in t.list_traces()] == [c, b, a]
    assert [x.id for x in t.list_traces("chat")] == [c, a]
    assert all(x.steps == [] for x in t.list_traces())
    assert len(t.list_traces(limit=1)) == 1


def test_non_json_inputs_stringified(db):
    class Thing:
        def __str__(self):
            return "thing with SECRETKEY inside"

    t = Tracer(db, secrets=["SECRETKEY"])
    tid = t.start_trace("chat", "x")
    step = t.add_step(tid, "tool_call", "c", inputs={"o": Thing()}, outputs={1, 2})
    assert step.inputs == {"o": "thing with [redacted] inside"}
    with db.connect() as conn:
        raw = conn.execute("SELECT input_json FROM trace_steps").fetchone()[0]
    assert "SECRETKEY" not in raw
    assert json.loads(raw) == step.inputs


def test_current_trace_id_default():
    assert current_trace_id.get() is None
