"""Shared pytest fixtures."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from subagent_multiturn_prompting.acpx_transport import AcpxTransport, TurnResult
from subagent_multiturn_prompting.model_lifecycle import ModelLifecycleManager, LifecycleState
from subagent_multiturn_prompting.orchestrator import Orchestrator, OrchestrationSpec, TurnSpec, PhaseHandler, EscalationPolicy
from subagent_multiturn_prompting.profile_registry import ModelProfile, DegenerateRisk, default_registry


@pytest.fixture
def registry():
    return default_registry()


pytest_plugins = ["pytest_asyncio"]


class FakeTransport(AcpxTransport):
    """Mock transport for testing."""
    def __init__(self, responses: list[TurnResult] = None):
        super().__init__(acpx_bin="/bin/true")
        self.calls: list[dict[str, Any]] = []
        self._responses = list(responses) if responses else []

    async def dispatch(self, **kwargs) -> TurnResult:
        self.calls.append(kwargs)
        if self._responses:
            return self._responses.pop(0)
        return TurnResult(text="ok", phase="done", turn_number=0, metadata={})


@pytest.fixture
def explorer_profile(registry):
    return registry["explorer"]


@pytest.fixture
def critic_profile(registry):
    return registry["critic"]


@pytest.fixture
def single_turn_spec(registry):
    return OrchestrationSpec(
        task_id="test-001",
        profiles=registry,
        turns=[
            TurnSpec(
                turn_number=1,
                profile="explorer",
                max_tokens=400,
                prompt_template="Research: {{ task_spec }}",
                requires_prior_context=False,
            )
        ],
        phase_handlers={},
        escalation_policy=EscalationPolicy(),
    )


@pytest.fixture
def multi_turn_spec(registry):
    return OrchestrationSpec(
        task_id="test-002",
        profiles=registry,
        turns=[
            TurnSpec(
                turn_number=1,
                profile="critic",
                max_tokens=400,
                prompt_template="Verify: {{ task_spec }}",
                requires_prior_context=False,
            ),
            TurnSpec(
                turn_number=2,
                profile="critic",
                max_tokens=400,
                prompt_template="Verify again: {{ task_spec }}\nPrior: {{ prior_output }}",
                requires_prior_context=True,
            ),
        ],
        phase_handlers={
            "degraded": PhaseHandler(phase="degraded", action="raise_temp"),
            "verify_complete": PhaseHandler(phase="verify_complete", action="serve_next_turn"),
        },
        escalation_policy=EscalationPolicy(),
    )


@pytest.fixture
def gemma_critic_spec(registry):
    """5-turn critic workflow for Gemma4 — matches behavioral test beh-002."""
    profiles = {"critic": registry["critic"]}
    turns = []
    for i in range(1, 5):
        turns.append(TurnSpec(
            turn_number=i,
            profile="critic",
            max_tokens=400,
            prompt_template=f"Verify exploration {i}: {{ task_spec }}",
            requires_prior_context=(i > 1),
        ))
    turns.append(TurnSpec(
        turn_number=5,
        profile="critic",
        max_tokens=1000,
        prompt_template="Synthesize verified findings: {{ task_spec }}\nPrior: {{ prior_output }}",
        requires_prior_context=True,
        temperature=0.3,
    ))
    return OrchestrationSpec(
        task_id="gemma-critic-test",
        profiles=profiles,
        turns=turns,
        phase_handlers={
            "degraded": PhaseHandler(phase="degraded", action="raise_temp"),
            "verify_complete": PhaseHandler(phase="verify_complete", action="serve_next_turn"),
        },
        escalation_policy=EscalationPolicy(),
    )


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"
