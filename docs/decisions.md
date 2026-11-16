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
*Chose:* An FTS5 table `chunks_fts` in `study.db`, kept in step with `chunks` by `ChunksRepo` in the same transaction; each FTS row's rowid is the chunk's explicit integer key (`chunks.rid`, stable across VACUUM) so deletes and joins are indexed.
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
*Why:* SQLite reuses the id of a deleted highest row, but chunk ids (`f{file_id}-…`) and `removed_chunks` records must stay unique forever, or a new file's chunks could be mistaken for removed ones, and an old citation to a deleted chunk would show the new file's text.

## 2026-11-11 — Chunks have an explicit integer key for the keyword index
*Chose:* `chunks.rid INTEGER PRIMARY KEY` with `id TEXT NOT NULL UNIQUE`; each `chunks_fts` row uses `rid` as its rowid, and the upsert (`ON CONFLICT(id) DO UPDATE … RETURNING rid`) keeps `rid` when a chunk is overwritten (migration 0003 edited in place; it had never been applied).
*Rejected:* Using the implicit rowid of a table whose primary key is the text `id`; linking FTS rows by the `chunk_id` text column.
*Why:* SQLite only keeps rowids stable for tables with an explicit `INTEGER PRIMARY KEY`; VACUUM may renumber the others, which would silently join search hits to the wrong chunk text. The text column is not indexed inside FTS5, so linking by it would scan the whole index on every delete.

## 2026-11-11 — Chroma runs as its own `chroma run` server, not embedded
*Chose:* The launcher starts the Rust `chroma run --path data/chroma --host 127.0.0.1 --port 8001` and every component talks to it with `HttpClient`.
*Rejected:* `PersistentClient` (embedded) and the Python FastAPI server.
*Why:* The app and the KB MCP server are separate processes that both write; an embedded store allows only one process to own the files. The Python server is affected by CVE-2026-45829.

## 2026-11-11 — An already-running Chroma on the port is reused
*Chose:* `ChromaServer.start()` returns ready if the heartbeat already answers; `stop()` only stops a process this object started.
*Rejected:* Failing, or killing whatever holds the port.
*Why:* A second app start or a leftover server must not break the first or lose its data; we never stop something we did not start.

## 2026-11-11 — Chroma holds vectors and filter metadata only
*Chose:* Vector id = chunk id; metadata `chunk_id, course_id, module_id (0 = none), origin, file_id, kind, uploaded_week`; no text.
*Rejected:* Storing chunk text in Chroma.
*Why:* One copy of the text (SQLite); moving a file is one metadata update, deleting is `delete(where file_id)`.

## 2026-11-11 — Chroma never gets an embedding function, and telemetry is off
*Chose:* The collection is created with `embedding_function=None` (we always pass our own vectors) and `configuration={"hnsw": {"space": "cosine"}}`; the client uses `Settings(anonymized_telemetry=False)` and as a best effort the server process also gets `ANONYMIZED_TELEMETRY=False` and `CHROMA_ANONYMIZED_TELEMETRY=False` (`chroma run --help` documents no telemetry flag, so these are set in case the server reads them).
*Rejected:* Chroma's default embedding function; default telemetry.
*Why:* The default would download an ONNX model to `C:\Users\...\.cache`, against the models-folder rule; the app is local and personal, so nothing should be reported out.

## 2026-11-11 — Only a Chroma server we can prove is ours is reused (R12)
*Chose:* When the launcher starts Chroma it writes `data/chroma_server.json` (pid, port, resolved chroma folder), beside `data/chroma`, and removes it when it stops the server. A server already answering the heartbeat is adopted (and stopped on exit) only if the marker matches our port and folder and its pid is alive; otherwise start returns the "didn't start ... port N is already used by another program" warning and never touches that server. A stale marker is overwritten by the next launch.
*Rejected:* Reusing any server that answers the heartbeat (the earlier behaviour).
*Why:* After a crash the orphan would be reused forever and never stopped, and the app could silently attach to someone else's Chroma (other data folder, a Python server, or one bound beyond localhost), breaking the Rust-only, localhost-only rule. Failing closed costs one warning.

## 2026-11-11 — Model cache variables are overridden, not defaulted (R13)
*Chose:* `configure_model_dirs` always sets `HF_HOME`, `FASTEMBED_CACHE_PATH` and `DOCLING_ARTIFACTS_PATH` to folders under `models_dir`, and logs at INFO when it replaces an existing different value.
*Rejected:* `os.environ.setdefault`.
*Why:* A `HF_HOME` already pointing at the user's `.cache` folder would send downloads there and break "all models live under data/models".

## 2026-11-16 — fastembed runs the reranker
*Chose:* fastembed `TextCrossEncoder("Xenova/ms-marco-MiniLM-L-6-v2")` with `cache_dir` under the models folder, loaded on first use. It pulled in no torch (only loguru, pillow, py-rust-stemmers, win32-setctime).
*Rejected:* FlashRank; sentence-transformers (needs torch).
*Why:* ONNX only, ships the exact MiniLM-L6 cross-encoder the design names, and its cache folder can be pointed at `data/models`.

## 2026-11-16 — `truncate: false` + a 1,500-token cap counted with the model's tokenizer (R15)
*Chose:* Every `/api/embed` call sends `"truncate": false`. The embedder counts the whole input (prefix + header + chunk) with nomic-embed-text's own `tokenizer.json` (`nomic-ai/nomic-embed-text-v1.5`, pinned revision, fetched once into `data/models/hf`, offline afterwards) and raises "A piece of text was too long for the embedding model." before sending if it exceeds `MAX_EMBED_TOKENS = 1500`. The count includes special tokens and equals Ollama's `prompt_eval_count` exactly. It never sends `num_ctx`, and sends `num_gpu: 0` unless `OLLAMA_USE_GPU` is on (R14).
*Rejected:* A character cap (`MAX_EMBED_CHARS = 4500`); letting Ollama truncate; sending the Qwen options.
*Why:* Silent truncation was measured on 2026-11-09 and would index only the start of a chunk. Characters per token vary too much for one cap to be both safe and roomy: prose runs at 5.1 chars/token (a 4,247-char fixture was 831 tokens), code at 2.2 (4,497 chars was 2,044 tokens, just under the limit), numeric tables and LaTeX at 1.7 (a 4,497-char input returned HTTP 400 `the input length exceeds the context length`). A real token count is safe for all of them. The laptop's 2 GB GPU crashed Ollama on CUDA init, and the limits were measured on CPU with the model's own 2048-token context.

## 2026-11-16 — `clustering:` prefix for topic-name similarity
*Chose:* Topic names are embedded with nomic's `clustering: ` prefix (`embed_labels`), separate from `search_document: ` and `search_query: `.
*Rejected:* Reusing the document or query prefix for names.
*Why:* Comparing short labels with each other is a clustering task; nomic-embed-text defines that prefix for it.

## 2026-11-16 — Own regex sentence splitter
*Chose:* A ~30-line regex splitter (`kb/sentences.py`). It ends a sentence at `.`, `?` or `!` (plus closing quotes or brackets) followed by whitespace, and protects the abbreviations `e.g., i.e., etc., vs., Fig., Eq., Dr., al., approx.` (case-insensitive), decimals and single-capital initials.
*Rejected:* nltk / spaCy / pysbd.
*Why:* The chunker only needs sentence-sized pieces to pack, not linguistic accuracy, and a regex adds no dependency or model download. A sentence that truly ends in one capital letter ("model B. Then") will not split; that is an accepted trade-off.

## 2026-11-16 — One `Block` model for every parser
*Chose:* Every parser (text, Markdown, Docling, web) emits `Block(text, kind, level, loc, loc_end)`, defined in `kb/types.py`.
*Rejected:* Letting the chunker handle each file format.
*Why:* The structure-aware chunker never sees a file format, so adding a format means writing one parser and nothing else.

## 2026-11-16 — Newline boundaries in the sentence splitter (R16)
*Chose:* A blank line always ends a sentence. A single newline ends one only when the next line starts with a list marker (`-`, `*`, `•`, or a number then `.` or `)`). Any other single newline is ordinary whitespace.
*Rejected:* Treating every newline as a boundary.
*Why:* Hard-wrapped TXT files and transcripts must not be cut mid-sentence, while bullet lines without full stops still become separate sentences.

## 2026-11-16 — Splitter and parser fidelity (R17)
*Chose:* `split_sentences` returns stripped substrings of the input in order, so no text is added, rewritten or lost apart from whitespace. `parse_markdown` keeps fence lines (with the language tag) in a code block's text, and an unclosed fence runs to the end of the document, as in CommonMark.
*Rejected:* Rebuilding sentences or dropping fence lines.
*Why:* Chunk text must be quotable from the source exactly, and the language tag helps the tutor read code.

## 2026-11-16 — Numbered lines are boundaries only after a finished line (R18)
*Chose:* A single newline before a bullet (`-`, `*`, `•`) is always a sentence boundary. A single newline before a numbered marker (1–2 digits then `.` or `)`) is a boundary only when the previous line ends with `.`, `?`, `!` (plus closers) or `:`, or itself starts with a list marker. The "line-leading number is not a sentence end" protection applies to 1–2-digit numbers only, so a year like `1986.` still ends a sentence. This replaces the numbered-list part of R16.
*Rejected:* Cutting before every line that starts with a number.
*Why:* Hard-wrapped text often wraps right before a number ("The answer was\n42. Then..."); cutting there splits a sentence in half. Under-splitting is safe, mid-sentence cuts are not. The splitter also looks back over a bounded window only, so a transcript pasted on one line splits in linear time.

## 2026-11-16 — Chunk sizes at the low end of 500–800 words
*Chose:* Sections are cut at 450–550 words (hard maximum 800, 2-sentence overlap), text windows at 400–500 words with about 15% whole-sentence overlap, slides one per chunk with slides under 25 words merged.
*Rejected:* The 500–800-word middle of the spec's range, and fixed-size windows everywhere.
*Why:* Chroma (2024) and NVIDIA (2025) studies favour about 250–500 tokens for factual questions, and section-following chunks beat fixed windows slightly but consistently (Kuehlkamp 2026).

## 2026-11-16 — Heading path goes into the embedding text only
*Chose:* Heading blocks feed `heading_path` and are not repeated in the chunk text; `embedding_text` adds `title > heading path` in front. The Ingestor passes `embedding_body` (the same without the prefix) to the embedder, which adds `search_document: ` itself (R21).
*Rejected:* Storing the heading inside the chunk text, or adding the prefix in two places.
*Why:* Stored and shown text stays the exact quotable source, the keyword index has its own heading column, and the document prefix is applied exactly once.

## 2026-11-16 — Overlap only where boundaries are arbitrary
*Chose:* Overlap in section-split documents and text windows only. Slides and DOCX sections get none.
*Rejected:* Overlap everywhere.
*Why:* A slide or a heading section is already a natural unit; overlap only helps where we cut inside running prose, and with a strong embedding model it added little.

## 2026-11-16 — Heading levels are kept across pieces (R20)
*Chose:* Carried and returned open paths are `(level, text)` pairs; a heading of level L drops every open entry of level L or deeper, then is pushed. Slides use the first heading on the slide, no stack. Lists from the JSON round trip are accepted.
*Rejected:* Carrying bare heading texts.
*Why:* Without levels, a new heading cannot tell which carried headings it closes, so a piece starting mid-chapter would give wrong paths.

## 2026-11-16 — The only cuts that are not at a sentence end (R21/R22)
*Chose:* Cuts mid-sentence happen only when a "sentence" is over the layout's word maximum (split at word boundaries into window-sized pieces) or when a table, code or formula block is over the cap or 800 words (split by lines, then whitespace, then characters). The cap is the whole embedding text in tokens, title and heading path included, for every layout; slides over the cap are split by lines and keep their slide number.
*Rejected:* Letting an oversize block through, or truncating at embedding time.
*Why:* Ollama rejects inputs over the context with HTTP 400 (truncation is off), and a transcript without punctuation or a wide table must still be searchable and finish ingesting.

## 2026-11-16 — Slide merging and locations
*Chose:* Short slides merge forward until the chunk has 25 words (speaker notes count), the last short group merges back, and a merge that would pass the cap is skipped. Locations are the min/max of the contributing blocks; text and Markdown count lines per sentence, so a window cites only its own lines; web and DOCX pass block locations through.
*Rejected:* Citing the whole block for every window.
*Why:* A citation should point at the lines the chunk actually contains.

## 2026-11-16 — Headings that are not in the path stay in the text (R23)
*Chose:* A heading whose text is not in the chunk's `heading_path` stays in the chunk text on its own line: titles of later slides in a merged group, extra headings on one slide, and every heading inside a DOCX whole-document chunk. A title-only slide contributes its title as text when nothing else carries it. Headings that are in the path are not repeated. Atomic blocks are split only over 800 words or the cap, oversize slides go through the normal sentence path, and forced pieces keep their own newlines and line numbers.
*Rejected:* Dropping such headings, or repeating every heading in the text.
*Why:* A slide title is often the only place a term appears, so losing it makes that slide unfindable by keyword; repeating path headings would only add noise.

## 2026-11-16 — Docling with formula enrichment, picture-only OCR, models under data/models
*Chose:* Docling (2.150.1 installed) parses PDF, PPTX and DOCX with formula enrichment on; a formula it cannot decode becomes the marker `[formula, see page N]` (or `slide N`). OCR is RapidOCR (English, onnxruntime) in `OcrMode.PDF_AWARE_LAYOUT_REGIONS`, which skips regions that already carry PDF text and reads only pictures and bitmaps. Speaker notes come from `ContentLayer.NOTES` and become `notes` blocks. All Docling and RapidOCR models are fetched once into `data/models/docling` (marker file `.ready` stops later network checks); the picture classifier is not downloaded.
*Rejected:* `OcrMode.FULL_PAGE` (slow, and re-reads good text), Docling's default RapidOCR download into the package folder.
*Why:* Formulas are common in the course material and a visible marker beats silent loss; text pages must not pay for OCR; nothing may land in the user's C: cache.

## 2026-11-16 — Landscape majority means slides; pypdfium2 checks before Docling
*Chose:* A PDF whose pages are mostly landscape is laid out as "slides", otherwise "document". pypdfium2 does the page count, orientation, text-layer check, password and not-a-PDF checks (plain-English `IngestError`) before the slow Docling run, in 25-page ranges.
*Rejected:* Sending every file to Docling first and failing there.
*Why:* A locked, fake or scanned file should fail in milliseconds with a reason the student can act on.

## 2026-11-16 — Docling failures become plain reasons; model marker records what was fetched
*Chose:* `RuntimeError` and `ConversionError` from Docling both become "This file couldn't be read…"; a failed model download becomes "Couldn't download the PDF reading models…". The `.ready` marker lists what was fetched (`base`, `formula`), so turning formula enrichment on later fetches only CodeFormula. Word files get the marker "[formula, see the original document]"; items spanning pages cite the full page range.
*Rejected:* Letting Docling's RuntimeError escape, a marker that only says "done".
*Why:* A bad file or a missing network must fail that one file with a reason, never crash the queue.

## 2026-11-16 — Hybrid search: TM2C2 fusion, per-origin pipelines, relevance floor only moves slots
*Chose:* Dense (Chroma) and keyword (FTS5) top 30 are fused per origin (module material, books) with TM2C2 at alpha 0.6 (cosine similarity normalised from -1, keyword score from 0; a candidate missing from one list scores 0 there), the fused top 30 of each origin are reranked separately, and the 10 results are split 70/30 by `allot_slots`. A chunk is relevant when its rerank score is at least `RERANK_RELEVANT_MIN = -2.8`. Rule R27: each group starts with its share (7 and 3); a group's slots it cannot fill with relevant chunks move to the other group only when that group has MORE relevant chunks than its own share (so no slot is given to irrelevant chunks), both are capped by what exists, and slots nobody could take go back to a group that still has chunks, so the floor never empties results. With the reranker off every found chunk counts as relevant and only an empty group gives slots away. Calibration (6 fixed questions, fixtures in `tests/kb/test_search_live.py`, exact printout in `tests/kb/search_calibration.md`): the best answer per question scored 0.65 to 9.20 and the highest non-answer per question at most -1.69 (gap 2.34 between the lowest best answer and the highest non-answer). The labels overlap: one supporting ridge-regression page labelled relevant scored -2.20, below an adjacent but unhelpful slide at -1.69, so no threshold separates every labelled chunk. First run used 0.0: that counted only 3 ridge chunks as relevant, which equals the book's share of 3, so the book-only ridge question returned 3 book chunks instead of 10 under R27. The floor is therefore set at -2.8, midway between the lowest labelled answer (-2.20) and the highest clearly unrelated chunk below it (-3.39); with it all six questions meet their expected outcome. The adjacent chunk (-1.69) counts as relevant, which only costs a slot move. Total time per query 520-710 ms warm on this CPU (embedding 95-230 ms, rerank 370-550 ms for 30+30 chunks). Revisit on real course material; six questions are thin evidence.
*Rejected:* A hard floor that drops low-scoring chunks (a weak but real match must still come back), RRF fusion (design 3.6), a floor below -2.2 (it would count adjacent but unhelpful slides as relevant).
*Why:* Design 3.6: alpha 0.6 lets keyword-only hits into the shortlist; separate pipelines stop one book's hundreds of chunks from crowding out a week of slides; a floor that only moves slots keeps "a question only the book covers returns up to 10 book chunks" without ever returning nothing.

## 2026-11-16 — The reranker loads its model under a lock
*Chose:* `Reranker.score` loads the cross-encoder once behind a double-checked `threading.Lock`.
*Rejected:* Loading in `__init__` (would make start-up slow and break the "import loads nothing" rule).
*Why:* The tutor and the ingestion thread can both search; two simultaneous first calls must not load the model twice.
