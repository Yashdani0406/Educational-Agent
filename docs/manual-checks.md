# Manual checks

## Routing

The router sends each chat message to one of four agents. A small Qwen model decides
when there is no `@mention` and no code. To measure it, make sure Ollama is running with
`qwen3:4b-instruct` pulled, then run:

```
uv run pytest -m ollama tests/agents -q -s
```

The test prints every miss and fails below 90% accuracy.

**Latest run (2026-11-08, `qwen3:4b-instruct`): 29/30.**
Miss: "why is my accuracy 100% on training but 60% on test" (no previous agent) was routed to
coding, expected tutor. Row 1 of the set was changed from "what is overfitting?" to
"what is regularization?" because the original is also an example in the prompt.

### Misroutes found in real use

Add every real misroute here **and** to `tests/agents/routing_cases.py`.

| Message | Last agent | Routed to | Should be | Date |
|---|---|---|---|---|
