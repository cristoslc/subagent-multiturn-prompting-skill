# Default Model Profiles

Default profiles that the spec author uses when constructing OrchestrationSpecs. The harness maps these profiles to concrete models and hardware at dispatch time.

## explorer

```yaml
name: explorer
temperature: 0.3
max_tokens_default: 400
degenerate_risk:
  low_temp: false
  long_prompt: false
  thinking_leak: false
```

Use for: codebase exploration, research, fact-finding, single-source discovery.

## critic

```yaml
name: critic
temperature: 0.4               # minimum safe temp for structured output
max_tokens_default: 400        # per verification turn
max_tokens_synthesis: 1000     # final synthesis turn
degenerate_risk:
  low_temp: true               # degrades at <= 0.2
  long_prompt: true            # degrades on >500 token single prompts
  thinking_leak: false
```

Use for: verification, contradiction detection, source checking, synthesis briefs. **Warning:** degenerate at temp ≤ 0.2 and on prompts > 500 tokens. Use pull model with incremental delivery (this skill).

## thinker

```yaml
name: thinker
temperature: 0.5               # higher for divergent reasoning
max_tokens_default: 600
degenerate_risk:
  low_temp: true
  long_prompt: false           # thinker prompts tend to be short, open-ended
  thinking_leak: false
```

Use for: divergent reasoning, open-ended analysis, brainstorming.

## fast_code

```yaml
name: fast_code
temperature: 0.2
max_tokens_default: 1200
degenerate_risk:
  low_temp: false
  long_prompt: false
  thinking_leak: false
```

Use for: code generation, editing, refactoring with high token budgets.

## How profiles are consumed

The spec author selects profiles and designs turn sequences. The harness maps each profile to a concrete model, temperature, and token budget. The harness manages hardware scheduling, model lifecycle, and concurrent sessions. This file defines the profile archetypes; the harness provides the runtime binding.
