# Educational Agent — Plan 1: Foundation (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **On approval:** copy this file to `docs/superpowers/plans/2026-11-06-plan-1-foundation.md` (and the roadmap below to `docs/superpowers/plans/2026-11-06-roadmap.md`) as part of Task 1, so the plan lives in the repo.

**Goal:** A runnable local app (one command) with the repo scaffold, SQLite data layer, Gemini/Qwen model routing with quota tracking and fallback, step tracing, an ADK coordinator with code-based routing, and the NiceGUI chat shell — the base every later agent plugs into.

**Architecture:** One Python package `eduagent` (src layout, uv, Python 3.12). Plain-code services (settings, db, quota, router, tracer) are wired into a `Services` bundle that both the ADK agents and the NiceGUI UI consume. A custom ADK `CoordinatorAgent` decides the target agent in plain code (`@mention` → code heuristic → local Qwen classifier) and delegates to sub-agents; every LLM call goes through `RoutedLlm`, which picks Gemini or Qwen, counts quota, falls back on errors, and writes trace steps.

**Tech Stack:** Python 3.12 · uv · google-adk · litellm (Ollama) · NiceGUI · pydantic-settings · SQLite (WAL) · tzdata · stdlib `logging` · pytest + pytest-asyncio.

**Frontend ↔ backend communication:** there is no hand-written REST API. NiceGUI runs one FastAPI server on `127.0.0.1:8000`; the browser does an HTTP `GET` for each page route, then holds **one websocket** (socket.io). A click or Enter in the browser travels over the websocket to a **Python event handler on the server**; the handler calls `Services` methods directly (in-process function calls), updates UI elements, and NiceGUI pushes the changes back over the same websocket. Outbound network calls happen only from backend code:

| Browser action | Handler calls | Which then calls (network) |
|---|---|---|
| Open `/`, `/chat/{id}`, `/library`, … | page function in `ui/pages/*` → `threads.list`, `courses.course_map`, `chat.history` | SQLite `data/study.db`, `data/sessions.db` (files, no network) |
| Send message | `chat.send(thread_id, text)` → ADK `Runner.run_async` → `CoordinatorAgent` → `route()` | Ollama `POST :11434/api/chat` (Qwen classifier, via LiteLLM) |
| (same request, agent answers) | `RoutedLlm.generate_content_async` | Gemini API `HTTPS generativelanguage.googleapis.com` (google-genai) **or** Ollama `POST :11434/api/chat` on fallback |
| New course / new chat / rename | `courses.create_course`, `chat.new_thread`, `threads.rename` | SQLite |
| Top-bar refresh (timer, 30 s) | `quota.remaining()`, `router.choose("chat")` | SQLite |
| App start | `launcher.preflight` | Ollama `GET :11434/api/tags` |
| *Later plans* | ingestion, KB/study-records tools | Chroma HTTP (Plan 2), MCP servers over **stdio** child processes (Plans 2, 4, 6), Ollama `POST /api/embed` (Plan 2) |

**Spec:** `docs/superpowers/specs/2026-11-05-educational-agent-design.md`

---

## Roadmap (spec too large for one plan — one plan per subsystem, each shippable)

| Plan | Scope (spec §) | Depends on |
|---|---|---|
| **1. Foundation (this plan)** | Scaffold, settings, SQLite layer, quota, model router + fallback, tracing, coordinator, chat shell, launcher (§4.1, 4.5, 4.11, 4.12, 4.14 tracing, 4.15) | — |
| 2. Knowledge base & ingestion | Chroma server in launcher, parsers, structural chunker, topic tagging + confirmation, embeddings, resumable background job runner, upload queue, Library page, dedupe/replace/delete safety rules, KB MCP server, Fetch MCP for links, upload traces (`parse/chunk/tag/embed/store` steps), retrieval tracing — KB tools return a `trace` section (embed ms, search ms, k, filters, per-chunk score) saved into the `tool_result` step (§4.2–4.4, 4.10, 4.14) | 1 |
| 3. Notes maker | Generation cache, confirm before starting any costly job (so a misrouted message never silently spends Gemini quota), heavy-job queueing on quota exhaustion, split-and-combine notes, flashcard generation, versioned notes, Notes page, Playwright PDF export (§4.6 Notes, 4.9) | 2 |
| 4. Tutor | Study-records MCP, grounded answers with citations + labels, doubt logging, web/arXiv fallback MCPs, flashcard review + SRS, module quiz generation/validation/taking, targeted quizzes, weak-topic nudges (§4.6 Tutor, 4.7, 4.8) | 3 |
| 5. Analytics | Mastery formula, snapshots, confusion/misconception/forgetting signals, Progress page with charts, "How am I doing?" (§4.6 Analytics) | 4 |
| 6. Coding agent | Snippet/file/folder input, filesystem MCP (read-only), explain + review, KB search (§4.6 Coding) | 1 (any time) |
| 7. How it works page | ECharts system map, zoom levels, live path, replay, demo mode (§4.14) | all |

Each later plan is written (with this same skill) when its predecessor is merged, so it can argue from real code.

## Global Constraints

- Python **3.12** in a **uv**-managed project env; package name `eduagent`, src layout.
- Pure Python everywhere, including UI (NiceGUI). No custom JavaScript.
- Everything free; Gemini free tier + local Ollama only. No paid APIs.
- `data/`, `.env`, `.venv/`, `.superpowers/` are git-ignored. **Never commit course material, notes, scores, or keys.** `.env.example` is committed.
- UI served on `127.0.0.1` only, port **8000**. Ollama at `http://127.0.0.1:11434`.
- Models: Gemini Flash (setting `GEMINI_MODEL`), `qwen3:4b-instruct` via LiteLLM `ollama_chat/`, embeddings `nomic-embed-text`.
- Routing is a **single setting** `ROUTING_MODE` ∈ `split | all_gemini | all_qwen`.
- API keys never appear in traces, logs, or the UI.
- Every module logs via `log = logging.getLogger(__name__)` (never `print`). Levels: `DEBUG` = message/course text and model prompts; `INFO` = lifecycle and decisions (startup, route chosen, model chosen); `WARNING` = degraded but working (Gemini fallback, quota exhausted, Ollama down); `ERROR` = failed request, always with `log.exception` so the traceback is kept. Course text is logged only at `DEBUG`.
- Mention tags: `@tutor`, `@notes`, `@code`, `@progress`.
- UI: professional, calm, not flashy; one colour scheme (see Task 10).
- MIT licence; public repo.
- **Teaching (§4.15), every task:** after the commit, the executor stops and explains to the student *what* the code does, *why* it's needed, and *why this way, not another* (alternatives rejected), then appends the task's "Decisions to record" to `docs/decisions.md` (3–5 lines each) and commits that. This is the natural pause for questions.
- Every agent/component module exposes a `WHAT_IT_DOES: str` constant (1–2 plain-English sentences) — consumed later by the How-it-works page (§4.14).
- Commit after every task; push only after the student confirms.

## Review Focus

1. **Quota day boundary on an IST laptop** — Gemini free quota resets at midnight **Pacific**, not local midnight; Windows has no system tz database, so `zoneinfo` needs the `tzdata` package. Expect the counter to reset at 00:00 America/Los_Angeles. → test `test_resets_at_pacific_midnight` in Task 4.
2. **Gemini errors that aren't 429** (503, network drop) — spec §4.1 says Qwen is the fallback "when the quota runs out or Gemini errors". Expect the answer to arrive from Qwen, with only a 429 marking quota exhausted. → test `test_non_rate_limit_error_falls_back_without_exhausting` in Task 7.
3. **Ollama not running / models not pulled at launch** — expect the app to start anyway with a clear banner naming the fix (`ollama serve`, `ollama pull qwen3:4b-instruct`), not a stack trace. → tests in Task 11; classifier failure covered in Task 8 (`test_classifier_exception_defaults`).
4. **API key leaking into traces or log files** — a tool input, log message, or exception traceback containing the key must be written as `[redacted]`. → test `test_secret_values_redacted_in_steps` in Task 5 and `test_secret_scrubbed_from_message_and_traceback` in Task 6.
5. **Qwen3 `<think>` blocks** leaking into routing labels or replies — expect them stripped. → test `test_strip_think` in Task 7 and `test_classifier_label_with_think_block` in Task 8.

---

## File Structure

```
pyproject.toml  .gitignore  .env.example  LICENSE  README.md
docs/decisions.md  docs/manual-checks.md
src/eduagent/
  config.py                      Settings (pydantic-settings)
  logging_setup.py               configure_logging (file + console, trace id, redaction)
  db/database.py                 Database: connect (WAL, FK), migrate
  db/migrations/0001_init.sql    schema for this plan
  db/courses.py                  CoursesRepo (courses, modules, topics, course map)
  db/threads.py                  ThreadsRepo (saved chats)
  models/quota.py                QuotaTracker
  models/router.py               ModelRouter, ModelChoice
  models/routed_llm.py           RoutedLlm(BaseLlm), is_rate_limit
  models/qwen.py                 strip_think, qwen_complete
  tracing/tracer.py              Tracer, current_trace_id
  tracing/redact.py              redact
  agents/routing.py              parse_mention, route, RouteDecision
  agents/coordinator.py          CoordinatorAgent(BaseAgent)
  agents/placeholder.py          PlaceholderAgent(BaseAgent)
  agents/tutor.py                build_tutor (basic, no tools yet)
  agents/registry.py             build_coordinator
  chat/service.py                ChatService, AgentReply
  services.py                    Services bundle + build_services(settings)
  ui/theme.py  ui/frame.py  ui/pages/chat.py  ui/pages/placeholders.py  ui/app.py
  launcher.py                    preflight, main (entry point `eduagent`)
tests/  (mirrors src: tests/db/, tests/models/, tests/tracing/, tests/agents/, tests/chat/, tests/ui/, tests/test_launcher.py)
```

---

### Task 1: Repo scaffold and tooling

**Files:** Create `pyproject.toml`, `.gitignore`, `.env.example`, `LICENSE`, `README.md`, `docs/decisions.md`, `src/eduagent/__init__.py`, `tests/test_smoke.py`; copy plan + roadmap into `docs/superpowers/plans/`.

**Interfaces:** Produces: importable package `eduagent` with `__version__ = "0.1.0"`; `uv run pytest` works.

- [ ] **Step 1:** `git init`, `git remote add origin https://github.com/Yashdani0406/Educational-Agent.git` (remote is currently empty), `git branch -M main`.
- [ ] **Step 2:** `uv init --package --python 3.12 --name eduagent .`; then `uv add google-adk litellm nicegui pydantic-settings tzdata httpx` and `uv add --dev pytest pytest-asyncio`. In `pyproject.toml` set `[tool.pytest.ini_options] asyncio_mode = "auto"`, `testpaths = ["tests"]`, and script `eduagent = "eduagent.launcher:main"`. (Chroma, MCP, Playwright, parsers are added by the plans that use them.)
- [ ] **Step 3:** `.gitignore`: `data/`, `.env`, `.venv/`, `.superpowers/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`. `.env.example` lists every Settings field from Task 2 with its default and a comment (`GEMINI_API_KEY=` empty). `LICENSE`: MIT, 2026, Yash Dani. `README.md`: one-paragraph intent + "Setup: see below (filled in Task 11)". `docs/decisions.md`: heading + format line `## <date> — <decision>` / *Chose* / *Rejected* / *Why*.
- [ ] **Step 4: Write `tests/test_smoke.py`:** `def test_package_imports(): import eduagent; assert eduagent.__version__ == "0.1.0"`.
- [ ] **Step 5:** `uv run pytest -q` → `1 passed`.
- [ ] **Step 6:** Make sure Ollama is running (`ollama serve` or the tray app), then `ollama pull qwen3:4b-instruct` and `ollama pull nomic-embed-text`; `ollama list` shows both.
- [ ] **Step 7:** `git status` must not list `data/` or `.env`. Commit: `chore: scaffold uv project, licence, gitignore, plans`.

**Decisions to record:** uv over pip/venv; Python 3.12 over 3.14; src layout; dependencies added per plan, not up-front.

---

### Task 2: Settings

**Files:** Create `src/eduagent/config.py`, `tests/test_config.py`.

**Interfaces — Produces:**
```python
RoutingMode = Literal["split", "all_gemini", "all_qwen"]
class Settings(BaseSettings):  # env_file=".env", extra="ignore"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-flash-latest"   # confirm current free-tier Flash in AI Studio
    gemini_daily_limit: int = 250                # set from AI Studio's real figure
    qwen_model: str = "qwen3:4b-instruct"
    embed_model: str = "nomic-embed-text"
    ollama_url: str = "http://127.0.0.1:11434"
    routing_mode: RoutingMode = "split"
    data_dir: Path = Path("data")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    @property log_dir -> Path                          # data_dir / "logs"
    @property effective_routing_mode -> RoutingMode   # "all_qwen" when no API key
    @property db_path -> Path                          # data_dir / "study.db"
    @property sessions_db_url -> str                   # sqlite+aiosqlite URL to data_dir/"sessions.db"
```

- [ ] **Step 1: Write failing tests** (use `monkeypatch.setenv` and `Settings(_env_file=None)`):
  - `test_defaults`: `routing_mode == "split"`, `qwen_model == "qwen3:4b-instruct"`, `db_path == Path("data/study.db")`, `log_level == "INFO"`, `log_dir == Path("data/logs")`.
  - `test_no_key_forces_all_qwen`: no key, `ROUTING_MODE=split` → `effective_routing_mode == "all_qwen"`.
  - `test_key_keeps_mode`: key set, `ROUTING_MODE=all_gemini` → `"all_gemini"`.
  - `test_invalid_mode_rejected`: `ROUTING_MODE=fast` → `pydantic.ValidationError`.
  - `test_key_not_in_repr`: `"sk-test" not in repr(settings)`.
- [ ] **Step 2:** `uv run pytest tests/test_config.py -q` → FAIL (module missing).
- [ ] **Step 3:** Implement `Settings` in `config.py`.
- [ ] **Step 4:** Tests pass. Commit `feat: settings with single routing switch`.

**Decisions to record:** pydantic-settings + `.env` over a YAML config; no key ⇒ all-Qwen instead of crashing.

---

### Task 3: Database, migrations, courses repo

**Files:** Create `src/eduagent/db/__init__.py`, `db/database.py`, `db/migrations/0001_init.sql`, `db/courses.py`, `tests/db/test_database.py`, `tests/db/test_courses.py`.

**Interfaces — Produces:**
```python
class Database:
    def __init__(self, path: Path) -> None
    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]   # WAL, foreign_keys=ON, Row factory; commits on success, rolls back on error
    def migrate(self) -> int                            # applies migrations/NNNN_*.sql in order, tracks PRAGMA user_version; returns version
@dataclass(frozen=True) class Course: id: int; name: str
@dataclass(frozen=True) class TopicNode: id: int; name: str; mastery: float | None
@dataclass(frozen=True) class ModuleNode: id: int; name: str; topics: list[TopicNode]
class CoursesRepo:
    def __init__(self, db: Database)
    def create_course(self, name: str) -> Course          # ValueError on duplicate (case-insensitive)
    def list_courses(self) -> list[Course]
    def add_module(self, course_id: int, name: str) -> int
    def add_topic(self, course_id: int, name: str) -> int # course-level topic
    def link_topic(self, module_id: int, topic_id: int) -> None  # idempotent
    def course_map(self, course_id: int) -> list[ModuleNode]     # modules in creation order; mastery None until Plan 5
```
Schema `0001_init.sql`: `courses(id, name UNIQUE COLLATE NOCASE, created_at)`, `modules(id, course_id FK, name, created_at, UNIQUE(course_id,name))`, `topics(id, course_id FK, name COLLATE NOCASE, created_at, UNIQUE(course_id,name))`, `module_topics(module_id FK, topic_id FK, PRIMARY KEY both)`, `gemini_usage(day TEXT PK, requests INT, exhausted INT)`, `traces(id TEXT PK, kind, label, started_at, ended_at, status)`, `trace_steps(id INTEGER PK, trace_id FK, seq, step_type, component, input_json, output_json, model, tokens_in, tokens_out, duration_ms, created_at)`, `threads(id TEXT PK, course_id FK NULL, title, last_agent, created_at, updated_at)`. Timestamps are ISO-8601 UTC text.

- [ ] **Step 1: Write failing tests** (`tmp_path` db):
  - `test_migrate_fresh_and_idempotent`: first `migrate()` returns 1; second returns 1 and doesn't error.
  - `test_wal_and_foreign_keys`: `PRAGMA journal_mode` == `"wal"`; inserting a `modules` row with unknown `course_id` raises `sqlite3.IntegrityError`.
  - `test_duplicate_course_rejected`: `create_course("ML")` then `create_course("ml")` → `ValueError`.
  - `test_shared_topic_appears_under_both_modules`: topic "Gradient Descent" linked to "Module 2" and "Module 6" → appears in both `ModuleNode.topics` with the same `id`.
  - `test_link_topic_idempotent`: linking twice → topic listed once.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** `uv run pytest tests/db -q` → pass.
- [ ] **Step 5:** Commit `feat: sqlite data layer with migrations and course map`.

**Decisions to record:** raw `sqlite3` + SQL migration files over an ORM; WAL mode; topics course-level with link table.

---

### Task 4: Gemini quota tracker

**Files:** Create `src/eduagent/models/__init__.py`, `models/quota.py`, `tests/models/test_quota.py`.

**Interfaces — Produces:**
```python
QUOTA_TZ = ZoneInfo("America/Los_Angeles")
class QuotaTracker:
    def __init__(self, db: Database, daily_limit: int, clock: Callable[[], datetime] = lambda: datetime.now(UTC))
    def record_request(self) -> None
    def mark_exhausted(self) -> None          # after a 429: available=False for the rest of the Pacific day
    def remaining(self) -> int                # max(0, limit - used); 0 if exhausted
    def is_available(self) -> bool
    def resets_at(self) -> datetime           # next Pacific midnight, tz-aware UTC
```

- [ ] **Step 1: Write failing tests** with an injectable clock:
  - `test_remaining_counts_down`: limit 3, two `record_request()` → `remaining() == 1`.
  - `test_never_negative`: limit 1, three records → `0`, `is_available() is False`.
  - `test_mark_exhausted`: limit 100 → `mark_exhausted()` → `remaining() == 0`, `is_available() is False`.
  - `test_resets_at_pacific_midnight`: record at `2026-11-06T07:59Z` (23:59 PST Nov 5); at `2026-11-06T08:01Z` `remaining() == limit`; an exhausted flag from Nov 5 PT no longer applies.
  - `test_resets_at_value`: clock `2026-11-06T12:00Z` → `resets_at() == datetime(2026,11,7,8,0,tzinfo=UTC)`.
- [ ] **Step 2–4:** fail → implement (row keyed by Pacific `date.isoformat()`) → pass.
- [ ] **Step 5:** Commit `feat: gemini daily quota tracker (pacific reset)`.

**Decisions to record:** local counting + 429 as ground truth (no API exposes remaining free quota); Pacific reset; `tzdata` for Windows.

---

### Task 5: Tracer with redaction

**Files:** Create `src/eduagent/tracing/__init__.py`, `tracing/redact.py`, `tracing/tracer.py`, `tests/tracing/test_tracer.py`.

**Interfaces — Produces:**
```python
StepType = Literal["route","agent","tool_call","tool_result","model_call","fallback","answer","error"]
current_trace_id: ContextVar[str | None]
def redact(value: Any, secrets: Sequence[str]) -> Any   # deep-copies; replaces secret substrings and values of keys matching (?i)key|token|secret|authorization with "[redacted]"
@dataclass class TraceStep: trace_id: str; seq: int; step_type: StepType; component: str; inputs: Any; outputs: Any; model: str|None; tokens_in: int|None; tokens_out: int|None; duration_ms: int|None
@dataclass class Trace: id: str; kind: Literal["chat","upload"]; label: str; status: str; steps: list[TraceStep]
class Tracer:
    def __init__(self, db: Database, secrets: Sequence[str] = ())
    def start_trace(self, kind: Literal["chat","upload"], label: str) -> str   # uuid4 hex; status "running"
    def add_step(self, trace_id: str, step_type: StepType, component: str, *, inputs=None, outputs=None, model=None, tokens_in=None, tokens_out=None, duration_ms=None) -> TraceStep  # seq auto-increments per trace; redacts; notifies subscribers
    def end_trace(self, trace_id: str, status: Literal["ok","error"]) -> None
    def get_trace(self, trace_id: str) -> Trace
    def list_traces(self, kind: str | None = None, limit: int = 50) -> list[Trace]   # newest first, steps empty
    def subscribe(self, callback: Callable[[TraceStep], None]) -> Callable[[], None]  # returns unsubscribe
```
(The upload step types `parse/chunk/embed/tag/store` are added to `StepType` in Plan 2.)

- [ ] **Step 1: Write failing tests:**
  - `test_steps_ordered`: three `add_step` → `get_trace(id).steps` seqs `[1,2,3]`.
  - `test_secret_values_redacted_in_steps`: `Tracer(db, secrets=["AIzaSECRET"])`, inputs `{"q": "x AIzaSECRET y", "api_key": "abc", "nested": [{"Authorization": "Bearer z"}]}` → stored `{"q": "x [redacted] y", "api_key": "[redacted]", "nested": [{"Authorization": "[redacted]"}]}`; the raw secret not in the `trace_steps` table text.
  - `test_subscribers_notified_and_unsubscribe`.
  - `test_end_trace_sets_status`; `test_list_traces_filters_kind`.
  - `test_non_json_inputs_stringified`: inputs containing an object → stored via `json.dumps(default=str)`, no crash.
- [ ] **Step 2–4:** fail → implement → pass. **Step 5:** Commit `feat: request step tracing with secret redaction`.

**Decisions to record:** tracing in own SQLite tables (not OpenTelemetry) — it doubles as debug tool and feeds the replay page; redaction at write time.

---

### Task 6: Logger

**Files:** Create `src/eduagent/logging_setup.py`, `tests/test_logging_setup.py`.

**Interfaces — Consumes:** `Settings.log_level`, `Settings.log_dir`, `Settings.gemini_api_key`, `current_trace_id`, `redact`. **Produces:**
```python
LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] trace=%(trace_id)s %(message)s"
class TraceIdFilter(logging.Filter)        # sets record.trace_id = current_trace_id.get() or "-"
class RedactingFormatter(logging.Formatter)  # formats normally (incl. exc_info traceback), then replaces each secret substring with "[redacted]"
def configure_logging(settings: Settings) -> Path   # returns the log file path
```
Behaviour: root logger gets (a) `RotatingFileHandler(settings.log_dir / "eduagent.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")` at `settings.log_level`, and (b) a console `StreamHandler(sys.stderr)` at `INFO` (never stdout — later MCP stdio servers use stdout for protocol). Both use `TraceIdFilter` + `RedactingFormatter`. Libraries `litellm`, `LiteLLM`, `httpx`, `httpcore`, `google_genai`, `urllib3`, `watchfiles` are set to `WARNING`. Calling twice replaces our handlers rather than duplicating them (tagged via a handler attribute). Log files live under `data/` so they're git-ignored. Traces vs logs: traces are per-request structured steps for replay; logs are the developer's timeline of everything, including startup and full tracebacks.

- [ ] **Step 1: Write failing tests** (`tmp_path` as `data_dir`; restore root handlers in a fixture):
  - `test_log_file_written`: `configure_logging(s)`; `logging.getLogger("eduagent.x").info("hello")`; file contains `"INFO"`, `"[eduagent.x]"`, `"hello"`.
  - `test_trace_id_in_line`: with `current_trace_id` set to `"abc123"` the line contains `"trace=abc123"`; unset → `"trace=-"`.
  - `test_secret_scrubbed_from_message_and_traceback`: key `"AIzaSECRET"`; log `"calling with AIzaSECRET"` and `log.exception` inside `except ValueError("bad AIzaSECRET")` → file contains `"[redacted]"` twice-plus and never `"AIzaSECRET"`.
  - `test_level_respected`: `LOG_LEVEL=WARNING` → an `info` line is absent from the file, a `warning` line present.
  - `test_configure_twice_no_duplicate_lines`: configure twice, log once → message appears exactly once in the file.
  - `test_noisy_libraries_quieted`: `logging.getLogger("litellm").level == logging.WARNING`.
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5:** Commit `feat: rotating file logger with trace ids and secret redaction`.

**Decisions to record:** stdlib `logging` over loguru/structlog (no dependency, every library already speaks it); rotating file in `data/logs/`; trace id on every line to jump from a log line to its replay; console on stderr.

---

### Task 7: Model router and RoutedLlm

**Files:** Create `models/router.py`, `models/qwen.py`, `models/routed_llm.py`, `tests/models/test_router.py`, `tests/models/test_routed_llm.py`, `tests/models/test_qwen.py`.

**Interfaces — Consumes:** `Settings`, `QuotaTracker`, `Tracer`, `current_trace_id`. **Produces:**
```python
JobKind = Literal["chat", "heavy", "light"]
@dataclass(frozen=True) class ModelChoice: provider: Literal["gemini","qwen"]; model_id: str; reason: str
class ModelRouter:
    def __init__(self, settings: Settings, quota: QuotaTracker)
    def choose(self, job: JobKind) -> ModelChoice
def strip_think(text: str) -> str                                  # removes <think>…</think> (incl. unclosed leading block), trims
async def qwen_complete(prompt: str, settings: Settings, *, system: str | None = None) -> str   # litellm.acompletion("ollama_chat/<qwen_model>", api_base=ollama_url), thinking disabled, returns strip_think(text)
def is_rate_limit(exc: BaseException) -> bool                       # google.genai ClientError code 429, litellm.RateLimitError, or "RESOURCE_EXHAUSTED" in str(exc)
class RoutedLlm(BaseLlm):   # google.adk.models.BaseLlm
    # fields: job: JobKind; router: ModelRouter; quota: QuotaTracker; tracer: Tracer; gemini: BaseLlm; qwen: BaseLlm
    async def generate_content_async(self, llm_request, stream: bool = False) -> AsyncGenerator[LlmResponse, None]
def build_routed_llm(job: JobKind, settings: Settings, router: ModelRouter, quota: QuotaTracker, tracer: Tracer) -> RoutedLlm  # real gemini = google.adk Gemini(model=settings.gemini_model); qwen = LiteLlm(model=f"ollama_chat/{settings.qwen_model}")
```
Routing table for `choose` (`mode` = `settings.effective_routing_mode`):
| mode | chat / heavy | light |
|---|---|---|
| all_qwen | qwen | qwen |
| split | gemini if `quota.is_available()` else qwen | qwen |
| all_gemini | gemini if available else qwen | gemini if available else qwen |

`reason` is one of `"mode"`, `"job split"`, `"gemini quota exhausted"`.
`RoutedLlm` behaviour: gemini choice → `quota.record_request()`, delegate; on exception → if `is_rate_limit` then `quota.mark_exhausted()`; add a `fallback` trace step (component `"model_router"`, outputs `{"error": type(e).__name__}`) when `current_trace_id` is set; delegate the same request to qwen (with `llm_request.model` swapped). Every completed call adds a `model_call` step with model id, `usage_metadata` token counts, duration, **and the full request and response** (spec §4.14: "clicking a step shows exactly what went in and came out"), and logs `INFO "model=<id> tokens=<in>/<out> ms=<d>"`; a fallback logs `WARNING "gemini failed (<ExcType>), falling back to qwen"`; quota exhaustion is logged once by `QuotaTracker.mark_exhausted` (not here). Chat runs non-streaming in v1 so errors always arrive before any output.

`model_call` step payload (built by `summarize_request(llm_request) -> dict` and `summarize_response(responses: list[LlmResponse]) -> dict` in `models/routed_llm.py`):
- `inputs` = `{"system_instruction": str | None, "messages": [{"role": str, "parts": [...]}], "tools": [tool names offered]}` — each part rendered as `{"text": ...}`, `{"function_call": {"name", "args"}}` or `{"function_response": {"name", "response"}}` (so retrieved chunks and tool results the model saw are visible).
- `outputs` = `{"text": str | None, "function_calls": [{"name", "args"}], "finish_reason": str | None}`.
- Size cap: `TRACE_FIELD_CAP = 20_000` characters per string value; longer strings are cut and suffixed `"… [truncated N chars]"`. Applied before `Tracer.add_step` (which still redacts secrets).
- A failed attempt that triggers fallback records its `inputs` on the `fallback` step too, so the replay shows what Gemini was sent before it failed.

- [ ] **Step 1: Write failing tests** (fake `BaseLlm` subclasses that yield a fixed `LlmResponse` or raise):
  - `test_choose_table`: parametrized over all 9 cells above, with quota available and exhausted.
  - `test_strip_think`: `"<think>hmm</think>\n tutor"` → `"tutor"`; `"<think>unclosed tutor"`→ `""`; plain text unchanged.
  - `test_gemini_success_counts_quota`: one call → `quota.remaining() == limit-1`, response from gemini fake, a `model_call` step recorded.
  - `test_rate_limit_falls_back_and_exhausts`: gemini fake raises an error for which `is_rate_limit` is true → response from qwen fake, `quota.is_available() is False`, steps `["fallback","model_call"]`.
  - `test_non_rate_limit_error_falls_back_without_exhausting`: gemini raises `ConnectionError` → qwen answers, `quota.is_available() is True`.
  - `test_qwen_error_propagates`: mode all_qwen, qwen raises → exception surfaces (no infinite fallback).
  - `test_model_call_records_request_and_response`: request with system instruction "Be brief", a user message "what is overfitting?", a prior function_response part `{"name": "search_material", "response": {"chunks": ["c1"]}}`, and one tool declared → stored step `inputs.system_instruction == "Be brief"`, the messages include the user text and the function_response, `inputs.tools == ["search_material"]`; `outputs.text` equals the fake's reply.
  - `test_model_call_records_function_call_output`: fake returns a function_call `search_material(query="x")` → `outputs.function_calls == [{"name": "search_material", "args": {"query": "x"}}]`.
  - `test_trace_fields_truncated`: a 50_000-char user message → stored text length ≤ `TRACE_FIELD_CAP` + suffix and ends with `"[truncated 30000 chars]"`.
  - `test_fallback_step_includes_request`: rate-limit fallback → the `fallback` step's inputs contain the user message.
- [ ] **Step 2–4:** fail → implement → pass. `qwen_complete` gets one integration test marked `@pytest.mark.ollama` (skipped unless `-m ollama`): returns non-empty text without `<think>`.
- [ ] **Step 5:** Commit `feat: model router with gemini quota and qwen fallback`.

**Decisions to record:** a `BaseLlm` wrapper over ADK callbacks for fallback (one place, transparent to agents); non-streaming v1; how Qwen thinking is disabled; full prompt/response stored in `model_call` steps with a 20k-char cap per field (replay must show what the model actually saw, incl. retrieved chunks).

---

### Task 8: Routing and coordinator

**Files:** Create `agents/__init__.py`, `agents/routing.py`, `agents/placeholder.py`, `agents/tutor.py`, `agents/coordinator.py`, `agents/registry.py`, `tests/agents/test_routing.py`, `tests/agents/test_coordinator.py`, `tests/agents/routing_cases.py`, `tests/agents/test_routing_eval.py`; create `docs/manual-checks.md`.

> **Amended 2026-11-08 (student-approved):** routing mistakes are handled in layers — deterministic rules first, a few-shot classifier prompt measured on a 30-message eval set (basic prompt 24/30; few-shot with the previous agent in the user message 30/30 twice, ~1 s each on `qwen3:4b-instruct`), "if unsure → tutor", the raw classifier label recorded in the `route` step, and an `ollama`-marked eval test with a ≥ 90% bar that grows with every real misroute. Rulings R6/R7 are folded into the interfaces below.

**Interfaces — Consumes:** `Settings`, `qwen_complete`, `strip_think`, `Tracer`, `ModelRouter`, `QuotaTracker`, `build_routed_llm`. **Produces:**
```python
AgentName = Literal["tutor", "notes_maker", "coding", "analytics"]
MENTIONS: dict[str, AgentName] = {"tutor": "tutor", "notes": "notes_maker", "code": "coding", "progress": "analytics"}
DISPLAY_NAMES: dict[AgentName, str] = {"tutor": "Tutor", "notes_maker": "Notes maker", "coding": "Coding", "analytics": "Analytics"}
def parse_mention(text: str) -> tuple[AgentName | None, str]          # only a leading @mention, case-insensitive; returns stripped text
@dataclass(frozen=True) class RouteDecision: agent: AgentName; method: Literal["mention","code","classifier","default"]
Classifier = Callable[[str, AgentName | None], Awaitable[str]]          # (message, last_agent) -> raw label
async def route(text: str, last_agent: AgentName | None, classify: Classifier, *, has_attachment: bool = False) -> RouteDecision
ROUTER_PROMPT: str                                                       # system prompt, verbatim below
def classifier_message(text: str, last_agent: AgentName | None) -> str     # f"Previous agent: {last_agent or 'none'}\nStudent message: {text}"
def make_qwen_classifier(settings: Settings) -> Classifier                 # qwen_complete(classifier_message(...), settings, system=ROUTER_PROMPT)
class PlaceholderAgent(BaseAgent):  # yields one final Event: "<Display name> isn't built yet — coming in Plan N." No model call.
def build_tutor(model: BaseLlm) -> LlmAgent    # name "tutor"; no tools yet; instruction: teach, check understanding with one short question, label content "General knowledge (not from your material)" since no KB exists yet, use Mermaid where helpful, never nag
class CoordinatorAgent(BaseAgent):  # name "coordinator"; sub_agents = the four agents; router fn injected
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]
def build_coordinator(settings: Settings, router: ModelRouter, quota: QuotaTracker, tracer: Tracer, classify: Classifier | None = None) -> CoordinatorAgent   # classify defaults to make_qwen_classifier(settings); tutor = build_tutor(build_routed_llm("chat", ...)); others PlaceholderAgent (notes→Plan 3, coding→Plan 6, analytics→Plan 5)
```
`RouteDecision` also carries `raw_label: str | None = None` (the stripped classifier output; `None` when the classifier wasn't called).

`ROUTER_PROMPT` (verbatim; measured 30/30 on the eval set):
```text
You are the router of a study app for a data-science student. Pick the ONE agent that should answer.

Agents:
- tutor: explains concepts and theory, answers doubts, maths, "why/how does X work", runs quizzes and flashcard reviews, explains simpler.
- notes_maker: ONLY when the student asks to CREATE notes, summaries, revision sheets or flashcards for a module/topic.
- coding: anything about specific code or programming: what code does, errors, tracebacks, bugs, library/function usage (pandas, numpy, sklearn, Python syntax), how to write or fix code.
- analytics: the student's OWN performance: progress, scores, mastery, weak/strong topics, quiz history, "how am I doing".

Rules:
- Each message starts with "Previous agent: <name or none>". Short follow-ups ("why?", "more", "another example", "I don't get it") stay with the previous agent.
- Explaining a concept is tutor, even if it is a coding-related concept like recursion or Big-O, unless the student is asking about specific code or a library call.
- If unsure, answer tutor.

Examples:
"what is overfitting?" -> tutor
"make flashcards for module 2" -> notes_maker
"why does my loop never end?" -> coding
"what does df.groupby return?" -> coding
"I got a KeyError when indexing my dataframe" -> coding
"am I getting better at statistics?" -> analytics
"give me a quick summary sheet of PCA to revise" -> notes_maker
"test me on regression" -> tutor
(previous agent: coding) "show me another one" -> coding
(previous agent: tutor) "why?" -> tutor
(previous agent: analytics) "and last month?" -> analytics

Reply with exactly one word: tutor, notes_maker, coding or analytics.
```

Routing eval set (`tests/agents/routing_cases.py`, `ROUTING_CASES: list[tuple[str, AgentName | None, AgentName]]` = message, last_agent, expected; none of these may be copied into the prompt's examples):
| message | last | expected |
|---|---|---|
| what is regularization? | – | tutor |
| make notes for module 3 | – | notes_maker |
| how am I doing? | – | analytics |
| and why is that? | tutor | tutor |
| what does this python function return when the list is empty | – | coding |
| quiz me on decision trees | – | tutor |
| can you explain the difference between precision and recall with an example | – | tutor |
| i dont understand the backprop slide from tuesday | – | tutor |
| prepare revision notes on k-means for my exam | – | notes_maker |
| summarise module 5 for me | – | notes_maker |
| my sklearn model gives ValueError: Input contains NaN, what's wrong | – | coding |
| how do I use pd.merge on two columns | – | coding |
| which topics should I revise before the midterm based on my quiz results? | – | analytics |
| did my score on the clustering quiz improve? | – | analytics |
| what's my weakest topic | – | analytics |
| explain recursion simply | – | tutor |
| what is the time complexity of quicksort | – | tutor |
| ok another example please | coding | coding |
| ok another example please | tutor | tutor |
| thanks! now make flashcards out of this | tutor | notes_maker |
| why is my accuracy 100% on training but 60% on test | – | tutor |
| is my for loop in the attached notebook efficient | – | coding |
| give me practice questions on hypothesis testing | – | tutor |
| how many quizzes have I done this week | – | analytics |
| whats the formula for the gini index | – | tutor |
| I keep getting confused between bagging and boosting | – | tutor |
| can you review my linear regression implementation for bugs | – | coding |
| hmm still not clear | tutor | tutor |
| what does random_state do in train_test_split | – | coding |
| create a one-page cheat sheet for SVMs | – | notes_maker |
`route` order: mention → `` ``` `` in text or `has_attachment` → `coding` (method `code`) → classifier: first known agent name found in `strip_think(label).lower()` → else `last_agent` or `"tutor"` (method `default`); classifier exceptions → default.
Coordinator: reads text from `ctx.user_content`, `last_agent` from `ctx.session.state`, calls route, adds a `route` trace step with outputs `{agent, method, raw_label}`, logs `INFO "routed to <agent> via <method>"` (and `DEBUG` the raw label), writes `state["last_agent"]` via an event `state_delta`, then re-yields `target.run_async(ctx)` events.
Each agent module defines `WHAT_IT_DOES`.

- [ ] **Step 1: Write failing tests** (`tests/agents/test_routing.py`, fake classifiers):
  - `test_parse_mention`: `"@Tutor explain x"` → `("tutor","explain x")`; `"@notes"` → `("notes_maker","")`; `"mail me@notes"` → `(None, ...)`; `"@foo hi"` → `(None,"@foo hi")`.
  - `test_mention_beats_classifier` (classifier would say coding).
  - `test_code_fence_routes_coding`; `test_attachment_routes_coding`.
  - `test_classifier_label_with_think_block`: label `"<think>…</think> Analytics."` → `analytics`.
  - `test_classifier_garbage_defaults_to_last_agent` and `…_to_tutor` when no last agent.
  - `test_classifier_exception_defaults` (classifier raises `ConnectionError` → `tutor`, method `default`).
  - `test_raw_label_recorded`: classifier returns `"<think>x</think> Coding."` → `RouteDecision.raw_label == "Coding."`; mention/code routes → `raw_label is None`.
  - `test_classifier_message_format`: `classifier_message("why?", "tutor") == "Previous agent: tutor\nStudent message: why?"`; `None` → `"Previous agent: none\n…"`.
  - `test_prompt_examples_not_in_eval_set`: no `ROUTING_CASES` message appears verbatim in `ROUTER_PROMPT` (keeps the eval honest).
- [ ] **Step 2: Coordinator test** (`tests/agents/test_coordinator.py`): ADK `Runner` + `InMemorySessionService`, coordinator with four `PlaceholderAgent`s and a fake classifier returning `"analytics"` → final event `author == "analytics"`; session state `last_agent == "analytics"`; tracer has a `route` step whose outputs include `raw_label == "analytics"`.
- [ ] **Step 3–4:** fail → implement → pass.
- [ ] **Step 5: Routing eval** (`tests/agents/test_routing_eval.py`, `@pytest.mark.ollama`): runs every `ROUTING_CASES` row through `route(text, last, make_qwen_classifier(Settings()))`, prints each miss (`message (last) -> got, want`), and asserts accuracy ≥ 0.9. Run it (`uv run pytest -m ollama tests/agents -q -s`) and put the score in the report. `docs/manual-checks.md` gets a "Routing" section: how to run the eval, the score from this run, and an empty "Misroutes found in real use" table (message · last agent · routed to · should be · date) — every real misroute is added there **and** to `ROUTING_CASES`.
- [ ] **Step 6:** Commit `feat: coordinator with mention/code/qwen routing`.

**Decisions to record:** code routing in a custom `BaseAgent` vs ADK LLM transfer (saves Gemini quota, deterministic, still an ADK agent tree for §4.14); few-shot prompt with the previous agent inside the user message (a 4B model ignored it in the system prompt: follow-ups misrouted) — measured 24/30 → 30/30; "if unsure → tutor" (cheapest wrong answer); an eval set that grows from real misroutes instead of a one-off manual check; placeholders instead of half-built agents.

---

### Task 9: Saved chats and ChatService

**Files:** Create `db/threads.py`, `chat/__init__.py`, `chat/service.py`, `services.py`, `tests/db/test_threads.py`, `tests/chat/test_service.py`.

**Interfaces — Consumes:** `CoordinatorAgent`, `build_coordinator`, `Tracer`, `current_trace_id`, `DISPLAY_NAMES`, `MENTIONS`, `AgentName`. **Produces:**
```python
@dataclass(frozen=True) class Thread: id: str; course_id: int | None; title: str; last_agent: str | None; updated_at: str
class ThreadsRepo:
    def create(self, course_id: int | None, title: str = "New chat") -> Thread
    def list(self, course_id: int | None) -> list[Thread]       # most recently updated first
    def rename(self, thread_id: str, title: str) -> None
    def touch(self, thread_id: str, last_agent: str | None) -> None
@dataclass(frozen=True) class AgentReply: agent: str; display_name: str; text: str; model: str | None; trace_id: str
class ChatService:
    def __init__(self, runner: Runner, session_service: BaseSessionService, threads: ThreadsRepo, tracer: Tracer, app_name: str = "eduagent")
    async def new_thread(self, course_id: int | None) -> Thread     # also creates ADK session (id = thread id, user "student")
    async def send(self, thread_id: str, text: str) -> list[AgentReply]
    async def resend_to(self, thread_id: str, user_text: str, wrong: AgentReply, agent: AgentName) -> list[AgentReply]   # "Ask another agent": sends f"@{mention} {user_text}" and records a `reroute` step
    async def history(self, thread_id: str) -> list[tuple[str, str]]   # (role/agent, text) from ADK session events, for reopening saved chats
@dataclass class Services: settings: Settings; db: Database; courses: CoursesRepo; threads: ThreadsRepo; quota: QuotaTracker; router: ModelRouter; tracer: Tracer; chat: ChatService; warnings: list[str] = field(default_factory=list)
def build_services(settings: Settings) -> Services   # real wiring; ADK DatabaseSessionService(settings.sessions_db_url)
```
`send`: start trace (`chat`, label = first 60 chars), set `current_trace_id`, run `runner.run_async`, map events → steps (`function_call`→`tool_call`, `function_response`→`tool_result`, final response→`answer`), collect final texts as `AgentReply` (model = last `model_call` step's model), `touch` thread, auto-title a "New chat" thread from the first message (first 40 chars), end trace `ok`; on exception end trace `error`, add `error` step, `log.exception("chat send failed")` (full traceback goes to the log file, tagged with the trace id), return one `AgentReply(agent="system", text="Something went wrong: <type>. Details are in the trace.")` — never a raw traceback. Only non-thought text parts become `AgentReply.text` (ADK yields Qwen reasoning as `thought=True` parts — ruling R14).
`resend_to` (added 2026-11-08 — routing corrections): looks up the mention tag for `agent` (inverse of `MENTIONS`), runs the same flow as `send` with text `f"@{tag} {user_text}"`, and in that new trace adds a step of the new type `"reroute"` (add `"reroute"` to `StepType` in `tracing/tracer.py`), component `"chat"`, inputs `{"from_trace": wrong.trace_id, "from_agent": wrong.agent, "to_agent": agent, "text": user_text}`; logs `INFO "reroute <from> -> <to>"`. `SELECT … FROM trace_steps WHERE step_type='reroute'` is then the list of real misroutes to add to `ROUTING_CASES`.

- [ ] **Step 1: Write failing tests:**
  - threads: `test_create_list_order`, `test_touch_updates_last_agent_and_order`.
  - `test_send_returns_labelled_reply`: coordinator with `PlaceholderAgent`s + fake classifier `"analytics"`, `InMemorySessionService` → one reply, `display_name == "Analytics"`, trace status `ok`, steps include `route` and `answer`.
  - `test_first_message_titles_thread`.
  - `test_agent_exception_returns_system_reply`: sub-agent raises → reply agent `"system"`, trace status `error`.
  - `test_history_roundtrip`: after one send, `history()` returns user text then agent text.
  - `test_reply_excludes_thought_parts`: a sub-agent event with a `thought=True` part "reasoning" and a text part "answer" → `AgentReply.text == "answer"`.
  - `test_resend_to_records_reroute`: send "what is a dataframe?" (fake classifier → `"tutor"`), then `resend_to(thread, "what is a dataframe?", reply, "coding")` → reply from `coding`; its trace has a `reroute` step with `from_agent == "tutor"`, `to_agent == "coding"`, and a `route` step with method `mention`.
- [ ] **Step 2–4:** fail → implement → pass. **Step 5:** Commit `feat: chat service with saved threads and traced runs`.

**Decisions to record:** ADK `DatabaseSessionService` in a separate `sessions.db` (ADK owns its schema) vs our own message table; thread id = session id.

---

### Task 10: UI shell

**Files:** Create `ui/__init__.py`, `ui/theme.py`, `ui/frame.py`, `ui/pages/chat.py`, `ui/pages/placeholders.py`, `ui/app.py`, `tests/ui/conftest.py`, `tests/ui/test_shell.py`.

**Interfaces — Consumes:** `Services`, `CoursesRepo.course_map`, `ThreadsRepo`, `ChatService`, `QuotaTracker.remaining`, `ModelRouter.choose("chat")`. **Produces:** `def register_pages(services: Services) -> None` (defines all `@ui.page` routes); `def apply_theme() -> None`.

Palette (theme.py, Quasar `ui.colors`): primary `#35618C`, background `#F7F8FA`, surface `#FFFFFF`, text `#1F2933`, muted `#6B7785`; mastery dots strong `#3A8D5C`, okay `#C9A227`, weak `#C0504D`, untested `#9AA5B1`. One sans font (system UI stack). No gradients or animations beyond Quasar defaults.

Layout (`frame.py`, a context manager `page_frame(services, title)`):
- **Top bar:** app title "Educational Agent", course selector, `Model: <provider · model_id>` from `router.choose("chat")`, `Gemini: <n> left today` (or `Gemini: off (all Qwen)`), refreshed by `ui.timer(30)` and after each send.
- **Left drawer:** course select + "New course" dialog; course map tree (module → topics with coloured dot; grey until Plan 5); links Chat · Library · Notes · Flashcards · Progress · How it works; "Saved chats" list for the course + "New chat" button.
- **Pages:** `/` (redirect to latest thread or new), `/chat/{thread_id}`; `/library`, `/notes`, `/flashcards`, `/progress`, `/how-it-works` show a calm "Coming in Plan N" card.
- **Chat page:** message list; user messages right-aligned; each reply shows an agent chip (`display_name`) and small model caption, body rendered with `ui.markdown(..., extras=["fenced-code-blocks","tables","mermaid"])` (verify Mermaid support in the installed NiceGUI; if absent, split out ```mermaid blocks and render with `ui.mermaid`). Input + Send (Enter sends, Shift+Enter newline); spinner "Thinking…" while `send` runs; input disabled during a run. Quick buttons come in Plan 4.
- **"Ask another agent"** (added 2026-11-08): under each agent reply (not `system` replies), a small muted line "Ask instead:" followed by flat text buttons with the `DISPLAY_NAMES` of the other three agents. Clicking one calls `chat.resend_to(thread_id, <the user message that produced this reply>, reply, agent)`, shows the mention-prefixed user message and the new reply like any other turn. Calm styling: muted colour, small text, no icons.

- [ ] **Step 1: Write failing tests** with NiceGUI's `user` fixture (`pytest_plugins = ["nicegui.testing.user_plugin"]`, `Services` built on a `tmp_path` db with a fake `ChatService`):
  - `test_shell_shows_quota_and_links`: open `/` → sees `"Gemini:"`, `"Library"`, `"Progress"`, `"How it works"`.
  - `test_create_course_appears_in_selector`.
  - `test_course_map_shows_shared_topic_twice` (seeded via `CoursesRepo`).
  - `test_send_shows_labelled_reply`: type "hello", click Send → sees `"Analytics"` chip and the fake reply text.
  - `test_placeholder_page`: `/notes` → sees `"Coming in Plan 3"`.
  - `test_ask_another_agent`: after the "hello" reply from Analytics, the reply shows "Ask instead:" with `"Tutor"`, `"Notes maker"`, `"Coding"` (not `"Analytics"`); clicking `"Coding"` calls the fake `resend_to` with `("hello", <that reply>, "coding")` and shows its reply.
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5:** Commit `feat: nicegui shell with chat, sidebar, top bar`.

**Decisions to record:** NiceGUI over Streamlit/Gradio (multi-page app, persistent websocket, Quasar components, ECharts later); palette rationale; non-streaming replies with spinner; one-click "Ask another agent" (a misroute costs one click and becomes eval data) over making the student retype with an `@mention`.

---

### Task 11: Launcher, preflight, README, end-to-end check

**Files:** Create `launcher.py`, `tests/test_launcher.py`; modify `README.md`, `docs/manual-checks.md`.

**Interfaces — Consumes:** `Settings`, `build_services`, `register_pages`, `apply_theme`. **Produces:**
```python
def preflight(settings: Settings, fetch_ollama_models: Callable[[], list[str]]) -> list[str]   # human-readable warnings; empty = all good
def main() -> None   # Settings(); mkdir data dirs; configure_logging (first, so startup is logged); log each preflight warning at WARNING; Database.migrate(); preflight (real fetch = GET {ollama_url}/api/tags); build_services; register_pages; ui.run(host="127.0.0.1", port=8000, title="Educational Agent", reload=False, show=True)
```
Warnings (exact copy): no key → `"No GEMINI_API_KEY in .env — running everything on Qwen."`; Ollama unreachable → `"Ollama isn't running. Start it with: ollama serve"`; model missing → `"Model <name> not found. Run: ollama pull <name>"`. Warnings are shown as a dismissible banner at the top of the chat page; the app still starts. (Chroma server start is added to `main` in Plan 2.)

- [ ] **Step 1: Write failing tests:** `test_preflight_all_good` (key set, both models listed → `[]`); `test_preflight_ollama_down` (fetch raises `httpx.ConnectError` → contains `"ollama serve"`); `test_preflight_missing_model` (only `nomic-embed-text:latest` listed → contains `"ollama pull qwen3:4b-instruct"`; note Ollama reports tags like `qwen3:4b-instruct` and `nomic-embed-text:latest` — match with or without `:latest`); `test_preflight_no_key`.
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5:** README: setup (install Ollama, pull both models, install uv, `uv sync`, copy `.env.example` → `.env`, add key from AI Studio, `uv run eduagent`), what works so far, roadmap table, "your data stays in `data/` and is never committed". Screenshot added after Step 6.
- [ ] **Step 6: Manual end-to-end** (`uv run eduagent`): browser opens on `127.0.0.1:8000`; create a course; new chat; ask "what is overfitting?" → reply labelled **Tutor**, model caption Gemini, quota count drops by ≥1; `@progress hi` → Analytics placeholder; set `ROUTING_MODE=all_qwen`, restart → caption shows Qwen and the top bar says all Qwen; stop Ollama, restart → banner names `ollama serve`. Run the routing eval (`uv run pytest -m ollama tests/agents -q -s`) and record the score in `docs/manual-checks.md`; in the app, click "Ask instead: Coding" under a Tutor reply and confirm the trace has a `reroute` step. Check `data/study.db` `trace_steps` contains no API key (`SELECT count(*) FROM trace_steps WHERE input_json LIKE '%<first 8 chars of key>%'` → 0) and `data/logs/eduagent.log` doesn't contain it either; confirm the log shows startup, preflight, each route decision, model used, and (with Gemini key temporarily wrong) a fallback WARNING.
- [ ] **Step 7:** Full suite `uv run pytest -q` → all pass (ollama-marked tests skipped). `git status` clean of `data/` and `.env`. Commit `feat: one-command launcher with preflight checks`.
- [ ] **Step 8:** Ask the student to confirm, then `git push -u origin main`.

**Decisions to record:** preflight warns instead of failing; localhost-only binding.

---

## Verification (whole plan)

- `uv run pytest -q` green; `uv run pytest -m ollama -q` green with Ollama running.
- Manual end-to-end in Task 11 Step 6, with routing checks recorded in `docs/manual-checks.md`.
- `git log` shows one commit per task plus decision-log commits; `git ls-files` contains nothing under `data/` and no `.env`.
