"""Unit tests for model lifecycle management."""
import pytest

from subagent_multiturn_prompting.model_lifecycle import LifecycleState, ModelLifecycleManager
from subagent_multiturn_prompting.profile_registry import ModelProfile, DegenerateRisk


@pytest.fixture
def manager():
    return ModelLifecycleManager()


@pytest.fixture
def gemma():
    return ModelProfile(
        name="critic",
        model="gemma",
        agent="general",
        temperature=0.4,
        max_tokens_default=400,
        memory_gb=15.0,
        degenerate_risk=DegenerateRisk(),
    )


@pytest.fixture
def deepseek():
    return ModelProfile(
        name="explorer",
        model="deepseek",
        agent="explore",
        temperature=0.3,
        max_tokens_default=400,
        memory_gb=8.85,
        degenerate_risk=DegenerateRisk(),
    )


@pytest.fixture
def tiny():
    return ModelProfile(
        name="tiny",
        model="tiny",
        agent="general",
        temperature=0.5,
        max_tokens_default=400,
        memory_gb=1.0,
        degenerate_risk=DegenerateRisk(),
    )


class TestLifecycleCanLoadTogether:
    def test_two_explorers_ok(self, manager, deepseek):
        assert manager.can_load_together(deepseek, deepseek)

    def test_gemma_plus_deepseek_fails(self, gemma, deepseek):
        # 15.0 + 8.85 = 23.85 > ~22 usable on a constrained system
        state = LifecycleState(system_ram_gb=30.0, system_overhead_gb=8.0)
        constrained_manager = ModelLifecycleManager(state)
        assert not constrained_manager.can_load_together(gemma, deepseek)

    def test_tiny_plus_deepseek_ok(self, gemma, deepseek):
        # 1.0 + 8.85 = 9.85 <= ~22 usable on a constrained system
        tiny = ModelProfile(
            name="tiny",
            model="tiny",
            agent="general",
            temperature=0.5,
            max_tokens_default=400,
            memory_gb=1.0,
            degenerate_risk=DegenerateRisk(),
        )
        state = LifecycleState(system_ram_gb=30.0, system_overhead_gb=8.0)
        constrained_manager = ModelLifecycleManager(state)
        assert constrained_manager.can_load_together(tiny, deepseek)


class TestLifecycleWouldOom:
    def test_gemma_fits(self, manager, gemma):
        # 15.0 < 32 -> fits (single model)
        assert not manager.would_oom(gemma)

    def test_huge_model_ooms(self, manager):
        huge = ModelProfile(
            name="huge",
            model="huge-model",
            agent="general",
            temperature=0.5,
            max_tokens_default=400,
            memory_gb=35.0,
            degenerate_risk=DegenerateRisk(),
        )
        assert manager.would_oom(huge)

    def test_boundary_model_exactly_at_limit(self, manager):
        exact = ModelProfile(
            name="exact",
            model="exact",
            agent="general",
            temperature=0.5,
            max_tokens_default=400,
            memory_gb=36.0,
            degenerate_risk=DegenerateRisk(),
        )
        assert manager.would_oom(exact)


class TestRecommendSequence:
    def test_sorts_descending(self, manager, gemma, deepseek, tiny):
        seq = manager.recommend_sequence([tiny, gemma, deepseek])
        assert seq[0].name == "critic"  # gemma 15.0
        assert seq[1].name == "explorer"  # deepseek 8.85
        assert seq[2].name == "tiny"

    def test_single_profile(self, manager, tiny):
        seq = manager.recommend_sequence([tiny])
        assert len(seq) == 1
        assert seq[0].name == "tiny"


class TestLifecycleState:
    def test_usable_ram_default(self):
        state = LifecycleState()
        assert state.usable_ram_gb == 32.0  # 36 - 4

    def test_custom_system(self):
        state = LifecycleState(system_ram_gb=64.0, system_overhead_gb=8.0)
        assert state.usable_ram_gb == 56.0
