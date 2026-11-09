# Manual checks

## Routing

The router sends each chat message to one of four agents. A small Qwen model decides
when there is no `@mention` and no code. To measure it, make sure Ollama is running with
`qwen3:4b-instruct` pulled, then run:

```
uv run pytest -m ollama tests/agents -q -s
```

The test prints every miss and fails below 90% accuracy.

**Latest run (2026-11-09, `qwen3:4b-instruct`, temperature 0, 45 cases): 41/45.**
Misses: all four eval rows for "draw a mermaid flowchart of train/test split (with validation)" (last agent
none, tutor, coding, notes_maker) were routed to coding, expected tutor (the phrase is also the sklearn
function name). All other cases pass. In real use, before the 2026-11-09 router change, the same message
went to coding or notes_maker (see the table below).

Previous run (2026-11-08, `qwen3:4b-instruct`): **29/30.**
Miss: "why is my accuracy 100% on training but 60% on test" (no previous agent) was routed to
coding, expected tutor. Row 1 of the set was changed from "what is overfitting?" to
"what is regularization?" because the original is also an example in the prompt.

### Misroutes found in real use

Add every real misroute here **and** to `tests/agents/routing_cases.py`.

| Message | Last agent | Routed to | Should be | Date |
|---|---|---|---|---|
| draw a mermaid flowchart of train/test split (with validation) | tutor / coding / notes_maker | coding / notes_maker | tutor | 2026-11-09 |

## End-to-end check (Plan 1)

Run with `uv run eduagent`. Fill in the result column as you go.

Run on 2026-11-09 by the student at the browser, with the assistant checking the database and logs.

| # | Check | Result |
|---|---|---|
| 1 | Browser opens on `127.0.0.1:8000` | Pass |
| 2 | Create a course, start a new chat | Pass |
| 3 | Ask "what is overfitting?": reply labelled **Tutor**, model caption Gemini, quota count drops by at least 1 | Pass with `GEMINI_MODEL=gemini-3.5-flash-lite` (caption, quota drop). `gemini-flash-latest` was overloaded that day (503, one 60 s hang), so replies fell back to Qwen as designed; this led to the 30 s Gemini timeout. |
| 4 | `@progress hi` shows the Analytics placeholder | Pass |
| 5 | Set `ROUTING_MODE=all_qwen`, restart: caption shows Qwen and the top bar says all Qwen | Pass |
| 6 | Stop Ollama, restart: banner names `ollama serve` | Pass (Ollama made unreachable with `OLLAMA_URL=http://127.0.0.1:9`; banner shown and dismissible) |
| 7 | Routing eval (`uv run pytest -m ollama tests/agents -q -s`): score recorded in the Routing section above | Pass: 41/45 |
| 8 | Click "Ask instead: Coding" under a Tutor reply: the trace has a `reroute` step | Pass |
| 9 | `SELECT count(*) FROM trace_steps WHERE input_json LIKE '%<first 8 chars of key>%'` on `data/study.db` returns 0 | Pass: 0 of 41 steps (inputs and outputs) |
| 10 | `data/logs/eduagent.log` does not contain the key | Pass: 0 |
| 11 | Log shows start-up, preflight, each route decision and the model used | Pass |
| 12 | With the Gemini key temporarily wrong, the log shows a fallback WARNING | Pass: `gemini failed (ClientError: 400 INVALID_ARGUMENT … API key not valid …), falling back to qwen`; reply from Qwen; the wrong key never appears in the log |

Also checked: Enter sends and Shift+Enter adds a line; a Mermaid diagram renders. Found and fixed during the run:
no Gemini timeout, Ollama crashing on the 2 GB GPU (Qwen now runs on CPU), invalid Mermaid labels from the model
(prompt rule + auto-quoting), and the diagram misroute (router decides by goal, not format).
