# Educational Agent

A local, pure-Python study companion. Upload your course material, then chat with specialised agents (tutor, notes maker, coding helper, progress analyst) built on Google ADK, with a NiceGUI interface and models from Gemini (free tier) or local Ollama. Everything runs on your machine, and everything is free.

## Setup

1. Install [Ollama](https://ollama.com) and pull the two local models:
   ```
   ollama pull qwen3:4b-instruct
   ollama pull nomic-embed-text
   ```
2. Install [uv](https://docs.astral.sh/uv/), then install the project:
   ```
   uv sync
   ```
3. Copy `.env.example` to `.env`. To use Gemini for the heavier tasks, create a free key in [Google AI Studio](https://aistudio.google.com/apikey) and put it after `GEMINI_API_KEY=`. Without a key everything runs on local Qwen.
4. Start the app (it opens in your browser at http://127.0.0.1:8000):
   ```
   uv run eduagent
   ```
   Run it from the project folder: `.env` and `data/` are found relative to the folder you start from.

If Ollama isn't running, or a model or the key is missing, the app still starts and shows a banner at the top of the chat page telling you what to fix.

## What works so far (Plan 1: foundation)

- Courses, chat threads and message history, stored locally.
- A coordinator that routes each message to the Tutor, Notes, Coding or Progress agent. Use `@tutor`, `@notes`, `@code` or `@progress` to choose one yourself.
- Model routing between Gemini and local Qwen (`ROUTING_MODE` = `split`, `all_gemini` or `all_qwen`), with a daily Gemini quota counter and automatic fallback to Qwen.
- A trace of every step behind each reply, and one-click "Ask instead" buttons to resend a question to another agent.
- Rotating log file in `data/logs/`.

- Side pages: Library, Notes, Flashcards, Progress and How it works. They are placeholders for now, each saying "Coming in Plan N". There is no Analytics page.
- Traces are recorded for every reply, but there is no screen to view them until Plan 7.

## Roadmap

| Plan | What it adds |
|---|---|
| 1. Foundation | Chat shell, model routing, tracing, logging, one-command start (done) |
| 2. Knowledge base & ingestion | Upload and parse course material, search it, Library page |
| 3. Notes maker | Generated notes and flashcards from your material, Notes page, PDF export |
| 4. Tutor | Grounded answers with citations, doubt logging, flashcard review, quizzes |
| 5. Analytics | Mastery tracking and the Progress page with charts |
| 6. Coding agent | Explain and review your code, with course-material search |
| 7. How it works page | Interactive map of the system, live path, replay and demo mode |

## Your data

Your data stays in `data/` and is never committed: the database, uploads, notes and logs are all git-ignored, as is `.env` with your key.

## Tests

```
uv run pytest -q              # fast tests
uv run pytest -m ollama -q    # runs ONLY the tests that need Ollama
```

## Licence

MIT.
