# Plan 2: Knowledge Base and Ingestion (Design)

*Date: 2026-11-10 · Status: draft for the student's approval*
*Parent spec: `docs/superpowers/specs/2026-11-05-educational-agent-design.md` (binding where this document does not say otherwise). Roadmap row: Plan 2 in `docs/superpowers/plans/2026-11-06-roadmap.md`.*

Items marked **(my call)** were decided by the assistant and not explicitly agreed by the student. Everything else was stated or chosen by the student during brainstorming on 2026-11-09/10. Research behind each choice is summarised with sources so the plan can cite it.

---

## 1. Intent

Plan 2 gives the app a knowledge base: the student adds each week's material, the app turns it into searchable, citable chunks, and agents can search it. Every later plan (notes, tutor, analytics, coding) reads from it.

**Why:** the spec's core promise is that every answer, note and quiz question cites the student's own material (file plus slide, page or line). That only works if ingestion keeps exact locations and search reliably finds the right chunk, including for exact terms such as `train_test_split` or "Gini index".

**Success for this plan:** the student uploads a week's slides, pastes a transcript and adds a book; each file shows live status in the Library and finishes (or fails with a plain reason); the student reviews and saves topics per file; the course map shows the topics; and a question in chat makes the Tutor search the material and name the slide or page it used. Upload and search steps appear in traces.

## 2. Scope

From the roadmap (spec §4.2–4.4, 4.10, 4.14), with the changes in §4 below:
- Chroma server started and stopped by the launcher.
- Parsers, structure-aware chunker, embeddings, keyword index, hybrid search with reranking.
- Topic tagging with per-file review (accept / rename / merge / drop), module suggestion on upload.
- Resumable background job runner and upload queue.
- Library page.
- Safety rules: duplicates skipped, replace, delete.
- Knowledge-base MCP server (FastMCP, stdio).
- Web links (by httpx + trafilatura, not the Fetch MCP; see §4).
- Upload traces (`parse / chunk / tag / embed / store` steps) and retrieval traces (KB tools return a `trace` section saved into the `tool_result` step).
- The Tutor gets the KB search tool so the end-to-end check can show retrieval in chat. **(my call, implied by the roadmap's `tool_result` requirement and the carry-forward items about tools)** Full grounding rules (labels, web fallback, citation format) stay in Plan 4.
- All Plan 2 carry-forward items from Plan 1 (§7).

**Non-goals for Plan 2:** notes, flashcards, quizzes (Plans 3–4); "save note / flashcard / practice page" KB tools (added by the plans that create those things); OCR of whole scanned documents, photos or handwriting; JavaScript-rendered web pages; a Pause button (student declined).

**Anti-goals (from the spec, sharpened):** a chunk cited after its file was deleted or replaced; formulas silently disappearing from PDFs; menus and footers of web pages becoming "material"; course material or models committed to git; the app crashing on a bad file.

## 3. Decisions made with the student

### 3.1 How material arrives
- **Per module**, the student can: upload files (PPTX, PDF, DOCX, TXT, MD), **paste text** (lecture transcripts, with a title), or **add a web link**.
- Most material is **slides**. PDFs are mostly **books**. Transcripts are **pasted as raw text**.
- **Books are course references, not module material.** The student dips into books as a reference. A book is attached to the course, has **no module and no topic tags**, never appears in topic review, and is found by search (by the Tutor and, later, the Notes maker). Reason: tagging a 500-page book would mean ~700 Qwen calls and hundreds of topics to review, and tags made in week 1 would never pick up topics that arrive in week 8; search always uses current topics. *This changes the spec's "each file belongs to exactly one module" rule for books only.*
- Pasted text is saved as a `.txt` source in `data/sources/` so citations point to line ranges like any text file. **(my call)**

### 3.2 Parsing
- **Docling** for PDF, PPTX and DOCX. **Own splitter** for TXT, MD and pasted text (no parser needed).
  - Research (Docling 2.149, 2026-11): best scores among local, permissive-licence parsers on opendataloader-bench (overall 0.882, tables 0.887, headings 0.824); per-item page numbers and slide numbers (`prov.page_no`); `page_range` support for big files; MIT licence.
  - Rejected: **MarkItDown** (no page boundaries in PDFs, headings score 0.00); **PyMuPDF / PyMuPDF4LLM** (AGPL, unsuitable for a public MIT repo).
  - Cost: Docling pulls in torch plus ~0.5 GB of layout and table models (~1.3 GB installed). Published CPU speed is ~1–2 s per PDF page with OCR off (server benchmarks). **The student chose not to time it on this laptop**; figures are published, not measured.
- **PPTX:** Docling's PowerPoint reader also extracts **speaker notes** and converts **equation-editor formulas to LaTeX** with no model. Known gap: an equation inside a table cell is likely lost (cells are read as plain text).
- **DOCX:** no page numbers exist in DOCX, so citations use the heading path. **(my call)**
- **Scanned content:** there are **no scanned pages in slides**. Books may contain **tables pasted in as pictures**. So: OCR runs **only on picture areas of PDF pages** (Docling's OCR limited to bitmap regions; builder confirms the exact option), so text pages stay fast. Whole scanned documents, photos and handwriting stay out of scope. A PDF with no text layer at all fails with a clear message (cheap check before conversion).
- **Formulas in PDFs: formula reading is ON for every PDF** (`do_formula_enrichment`, model CodeFormula, 0.2B parameters, MIT). Without it Docling replaces each PDF formula with `<!-- formula-not-decoded -->` (confirmed by Docling maintainers, issue #1631). CPU cost per formula is unpublished (expected seconds each). A `.env` setting can turn it off. A formula the model can't read is written as a visible marker, e.g. `[formula, see page 42]`, never silently dropped.

### 3.3 Web links
- **httpx + trafilatura**, run inside the upload worker. **This replaces the spec's Fetch MCP for ingestion.** Student-approved.
  - Research: trafilatura 2.3 scored the best F1 among local, non-AI extractors on three independent benchmarks: its own (0.926, 990 pages, 2026-10), WCXB (0.833 test vs Readability 0.726), Sandia 2024 (0.937, best mean). The Fetch MCP uses Readability (lower in all three), returns pages in 5,000-character slices, runs as a separate process and may `npm install` on first use. It suits an agent reading a page in chat, not a background upload. Plain HTML-to-text converters (html2text, markdownify) don't remove boilerplate (F1 ~0.66–0.69). Hosted readers send links to third parties.
- Flow: validate URL (http/https only; refuse loopback, private and link-local addresses, re-checked on every redirect); check `robots.txt` (stdlib `urllib.robotparser`); download with timeout and size cap; **if the response is a PDF, save it and send it through the PDF path**; else extract main content as Markdown (tables kept, title/author/date metadata); **save the Markdown snapshot to `data/sources/`** so citations survive the site changing; chunk with the Markdown splitter; citation = URL + section heading.
- **Too little text (roughly under 200 words) fails** with: *"This page needs a browser to load its content. Save it as PDF from your browser and upload that instead."* Covers JavaScript-only pages and login walls. A headless-browser fallback can be added once Playwright exists (Plan 3), not in Plan 2.

### 3.4 Chunking
Research: Chroma (2024) and NVIDIA (2025) chunking studies favour ~250–500 tokens for factual questions (most studying); section-following chunks beat fixed windows slightly but consistently (Kuehlkamp 2026); with a strong embedding model overlap added little. So we sit at the **low end** of the spec's 500–800 words.

| Material | Rule | Overlap | Location kept |
|---|---|---|---|
| Slides (PPTX or slide PDFs) | One chunk per slide, speaker notes included; slides under ~25 words merged into the next | none | slide number or range |
| Books, papers, other portrait PDFs | One chunk per heading section; long sections split at ~450–550 words, hard max 800 | 1–2 sentences | page or page range, heading path |
| DOCX, cheat sheets | One chunk per heading; whole sheet if under 800 words | none | heading path |
| Pasted text, TXT, MD, web snapshots | Sentence-aligned ~400–500 words (heading sections first for MD/web) | ~15% | line range (TXT/MD/paste), heading (web) |

- **Slide PDF or document PDF (my call):** decided by page shape. Mostly landscape pages → slide rules, cited as "slide N"; mostly portrait → section rules, cited as "page N › heading". No extra picker in the Library. Module PDFs of either shape get topic review; only books (course references) skip it.
- Never cut mid-sentence. Code blocks and tables are not split internally unless they alone exceed the hard max.
- **Embedding text** = `search_document: {file title} > {heading path}\n\n{chunk text}`; **stored and shown text** = the raw chunk. (Header prefix: small measured gain at no cost; Kuehlkamp 2026, Anthropic 2024.)

### 3.5 Embeddings
- `nomic-embed-text` via Ollama `/api/embed`, 768 dimensions, with the required prefixes `search_document: ` / `search_query: `.
- **Measured on this laptop (2026-11-09, Ollama 0.32.15, CPU):** ~480 tokens/s; a 500-word chunk ~1.3 s; batching gives no speed-up. A 500-page book ≈ 11–12 min of embedding.
- **Measured:** Ollama silently truncates inputs beyond the model context (2048 tokens) by default. Send `truncate: false` and keep every embedding input (prefix + header + chunk) under ~1,500 tokens; a 1,447-token input passed, ~2,300 failed with HTTP 400.

### 3.6 Search: hybrid with reranker (student's choice)
- **Dense search** in Chroma and **keyword search** in a SQLite FTS5 index in `study.db`. Chroma's own BM25/hybrid search is Chroma Cloud only, not in the local server.
- **Fusion: convex combination, `alpha = 0.6`** (weight on dense), after **theoretical min-max normalisation** (Bruch et al.'s TM2C2: keyword score scaled from 0, cosine similarity from −1). Setting `HYBRID_ALPHA=0.6`.
  - Why 0.6: inside the range Bruch, Gai & Ingber (ACM TOIS 2023) found consistently improves on both single methods (0.6–0.8); exactly the best fixed value in DAT's grid search (2025); the low end suits a general embedding model that has never seen this course and questions full of exact terms; with a reranker after fusion, alpha's job is to get the right chunk into the shortlist, and a lower alpha lets keyword-only hits in.
  - Rejected: 0.8 (tuned for a dense model on its own training data), 0.5 (a product default outside the consistently-helpful range, measured worse than 0.6 by DAT), ≤0.3 (advice for code/part-number collections), RRF k=60 (worse than tuned convex combination on all 9 of Bruch's datasets).
- **Pipeline:** top 30 from dense + top 30 from keyword → fuse → top 30 to the **reranker** (MiniLM-L6 cross-encoder, ~80 MB, ONNX, no torch needed) → return **10** chunks.
- **Module material vs books: 70 / 30 (student's choice).** Of the 10 results, **7 come from module material** (slides, module PDFs, pasted text, web links) and **3 from books**. Reason: one book is ~700 chunks against ~40 for a week's slides, so without slots book passages would crowd out the lecture. Implementation **(my call)**: every chunk carries `origin = module | reference`; the dense, keyword and fusion steps run per origin (each with its own top-30 shortlist), the reranker ranks each group separately, then the two groups are combined. **Unused slots go to the other group** (a question only the book covers returns up to 10 book chunks; with no books, 10 module chunks), so a slot is never wasted on an irrelevant chunk. **(my call)** The 70/30 split and the total are settings. The builder checks that 10 chunks fit Qwen's context window when Qwen is the active model, and lowers the total for Qwen if needed, keeping the 70/30 split.
  - **Reranker is on by default and switchable** with a setting. Caveat recorded: in one public 32-query test it added only +0.005 nDCG@10 overall (helped mixed queries 0.753→0.804, hurt purely conceptual ones 0.493→0.446).
- Search is always scoped to the active course; optional filters by module, topic, file and kind.

### 3.7 Topic tagging and review
- Qwen suggests topics for each **module file** (not books) and matches them to existing course topics. Topics are course-level and linked to modules (spec §4.3).
- **Review per file (option A, student's choice):** each finished file's Library row shows "**N topics to review**"; a panel opens under the row listing that file's topics only. Each topic shows the slides/lines it came from and a badge:
  - **matches existing** (green): ✓ keep, or unlink;
  - **looks like "X"** (amber, close to an existing topic): merge into X, or keep new;
  - **new** (blue): accept, rename, merge ▾ (into an existing topic or another suggestion), drop.
- **Save topics** applies everything at once; nothing changes in the course map before that. The student reviews carefully (renames and merges), so the panel must make those actions quick.
- **The file is searchable before review.** Topics decide course-map grouping and topic-filtered retrieval ("all chunks for topic X"), not whether material can be found.
- Once a topic is accepted, later files show it as a green match.
- Mockup: `.superpowers/brainstorm/70-1794259000/content/topic-review.html` (option A).

### 3.8 Library page (student-approved mockup)
Mockup: `.superpowers/brainstorm/70-1794259000/content/library.html`. Top to bottom:
1. **Add material** with three tabs: *Upload files* (drop zone), *Paste text* (title, module, text box), *Add web link* (URL, module). Every item gets a module picker pre-filled with the app's suggestion ("suggested from the title slide"), plus **Course reference (book)** as an alternative to a module. *Add to queue*.
2. **Files grouped by module**, each with a status chip: *queued (position) → reading → chunking → embedding → tagging → done / failed*. Done files show "N topics to review" and *Review*. Failed files show the reason in plain words and *Retry*.
3. **Course references (books)** with a progress bar, current pages and pieces ("pages 201–225 · 8 / 25 pieces").
4. **Messages and dialogs:** duplicate skipped note; **Replace** confirm that lists what will be flagged *possibly outdated* (counts appear once Plans 3–4 create derived content) and offers *Replace / Keep both / Cancel*; **Delete** confirm of the same shape. Per-file ⋯ menu: Replace with new version, **Move to another module (my call, added after the builder check)**, Delete, Show where it's cited.
   - **Move to another module** re-labels the file's chunks in every store and moves its topic links to the new module (removing links from the old module that no other file there supports), with no re-processing. So the module must not be part of chunk IDs. Switching between module material and book is delete + re-add (rare, and it changes topic review).
   - "Show where it's cited" was added by the assistant and accepted with the page; it has nothing to show until notes and answers record citations (Plans 3–4). **(my call)** Plan 2 hides it until then.

### 3.9 Load on the laptop
Checked 2026-11-10: i7-1255U (10 cores / 12 threads), 15.7 GB RAM with ~6.2 GB free while VS Code, Chrome and other apps were open; C: 23 GB free, Y: 192 GB free (same NVMe SSD).
- **Student's choices:** cap Docling at **4 threads** (`INGEST_THREADS=4`); store all downloaded models (Docling, CodeFormula, reranker) under **`data/models/` on Y:** (git-ignored; saves ~3 GB on C:, no speed cost).
- **Student declined:** a separate short-lived process for Docling, and a free-memory check before each piece.
- **Consequences, accepted:** Docling runs **inside the app process on a background thread** (the UI must not freeze); its 2–4 GB stays held until the app restarts; a hard crash inside Docling (out-of-memory) closes the app, and the queue resumes on the next start. The tight case is chatting (Qwen loaded, ~2.5–3 GB) while a book is at Docling's peak: up to ~8 GB against ~6 GB free, so Windows pages to disk and things slow down.
- One file at a time; within a file, steps run in order, so Docling and Qwen tagging don't run at once.

## 4. Changes to the parent spec
1. **Web links:** httpx + trafilatura in the upload worker replaces the Fetch MCP (spec §4.4 step 2, §4.10 table row "Fetch"). The spec's MCP table should mark Fetch as "not used; see Plan 2 design".
2. **Books:** a course-level reference with no module and no topics (spec §4.3 "each file belongs to exactly one module" now applies to module material only).
3. **OCR:** still a non-goal for scanned documents, but picture areas inside PDF pages are OCR'd so image tables in books are read (spec §2 non-goals).
4. **Chunk sizes:** the low end of 500–800 words, per §3.4.
5. **Pasted text** is an input type alongside uploads (spec §4.5 Library).
The executor updates the parent spec with these, each marked "Changed 2026-11-10".

## 5. Settings added (`.env.example`)
`CHROMA_PORT=8001` **(my call; Chroma's default 8000 clashes with the app)** · `HYBRID_ALPHA=0.6` · `RERANK_ENABLED=true` · `SEARCH_RESULTS=10` · `SEARCH_MODULE_SHARE=0.7` · `FORMULA_ENRICHMENT=true` · `INGEST_THREADS=4` · models directory under `data/models` · a timeout for Qwen calls (§7).

## 6. Safety rules (spec §4.4, made concrete)
- **Duplicates:** content hash (SHA-256 of the file bytes; of the normalised text for pasted text and web snapshots) anywhere in the course → skipped with a note.
- **New version (my call):** an upload with the **same file name in the same module** (or the same URL) but different content triggers the Replace dialog. *Keep both* adds it as a separate file.
- **Replace:** old chunks removed from Chroma, the keyword index and SQLite; the new version ingested; anything derived from the old version flagged *possibly outdated* (nothing exists yet in Plan 2).
- **Delete:** removes the file's chunks from every store, its topic links that no other file supports **(my call)**, and the original in `data/sources/` **(my call)**. Accepted topics are kept even if no file supports them any more, so the student's history isn't lost **(my call)**.
- **Citations to removed chunks:** Plan 2 keeps a record of removed chunk IDs and their file, so later plans can mark citations "source removed" (spec anti-goal). **(my call)**
- **Strict queue order (student's choice):** files are processed one at a time, in the order added. A module file added after a book **waits until the book finishes**, even if that takes hours. The Library shows each queued file's position.
- **One failure doesn't block the queue.** A failed file keeps its reason and can be retried.
- **Big files resume:** PDFs are converted in 25-page pieces; progress is checkpointed per piece in SQLite; on start-up unfinished jobs resume from the last finished piece. Re-running a piece must not duplicate chunks (deterministic chunk IDs). **(my call)**

## 7. Carry-forward items from Plan 1 (all still open on `main` at affedd5, checked 2026-11-09)
| Item | Current code | Required |
|---|---|---|
| Preflight crash on malformed `/api/tags` or `OLLAMA_URL` | `launcher.py:32` catches only `httpx.HTTPError` | Also catch `ValueError`, `KeyError`, `TypeError`, `httpx.InvalidURL`; the launcher never crashes |
| ADK "App name mismatch" warning at every start | path contains `agents` | Rename the package folder (e.g. `eduagent/team/`) or add a narrow log filter. **Never change `APP_NAME`** (sessions are keyed by it) |
| `exc_text` not scrubbed | `logging_setup.py:31` | Scrub `record.exc_text` in `RedactingFormatter` |
| No Qwen timeout | litellm default ~600 s | One `asyncio.wait_for` covering the classifier and the Qwen reply/fallback path, with headroom for a cold model load |
| Repo races | `courses.py:58-85` SELECT-then-INSERT | `_get_or_create` → `INSERT … ON CONFLICT`; `link_topic` checks the module and topic share a course. Topic tagging will exercise this heavily |
| `mcp` dependency | not in `pyproject.toml` | Add before any LiteLlm agent gets tools (litellm 1.108 crashes on `tools=` without it) |
| `has_attachment` never passed | `coordinator.py:29` | Coordinator passes it |
| Shallow `model_copy` in fallback | `routed_llm.py:157` | `deep=True` now that tools exist |

## 8. Environment facts the plan must respect
- Ollama 0.32.15 at `http://127.0.0.1:11434` with `qwen3:4b-instruct` and `nomic-embed-text`; Qwen runs on CPU (`num_gpu=0`) because the 2 GB MX570 crashed Ollama.
- Chroma: use the **Rust server via `chroma run`** only. CVE-2026-45829 (pre-auth RCE) affects the Python FastAPI server in chromadb 1.0–1.5.9, not `chroma run`. Bind to 127.0.0.1. Health check `GET /api/v2/heartbeat`. List-valued metadata with `$contains` needs chromadb ≥ 1.5.0.
- Python 3.12, uv, Windows 11; stdout is reserved for MCP stdio servers (logs go to stderr and the log file).
- `.superpowers/` and `data/` are git-ignored; nothing from the student's course may be committed. Test fixtures must be freely licensed or written for the tests.

## 9. Process (student's rules for executing this plan)
- Branch `plan-2-knowledge-base` from `main`; superpowers:subagent-driven-development with implementer → task review → fix rounds → scoped re-review for every task; every finding, minor and ruling in the ledger.
- Where tests only use fakes, also run a live check against the real models (Ollama must be reachable first; start `ollama serve` if not).
- After each task passes review: push the plan branch (never `main` without asking); then stop and teach (what, why, why this way and not another, what reviews caught) and wait for questions or "continue".
- No Co-Authored-By or any AI attribution in commits or PRs. Never delete local branches; ask before deleting any record of the work (e.g. the ledger).
- End: manual end-to-end check with the student at the browser, final whole-branch review, list of every ruling from the ledger, then finishing-a-development-branch; the student prefers a PR merged with "Create a merge commit".
- Teaching requirement (spec §4.15) and `docs/decisions.md` entries per task, as in Plan 1. `WHAT_IT_DOES` on every new component module.

## 10. Left to the builder
- SQLite schema for files, ingestion jobs/pieces, chunks, chunk–topic links, keyword index and removed-chunk records; where topic tags live so that rename and merge after storage are cheap.
- KB MCP tool names and signatures (at least: search material, get all chunks for a topic), their docstrings (written carefully for Qwen), and the exact `trace` section fields (at least embed ms, search ms per method, fusion and rerank ms, k, filters, per-chunk scores).
- How Qwen proposes topics and the module suggestion (prompts, per-chunk vs per-file), and how "looks like X" is detected.
- How the Tutor is given the search tool in Plan 2 (McpToolset over stdio), with a reduced tool set when Qwen is the active model if needed.
- Reranker package (fastembed or FlashRank) and how its model is stored under `data/models/`.
- Sentence splitter (regex with an abbreviation list, or a light library such as semchunk).
- The week label ("uploaded in week N") reference point.
- Task breakdown, test strategy (core logic must have automated tests; `ollama`-marked live tests for real embeddings, tagging and retrieval), and the manual end-to-end checklist.

## 11. Sources
Parsers: pypi.org/project/docling · arxiv.org/html/2501.17887 · github.com/opendataloader-project/opendataloader-bench · docling-project.github.io/docling/usage/enrichments · github.com/docling-project/docling/issues/1631 · github.com/docling-project/docling/issues/3345 · huggingface.co/ds4sd/CodeFormula · Docling `mspowerpoint_backend.py` (main).
Chunking and embeddings: trychroma.com/research/evaluating-chunking · developer.nvidia.com/blog/finding-the-best-chunking-strategy-for-accurate-ai-responses · arxiv.org/abs/2410.13070 · alphaxiv.org/abs/2610.10170v1 · anthropic.com/news/contextual-retrieval · docs.ollama.com/api/embed · huggingface.co/nomic-ai/nomic-embed-text-v1.5.
Search: arxiv.org/abs/2210.11934 (Bruch et al.) · arxiv.org/html/2503.23013 (DAT) · arxiv.org/pdf/2511.10297 · docs.weaviate.io hybrid search · github.com/rahin1301/hybrid-retrieval-search · docs.trychroma.com/cloud/search-api/overview · trychroma.com/changelog/metadata-arrays · CVE-2026-45829 (hadrian.io write-up).
Web: trafilatura.readthedocs.io (usage, evaluation 2026-10-02) · arxiv.org/html/2605.21097v1 (WCXB) · osti.gov/servlets/purl/2429881 (Sandia) · github.com/scrapinghub/article-extraction-benchmark · github.com/modelcontextprotocol/servers/tree/main/src/fetch.
