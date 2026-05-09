# subagent-orchestrator

Temporal steer-by-wire for multi-model subagent fleets.

## Status

**Discovery phase.** Trove `subagent-orchestration@a18b123` gathered 8 sources on subagent patterns, Goose/Goosetown, opencode agent config, and MCP orchestration. Three gaps identified that no existing tool fills.

## Quickstart

Read `PURPOSE.md` for the architectural thesis.

## Key References

- Trove: `../scrap/docs/troves/subagent-orchestration/synthesis.md` — landscape of existing tools
- Related: `../dispatch-opencode-skill/` — ACP transport adapter (complement, not dependency)
- Transport: `acpx` — the ACP client this orchestrator will call (https://github.com/nicolaide/acpx)
- Empirical evidence: `../scrap/gemma4-recon-swarm-multiturn.json` — 10/10 on M3 Pro 36GB with pull model

## Project Layout

```
subagent-orchestrator-skill/
├── README.md              # this file
├── PURPOSE.md             # architectural thesis and constraints
├── skills/
│   └── subagent-orchestrator/
│       └── SKILL.md       # skill definition (not yet written)
├── docs/
│   ├── design/            # swain-design artifacts
│   └── troves/            # research troves
└── src/                   # orchestrator implementation
    └── mcp-server/        # MCP server (Python, Node, or Go — TBD)
```

## Design Decisions (pre-design, from trove research)

1. **Pull model over push.** Subagents request turns; they do not receive a pre-rendered monolith.
2. **acpx for transport.** Don't re-implement ACP client logic.
3. **MCP server interface.** The orchestrator is a tool the host agent calls via MCP, not a separate agent runtime.
4. **Phase-state protocol is the core primitive.** Turn sequencing, degraded escalation, model hot-switching all hang off phase reports.

## Roadmap

1. **Spec phase** — swain-design artifact (spike or ADR) defining the orchestrator contract, phase-state wire format, and model lifecycle constraints.
2. **Prototype** — MCP server with hardcoded turn specs for Gemma4 critic test. Validate pull model end-to-end.
3. **Generalize** — configurable turn specs, model profile registry, degraded-state escalation rules.
4. **Harness integration** — test against Claude Code, opencode, and dispatch-opencode transport.

## License

MIT (planned — aligns with trove sources and ecosystem norms)
