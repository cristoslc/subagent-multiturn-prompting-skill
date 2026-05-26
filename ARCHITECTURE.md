# ARCHITECTURE

## Contract

This project is a **protocol definition**. It produces:

1. **OrchestrationSpec schema** — a JSON specification encoding all turn instructions, model profiles, temperatures, and prior-context flags
2. **Validation script** — `validate-orchestration-spec.sh` — that checks a spec for structural correctness before dispatch
3. **MCP tool surface** — two tools that any harness can serve:
   - `multiturn_run(spec, task_spec)` → run_id — accepts a spec and starts execution
   - `multiturn_prompt(run_id)` → NextTurn — subagent calls this to receive the next progressive-disclosure chunk

The harness (opencode, Claude Code, `llm`, `ollama launch`, etc.) owns execution. It serves the MCP tools, spawns sessions, and manages subagent lifecycle. The spec defines what to send and when.

## How Turns Are Served

```
1. Harness calls multiturn_run(spec) → run_id
2. Harness spawns subagent session
3. Harness calls multiturn_prompt(run_id) → Turn 1
4. Subagent processes turn, signals verify_complete (via its own protocol)
5. Harness calls multiturn_prompt(run_id) → Turn 2 (with prior_context injected)
6. Repeat until spec exhausted
```

The harness decides how to spawn the subagent, how to detect `verify_complete`, how to manage concurrency, and how to handle errors. The spec is consumed passively.

## Layer Stack

```
Host Agent (opencode, Claude Code, llm, ollama launch)
  │ serves MCP tools         │ reads spec
  ▼                           ▼
multiturn-prompting        OrchestrationSpec (JSON)
  MCP tools                   │ schema + validation
  │                           ▼
  └─→ multiturn_run(spec)   validate-orchestration-spec.sh
  └─→ multiturn_prompt(id)
```

## What This Project Does NOT Do

- Implement subagent sessions — the harness handles that
- Manage model loading or hardware lifecycle — the harness handles that
- Detect degenerate output — subagent's host does that
- Manage concurrency or provider routing — that's subagent-rank-based-orchestrator's domain

## MCP Tool Surface

| Tool | Purpose |
|---|---|
| `multiturn_run` | Accept an OrchestrationSpec, return a run_id |
| `multiturn_prompt` | Return the next turn for a run_id, with prior context accumulated |

## Integration with subagent-rank-based-orchestrator

subagent-rank-based-orchestrator decomposes tasks into ranks and routes them to providers. When a Grandmaster or Expert subagent task requires progressive disclosure (e.g., a model that degenerates on large prompts), the rank-based orchestrator uses this project's spec format and tools to serve chunks. The rank-based orchestrator owns *which* subagent models get which turns; this project owns *how* the turns are structured and served.
