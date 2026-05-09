# ARCHITECTURE

## Layer Stack

```
Host Agent (Claude Code, opencode, Codex, Gemini CLI)
  │ calls MCP tools
  ▼
subagent-orchestrator (MCP server)
  │ per-turn: acpx → opencode acp → model (Gemma4 / DeepSeek-Coder)
  │ manages: phase-state, model lifecycle, turn routing
  ▼
acpx (ACP transport)
  │ initialize, newSession, prompt, idle detection, crash recovery
  ▼
opencode acp (session runtime)
  │ agent profiles, permissions, tools
  ▼
MLX / oMLX / Ollama (model runtime)
  │ Gemma4-26B-A4B-4bit, DeepSeek-Coder-V2-Lite-4bit
  ▼
M3 Pro 36GB (hardware, 150 GB/s)
```

## The orchestrator does NOT

- Implement ACP — delegates to acpx
- Manage git worktrees — the harness (or swain-do) does that
- Run models directly — delegates to acpx → opencode
- Define agent prompts — the harness owns AGENTS.md and agent profiles
- Replace dispatch-opencode — dispatch-opencode remains available for push-model dispatch

## Core Loop

```
1. Parent agent: "Run exploration on Portland shipbuilding" (MCP call)
2. Orchestrator: looks up profile "explorer" → DeepSeek-Coder, agent "explore"
3. Orchestrator: acpx → opencode, turn 1 dispatched
4. Subagent: runs search, returns findings
5. Subagent self-declares phase=done (or orchestrator detects idle)
6. Orchestrator: returns findings to parent agent

— later —

7. Parent agent: "Critique these 4 explorations" (MCP call)
8. Orchestrator: looks up profile "critic" → Gemma4, agent "general", temp 0.4
9. Orchestrator: acpx → opencode, turn 1 (299 tokens)
10. Subagent: processes lighthouse findings, declares phase=verify_complete
11. Orchestrator: turn 2 dispatched (shipbuilding, 817 tokens, prior context)
12. Subagent: processes, declares phase=verify_complete
...
15. Orchestrator: turn 5 dispatched (synthesize, 2,754 tokens)
16. Subagent: produces brief, declares phase=done
17. Orchestrator: returns brief to parent agent
```

## Pull Model Flow

The pull model separates a task into two parts:

**Spec (exists upfront):**
- Target: which task this is
- Turns: ordered list of turn specifications
- Profiles: model, agent, temperature, max_tokens per turn
- Phase handlers: what to do on each phase declaration

**Runtime (steered temporally):**
- Turn 1 dispatched
- Subagent processes, declares `phase=verify_complete`
- Orchestrator checks spec: turn 2 targets "Gemma4, temp 0.4, max_tokens=400"
- acpx loads new session with updated model if changed
- Turn 2 dispatched (includes prior turn output in context)
- Repeat until spec exhausted or subagent declares `done`

## Model Lifecycle

The orchestrator tracks model state across turns:

| State | Meaning | Action on next turn |
|---|---|---|
| `loaded` | Model is in memory, ready for inference | Reuse session if same model; load new if different |
| `unloaded` | Model was evicted (Metal OOM, TTL expired) | acpx → new session with model |
| `switching` | Different model needed for next turn | Hot-switch: unload current, load target |
| `oom` | Metal OOM on last load attempt | Retry with max_tokens reduction; escalate to parent if repeated |

On M3 Pro 36GB with Gemma4 (15 GB) + DeepSeek-Coder (8.85 GB), simultaneous load is impossible (23.85 GB total, Metal OOM). The orchestrator ensures only one model is resident at a time, unloads before loading the next.

## Phase-State Machine

```
                ┌─────────┐
                │ spawning │──── timeout ────► escalate to parent
                └────┬────┘
                     │ transport ready
                ┌────▼────┐
                │receiving│
                └────┬────┘
           ┌────────┼────────┐
           ▼        ▼        ▼
      ┌────────┐ ┌────────┐ ┌───────────┐
      │searching│ │synth'ing│ │tool-calling│
      └───┬────┘ └───┬────┘ └─────┬─────┘
          │          │            │
          └──────────┼────────────┘
                     │ turn complete
                ┌────▼─────┐
                │ verify    │
                │ _complete │─── degraded → escalate (raise temp, retry)
                └────┬─────┘
                     │ more turns remain
                ┌────▼─────┐
                │ receiving │ (next turn served)
                └────┬─────┘
                     ...
                     │ all turns done
                ┌────▼─────┐
                │   done   │── return result to parent
                └──────────┘

   At ANY state:
   ┌──────────┐
   │ degraded │──→ if recoverable: retry with adjusted config
   └────┬─────┘     if unrecoverable: escalate to parent
        │
   ┌────▼─────┐
   │  error   │──→ retry N times, then escalate
   └──────────┘
```

## MCP Tool Surface

The orchestrator exposes a minimal tool set to the host agent:

| Tool | Purpose |
|---|---|
| `orchestrate_run` | Start a new orchestrated run with a spec. Returns run_id. |
| `orchestrate_status` | Query current phase, model state, turn number. |
| `orchestrate_cancel` | Kill active subagent session, clean up. |
| `orchestrate_result` | Block until run completes; return final output. |

The host agent never touches ACP, model lifecycle, or turn sequencing. It calls `orchestrate_run` with a spec and collects results via `orchestrate_result`.
