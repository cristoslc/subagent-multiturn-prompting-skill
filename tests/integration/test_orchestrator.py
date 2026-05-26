"""Integration tests for the Orchestrator with a mock transport."""
import pytest

from subagent_multiturn_prompting.acpx_transport import TurnResult
from subagent_multiturn_prompting.orchestrator import Orchestrator, PhaseHandler, EscalationPolicy
from tests.conftest import FakeTransport


class TestOrchestratorSingleTurn:
    @pytest.mark.asyncio
    async def test_success(self, single_turn_spec):
        transport = FakeTransport([
            TurnResult(text="Found 3 yards.", phase="done", turn_number=1, metadata={}),
        ])
        orch = Orchestrator(transport)
        result = await orch.run(single_turn_spec, "Portland shipbuilding")
        assert result.status == "done"
        assert result.final_output == "Found 3 yards."
        assert len(result.outputs) == 1
        assert len(transport.calls) == 1
        call = transport.calls[0]
        assert call["agent"] == "explore"
        assert "Portland shipbuilding" in call["prompt"]

    @pytest.mark.asyncio
    async def test_error_phase(self, single_turn_spec):
        transport = FakeTransport([
            TurnResult(text="", phase="error", turn_number=1, metadata={"err": "oom"}),
            TurnResult(text="ok", phase="done", turn_number=1, metadata={}),
        ])
        orch = Orchestrator(transport)
        result = await orch.run(single_turn_spec, "task")
        assert result.status == "done"
        assert result.final_output == "ok"
        assert len(transport.calls) == 2

    @pytest.mark.asyncio
    async def test_error_escalation(self, single_turn_spec):
        transport = FakeTransport([
            TurnResult(text="", phase="error", turn_number=1, metadata={}),
            TurnResult(text="", phase="error", turn_number=1, metadata={}),
            TurnResult(text="", phase="error", turn_number=1, metadata={}),
        ])
        orch = Orchestrator(transport)
        result = await orch.run(single_turn_spec, "task")
        assert result.status == "error"
        assert "Too many consecutive errors" in result.error


class TestOrchestratorMultiTurnPullModel:
    @pytest.mark.asyncio
    async def test_prior_context_accumulation(self, multi_turn_spec):
        transport = FakeTransport([
            TurnResult(text="Yard A found.", phase="verify_complete", turn_number=1, metadata={}),
            TurnResult(text="Yard B found.", phase="done", turn_number=2, metadata={}),
        ])
        orch = Orchestrator(transport)
        result = await orch.run(multi_turn_spec, "Portland shipbuilding")
        assert result.status == "done"
        assert result.final_output == "Yard B found."
        assert len(transport.calls) == 2
        # Turn 2 prompt should include prior output
        turn2_call = transport.calls[1]
        assert "Yard A found." in turn2_call["prompt"]

    @pytest.mark.asyncio
    async def test_temperature_override(self, multi_turn_spec):
        transport = FakeTransport([
            TurnResult(text="ok", phase="done", turn_number=1, metadata={}),
        ])
        orch = Orchestrator(transport)
        result = await orch.run(multi_turn_spec, "task")
        # Default critic temperature is 0.4
        assert transport.calls[0]["temperature"] == 0.4


class TestOrchestratorDegenerateRecovery:
    @pytest.mark.asyncio
    async def test_retry_with_higher_temp(self, single_turn_spec):
        spec = single_turn_spec
        spec.phase_handlers = {
            "degraded": PhaseHandler(phase="degraded", action="raise_temp"),
        }
        transport = FakeTransport([
            TurnResult(text="loop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop\nloop", phase="done", turn_number=1, metadata={}),
            TurnResult(text="Clean output now.", phase="done", turn_number=1, metadata={}),
        ])
        orch = Orchestrator(transport)
        result = await orch.run(spec, "task")
        assert result.status == "done"
        assert result.final_output == "Clean output now."
        assert len(transport.calls) == 2
        assert transport.calls[1]["temperature"] == 0.4  # was 0.3 + 0.1

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, single_turn_spec):
        spec = single_turn_spec
        spec.phase_handlers = {
            "degraded": PhaseHandler(phase="degraded", action="raise_temp"),
        }
        spec.escalation_policy = EscalationPolicy(max_retries=1)
        transport = FakeTransport([
            TurnResult(text="loop\n" * 30, phase="done", turn_number=1, metadata={}),
            TurnResult(text="loop\n" * 30, phase="done", turn_number=1, metadata={}),
            TurnResult(text="loop\n" * 30, phase="done", turn_number=1, metadata={}),
        ])
        orch = Orchestrator(transport)
        result = await orch.run(spec, "task")
        # After 1 retry (total 2 attempts including first), retries exhausted
        assert result.status == "error"
        assert "Retries exhausted" in result.error

    @pytest.mark.asyncio
    async def test_handler_max_occurrences(self, single_turn_spec):
        spec = single_turn_spec
        spec.phase_handlers = {
            "degraded": PhaseHandler(phase="degraded", action="raise_temp", max_occurrences=1),
        }
        transport = FakeTransport([
            TurnResult(text="loop\n" * 30, phase="done", turn_number=1, metadata={}),
            TurnResult(text="loop\n" * 30, phase="done", turn_number=1, metadata={}),
        ])
        orch = Orchestrator(transport)
        result = await orch.run(spec, "task")
        assert result.status == "degraded"
        assert "Recovery exhausted" in result.error

    @pytest.mark.asyncio
    async def test_no_degenerate_skips(self, single_turn_spec):
        spec = single_turn_spec
        transport = FakeTransport([
            TurnResult(text="Normal good output here.", phase="done", turn_number=1, metadata={}),
        ])
        orch = Orchestrator(transport)
        result = await orch.run(spec, "task")
        assert result.status == "done"
        assert len(transport.calls) == 1

    @pytest.mark.asyncio
    async def test_switch_model_action(self):
        from subagent_multiturn_prompting.profile_registry import default_registry
        reg = default_registry()
        from subagent_multiturn_prompting.orchestrator import OrchestrationSpec, TurnSpec
        spec = OrchestrationSpec(
            task_id="switch-test",
            profiles=reg,
            turns=[TurnSpec(
                turn_number=1,
                profile="critic",
                max_tokens=400,
                prompt_template="Test {task_spec}",
            )],
            phase_handlers={"degraded": PhaseHandler(phase="degraded", action="switch_model")},
            escalation_policy=EscalationPolicy(),
        )
        transport = FakeTransport([
            TurnResult(text="loop\n" * 30, phase="done", turn_number=1, metadata={}),
        ])
        orch = Orchestrator(transport)
        result = await orch.run(spec, "task")
        assert result.status == "degraded"
        assert "Switching model" in result.error


class TestOrchestratorLifecycle:
    @pytest.mark.asyncio
    async def test_oom_guard(self, single_turn_spec):
        from subagent_multiturn_prompting.model_lifecycle import ModelLifecycleManager, LifecycleState
        state = LifecycleState(system_ram_gb=10.0, system_overhead_gb=4.0)
        manager = ModelLifecycleManager(state)
        transport = FakeTransport()
        orch = Orchestrator(transport, lifecycle=manager)
        result = await orch.run(single_turn_spec, "task")
        assert result.status == "error"
        assert "Cannot load profile" in result.error
