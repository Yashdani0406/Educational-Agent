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
