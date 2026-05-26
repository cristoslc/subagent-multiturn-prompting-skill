# subagent-multiturn-prompting

Progressive-disclosure protocol for single-agent multi-turn prompts. Defines the OrchestrationSpec schema, turn sequencing, and validation — consumed by existing harnesses, not a runtime.

## Status

**Spec phase.** Schema defined, validation script exists, behavioral tests passing (27/27). No MCP server or runtime code.

## Project Layout

```
subagent-multiturn-prompting-skill/
├── PURPOSE.md
├── ARCHITECTURE.md
├── ABSTRACTIONS.md
├── README.md
├── skills/
│   └── subagent-multiturn-prompting/
│       ├── SKILL.md
│       ├── spec.md
│       ├── references/
│       │   ├── orchestration-spec-schema.md
│       │   └── model-profiles.md
│       ├── scripts/
│       │   └── validate-orchestration-spec.sh
│       └── tests/
│           ├── behavioral-tests.json      (27/27 passing)
│           ├── adversarial-tests.json
│           └── .eval-results.json
```

## How It Works

A harness serves two MCP tools:
- `multiturn_run(spec)` — accept an OrchestrationSpec, return a run_id
- `multiturn_prompt(run_id)` — return the next progressive-disclosure chunk for the subagent

The subagent invokes `multiturn_prompt` when ready for the next turn. The harness manages subagent session lifecycle.

## Related

- `subagent-rank-based-orchestrator` — concurrent fleet dispatch with capability ranks (Novice→Grandmaster). Uses this project's spec format internally for subagent turn serving.
- `validate-orchestration-spec.sh` — validates OrchestrationSpec JSON before dispatch

## License

MIT
