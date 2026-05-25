"""Unit tests for TurnSpec prompt rendering."""
from subagent_multiturn_prompting.orchestrator import TurnSpec, EscalationPolicy, PhaseHandler
from subagent_multiturn_prompting.profile_registry import ModelProfile, DegenerateRisk, default_registry


class TestPromptRendering:
    def test_single_placeholder(self):
        spec = TurnSpec(
            turn_number=1,
            profile="explorer",
            max_tokens=400,
            prompt_template="Research: {{ task_spec }}",
        )
        assert spec.render_prompt("Portland shipbuilding") == "Research: Portland shipbuilding"

    def test_curly_brace_placeholder(self):
        spec = TurnSpec(
            turn_number=1,
            profile="explorer",
            max_tokens=400,
            prompt_template="Research: {task_spec}",
        )
        assert spec.render_prompt("Portland shipbuilding") == "Research: Portland shipbuilding"

    def test_prior_context_included(self):
        spec = TurnSpec(
            turn_number=2,
            profile="critic",
            max_tokens=400,
            prompt_template="Verify: {{ task_spec }}\nPrior: {{ prior_output }}",
            requires_prior_context=True,
        )
        result = spec.render_prompt(
            "Portland shipbuilding",
            prior_output="Found 3 active yards."
        )
        assert "Portland shipbuilding" in result
        assert "Found 3 active yards." in result

    def test_prior_context_ignored_when_false(self):
        spec = TurnSpec(
            turn_number=1,
            profile="critic",
            max_tokens=400,
            prompt_template="First look: {{ task_spec }}",
            requires_prior_context=False,
        )
        result = spec.render_prompt("test", prior_output="extra")
        assert "extra" not in result

    def test_curly_brace_prior(self):
        spec = TurnSpec(
            turn_number=2,
            profile="critic",
            max_tokens=400,
            prompt_template="Verify: {task_spec}\nPrior: {prior_output}",
            requires_prior_context=True,
        )
        result = spec.render_prompt("task", prior_output="prev")
        assert "task" in result
        assert "prev" in result

    def test_both_styles_mixed(self):
        spec = TurnSpec(
            turn_number=2,
            profile="critic",
            max_tokens=400,
            prompt_template="{{ task_spec }} and {task_spec}",
            requires_prior_context=True,
        )
        result = spec.render_prompt("test", prior_output="prev")
        assert result == "test and test"

class TestTurnSpecFromDict:
    def test_minimal(self):
        d = {
            "turn_number": 1,
            "profile": "explorer",
            "max_tokens": 400,
            "prompt_template": "hello",
        }
        spec = TurnSpec.from_dict(d)
        assert spec.turn_number == 1
        assert spec.profile == "explorer"
        assert spec.max_tokens == 400
        assert spec.prompt_template == "hello"
        assert spec.requires_prior_context is False

    def test_full(self):
        d = {
            "turn_number": 2,
            "profile": "critic",
            "max_tokens": 400,
            "prompt_template": "verify",
            "requires_prior_context": True,
            "model": "custom-model",
            "agent": "custom-agent",
            "temperature": 0.4,
        }
        spec = TurnSpec.from_dict(d)
        assert spec.model == "custom-model"
        assert spec.agent == "custom-agent"
        assert spec.temperature == 0.4
        assert spec.requires_prior_context is True

    def test_default_temperature_none(self):
        d = {
            "turn_number": 1,
            "profile": "explorer",
            "max_tokens": 400,
            "prompt_template": "hello",
        }
        spec = TurnSpec.from_dict(d)
        assert spec.temperature is None


class TestEscalationPolicy:
    def test_defaults(self):
        p = EscalationPolicy()
        assert p.max_retries == 2
        assert p.retry_temp_delta == 0.1
        assert p.escalate_after == 3

    def test_from_dict(self):
        d = {"max_retries": 5, "retry_temp_delta": 0.2, "escalate_after": 4}
        p = EscalationPolicy.from_dict(d)
        assert p.max_retries == 5
        assert p.retry_temp_delta == 0.2
        assert p.escalate_after == 4


class TestPhaseHandler:
    def test_defaults(self):
        h = PhaseHandler(phase="degraded", action="raise_temp")
        assert h.config_override == {}
        assert h.max_occurrences == 1000000

    def test_from_dict(self):
        d = {
            "phase": "degraded",
            "action": "raise_temp",
            "config_override": {"temp": 0.5},
            "max_occurrences": 3,
        }
        h = PhaseHandler.from_dict(d)
        assert h.max_occurrences == 3
        assert h.config_override == {"temp": 0.5}


class TestModelProfileFromDict:
    def test_full(self):
        d = {
            "model": "test-model",
            "agent": "explore",
            "temperature": 0.3,
            "max_tokens_default": 400,
            "memory_gb": 8.0,
            "degenerate_risk": {
                "low_temp": False,
                "long_prompt": True,
                "thinking_leak": False,
            },
        }
        p = ModelProfile.from_dict("explorer", d)
        assert p.name == "explorer"
        assert p.degenerate_risk.low_temp is False
        assert p.degenerate_risk.long_prompt is True
        assert p.max_tokens_synthesis is None

    def test_with_synthesis(self):
        d = {
            "model": "test-model",
            "agent": "general",
            "temperature": 0.4,
            "max_tokens_default": 400,
            "max_tokens_synthesis": 1000,
            "memory_gb": 15.0,
            "degenerate_risk": {
                "low_temp": True,
                "long_prompt": False,
                "thinking_leak": False,
            },
        }
        p = ModelProfile.from_dict("critic", d)
        assert p.max_tokens_synthesis == 1000
        assert p.degenerate_risk.low_temp is True


class TestDefaultRegistry:
    def test_has_four_profiles(self):
        reg = default_registry()
        assert set(reg.keys()) == {"explorer", "critic", "thinker", "fast_code"}

    def test_critic_memory(self):
        reg = default_registry()
        assert reg["critic"].memory_gb == 15.0

    def test_explorer_risk(self):
        reg = default_registry()
        assert reg["explorer"].degenerate_risk.low_temp is False

    def test_critic_risk(self):
        reg = default_registry()
        assert reg["critic"].degenerate_risk.low_temp is True
        assert reg["critic"].degenerate_risk.long_prompt is True

    def test_fast_code_model(self):
        reg = default_registry()
        assert reg["fast_code"].max_tokens_default == 1200
