---
name: subagent-orchestrator
description: Temporal steer-by-wire layer for multi-turn, multi-model subagent dispatch using a pull-model phase-state protocol. Constructs OrchestrationSpecs, routes tasks to model profiles (explorer/critic/thinker/fast_code), manages model lifecycle on constrained hardware, detects degenerate output and escalates, and validates specs before dispatch. Use when dispatching subagents that need incremental context delivery, multi-step verification, or per-turn model/temperature configuration. Do NOT use for simple single-turn self-contained tasks — use direct subagent dispatch or dispatch-opencode instead.
license: MIT
compatibility: opencode
metadata:
  version: "0.1.0"
  audience: agents
  transport: acpx
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
---

# subagent-orchestrator

You orchestrate multi-turn, multi-model subagent dispatch using a pull-model phase-state protocol. The parent agent gives you a task; you decide whether it needs push-model dispatch (single self-contained turn) or pull-model orchestration (multi-turn with incremental context delivery).

## Decision tree: push vs pull

Before constructing any spec, classify the task:

| Characteristic | Push model (direct / dispatch-opencode) | Pull model (subagent-orchestrator) |
|---|---|---|
| Turns | 1 self-contained turn | 2+ turns with phase-state control |
| Models | Single model | Multiple models or per-turn reconfiguration |
| Context delivery | All at once (monolith prompt) | Incremental, subagent requests next turn |
| Recovery | None (fire-and-forget) | Degenerate output detection, retry, model switch, escalate |
| Examples | "Review this PR", "Generate this component" | "Critique 4 explorations, verify each, then synthesize", "Multi-pass research across 3 sources" |

For push-model tasks, route to direct ACP prompt or dispatch-opencode. For pull-model tasks, proceed to spec construction. When the user asks why a particular routing decision was made, explain the reasoning: single vs multi-turn, self-contained vs verification-needed, and whether the model benefits from incremental context delivery.

## Constructing the OrchestrationSpec

See `references/orchestration-spec-schema.md` for the complete field reference.

### Step 1: Select model profiles

Map task phases to profiles from the default registry (see `references/model-profiles.md`):

- **explorer** — DeepSeek-Coder, temp 0.3, 400 tokens/turn. Research, codebase exploration, fact-finding.
- **critic** — Gemma4, temp 0.4, 400 tokens/turn. Verification, contradiction detection, source checking.
- **thinker** — Gemma4, temp 0.5, 600 tokens/turn. Divergent reasoning, open-ended analysis.
- **fast_code** — DeepSeek-Coder, temp 0.2, 1200 tokens/turn. Code generation, editing.

If a profile doesn't fit, ask the user to define a custom profile.

### Step 2: Design turn sequence

For multi-turn workflows:

1. **Per-item verification turns** — one turn per item, small prompt (~300 tokens), subagent verifies and declares `phase=verify_complete`.
2. **Synthesis turn** — final turn with accumulated prior context, higher max_tokens, lower temp.
3. **Include `requires_prior_context: true`** on turns that need the prior turn's output injected.

Example 5-turn critic workflow for 4 explorations:

```
Turn 1: "Verify exploration 1 against its sources" (profile=critic, temp=0.4, ~300 tokens)
Turn 2: "Verify exploration 2 against its sources" (profile=critic, prior_context=true)
Turn 3: "Verify exploration 3 against its sources" (profile=critic, prior_context=true)
Turn 4: "Verify exploration 4 against its sources" (profile=critic, prior_context=true)
Turn 5: "Synthesize verified findings into a brief" (profile=critic, temp=0.3, 1000 tokens)
```

### Step 3: Write prompt templates

Use `{task_spec}` and `{prior_output}` variables. The orchestrator fills them at runtime:

```
prompt_template: "Critique this exploration. Flag contradictions, check sources, rate confidence. Exploration: {{ task_spec }}"
```

## Validating the spec

Before dispatch, always call the validation script:

```bash
bash skills/subagent-orchestrator/scripts/validate-orchestration-spec.sh <spec-file>
```

Interpret results:
- **Exit 0 + "OK"** — spec is valid, proceed to dispatch.
- **Exit 1 + JSON error list** — spec has structural errors. Report each error to the user.
- **Exit 10** — one or more profiles are missing `degenerate_risk`. Warn the user: degenerate output detection is disabled for those profiles. Do NOT silently proceed.
- **Exit 2** — input is not valid JSON or the file doesn't exist. Report to user.

## Model lifecycle awareness

On hardware with limited Metal RAM (e.g., M3 Pro 36GB), check profile `memory_gb` fields:

| Profile | Memory | 
|---|---|
| Gemma4 models | 15.0 GB |
| DeepSeek-Coder models | 8.85 GB |
| macOS overhead | ~3-4 GB |
| Usable for models | ~22 GB |

**Maximum one model at a time** when combined >22 GB. If the user requests simultaneous execution of profiles with `memory_gb` sum > 22 GB:

1. Warn with the specific numbers.
2. Propose sequential execution: run profile A, hot-switch to profile B.
3. Do NOT attempt to load both.

## Degenerate output detection and recovery

When a subagent returns output, check for these degenerate patterns:

1. **Repeating blocks** — identical 5-line blocks appearing more than once in outputs over 20 lines.
2. **Copy-paste midsection** — first 100 characters match a 100-character block starting at the midpoint.
3. **Token loops** — patterns like `(brand-heavy-on-volume)` repeated verbatim.

If degenerate output is detected:

1. **Retry with higher temp** — bump temperature by +0.1, re-dispatch the same turn. Report: "Degenerate output detected on Turn N. Retrying at temp X.X."
2. **Reduce max_tokens** — if retry still degenerates, halve max_tokens for that turn.
3. **Switch model** — if the current model is Gemma4 (known degenerate_risk.low_temp), switch to DeepSeek-Coder if available.
4. **Escalate to user** — if all recovery attempts fail: "Degenerate output on Turn N with [model] at temp [x]. Recovery attempted: [list]. Suggestions?"
5. **Never silently advance** — do not serve the next turn when the current turn's output is degenerate.

## Phase-state protocol

The orchestrator uses phases to control turn sequencing. You don't implement phases — you specify `phase_handlers` in the OrchestrationSpec:

```json
{
  "phase_handlers": {
    "verify_complete": {
      "phase": "verify_complete",
      "action": "serve_next_turn",
      "max_occurrences": 10
    },
    "degraded": {
      "phase": "degraded",
      "action": "raise_temp",
      "config_override": {"temp": 0.5},
      "max_occurrences": 3
    },
    "error": {
      "phase": "error",
      "action": "retry_turn",
      "max_occurrences": 2
    }
  }
}
```

The orchestrator handles: spawning, receiving, searching, synthesizing, and done. You configure what happens on verify_complete, degraded, and error.

## Escalation policy

Always include an `escalation_policy` in every spec:

```json
{
  "escalation_policy": {
    "max_retries": 2,
    "retry_temp_delta": 0.1,
    "escalate_after": 3
  }
}
```

- `max_retries` — per-turn retry limit before moving to next recovery step.
- `retry_temp_delta` — temperature increment per retry.
- `escalate_after` — consecutive errors before escalating to the user.

## Reference documents

- `references/orchestration-spec-schema.md` — complete field reference for OrchestrationSpec, ModelProfile, TurnSpec, Phase, PhaseHandler.
- `references/model-profiles.md` — default profile registry and hardware-specific degenerate risk flags.
