# subagent-multiturn-prompting specification

## What it should do
- Teach agents when and how to construct an OrchestrationSpec for multi-turn progressive-disclosure subagent dispatch
- Route tasks to the correct model profile (explorer/critic/thinker/fast_code) based on task characteristics
- Define turn sequences with prior-context injection: per-verification-item turns then a synthesis turn
- Write prompt templates using `{task_spec}` and `{prior_output}` variables that the harness fills
- Distinguish when to use progressive disclosure (multi-turn, models that degenerate on large prompts) vs direct dispatch (single turn, self-contained)

## What it must NOT do
- Must not implement subagent sessions — the harness serves MCP tools and manages sessions
- Must not implement model lifecycle or hardware management — the harness does that
- Must not manage git worktrees — the harness does that
- Must not override the host agent's AGENTS.md or agent profiles
- Must not replace dispatch-opencode — it serves push-model use cases

## Boundaries
- Owns: skills/subagent-multiturn-prompting/** (this skill directory)
- Reads but never writes: the harness MCP server's OrchestrationSpec format
- Forbidden: must never modify the host agent's AGENTS.md, .opencode/ directory, or agent profiles

## Scripts
- scripts/validate-orchestration-spec.sh — validates a given orchestration spec (YAML or JSON) against the OrchestrationSpec schema. Input: file path or stdin. Output: OK or JSON error list. Exit codes: 0 (valid), 1 (invalid), 2 (not-json-or-yaml), 10 (depends-on-degenerate-risk-not-set).
