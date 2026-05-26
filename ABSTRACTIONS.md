# ABSTRACTIONS

## Core Data Structures

### TurnSpec

A single turn in a multi-turn orchestration.

```python
@dataclass
class TurnSpec:
    turn_number: int              # 1-indexed position in sequence
    profile: str                  # logical profile name ("explorer", "critic")
    max_tokens: int               # output token budget for this turn
    prompt_template: str          # template with {prior_output} and {task_spec} vars
    requires_prior_context: bool  # True if this turn needs accumulated history
```

### ModelProfile

How to configure a model for a given role.

```python
@dataclass
class ModelProfile:
    name: str                     # "explorer", "critic", "thinker"
    model: str                    # model path or repo
    agent: str                    # opencode agent name ("explore", "general", "build")
    temperature: float            # 0.0–1.0
    max_tokens_default: int       # fallback if TurnSpec doesn't override
    degenerate_risk:
        low_temp: bool            # True if model degrades at temp ≤ 0.2
        long_prompt: bool         # True if model degrades on >500 token prompts
        thinking_leak: bool       # True if reasoning distills leak thinking tokens
```

### OrchestrationSpec

The complete specification for a run, provided by the parent agent.

```python
@dataclass
class OrchestrationSpec:
    task_id: str                  # unique run identifier
    profiles: dict[str, ModelProfile]  # profile name → profile config
    turns: list[TurnSpec]         # ordered turn sequence
    phase_handlers: dict[str, PhaseHandler]  # per-phase behavior
    escalation_policy:
        max_retries: int          # per-turn retry limit (default: 2)
        retry_temp_delta: float   # temperature bump on retry (default: +0.1)
        escalate_after: int       # consecutive errors before parent escalation (default: 3)
```

### Phase

```python
class Phase(Enum):
    SPAWNING = "spawning"
    RECEIVING = "receiving"
    SEARCHING = "searching"
    SYNTHESIZING = "synthesizing"
    TOOL_CALLING = "tool_calling"
    VERIFY_COMPLETE = "verify_complete"
    DEGRADED = "degraded"
    ERROR = "error"
    DONE = "done"
```

## How the Project Is Consumed

A harness:
1. Reads an OrchestrationSpec (from file or parent agent)
2. Calls `multiturn_run(spec)` → run_id
3. Spawns a subagent session for the profile on turn 1
4. Calls `multiturn_prompt(run_id)` → get the rendered turn prompt
5. Sends the prompt to the subagent
6. On `verify_complete`, calls `multiturn_prompt(run_id)` again for turn 2 (with prior context)
7. Repeats until `done`

The harness manages the subagent session, concurrency, error recovery, and provider routing. This project provides turn sequencing.
