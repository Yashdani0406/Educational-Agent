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

If Ollama isn't running, or a model or the key is missing, the app still starts and shows a banner at the top of the chat page telling you what to fix.

## What works so far (Plan 1: foundation)

- Courses, chat threads and message history, stored locally.
- A coordinator that routes each message to the Tutor, Notes, Coding or Progress agent. Use `@tutor`, `@notes`, `@code` or `@progress` to choose one yourself.
- Model routing between Gemini and local Qwen (`ROUTING_MODE` = `split`, `all_gemini` or `all_qwen`), with a daily Gemini quota counter and automatic fallback to Qwen.
- A trace of every step behind each reply, and one-click "Ask instead" buttons to resend a question to another agent.
- Rotating log file in `data/logs/`.

The Notes, Progress, Analytics and course-material pages are placeholders for now.

## Roadmap

| Plan | What it adds |
|---|---|
| 1. Foundation | Chat shell, routing, tracing, logging, one-command start (done) |
| 2. Course material | Upload files, search them, answers grounded in your material |
| 3. Notes and coding | Notes maker and coding helper working on your material |
| 4. Progress | Quizzes, mastery tracking, analytics, semantic answer cache |

## Your data

Your data stays in `data/` and is never committed: the database, uploads, notes and logs are all git-ignored, as is `.env` with your key.

## Tests

```
uv run pytest -q              # fast tests
uv run pytest -m ollama -q    # also runs the tests that need Ollama
```

## Licence

MIT.
