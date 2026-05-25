# PURPOSE

subagent-multiturn-prompting is a temporal steer-by-wire layer between a parent agent and its subagent fleet. It addresses three gaps in current agent infrastructure:

1. **Model-specific routing** — parent says "use Gemma4, temp 0.4, agent critic" for this task and "DeepSeek-Coder, agent explore" for that one. No existing tool maps task profiles to models with per-profile configuration.
2. **Phase-state protocol** — subagents are long-lived entities that report progress (`phase=verify_complete`, `phase=degraded`) and request the next instruction set rather than receiving everything upfront. This is a pull model, not the push model of fire-and-forget subagent dispatch.
3. **Model lifecycle management** — multiple models on limited hardware (e.g., Gemma4 + DeepSeek-Coder on M3 Pro 36GB, 23.85 GB combined, Metal OOM if loaded simultaneously). The orchestrator manages load/unload/hot-switch, not the parent agent.

## Architectural Premise

Current agent dispatch is push-based: "here is your entire task, go execute it." This works for Pattern 1-2 subagent dispatch (inline tool, fan-out) but breaks for models that need incremental context delivery.

**subagent-multiturn-prompting inverts this to pull-based.** The full task specification — all turn instructions, all model profiles, all temperatures — exists upfront. But the subagent controls pacing. When it reaches `phase=verify_complete`, it requests the next turn. The orchestrator serves it.

This was empirically validated on M3 Pro 36GB with oMLX/Gemma4:
- Single-turn push (1,277 tokens): 7/7, clean output
- Single-turn push with complex formatting (3,143 tokens): degenerate output, `(brand-heavy-on-volume)` loop
- Multi-turn pull across 5 turns (299→2,754 tokens): **10/10, zero degeneration**

The pull model is not a convenience — it is a reliability requirement for certain architecture/model combinations.

## Transport Layer

subagent-multiturn-prompting does not implement ACP itself. It delegates transport to `acpx` (Apache-2.0, 2.3k stars) which handles:

- `opencode acp` spawn and lifecycle
- `initialize`, `newSession({ model, agent, cwd })`
- `prompt` dispatch, idle detection, crash recovery
- multi-agent routing

The orchestrator operates one layer up: which model, which turn, which temperature, which harness configuration. ACP sessions are ephemeral per-turn.

## Relationship to dispatch-opencode

**Neither subsumed nor wrapped.** dispatch-opencode is a transport adapter (ACP ↔ opencode) with a push model — fully-rendered task, per-kind permission allowlists, on-disk artifacts. subagent-multiturn-prompting is a temporal orchestration layer with a pull model. They serve different consumers:

| | dispatch-opencode | subagent-multiturn-prompting |
|---|---|---|
| Model | Push — task rendered upfront | Pull — subagent requests next turn |
| Scope | Dispatch, permissions, artifacts | Routing, phase-state, model lifecycle |
| Transport | Built-in client or acpx | acpx exclusively |

subagent-multiturn-prompting uses acpx directly. dispatch-opencode remains available for push-model dispatch where it fits.

## Harness Integration

The orchestrator runs as an MCP server consumable by any host agent (Claude Code, opencode, Codex, Gemini CLI). The host agent's harness — AGENTS.md, skills, custom tools — remains in control. The orchestrator is a harness-level capability, not a replacement for the harness.

## Phase-State Protocol

A subagent declares phases; the orchestrator routes accordingly:

| Phase | What it means | Orchestrator action |
|---|---|---|
| `spawning` | Agent is being initialized | Wait for the agent's transport to be ready |
| `receiving` | Agent is processing initial or follow-up instructions | Await completion or timeout |
| `searching` | Agent is performing search/exploration work | Provide search-related tools or resources |
| `synthesizing` | Agent is preparing a synthesis or final output | Ensure sufficient token budget and appropriate temp |
| `verify_complete` | Turn's verification pass is done | Serve next turn spec (target model, temp, max_tokens) |
| `degraded` | Output quality has fallen below thresholds | Escalate: raise temp, switch model, or restart turn |
| `error` | Turn failed (OOM, timeout, bad response) | Retry with adjusted config or escalate to parent |
| `done` | All turns complete | Return final brief/result to parent agent |
