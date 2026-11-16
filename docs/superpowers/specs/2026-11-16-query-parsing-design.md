# Query parsing — decision (short design)

Date: 2026-11-16 · Status: approved by the student 2026-11-16 · Relates to: Plan 2 Task 13 (hybrid search), Plan 4 (Tutor grounding)

## Intent
The student asked whether search should handle follow-up questions, abbreviations, multi-part questions and spelling mistakes before it searches. They want to decide from real failures on their own course material, tested with many questions once the app is built and the material is in place — not from guesses.

## How search reads a question today (Plan 2 as designed)
- The Tutor writes the `query` argument of `search_material` itself from the whole chat, so follow-ups are partly rewritten already; quality depends on the active model (Qwen 4B less reliable than a cloud model).
- Dense search (nomic-embed-text, `search_query: ` prefix) tolerates small typos and some paraphrase; keyword search (SQLite FTS5, quoted tokens OR-ed) matches exact words only — no fuzzy matching, no abbreviation expansion.
- A multi-part question is one search.
- Any rewrite step done by Qwen costs roughly 2–10 s per question on the student's CPU.

## Goals / non-goals / anti-goals
- Goal: decide each query-parsing fix on measured evidence from the student's own questions and material.
- Non-goal: any query-parsing change in Plan 2. Task 13 is built exactly as planned.
- Anti-goal: adding Qwen latency to every question for a fix the student's questions don't need; committing the student's questions or material.

## Approaches
- A. Change nothing; test a handful of questions in the Task 22 browser session by reading retrieval traces. Free, but only a few questions, one at a time.
- B. Add a question runner to Plan 2 now (a questions file in `data/`, prints top hits and scores per question). Fast to re-run, but bypasses the Tutor's own rewording (can't show follow-up problems) and builds a tool before we know what to measure.
- **C. A, plus a question-set evaluation as the first step of Plan 4 (chosen by the student).** Plan 4 builds how the Tutor grounds answers (labels, citations, web fallback, semantic cache), so it is where query handling belongs.

## Decision
1. Plan 2: no design change. Task 13 as planned. In the Task 22 browser session the student asks a few real questions and we read the search traces (the query the Tutor wrote, the chunks returned, their scores).
2. Plan 4 starts with a question-set evaluation: the student's real questions (kept under git-ignored `data/`), run through a direct search runner and through real chats. The failures found decide which of these are built, each measured before and after:
   - follow-up rewriting (beyond what the Tutor already does when it writes the query),
   - an abbreviation list drawn from the course,
   - splitting multi-part questions into several searches,
   - fuzzy or typo-tolerant keyword matching.
3. The retrieval trace Plan 2 already records (Task 13 trace dict, saved in the `tool_result` step) is the evidence source; no extra recording is added now.

## Left to the builder (Plan 4)
The runner's form (CLI or test helper), the size of the question set, and the success metric (e.g. "the expected slide/page in the top 3") — agreed with the student when Plan 4 is designed.
