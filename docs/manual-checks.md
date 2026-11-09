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
Misses: "draw a mermaid flowchart of train/test split (with validation)" with last agent none, tutor, coding and notes_maker
was routed to coding, expected tutor (the phrase is also the sklearn function name). All other cases pass.

Previous run (2026-11-08, `qwen3:4b-instruct`): 29/30.**
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

| # | Check | Result |
|---|---|---|
| 1 | Browser opens on `127.0.0.1:8000` | |
| 2 | Create a course, start a new chat | |
| 3 | Ask "what is overfitting?": reply labelled **Tutor**, model caption Gemini, quota count drops by at least 1 | |
| 4 | `@progress hi` shows the Analytics placeholder | |
| 5 | Set `ROUTING_MODE=all_qwen`, restart: caption shows Qwen and the top bar says all Qwen | |
| 6 | Stop Ollama, restart: banner names `ollama serve` | |
| 7 | Routing eval (`uv run pytest -m ollama tests/agents -q -s`): score recorded in the Routing section above | |
| 8 | Click "Ask instead: Coding" under a Tutor reply: the trace has a `reroute` step | |
| 9 | `SELECT count(*) FROM trace_steps WHERE input_json LIKE '%<first 8 chars of key>%'` on `data/study.db` returns 0 | |
| 10 | `data/logs/eduagent.log` does not contain the key | |
| 11 | Log shows start-up, preflight, each route decision and the model used | |
| 12 | With the Gemini key temporarily wrong, the log shows a fallback WARNING | |
