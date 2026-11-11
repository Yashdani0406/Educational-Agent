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

## 2026-11-07 — One `BaseLlm` wrapper (`RoutedLlm`) for routing and fallback
*Chose:* A `BaseLlm` subclass that picks Gemini or Qwen, counts quota, falls back on any Gemini error and writes the trace steps.
*Rejected:* ADK before/after-model callbacks on each agent.
*Why:* One place holds all of it and agents just see a model; callbacks would have to be repeated on every agent.

## 2026-11-07 — Chat is non-streaming in v1
*Chose:* Collect the whole model reply, then yield it.
*Rejected:* Streaming tokens to the UI.
*Why:* Any Gemini error then arrives before output, so the fallback to Qwen is clean and the user never sees a half answer.

## 2026-11-07 — Qwen thinking is separated and stripped, not disabled
*Chose:* Send no `think` option and let Ollama return reasoning in its own field (ADK shows it as a `thought` part, which agents ignore); `strip_think` also runs on every Qwen reply as a safety net, including a reply with only a closing `</think>`.
*Rejected:* `think=False` (also tried `reasoning_effort="none"` and `extra_body`): with this `qwen3:4b` and Ollama build none of them stops the thinking, and `think=False` makes the reasoning leak into the reply text ending in a bare `</think>`.
*Why:* Checked directly against Ollama: the model always thinks (about 120-200 tokens for a one-word reply); only the default setting keeps the reply text clean.

## 2026-11-07 — Full prompt and reply stored in `model_call` steps, capped at 20k chars per field
*Chose:* Store system instruction, all messages (including retrieved chunks and tool results), tool names and the reply, cutting any string over 20,000 characters.
*Rejected:* Storing only token counts, or uncapped text.
*Why:* The replay must show exactly what the model saw; the cap keeps one huge prompt from bloating the database.

## 2026-11-08 — Default Qwen is `qwen3:4b-instruct`, not the thinking `qwen3:4b`
*Chose:* `qwen3:4b-instruct` (Qwen3-4B-Instruct-2507, non-thinking, same 2.5 GB).
*Rejected:* `qwen3:4b`, which Ollama now maps to the thinking-only Qwen3-4B-Thinking-2507.
*Why:* Measured on this laptop's CPU: routing 0.8 s vs 37 s per message, a tutor answer 10 s vs 116 s, with the same routing and tool-choice accuracy on our checks. Thinking scores higher on hard reasoning benchmarks, but Qwen's jobs here are light work and fallback, where minutes per reply is unusable. Switching back is one `.env` line.

## 2026-11-08 — Routing lives in a custom coordinator agent, not ADK LLM transfer
*Chose:* A `BaseAgent` coordinator that routes with plain code (mention, code fence or attachment) and a small local Qwen classifier, then runs the chosen sub-agent.
*Rejected:* ADK's LLM-driven transfer, where a Gemini call decides who answers.
*Why:* Saves Gemini quota, is deterministic for mentions and code, and is still an ADK agent tree so traces and agent cards work.

## 2026-11-08 — Few-shot router prompt with the previous agent inside the user message
*Chose:* Examples in the prompt and "Previous agent: ..." at the top of each user message.
*Rejected:* The previous agent in the system prompt with no examples.
*Why:* The 4B model ignored the system-prompt version and misrouted follow-ups. Measured on 30 messages: 24/30 before, 30/30 after (about 1 s each).

## 2026-11-08 — "If unsure, answer tutor"
*Chose:* Unclear or failed classification goes to the previous agent, else the tutor.
*Rejected:* Asking the student to pick, or erroring.
*Why:* The tutor is the cheapest wrong answer: it can still help with almost anything.

## 2026-11-08 — Routing eval set that grows from real misroutes
*Chose:* A 30-message eval test (`ollama` marker, 90% bar) plus a table of real misroutes, each also added to the set.
*Rejected:* A one-off manual check of the prompt.
*Why:* Prompt edits can silently break old cases; the set turns every real mistake into a permanent regression check.

## 2026-11-08 — Placeholders instead of half-built agents
*Chose:* `PlaceholderAgent` replies "<Name> isn't built yet — coming in Plan N." with no model call.
*Rejected:* Stub agents that call the model with a guess at their job.
*Why:* Routing and the agent tree work end to end now, and nothing pretends to be finished.

## 2026-11-09 — ADK session store in a separate sessions.db
*Chose:* ADK `DatabaseSessionService` in `sessions.db`, which ADK owns and migrates; our `threads` table holds only titles and the last agent.
*Rejected:* Our own messages table in `study.db`.
*Why:* ADK needs its own event format to replay a conversation. Copying it into our schema would mean maintaining two versions of the same history.

## 2026-11-09 — Thread id is the ADK session id
*Chose:* One id for both: creating a thread creates the session with the same id.
*Rejected:* A separate id with a mapping table.
*Why:* Reopening a saved chat is a single lookup, and the two can never point at different conversations.

## 2026-11-09 — NiceGUI for the front end
*Chose:* NiceGUI (pure Python, Quasar components, one persistent websocket, multi-page routes, ECharts available later).
*Rejected:* Streamlit and Gradio.
*Why:* Streamlit reruns the whole script on every click and Gradio is built for single-screen demos. This app needs several pages, a live sidebar and a chat that keeps its state.

## 2026-11-09 — One calm palette
*Chose:* A muted blue primary (`#35618C`) on a near-white background, with one system sans font and four mastery-dot colours (green, amber, red, grey for untested).
*Rejected:* Dark theme, gradients, animated accents.
*Why:* A study tool is used for long sessions, so it should stay quiet. Colour is kept for meaning: the mastery dots.

## 2026-11-09 — Non-streaming replies with a spinner
*Chose:* Wait for the full reply and show a "Thinking…" spinner with the input disabled.
*Rejected:* Token streaming.
*Why:* Several agents and tools can run before the final answer, and the trace records one finished answer. Streaming would add complexity for little gain in a single-user local app.

## 2026-11-09 — One-click "Ask another agent"
*Chose:* Small "Ask instead:" buttons under each reply that resend the same question to another agent.
*Rejected:* Making the student retype the question with an `@mention`.
*Why:* A misroute then costs one click, and each click is recorded as a reroute step, so it becomes eval data for the router.

## 2026-11-09 — Preflight warns instead of failing
*Chose:* Check Ollama, both models and the Gemini key at start-up, log each problem and show it as a banner, but always start the app.
*Rejected:* Refusing to start when something is missing.
*Why:* Most problems are fixable while the app is open, and Gemini-only or Qwen-only use is valid. The banner names the exact command to run.

## 2026-11-09 — Localhost-only binding
*Chose:* Serve the UI on `127.0.0.1:8000` only.
*Rejected:* Binding to `0.0.0.0` so other devices can connect.
*Why:* The app has no login and holds personal course material, so it should not be reachable from the network.

## 2026-11-09 — Qwen on CPU by default
*Chose:* Send Ollama `num_gpu=0` on every Qwen request unless `OLLAMA_USE_GPU=true`.
*Rejected:* Ollama's automatic partial GPU offload (3 of 37 layers on the 2 GB MX570).
*Why:* Measured no speed gain (about 10 tok/s either way), and the GPU load crashed Ollama once, which failed the routing classifier.

## 2026-11-09 — Gemini requests time out after 30 s
*Chose:* Give the Gemini client a 30 s request timeout so a hung call raises and the Qwen fallback runs.
*Rejected:* No timeout (the library default).
*Why:* A hung call never errors, so the fallback never triggered and the student sat on "Thinking…" indefinitely.

## 2026-11-09 — Mermaid labels: prompt rule plus deterministic quoting
*Chose:* Tell the tutor to quote every node label, and also quote labels containing brackets before display.
*Rejected:* Prompt-only (small models still slip) or showing the raw diagram code on a syntax error.
*Why:* An unquoted label with parentheses is a Mermaid syntax error; a small deterministic fix guarantees the diagram draws.

## 2026-11-09 — Router decides by goal, not output format
*Chose:* A goal-not-format rule, one diagram example per agent, and a Goal line before the label.
*Rejected:* Making diagrams tutor-only (notes and analytics draw diagrams too); embedding-only routing (18/30 on our eval, can't use the previous agent); forced-JSON labels (shape, not correctness).
*Why:* Measured 30/30 + 11/14 held-out vs 29/30 + 10/14, and the Goal line makes each misroute explain itself in the trace.

## 2026-11-09 — Routing at temperature 0
*Chose:* The classifier call sends temperature 0.
*Rejected:* The model's default temperature.
*Why:* Routing must be deterministic: same message, same agent (the default split one message tutor 3 / coding 2).

## 2026-11-09 — Only a per-day 429 marks the Gemini day exhausted
*Chose:* Mark the day exhausted only when the 429 names a per-day quota (a quotaId containing `PerDay`); any other 429 just falls back to Qwen for that request.
*Rejected:* Any 429 marks the day exhausted.
*Why:* The free tier also returns 429 for per-minute limits; one burst would have switched Gemini off until midnight Pacific with no way to recover.

## 2026-11-10 — Plan 2 decisions live in the Plan 2 design
*Chose:* Keep the decisions for Plan 2 (parsers, web links, chunking, search, books) in docs/superpowers/specs/2026-11-10-plan-2-knowledge-base-design.md, and mark each change to the parent spec "Changed 2026-11-10".
*Rejected:* Copying every decision into this log.
*Why:* The design records each choice with its research and rejected options; this log points to it so there is one source.

## 2026-11-10 — Rename the agents package to team; APP_NAME stays "eduagent"
*Chose:* Rename `eduagent.agents` to `eduagent.team` so ADK's Runner no longer infers the app name "agents" from the folder; keep `APP_NAME = "eduagent"`.
*Rejected:* Filtering the "App name mismatch" log line, or changing `APP_NAME` to "agents".
*Why:* A log filter hides the symptom, the folder name is the cause. ADK sessions are keyed by `APP_NAME`, so changing it would orphan saved chats.

## 2026-11-10 — INSERT ... ON CONFLICT for get-or-create
*Chose:* `_get_or_create` runs `INSERT ... ON CONFLICT(course_id, name) DO NOTHING` then `SELECT id` on one connection.
*Rejected:* SELECT-then-INSERT, which lets two concurrent taggers both miss and one hit an IntegrityError.
*Why:* The unique index decides the winner atomically, so concurrent topic tagging always returns one row and one id.

## 2026-11-10 — A second preflight wording for a reachable-but-odd Ollama
*Chose:* Network errors (including an invalid URL) keep "Ollama isn't running. Start it with: ollama serve"; a bad or non-Ollama answer (ValueError, KeyError, TypeError) says "Ollama answered with something unexpected (check OLLAMA_URL in .env)."
*Rejected:* One "isn't running" message for everything, or letting the exception crash start-up.
*Why:* Telling the student to start a server that is already running (a wrong OLLAMA_URL) sends them the wrong way.

## 2026-11-10 — One num_ctx (8192) for every Qwen call
*Chose:* `ollama_options` always sends `num_ctx` from `QWEN_NUM_CTX` (default 8192), and the classifier, the ADK Qwen model and later tagging calls all use it.
*Rejected:* Leaving Ollama's default, or a different context per call type.
*Why:* A different `num_ctx` makes Ollama reload the model, and its 4096 default silently cuts long prompts (course text plus history). Live check: `ollama ps` shows CONTEXT 8192 after both the classifier and the tutor call, same model, no reload.

## 2026-11-10 — Qwen answers must arrive within 240 s
*Chose:* `QWEN_TIMEOUT_S=240` wraps every Qwen call (`qwen_complete`, and the direct and fallback calls in `RoutedLlm`) and raises `QwenTimeout`; the router falls back to the default agent, chat shows "Something went wrong".
*Rejected:* No timeout (a stuck Ollama hangs the chat forever), or a tight one like 30 s.
*Why:* Measured on CPU: cold load 30 s for a short classifier call, warm classifier 4 s, a two-sentence tutor answer 7 s. Long tutor answers with course context are much slower than these, so 240 s is about 8x the cold start; it only trips on a real hang. Gemini keeps its own 30 s limit.

## 2026-11-10 — One `files` row per file is also its ingestion job
*Chose:* The `files` table holds the file and its job: `queue_pos` (unique) for order, `status`, `error`, and `pieces_done` with a `file_pieces` row per 25-page piece for checkpoints.
*Rejected:* A separate jobs table beside the files table.
*Why:* Queue order, progress and the Library list all read one row, so they cannot disagree, and a restart resumes with one query.

## 2026-11-10 — `week1_monday` is stored once on the course
*Chose:* `courses.week1_monday` is set by the course's first upload and never changed; `uploaded_week = (upload Monday - week1_monday) // 7 + 1`.
*Rejected:* Deriving week 1 from the earliest file still present.
*Why:* Deleting the first file would otherwise renumber the week label of every later file.

## 2026-11-10 — Duplicate content is refused by the database
*Chose:* `UNIQUE(course_id, content_hash)` on `files`; `add` raises `sqlite3.IntegrityError` for a repeat in the same course. NULL hashes (a web link before its snapshot) never collide.
*Rejected:* Checking `find_by_hash` first and trusting the check.
*Why:* Two uploads racing past a check would both insert; the constraint decides atomically. The same file in another course is allowed.

## 2026-11-10 — The week label uses the local calendar date
*Chose:* `week1_monday` and `uploaded_week` come from `clock().astimezone().date()`; `uploaded_at` stays ISO-8601 UTC text.
*Rejected:* The UTC date.
*Why:* A student uploading at 11 pm on a Sunday would otherwise get next week's label. Tests use 12:00 UTC clocks so they pass in any time zone.

## 2026-11-11 — Keyword search is FTS5 inside study.db
*Chose:* An FTS5 table `chunks_fts` in `study.db`, kept in step with `chunks` by `ChunksRepo` in the same transaction; each FTS row shares its chunk's rowid so deletes and joins are indexed.
*Rejected:* Chroma's hybrid (keyword) search; a separate search engine.
*Why:* Chroma's hybrid search is Cloud-only, and SQLite is already the source of truth for chunk text.

## 2026-11-11 — Tokenizer keeps underscores and stems words
*Chose:* `tokenize = "porter unicode61 tokenchars '_'"`.
*Rejected:* The default unicode61 tokenizer.
*Why:* `train_test_split` must stay one searchable term, and porter stemming lets "trees" find "tree".

## 2026-11-11 — Search queries are quoted tokens joined by OR
*Chose:* `fts_query` extracts word tokens (`\w+`), drops duplicates, double-quotes each and joins with ` OR `; no tokens means no search.
*Rejected:* Passing the student's text to MATCH, or escaping only some characters.
*Why:* Quoted tokens make FTS operators (`AND`, `NEAR`, `*`, quotes) inert, so user text can never raise a syntax error; OR with bm25 ranks chunks matching more terms higher.

## 2026-11-11 — Chunk text is stored once, in SQLite
*Chose:* `chunks` holds the text; `chunks_fts` indexes it; Chroma holds only vectors and filter metadata. Filters join `chunks` instead of duplicating columns in the FTS table.
*Rejected:* Storing text in Chroma too.
*Why:* One source of truth cannot drift; deleting a file means removing rows in SQLite plus vectors by id.

## 2026-11-11 — File ids are never reused (AUTOINCREMENT)
*Chose:* `files.id INTEGER PRIMARY KEY AUTOINCREMENT` (migration 0003 edited in place; it had never been applied).
*Rejected:* Plain `INTEGER PRIMARY KEY`.
*Why:* SQLite reuses the id of a deleted highest row, but chunk ids (`f{file_id}-…`) and `removed_chunks` records must stay unique forever, or a new file's chunks could be mistaken for removed ones.
