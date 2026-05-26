# PURPOSE

subagent-multiturn-prompting provides a progressive-disclosure protocol for subagents that degenerate on large single prompts. The orchestrator defines a multi-turn specification — each turn is a self-contained prompt chunk with prior-context injection. Subagents invoke an MCP tool to request the next turn when ready, maintaining clean output across complex tasks. The spec is consumed by existing harnesses (`llm`, `opencode run`, `ollama launch`); the project provides the schema, validation, and protocol definition — not a runtime.
