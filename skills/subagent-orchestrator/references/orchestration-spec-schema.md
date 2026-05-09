# OrchestrationSpec Schema Reference

Complete field reference for every data structure in an OrchestrationSpec.

## OrchestrationSpec

| Field | Type | Required | Description |
|---|---|---|---|
| `task_id` | string | yes | Unique run identifier |
| `profiles` | dict[str, ModelProfile] | yes | Profile name → profile config |
| `turns` | list[TurnSpec] | yes | Ordered turn sequence |
| `phase_handlers` | dict[str, PhaseHandler] | no | Per-phase behavior overrides |
| `escalation_policy` | EscalationPolicy | yes | Failure recovery configuration |

### EscalationPolicy

| Field | Type | Required | Description |
|---|---|---|---|
| `max_retries` | int | yes | Per-turn retry limit (default: 2) |
| `retry_temp_delta` | float | yes | Temperature bump on retry (e.g., +0.1) |
| `escalate_after` | int | yes | Consecutive errors before parent escalation (default: 3) |

## ModelProfile

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Profile name ("explorer", "critic", "thinker") |
| `model` | string | yes | Model path or repo |
| `agent` | string | yes | opencode agent name ("explore", "general", "build") |
| `temperature` | float | yes | 0.0–1.0 |
| `max_tokens_default` | int | yes | Fallback if TurnSpec doesn't override |
| `memory_gb` | float | yes | Expected RAM usage for lifecycle management |
| `degenerate_risk` | DegenerateRisk | yes | Known failure modes for this model |

### DegenerateRisk

| Field | Type | Required | Description |
|---|---|---|---|
| `low_temp` | bool | yes | True if model degrades at temp ≤ 0.2 |
| `long_prompt` | bool | yes | True if model degrades on >500 token single prompts |
| `thinking_leak` | bool | yes | True if reasoning distills leak thinking tokens |

## TurnSpec

| Field | Type | Required | Description |
|---|---|---|---|
| `turn_number` | int | yes | 1-indexed position in sequence |
| `profile` | string | yes | Logical profile name — must exist in profiles dict |
| `max_tokens` | int | yes | Output token budget for this turn |
| `prompt_template` | string | yes | Template with `{task_spec}` and `{prior_output}` vars |
| `requires_prior_context` | bool | yes | True if this turn needs accumulated history |

## Phase

```python
class Phase(Enum):
    SPAWNING = "spawning"               # agent transport is being initialized
    RECEIVING = "receiving"             # agent is processing instructions
    SEARCHING = "searching"             # agent is doing exploration work
    SYNTHESIZING = "synthesizing"       # agent is preparing structured output
    TOOL_CALLING = "tool_calling"       # agent is making tool calls
    VERIFY_COMPLETE = "verify_complete" # turn complete, ready for next
    DEGRADED = "degraded"              # output quality below threshold
    ERROR = "error"                     # turn failed (OOM, timeout, bad response)
    DONE = "done"                       # all turns complete, result ready
```

## PhaseHandler

| Field | Type | Required | Description |
|---|---|---|---|
| `phase` | string | yes | Which phase this handles |
| `action` | string | yes | "serve_next_turn" / "retry_turn" / "raise_temp" / "switch_model" / "escalate_to_parent" / "return_result" |
| `config_override` | dict | no | If action modifies config (e.g., `{"temp": 0.5}`) |
| `max_occurrences` | int | no | Max times per run (default: unlimited) |

## PhaseReport

What the subagent sends back at phase transitions:

| Field | Type | Description |
|---|---|---|
| `phase` | string | Current phase |
| `turn_number` | int | Which turn this report is for |
| `confidence.level` | string | "high" / "med" / "low" / "directional" |
| `confidence.source_count` | int | Independent sources backing claims |
| `confidence.quorum` | int | Sibling subagents converging |
| `confidence.self_flagged` | bool | Did subagent flag potential errors? |
| `output` | string | Turn's text output (empty if intermediate phase) |
| `error` | string | Error message if phase=error (optional) |
| `metadata` | dict | Extensible key/value bag |
