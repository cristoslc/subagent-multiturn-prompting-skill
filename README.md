# subagent-orchestrator

Temporal steer-by-wire for multi-model subagent fleets.

## Status

**Spec complete, pre-runnable.** The skill definition, schema references, behavioral/adversarial tests, and a spec-validation script are all written and passing. The orchestrator implementation (MCP server, acpx transport binding, and model-lifecycle runtime) has not yet been built. This skill is currently **read-only** — it teaches an agent how to construct and validate `OrchestrationSpec`s, but cannot dispatch them.

| Component | State |
|---|---|
| `spec.md`, `PURPOSE.md`, `ARCHITECTURE.md`, `ABSTRACTIONS.md` | **Done** |
| `SKILL.md` + `references/` (`orchestration-spec-schema.md`, `model-profiles.md`) | **Done** |
| `scripts/validate-orchestration-spec.sh` + acceptance tests | **Done** (12/12 passing) |
| `tests/behavioral-tests.json` | **Evaluated** (27/27 passing) |
| `tests/adversarial-tests.json` | **Written**, not yet evaluated |
| Runtime: MCP server, acpx transport, model lifecycle | **Not started** |

## Quickstart

Read `PURPOSE.md` for the architectural thesis and `ABSTRACTIONS.md` for data structures.

## Key References

- `skills/subagent-orchestrator/SKILL.md` — skill definition loaded by the host agent
- `skills/subagent-orchestrator/spec.md` — intent, boundaries, and script contracts
- `skills/subagent-orchestrator/references/orchestration-spec-schema.md` — complete field reference
- `skills/subagent-orchestrator/references/model-profiles.md` — default profile registry and hardware constraints
- Related: `../dispatch-opencode-skill/` — ACP transport adapter (complement, not dependency)
- Transport: `acpx` — the ACP client this orchestrator will call (https://github.com/nicolaide/acpx)

## Project Layout

```
subagent-orchestrator-skill/
├── README.md              # this file
├── PURPOSE.md             # architectural thesis and constraints
├── ARCHITECTURE.md        # layer stack, core loop, MCP tool surface
├── ABSTRACTIONS.md        # data structures and detection algorithms
├── skills/
│   └── subagent-orchestrator/
│       ├── SKILL.md       # skill definition (complete)
│       ├── spec.md        # lightweight intent + script contracts
│       ├── references/
│       │   ├── orchestration-spec-schema.md
│       │   └── model-profiles.md
│       ├── scripts/
│       │   └── validate-orchestration-spec.sh
│       └── tests/
│           ├── behavioral-tests.json
│           ├── adversarial-tests.json
│           ├── test-validate-orchestration-spec.sh
│           └── .eval-results.json
```

`docs/` and `src/` listed in earlier layout drafts have been removed until the runtime implementation starts.

## Design Decisions

1. **Pull model over push.** Subagents request turns; they do not receive a pre-rendered monolith.
2. **acpx for transport.** Do not re-implement ACP client logic.
3. **MCP server interface.** The orchestrator is a tool the host agent calls via MCP, not a separate agent runtime.
4. **Phase-state protocol is the core primitive.** Turn sequencing, degraded escalation, and model hot-switching all hang off phase reports.

## Roadmap

1. ~~**Spec phase**~~ ✅ — swain-design artifacts, schema, and model-lifecycle constraints defined.
2. **Prototype** — MCP server with hardcoded turn specs for Gemma4 critic test. Validate pull model end-to-end. *Blocked on `src/` implementation and acpx integration.*
3. **Generalize** — configurable turn specs, model profile registry, degraded-state escalation rules.
4. **Harness integration** — test against Claude Code, opencode, and dispatch-opencode transport.

## License

MIT (planned — aligns with trove sources and ecosystem norms)
