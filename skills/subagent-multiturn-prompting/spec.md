# subagent-multiturn-prompting specification

## What it should do
- Teach agents when and how to construct an OrchestrationSpec for multi-turn, multi-model subagent dispatch with pull-model phase-state control
- Route tasks to the correct model profile (explorer/critic/thinker/fast_code) based on task characteristics
- Interpret PhaseReports from the orchestrator and decide on next actions (serve next turn, retry, switch model, escalate)
- Handle degenerate output detection and recovery: retry with higher temp, reduce max_tokens, switch model, or escalate to parent
- Manage model lifecycle awareness on constrained hardware (detect when profiles would OOM if loaded together)
- Distinguish when to use the orchestrator (multi-turn, multi-model, incremental delivery) vs direct subagent dispatch (single turn, self-contained)

## What it must NOT do
- Must not implement ACP transport — the orchestrator delegates to acpx
- Must not manage git worktrees — the harness does that
- Must not override the host agent's AGENTS.md or agent profiles
- Must not replace dispatch-opencode — it serves push-model use cases
- Must not attempt to load two models simultaneously on hardware where combined memory exceeds available Metal RAM

## Boundaries
- Owns: skills/subagent-multiturn-prompting/** (this skill directory)
- Reads but never writes: the orchestrator MCP server's configuration and profile registry
- Forbidden: must never modify the host agent's AGENTS.md, .opencode/ directory, or agent profiles

## Scripts
- scripts/validate-orchestration-spec.sh — validates a given orchestration spec (YAML or JSON) against the OrchestrationSpec schema. Input: file path or stdin. Output: OK or JSON error list. Exit codes: 0 (valid), 1 (invalid), 2 (not-json-or-yaml), 10 (depends-on-degenerate-risk-not-set).
