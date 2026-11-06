# Educational Agent: Design

*Date: 2026-11-05 · Status: draft for approval*

Items marked **(my call)** were decided by the assistant during design and were not explicitly agreed by the user. Everything else was stated or chosen by the user.

---

## 1. Intent

A personal study companion for a Master's student in Data Science. The student uploads course material each week (slides, PPTX, PDFs, books, research papers, cheat sheets, lecture transcripts as text). Everything goes into one growing knowledge base, and four AI agents work on top of it to:

1. turn material into structured notes and flashcards,
2. teach, quiz, and clear doubts until the student fully understands each concept,
3. track what the student is strong and weak at, and how that changes over time,
4. explain and review code.

**Why:** the student wants a tool they will actually rely on during their degree, and they also want to learn agentic workflows, RAG, and MCP by building a real system. The repo is public on GitHub and documents the build progress.

**Success:** during a normal semester the student can upload each week's files, ask for notes and quizzes when they need them, study through one chat, and open a Progress page that accurately shows where they need work. **All four agents must work properly; none is optional.**

## 2. Goals, non-goals, anti-goals

**Goals**
- A knowledge base that grows with any number of uploads per week, and is searchable by every agent right after processing.
- Four agents (Notes maker, Tutor, Analytics, Coding) behind one chat, plus a coordinator.
- Every AI answer, note, and quiz question is grounded in and **cites** the student's material (file plus slide, page, or line).
  - **Grounding rule (my call):** agents may add their own explanations, analogies, and worked examples. Each answer or note lists its sources. Content that doesn't come from the student's material is **labelled** ("general knowledge" or "from the web"). When neither the material nor search covers a question, the tutor still answers, clearly labelled as not from the material, rather than refusing. No per-sentence citation checking.
- Completely free to run: free-tier cloud model plus local models.
- Pure Python, runs locally on the student's laptop.

**Non-goals**
- Public hosting, multiple users, accounts, logins. This was explicitly dropped.
- Running or executing code. The coding agent reads only.
- Audio files and speech-to-text. Transcripts arrive as text.
- Automatic note, flashcard, or quiz generation on upload. These are created only when asked.
- A JavaScript or React frontend.
- Paid APIs.
- OCR of scanned or image-only PDFs. **(my call)** They fail with a clear message.
- A mobile app. PDF export covers reading away from the app.

**Anti-goals** (failures even if the app "works")
- Confident explanations or quiz answers with no traceable source.
- Agents citing material that has been deleted or replaced.
- Any course material, notes, scores, or API keys ending up in the public GitHub repo.
- The app becoming unusable when the Gemini free quota runs out.
- A flashy UI. It should be professional, calm, and pleasant to use.
- A nagging tutor.

## 3. Constraints

- **Hardware:** Dell Inspiron 16, Intel i7-1255U (low-power laptop CPU), 16 GB RAM, NVIDIA MX570 with 2 GB (too small for LLMs). Local models run **on CPU only**, with roughly 8–10 GB RAM available while the student is also using a browser.
- **OS:** Windows 11.
- **Installed already:** Git 2.51, Node.js v25, Python 3.14. The GitHub CLI is not installed.
- **Python version:** use **Python 3.12** in a project environment managed by **uv**, because some dependencies may not support 3.14 yet. **(my call)**
- **Cost:** everything free.
- **Gemini free tier:** limits are low and have changed during 2026. Third-party reports range from about 100 to 1,500 requests per day, and Google's docs now point to AI Studio for the real figures. Free-tier prompts may be used by Google to improve its products, which the student accepts for course material.
- **Language:** all Python, including the UI.
- **Agent framework:** Google ADK (Agent Development Kit), chosen by the student.
- **Project folder:** `Y:\educational agent`. The repo is **public** on GitHub.

## 4. Decisions

### 4.1 Models
| Purpose | Model | Notes |
|---|---|---|
| Heavy, quality-critical work: detailed notes, teaching, code explanation and review, analytics write-ups, quiz generation | **Gemini Flash** (current free-tier Flash model) via Gemini API | Primary |
| Light, frequent work: topic suggestion and tagging, flashcard answer grading, simple checks, short summaries | **`qwen3:4b`** via Ollama | Also the **automatic fallback for everything** when the Gemini quota runs out or Gemini errors |
| Embeddings | **`nomic-embed-text`** via Ollama | Local, so ingestion never uses Gemini quota |

- The student agreed to this split (the "split by job" recommendation).
- ADK reaches Ollama through LiteLLM.
- Routing must be a **single, simple setting** so the student can switch to "all Qwen" or "all Gemini".
- The app tracks Gemini requests used today and shows the **remaining quota** in the top bar along with the active model. **(my call)** If Gemini returns a rate-limit error, the app falls back to Qwen without failing the user's request.
- Results are cached so the same generation is never paid for twice. **(my call)**
- **When the Gemini quota is exhausted (my call):**
  - **Chat** (tutor doubts, code questions, analytics) continues on Qwen.
  - **Heavy jobs** (notes for a module or topic, generating a quiz set) are **queued until the quota resets**, with a "run on Qwen anyway (slow)" button. All heavy generation runs as resumable background jobs with visible progress.
  - Qwen may need simpler prompts or a reduced tool set to be reliable.
  - If testing shows `qwen3:4b` is too weak, `qwen3:8b` (5.2 GB) may be swapped in through the same setting.

### 4.2 Knowledge base and storage
All data lives under `data/` inside the project, and **`data/` is git-ignored**.

```
data/
├── sources/    original uploaded files, untouched
├── notes/      generated notes as Markdown (diagrams as Mermaid code blocks)
├── exports/    generated PDFs
├── chroma/     vector store
└── study.db    SQLite
```

- **ChromaDB (vector store):** holds chunks of source material, generated notes, flashcards, and quiz practice pages. Every chunk carries metadata: `course`, `module`, `topic(s)`, `source_file`, location (`page` / `slide` / `line range`), `kind` (`source` | `detailed_note` | `summary_note` | `flashcard` | `quiz_practice` | `web`), `uploaded_week`.
- **SQLite:** courses, modules, topics, files, ingestion jobs, notes index, flashcards and their review schedule, quizzes, questions, attempts and answers, logged doubts (questions asked to the tutor, with topic tags), mastery snapshots over time, tutor suggestions shown or dismissed, and Gemini usage counts.
- **Concurrency (my call):** ChromaDB is not safe for writes from several processes. Run Chroma in its own local server mode (`chroma run --path data/chroma`) and have every component use the HTTP client. **Change from the conversation:** during design I said "only the knowledge-base MCP server touches Chroma." This replaces that so the ingestion worker and the MCP server can both use it safely. SQLite runs in WAL mode and is reached through one shared data-access package.

### 4.3 Course organisation
- **Course → Module → Topic.** A course has several modules, and a module has several topics.
- **Topics are course-level (my call):** a topic that appears in several modules (for example, gradient descent in Module 2 and Module 6) is **one topic record linked to all of them**. It is shown under each module in the course map. Its mastery score covers all appearances. "All chunks for a topic" can be filtered by module when notes are made for one module.
- Material arrives **week by week, with no syllabus**. One week can contain one or more modules. **Each file belongs to exactly one module**, and a module can have many files.
- The week is kept only as a date label ("uploaded in week 5").
- **On upload:** the student picks the module for each file, or creates a new one. The app suggests a module by reading the file (for example, "Module 4: Decision Trees" on a title slide). **(my call)**
- **Topics are detected automatically** within the module (by Qwen). The app matches them against existing topics, so a topic that returns later attaches to the same record. New topics are shown for quick confirmation (accept, rename, or merge) before saving.

### 4.4 Ingestion pipeline
Triggered by every upload, for any number of files:
1. Files are queued and processed **in the background**, one after another. The Library page shows per-file status: *queued → reading → chunking → embedding → tagging → done / failed (with reason)*.
2. **Parse** to Markdown. Supported: PDF (text-based), PPTX, DOCX, TXT/MD transcripts, and web links via the Fetch MCP. Docling (better for tables, heavier) and MarkItDown (lighter) were both suggested; the builder picks or combines them, keeping CPU-only performance in mind.
3. **Chunk by structure**: per slide, per heading section, or about 500–800 words with overlap, never mid-sentence. Keep the location metadata needed for citations.
4. **Tag** topics (see 4.3), **embed** with `nomic-embed-text`, and **store** in Chroma. Record the file in SQLite.

**Safety rules** (proposed by the assistant, **agreed by the student**):
- **Duplicates skipped:** each file is fingerprinted (content hash).
- **Updated versions replace old ones:** the old chunks are removed, and notes, flashcards, and quizzes made from the old version are flagged *possibly outdated*.
- **Delete removes everything** from that file in both stores.
- **Derived content on delete or replace (my call):**
  - notes, flashcards, quizzes, and practice pages built from the file are **kept but flagged outdated**,
  - their citations to removed chunks are marked "source removed", so no agent cites them as live material.
  - The student's **quiz and flashcard history is kept and still counts** toward mastery and trends, because it measures the student's knowledge, not the file.
  - Every generated artifact therefore records which chunk IDs it came from.
- **One failure doesn't block the queue.**
- **Big files** (for example a 500-page book) are processed in pieces and **resume** after the app is closed.

### 4.5 Interface
- **NiceGUI** (pure-Python web UI on FastAPI, using Quasar components), served on `localhost` only.
- Professional and calm with one consistent colour scheme. Dark mode is optional. **Not flashy.**
- **Layout B (chosen by the student): one chat, with agents working behind it.**
  - The student types normally, and the **coordinator routes** each message to the right agent. Each reply is **labelled** with the agent's name.
  - `@tutor`, `@notes`, `@code`, `@progress` force a specific agent.
  - **Left sidebar:** course selector; the **course map** (modules → topics, each topic with a strong / okay / weak coloured dot); links to the side pages; **saved chats** (separate threads, for example a doubt session and a code review).
  - **Side pages:** **Library** (uploads and processing status, module assignment, topic confirmation, delete/replace), **Notes** (browse by module and topic, read, export PDF), **Flashcards** (due count, review), **Progress** (analytics).
  - **Inside chat:** Markdown, inline **Mermaid** diagrams, code blocks, **source citations** under each answer, quick buttons (*Quiz me on this*, *Explain simpler*), quizzes answered inline, file attachment for code.
  - **Top bar:** active course, active model, Gemini requests left today.
- The mockups from the design session are a reference for structure only. "StudyMate" was a placeholder name.

### 4.6 Agents

**Coordinator.** Routes each message to an agent (ADK multi-agent). `@mentions` bypass routing. Routing should use as little Gemini quota as practical; the mechanism is left to the builder (see §6).

**Notes maker**
- Works **only when asked** (for example, "make notes for Module 3" or "notes on gradient descent").
- For each topic it produces:
  - **Detailed notes:** every sub-topic, beginner-friendly explanations, worked examples, and line diagrams or flowcharts (Mermaid) where helpful.
  - **Summary notes:** short notes for quick revision.
  - **Flashcards:** front and back, each with topic and source citation.
- Pulls **all chunks for the topic** from the knowledge base. Large topics need a split-and-combine approach.
- Output is saved as Markdown in `data/notes/<course>/<module>/`, indexed in SQLite, and **embedded into Chroma** (kinds `detailed_note` / `summary_note` / `flashcard`) so other agents can search it.
- Regenerating keeps the previous version. **(my call)**

**Tutor**
- Clears doubts, and **teaches** concepts the student doesn't understand. The goal is thorough understanding, so after explaining it checks understanding with a short question. Uses flowcharts and line diagrams along with text.
- Answers come from the student's material with citations. **Web search and arXiv are fallbacks only**, used when the material doesn't cover the question, and anything from them is **clearly labelled as outside course material**. **(my call)**
- Every doubt is logged with its topic for analytics.
- **Hands off code questions to the Coding agent** rather than duplicating it. **(my call; the student accepted the suggestion)**
- **Runs flashcard reviews:** shows due cards. The student can type an answer (Qwen grades it and suggests a rating) or reveal it and self-rate. Repeated misses can turn into a mini-lesson.
- **Module quizzes:** see 4.7.
- **Targeted quizzes:** extra short quizzes, separate from the module quizzes, on topics analytics marks weak.
- **Raises weak topics on its own** (the student's choice). When **(my call)**:
  - at the start of a new chat, with the weakest one or two topics as a "Practice now" button,
  - right after a quiz that reveals a weak spot,
  - during a related doubt session,
  - at most **once per topic per session**, and the student can dismiss it.

**Analytics**
- **Mastery score per topic (0–100)** computed in **plain code, not by the LLM**:
  - inputs: quiz answers and flashcard reviews,
  - hard questions weigh more,
  - recent attempts weigh more.
  - Exact formula left to the builder within these rules.
- **Extra signals:**
  - **doubt frequency** and repeated doubts, plus "Explain simpler" usage, as a confusion signal,
  - **misconceptions:** recurring wrong-option patterns, named specifically (for example "confuses precision and recall"),
  - **forgetting:** a well-scored topic whose flashcards are now missed.
- **Progress page:**
  - modules with topics coloured strong / okay / weak,
  - drill-down to the **exact questions and concepts** being missed,
  - trend over time per topic (**improving / flat / slipping**) as charts,
  - full quiz history.
- **Weak threshold:** about 60. Topics below it feed the tutor's targeted practice.
- **"How am I doing?" in chat:** the agent writes a profile **from computed numbers only**, so it never invents statistics.
- Mastery is **snapshotted over time** (for example, daily) to support trends.

**Coding agent**
- Input: pasted snippets, attached files, or a multi-file project in **one student-chosen folder** (read-only filesystem MCP).
- **Explains** in beginner-friendly terms:
  - the overall picture and purpose,
  - the flow (with a Mermaid flowchart),
  - each function,
  - line-by-line detail where the code is tricky.
- **Reviews:** finds errors and bugs, suggests improvements, and helps debug by reasoning.
- **Runs nothing.** The student chose this.
- Can search the knowledge base for related course code.

### 4.7 Module quizzes (student's specification)
- **All multiple choice.** Each question has a difficulty: easy, medium, or hard.
- **Each module gets a set of 3 quizzes** covering all its topics:

| | Easy | Medium | Hard |
|---|---|---|---|
| Quiz 1 | most | some | 1–2 |
| Quiz 2 | a few | a few | 3–4 |
| Quiz 3 | **none** | the rest | **at least 7** |

- **Size: fixed at 20 questions per quiz** (student's choice). Exact split **(my call)**: Q1 = 12 easy / 6 medium / 2 hard · Q2 = 6 / 10 / 4 · Q3 = 0 / 10 / 10.
- **Topic coverage (my call):** every topic in the module appears **at least once across the set of 3 quizzes** (60 questions), with questions spread as evenly as the topic count allows.
- Generated **only when asked**.
- **Growing modules:** if new files and topics arrive after a module's quizzes exist, the quiz set shows a **"new topics not covered yet"** flag. It is regenerated **only when the student chooses** (student's choice). The old set and its attempts are kept.
- **Each question (my call):** 4 options with exactly one correct; topic; difficulty; source citation; an **explanation for every option** (why right or why wrong).
- **Generated quizzes are validated in code** before they're shown: difficulty counts, exactly one correct option, every question has a citation, no duplicates. Invalid output is regenerated. **(my call)** This matters most when Qwen is the active model.
- **Taking a quiz** happens in the chat, with clickable options. Feedback and explanations appear **after each question**. **(my call)**
- **Retakes (my call):** the same quiz can be retaken (option order shuffled), and all attempts are kept. "New version" generates a fresh set and keeps the old one.
- **Storage:** questions, answers, and attempts go to SQLite. **Each quiz is also saved as a readable practice page** in the knowledge base (questions, correct answers, explanations, and the student's picks), so the student can reread it and the tutor can search it.

### 4.8 Spaced repetition
- Flashcards are scheduled by a **plain-code** spaced-repetition algorithm, not an agent. **(my call)**
- Cards answered wrong come back sooner, and cards answered right are spaced further apart.
- The algorithm is left to the builder (for example, SM-2 or FSRS).

### 4.9 PDF export
- An **Export PDF** button on notes pages, quiz practice pages, and flashcard sets.
- **Playwright** (headless browser) prints the rendered page, so Mermaid diagrams, code, and formatting come out exactly as in the app. **(my call)**
- Print layout: title, module and topic, date, page numbers, sources at the end.
- Saved to `data/exports/`.

### 4.10 MCP servers
| Server | Built or existing | Used by | Purpose |
|---|---|---|---|
| **Knowledge base** | **Built** (Python MCP SDK / FastMCP) | Notes, Tutor, Coding | Search material, get all chunks for a topic, save notes, flashcards, and practice pages |
| **Study records** | **Built** (Python MCP SDK / FastMCP) | Tutor, Analytics | Save quiz answers, get weak topics, get due cards, scores over time, log doubts |
| Filesystem | Existing (read-only, one folder) | Coding | Read multi-file projects |
| Fetch | Existing | Ingestion | Add a web page to the knowledge base |
| Web search (DuckDuckGo-based, no key) | Existing | Tutor | Fallback when material doesn't cover a question |
| arXiv search | Existing | Tutor | Related papers |

- **Run model:** all on the laptop. ADK's `McpToolset` starts each server as a **child process over stdio** (no ports), starting and stopping with the app.
- **Tool docstrings and type hints are the agents' tool descriptions** and must be written carefully, especially for Qwen.
- Each built server must be testable on its own with **MCP Inspector**.
- The exact community servers for search and arXiv should be checked as current at build time. The existing servers run on Node.js.
- **Not MCP:** diagrams (the UI renders Mermaid), charts, the spaced-repetition scheduler, mastery calculation, routing.

### 4.11 Process architecture (all local)
```
Browser ⇄ Main Python app (NiceGUI + ADK agents + upload queue + model router)  :8000
              ├─ Gemini API (internet)
              ├─ Ollama  :11434  (qwen3:4b, nomic-embed-text)
              ├─ Chroma server (data/chroma)
              └─ MCP servers via stdio: knowledge-base, study-records, filesystem, fetch, web search, arXiv
                     └─ data/study.db, data/sources, data/notes
```
**One command starts everything.**

### 4.12 Repository and GitHub
- **Public** repo, MIT licence. **(my call)**
- `.gitignore` covers `data/`, `.env`, the virtual env, and `.superpowers/`. The repo includes a `.env.example`.
- **Never commit course material, notes, scores, or keys.** Any demo content must be freely licensed.
- README with screenshots and setup steps.
- **Commit often** so history shows progress. The student wants to manage the project on GitHub (issues, progress), and installing the GitHub CLI is optional.

### 4.13 Build order
**No deadline** (student). Everything is in scope; this is order only:
1. knowledge base and ingestion,
2. notes maker,
3. tutor (with quizzes and flashcards),
4. analytics.

Each agent is finished properly before moving on. The coding agent can be built in parallel at any point. The UI shell and model routing come first, since everything sits on them.

### 4.14 "How it works" page (system map with live path and replay)
A separate page that visualises every component of the project and how they connect, in the spirit of node-based workflow tools. **The student will show this page to other people to explain the project's technical design**, so it must make sense to non-technical viewers and hold up to technical ones.

**Structure map (student's choice, combined with live path):**
- **Zoom levels:**
  - **Level 1 (overview):** 5 nodes: Interface → Agents → Tools (MCP) → Knowledge (Chroma + SQLite) → Models (Gemini + Qwen).
  - **Level 2:** clicking a node expands it, for example Agents opens into Coordinator, Notes, Tutor, Analytics, Coding.
  - **Level 3:** clicking an agent shows its tools, and clicking a tool shows its inputs, outputs, and the database it touches.
  - Expanded nodes can be collapsed again. **(my call)**
- **Each node has two tabs (my call):**
  - **"What it does":** 1–2 plain-English sentences.
  - **"Technical":** model, tool list, function signature, DB tables or collections, live item counts, and the repo file where it's implemented.
- **Generated from the running system, not hand-drawn (my call):** the agent tree is read from ADK, tool lists come from each MCP server (`list_tools`), and counts come from the databases. The plain-English descriptions live next to each component in code, so the map never goes stale. Only the Level-1 grouping and layout are defined by hand.

**Live path and replay (student's choice):**
- **Tracing (my call):** every request records each step (routing decision, agent, tool call with inputs and outputs, model used, tokens, duration, fallback events) into SQLite. This is built on ADK's event stream.
- **Live:** while a message is processed, the nodes it passes through **light up in order** on the map.
- **Replay:** any past request can be replayed step by step. Clicking a step shows exactly what went in and came out.
- **Two journeys (my call):**
  - a **chat message's** journey (coordinator → agent → tools → models → answer),
  - a **file upload's** journey (parse → chunk → embed → tag → store), which shows RAG visibly.

**Demo mode (my call):**
- Slow replay with a **caption under each step** explaining it.
- **Pinned showcase replays**, so demos don't depend on a live request.
- A **"hide content" switch** that blurs the student's questions and course text while keeping the mechanics visible.
- **API keys never appear** on this page.

**Technology:** **pure Python** (student's choice). NiceGUI's built-in **ECharts graph**, styled to look clean and professional. Click-to-expand is done by redrawing the graph from Python, and the step-by-step lighting is driven by Python timers. No custom JavaScript.

**Build order:** step tracing is built alongside the UI shell and model routing, since it's also the main debugging tool. The page itself is built after the coding agent (or whenever all components exist). Level 1 can appear early and fill in as components are added. **(my call)**

### 4.15 Who builds it, and how it's taught
- **The assistant (Claude) writes the code. The student reviews and steers** (student's choice).
- **Teaching alongside is a requirement, not an extra.** For each step the assistant explains:
  - **what** the code does,
  - **why** it's needed (its purpose in the system),
  - **why this way and not another**: the alternatives considered and why they were rejected.
- The plan is broken into **small, understandable steps** with a natural point after each to ask questions before moving on.
- A running **`docs/decisions.md`** records each significant "why this, not that" choice in a few lines, so the reasoning lives in the repo for later review and for anyone reading the GitHub project. **(my call)**

## 5. Install list (for the README)
- **Ollama** (Windows installer), then `ollama pull qwen3:4b` and `ollama pull nomic-embed-text`.
- **uv**, then a Python 3.12 environment.
- **Python packages:** `google-adk`, `litellm`, `mcp`, `chromadb`, `nicegui`, `playwright` (plus `playwright install chromium`), and the parsing libraries.
- **Gemini API key** from Google AI Studio, stored in `.env`.
- **Node.js** is already installed (for the existing MCP servers).

## 6. Left to the builder
- Exact Gemini model ID, and how quota is counted and reset.
- Coordinator routing mechanism within the quota constraint. For example: `@mention` bypass, follow-ups stay with the current agent, and a cheap classification step otherwise.
- Parser choice (Docling, MarkItDown, or both), chunk sizes, and whether to add keyword/hybrid search or reranking.
- The exact mastery formula, trend window, and snapshot frequency.
- The spaced-repetition algorithm.
- The SQLite schema details and the shared data-access layer.
- Prompt design for each agent, and how large topics are split for note generation.
- The project layout, and the test strategy. Core logic (ingestion, scheduler, mastery, quiz validation, data access) must have automated tests; agent quality needs at least a small manual check set.
- UI styling details within "professional, calm, not flashy."
