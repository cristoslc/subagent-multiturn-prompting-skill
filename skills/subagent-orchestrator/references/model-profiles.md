# Default Model Profiles

The orchestrator ships with these default profiles. Users extend them at the harness level.

## explorer

```yaml
name: explorer
model: mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit
agent: explore
temperature: 0.3
max_tokens_default: 400
memory_gb: 8.85
degenerate_risk:
  low_temp: false
  long_prompt: false
  thinking_leak: false
```

Use for: codebase exploration, research, fact-finding, single-source discovery.

## critic

```yaml
name: critic
model: mlx-community/gemma-4-26b-a4b-it-4bit
agent: general
temperature: 0.4               # minimum safe temp for structured output
max_tokens_default: 400        # per verification turn
max_tokens_synthesis: 1000     # final synthesis turn
memory_gb: 15.0
degenerate_risk:
  low_temp: true               # degrades at <= 0.2
  long_prompt: true            # degrades on >500 token single prompts
  thinking_leak: false
```

Use for: verification, contradiction detection, source checking, synthesis briefs. **Warning:** degenerate at temp ≤ 0.2 and on prompts > 500 tokens. Use pull model with incremental delivery.

## thinker

```yaml
name: thinker
model: mlx-community/gemma-4-26b-a4b-it-4bit
agent: general
temperature: 0.5               # higher for divergent reasoning
max_tokens_default: 600
memory_gb: 15.0
degenerate_risk:
  low_temp: true
  long_prompt: false           # thinker prompts tend to be short, open-ended
  thinking_leak: false
```

Use for: divergent reasoning, open-ended analysis, brainstorming.

## fast_code

```yaml
name: fast_code
model: mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit
agent: build
temperature: 0.2
max_tokens_default: 1200
memory_gb: 8.85
degenerate_risk:
  low_temp: false
  long_prompt: false
  thinking_leak: false
```

Use for: code generation, editing, refactoring with high token budgets.

## Hardware constraints (M3 Pro 36GB)

| Component | Memory |
|---|---|
| macOS overhead | 3-4 GB |
| Usable for models | ~22 GB |
| Gemma4 models (critic, thinker) | 15.0 GB each |
| DeepSeek-Coder models (explorer, fast_code) | 8.85 GB each |
| Gemma4 + DeepSeek-Coder combined | 23.85 GB — **OOM, cannot load simultaneously** |

Maximum one model at a time when profiles sum to > 22 GB. Hot-switch latency: ~7-8s (unload + load).
