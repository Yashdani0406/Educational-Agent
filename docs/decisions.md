# Decision log

Format: `## <date> — <decision>`, then *Chose* / *Rejected* / *Why*.

## 2026-11-06 — uv for environment and dependency management
*Chose:* uv (project env, lockfile, `uv run`).
*Rejected:* pip + venv.
*Why:* One tool gives a reproducible lockfile, fast installs and pinned Python versions, with no manual venv activation.

## 2026-11-06 — Python 3.12 over 3.14
*Chose:* Python 3.12.
*Rejected:* Python 3.14.
*Why:* Google ADK, LiteLLM, and their native dependencies are most reliably tested on 3.12; newest Python risks missing wheels.

## 2026-11-06 — src layout
*Chose:* `src/eduagent/` package layout.
*Rejected:* flat layout with the package at the repo root.
*Why:* Tests must import the installed package, not the working directory, which catches packaging mistakes early.

## 2026-11-06 — Dependencies added per plan, not up-front
*Chose:* Add each dependency in the plan that first uses it (Chroma, MCP, Playwright, parsers later).
*Rejected:* Installing everything the spec mentions on day one.
*Why:* Keeps the environment small and every dependency justified by real code that needs it.

## 2026-11-06 — pydantic-settings + .env for configuration
*Chose:* pydantic-settings `Settings` class reading environment variables and a git-ignored `.env`.
*Rejected:* A YAML config file.
*Why:* Typed, validated values (bad `ROUTING_MODE` fails fast), secrets stay in `.env` out of git, and no extra parser or file format is needed.

## 2026-11-06 — No Gemini key means all-Qwen, not a crash
*Chose:* `effective_routing_mode` returns `all_qwen` when the key is missing or blank.
*Rejected:* Raising an error at startup when `ROUTING_MODE` needs Gemini but no key exists.
*Why:* The app must stay usable fully offline with local Qwen; a blank `GEMINI_API_KEY=` line in `.env` counts as no key.

## 2026-11-06 — Raw sqlite3 + SQL migration files, no ORM
*Chose:* Plain `sqlite3` with numbered `.sql` migrations (shipped as package data) tracked by `PRAGMA user_version`; each migration applied atomically with its version bump.
*Rejected:* SQLAlchemy/Alembic or another ORM.
*Why:* The schema is small and local; an ORM and migration framework add dependencies and indirection for no gain, and SQL files are easy to read and review.

## 2026-11-06 — SQLite in WAL mode
*Chose:* `PRAGMA journal_mode=WAL` and `foreign_keys=ON` on every connection, one short-lived connection per operation.
*Rejected:* Default rollback-journal mode and a shared long-lived connection.
*Why:* WAL lets the UI read while background agents write without "database is locked" errors; per-use connections are closed promptly, which also avoids Windows file locks.

## 2026-11-06 — Topics are course-level, linked to modules
*Chose:* `topics` belong to a course; a `module_topics` link table attaches them to modules; adding a module or topic is get-or-create by case-insensitive name.
*Rejected:* Topics owned by a single module.
*Why:* The same topic (e.g. Gradient Descent) recurs across modules and must stay one record so mastery and notes accumulate in one place.

## 2026-11-06 — Gemini quota is counted locally, 429 is ground truth
*Chose:* Count requests in the `gemini_usage` table and mark the day exhausted when Gemini returns a 429.
*Rejected:* Querying the API for remaining free quota.
*Why:* No API exposes remaining free-tier quota, so a local count drives the "N left today" display and a real 429 overrides it if the count is wrong.

## 2026-11-06 — Quota resets at Pacific midnight
*Chose:* Key usage rows by the America/Los_Angeles calendar date (DST-aware) and report the next Pacific midnight as UTC.
*Rejected:* Resetting at local or UTC midnight.
*Why:* Google resets the free-tier daily quota at Pacific midnight, so matching it keeps the local count aligned with the real limit.

## 2026-11-06 — `tzdata` for Windows time zones
*Chose:* Depend on the `tzdata` package so `zoneinfo` can load `America/Los_Angeles`.
*Rejected:* Relying on a system tz database or a fixed UTC-8 offset.
*Why:* Windows ships no IANA tz database, and a fixed offset would be wrong during daylight saving time.

## 2026-11-06 — Tracing in our own SQLite tables, not OpenTelemetry
*Chose:* Record route/model/tool/fallback/answer steps in `traces` and `trace_steps`.
*Rejected:* OpenTelemetry spans and an external collector.
*Why:* The same rows double as the debugging tool and feed the "How it works" replay page, with no extra service to run.

## 2026-11-06 — Redact at write time, by full key name
*Chose:* Scrub secrets before storing: secret values everywhere (also in the serialized JSON), and dict keys matched by full name (`api_key`, `token`, `x-api-key`).
*Rejected:* Redacting on read, or substring key matching.
*Why:* Nothing sensitive ever reaches disk; substring matching would wrongly hide `max_tokens` and `prompt_token_count`.

## 2026-11-06 — stdlib `logging` for the app logger
*Chose:* Standard-library `logging` with a rotating file in `data/logs/` and a console handler on stderr.
*Rejected:* loguru or structlog.
*Why:* No extra dependency, and every library we use already logs through it. Stderr keeps stdout free for MCP stdio servers.

## 2026-11-06 — Trace id on every log line
*Chose:* Stamp the current trace id (or `-`) on each log line, and scrub the API key from the final formatted text, tracebacks included.
*Rejected:* Logging trace ids only inside trace rows.
*Why:* A log line can be matched to its replay page, and the key cannot leak through an exception message.
