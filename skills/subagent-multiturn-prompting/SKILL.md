---
name: subagent-multiturn-prompting
description: Progressive-disclosure protocol for subagents that degenerate on large single prompts. Defines the OrchestrationSpec schema (turn sequences, model profiles, prior-context injection) and validation. Subagents invoke MCP tools to pull the next turn incrementally. Harnesses serve the tools and manage subagent sessions. Use when a subagent needs turn-by-turn prompt delivery to avoid monolithic prompt degeneration. Do NOT use for single self-contained turns — use direct dispatch.
license: MIT
compatibility: opencode
metadata:
  version: "0.2.0"
  audience: agents
  transport: mcp
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
---

# subagent-multiturn-prompting

You define progressive-disclosure OrchestrationSpecs that break complex tasks into sequential turns. Subagents receive one turn at a time, request the next when ready, and get prior context injected. The harness serves the MCP tools; you construct and validate the spec.

## Decision tree: push vs pull

| Characteristic | Push model (direct dispatch) | Pull model (subagent-multiturn-prompting) |
|---|---|---|
| Turns | 1 self-contained turn | 2+ turns with prior-context injection |
| Context delivery | All at once | Incremental, subagent requests next turn |
| Recovery | Harness owned | Harness owned (model switch, retry, degrade) |
| When to use | Models that handle large prompts | Models that degenerate on >500 token prompts |

## Constructing the OrchestrationSpec

See `references/orchestration-spec-schema.md` for the complete field reference.

### Step 1: Select model profiles

Map task phases to profiles from the default registry (see `references/model-profiles.md`):

- **explorer** — temp 0.3, 400 tokens/turn. Research, codebase exploration, fact-finding.
- **critic** — temp 0.4, 400 tokens/turn. Verification, contradiction detection, source checking.
- **thinker** — temp 0.5, 600 tokens/turn. Divergent reasoning, open-ended analysis.
- **fast_code** — temp 0.2, 1200 tokens/turn. Code generation, editing.

### Step 2: Design turn sequence

1. **Per-item turns** — one turn per item, small prompt (~300 tokens), the subagent gets only what it can handle per-turn.
2. **Synthesis turn** — final turn with accumulated prior context, higher `max_tokens`, lower temp.
3. **`requires_prior_context: true`** — on turns that need prior output injected.

Example 5-turn critic workflow for 4 explorations:

```
Turn 1: "Verify exploration 1 against its sources" (profile=critic, temp=0.4, ~300 tokens)
Turn 2: "Verify exploration 2 against its sources" (profile=critic, prior_context=true)
Turn 3: "Verify exploration 3 against its sources" (profile=critic, prior_context=true)
Turn 4: "Verify exploration 4 against its sources" (profile=critic, prior_context=true)
Turn 5: "Synthesize verified findings into a brief" (profile=critic, temp=0.3, 1000 tokens)
```

### Step 3: Write prompt templates

Use `{task_spec}` and `{prior_output}` variables. The harness fills them at runtime:

```
prompt_template: "Critique this exploration. Flag contradictions, check sources, rate confidence. Exploration: {{ task_spec }}"
```

## Validating the spec

Always validate before handing off to the harness:

```bash
bash skills/subagent-multiturn-prompting/scripts/validate-orchestration-spec.sh <spec-file>
```

Results:
- **Exit 0 + "OK"** — spec is valid.
- **Exit 1 + JSON error list** — structural errors. Report each.
- **Exit 10** — profiles missing `degenerate_risk`. Warn the user.
- **Exit 2** — not valid JSON or file doesn't exist.

## How the harness consumes the spec

The harness serves two MCP tools. The subagent invokes them:

1. The parent agent passes the OrchestrationSpec to the harness
2. The harness calls `multiturn_run(spec, task_spec)` → `run_id`
3. The harness spawns a subagent session
4. The subagent calls `multiturn_prompt(run_id)` to receive turn 1
5. The subagent processes the turn and signals completion
6. The subagent calls `multiturn_prompt(run_id)` again for turn 2 (with prior context injected)
7. Repeat until the spec is exhausted

You construct the spec and hand it to the harness. You do not run the subagent.

## Reference documents

- `references/orchestration-spec-schema.md` — complete field reference for OrchestrationSpec, ModelProfile, TurnSpec, Phase, PhaseHandler.
- `references/model-profiles.md` — default profile registry.
