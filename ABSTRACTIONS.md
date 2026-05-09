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

How to load and configure a model for a given role.

```python
@dataclass
class ModelProfile:
    name: str                     # "explorer", "critic", "thinker"
    model: str                    # model path or repo (e.g. "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit")
    agent: str                    # opencode agent name ("explore", "general", "build")
    temperature: float            # 0.0–1.0
    max_tokens_default: int       # fallback if TurnSpec doesn't override
    memory_gb: float              # expected RAM usage (for lifecycle management)
    degenerate_risk:              # known failure modes for this model
        low_temp: bool            # True if model degrades at temp ≤ 0.2
        long_prompt: bool         # True if model degrades on >500 token single prompts
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
    phase_handlers: dict[Phase, PhaseHandler]  # per-phase behavior
    escalation_policy:            # what to do when a turn fails
        max_retries: int          # per-turn retry limit (default: 2)
        retry_temp_delta: float   # temperature bump on retry (default: +0.1)
        escalate_after: int       # consecutive errors before parent escalation (default: 3)
```

### Phase

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

### PhaseReport

What the subagent sends back at phase transitions.

```python
@dataclass
class PhaseReport:
    phase: Phase                   # current phase
    turn_number: int               # which turn this report is for
    confidence:                    # structural confidence (source_count, quorum, self_critique)
        level: str                 # "high" | "med" | "low" | "directional"
        source_count: int          # independent sources backing claims (0 if not applicable)
        quorum: int                # sibling subagents converging (0 if not applicable)
        self_flagged: bool         # did subagent flag potential errors in its own output?
    output: str                    # the turn's text output (empty tuple if intermediate)
    error: Optional[str]           # error message if phase=error
    metadata: dict[str, Any]       # extensible bag for future fields
```

### PhaseHandler

How the orchestrator responds to a phase declaration.

```python
@dataclass
class PhaseHandler:
    phase: Phase                   # which phase this handles
    action: str                    # "serve_next_turn" | "retry_turn" | "raise_temp" |
                                   # "switch_model" | "escalate_to_parent" | "return_result"
    config_override: Optional[dict]# if action modifies config (e.g. {"temp": 0.5})
    max_occurrences: int           # how many times this handler can fire per run (default: unlimited)
```

---

## Pull Model vs Push Model

### Push Model (dispatch-opencode)

```
Parent agent:  render(full_task, permissions) → ACP prompt → opencode → model
Subagent role: passive receiver. Gets everything at once. Single response.
```

Properties:
- Stateless subagent — runs once, returns once
- Permission policy baked into dispatch (per-kind allowlist)
- Artifact layout: `.dispatch-opencode/<task-id>/`
- Works for: self-contained tasks, any model that handles large single prompts

### Pull Model (subagent-orchestrator)

```
Parent agent:  define(spec: profiles + turns + phase_handlers) → orchestrator
Orchestrator:  Turn 1 → model; wait for phase=verify_complete
Orchestrator:  Turn 2 → model (with prior context); wait for phase=verify_complete
               ...
Orchestrator:  Turn N → return result to parent
Subagent role: active participant. Declares phase. Requests next turn implicitly.
```

Properties:
- Stateful across turns — cumulative context in model's conversation
- Orchestrator owns routing, not the parent agent
- Model lifecycle managed between turns (hot-switch if needed)
- Works for: models requiring incremental delivery, multi-step verification workflows

---

## Model Lifecycle Manager

```python
class ModelLifecycleManager:
    """Tracks which model is loaded and manages hot-switching."""
    
    active_model: Optional[str]          # currently loaded model path
    active_memory_gb: float              # RAM consumed by active model
    system_ram_gb: float                 # total system RAM (e.g., 36 GB)
    system_memory_bandwidth_gb_s: float  # bandwidth constraint (e.g., 150 GB/s)
    profiles: dict[str, ModelProfile]    # all known model profiles
    
    def can_load(self, profile: ModelProfile) -> bool:
        """Check if model fits based on active + requested + OS overhead."""
        
    def hot_switch(self, from_profile: str, to_profile: str) -> bool:
        """Unload `from`, load `to`. Returns True on success.
        Must handle: Metal OOM, temp file conflicts, session reuse."""
        
    def evict(self, profile: str) -> bool:
        """Force-unload a model (e.g., on repeated OOM)."""
        
    def health_check(self) -> dict:
        """Current state: which model, RAM used, swap pressure."""
```

Constraints on M3 Pro 36GB:
- macOS overhead: ~3-4 GB
- Usable for models: ~22 GB
- Gemma4 (15 GB) + DeepSeek (8.85 GB) = 23.85 GB → cannot load simultaneously
- Max single model: ~20 GB (leaves ~2 GB for KV cache + framework)
- Load time: Gemma4 ~5s, DeepSeek-Coder ~2s
- Hot-switch latency: unload + load = ~7-8s worst case

---

## Degenerate Output Detection

Some model/profile combinations produce repetitive/degenerate output (e.g., Gemma4 at temp ≤ 0.2 on >500 token structured prompts). The orchestrator detects and recovers:

```python
def is_degenerate(text: str) -> bool:
    """Check if output is a repetitive loop rather than meaningful text."""
    lines = text.strip().split("\n")
    if len(lines) > 20:
        # Check for identical repeating 5-line blocks
        chunks = [lines[i:i+5] for i in range(0, len(lines), 5)]
        for chunk in chunks:
            stripped = [l.strip() for l in chunk if l.strip()]
            if len(stripped) >= 3 and len(set(stripped)) == 1:
                return True
    if len(text) > 200:
        # Check for copy-paste mid-output
        half = len(text) // 2
        if text[:100] == text[half:half+100]:
            return True
    return False
```

Recovery actions (ordered by escalation):
1. **Retry same turn with higher temperature** (+0.1 to +0.2)
2. **Reduce max_tokens** for the failing turn
3. **Switch to alternative model** (if profile has a fallback)
4. **Escalate to parent agent** ("Degenerate output on Turn 3 with Gemma4 at temp 0.2. Suggestions?")

---

## Profile Registry

The orchestrator ships with a default profile registry. Harness-level configuration extends it.

```yaml
# default-profiles.yaml — ships with the orchestrator

explorer:
  model: "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit"
  agent: explore
  temperature: 0.3
  max_tokens_default: 400
  memory_gb: 8.85
  degenerate_risk:
    low_temp: false
    long_prompt: false
    thinking_leak: false

critic:
  model: "mlx-community/gemma-4-26b-a4b-it-4bit"
  agent: general
  temperature: 0.4              # minimum safe temp for structured output
  max_tokens_default: 400       # per verification turn
  max_tokens_synthesis: 1000    # final synthesis turn
  memory_gb: 15.0
  degenerate_risk:
    low_temp: true              # degrades at ≤ 0.2
    long_prompt: true           # degrades on >500 token single prompts
    thinking_leak: false

thinker:
  model: "mlx-community/gemma-4-26b-a4b-it-4bit"
  agent: general
  temperature: 0.5              # higher for divergent reasoning
  max_tokens_default: 600
  memory_gb: 15.0
  degenerate_risk:
    low_temp: true
    long_prompt: false          # thinker prompts tend to be short, open-ended
    thinking_leak: false

fast_code:
  model: "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit"
  agent: build
  temperature: 0.2
  max_tokens_default: 1200
  memory_gb: 8.85
  degenerate_risk:
    low_temp: false
    long_prompt: false
    thinking_leak: false
```
