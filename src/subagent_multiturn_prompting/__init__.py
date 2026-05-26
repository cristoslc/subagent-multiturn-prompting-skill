"""subagent-multiturn-prompting — Temporal steer-by-wire for multi-model subagent fleets."""

__version__ = "0.1.0"

from .acpx_transport import AcpxTransport, TurnResult as TurnResult
from .degenerate_detector import is_degenerate as is_degenerate
from .model_lifecycle import LifecycleState, ModelLifecycleManager
from .orchestrator import (
    EscalationPolicy,
    OrchestrationResult,
    OrchestrationSpec,
    Orchestrator,
    Phase,
    PhaseHandler,
    TurnSpec,
)
from .profile_registry import DegenerateRisk, ModelProfile, default_registry

__all__ = [
    "AcpxTransport",
    "DegenerateRisk",
    "EscalationPolicy",
    "LifecycleState",
    "ModelLifecycleManager",
    "ModelProfile",
    "OrchestrationResult",
    "OrchestrationSpec",
    "Orchestrator",
    "Phase",
    "PhaseHandler",
    "TurnResult",
    "TurnSpec",
    "default_registry",
    "is_degenerate",
]
