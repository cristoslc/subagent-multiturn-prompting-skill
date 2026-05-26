"""Core orchestrator: turn loop, phase-state, degenerate recovery."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .acpx_transport import AcpxTransport, TurnResult
from .degenerate_detector import is_degenerate
from .model_lifecycle import ModelLifecycleManager
from .profile_registry import ModelProfile

logger = logging.getLogger(__name__)


class Phase(str, Enum):
    SPAWNING = "spawning"
    RECEIVING = "receiving"
    SEARCHING = "searching"
    SYNTHESIZING = "synthesizing"
    TOOL_CALLING = "tool_calling"
    VERIFY_COMPLETE = "verify_complete"
    DEGRADED = "degraded"
    ERROR = "error"
    DONE = "done"


@dataclass
class TurnSpec:
    turn_number: int
    profile: str
    max_tokens: int
    prompt_template: str
    requires_prior_context: bool = False
    model: str | None = None
    agent: str | None = None
    temperature: float | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TurnSpec":
        return cls(
            turn_number=d["turn_number"],
            profile=d["profile"],
            max_tokens=d["max_tokens"],
            prompt_template=d["prompt_template"],
            requires_prior_context=d.get("requires_prior_context", False),
            model=d.get("model"),
            agent=d.get("agent"),
            temperature=d.get("temperature"),
        )

    def render_prompt(self, task_spec: str, prior_output: str = "") -> str:
        text = self.prompt_template.replace("{{ task_spec }}", task_spec).replace("{task_spec}", task_spec)
        if self.requires_prior_context:
            text = text.replace("{{ prior_output }}", prior_output).replace("{prior_output}", prior_output)
        return text


@dataclass
class EscalationPolicy:
    max_retries: int = 2
    retry_temp_delta: float = 0.1
    escalate_after: int = 3

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EscalationPolicy":
        return cls(
            max_retries=d.get("max_retries", 2),
            retry_temp_delta=d.get("retry_temp_delta", 0.1),
            escalate_after=d.get("escalate_after", 3),
        )


@dataclass
class PhaseHandler:
    phase: str
    action: str
    config_override: dict[str, Any] = field(default_factory=dict)
    max_occurrences: int = 1_000_000

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PhaseHandler":
        return cls(
            phase=d["phase"],
            action=d["action"],
            config_override=d.get("config_override", {}),
            max_occurrences=d.get("max_occurrences", 1_000_000),
        )


@dataclass
class OrchestrationSpec:
    task_id: str
    profiles: dict[str, ModelProfile]
    turns: list[TurnSpec]
    phase_handlers: dict[str, PhaseHandler]
    escalation_policy: EscalationPolicy

    @classmethod
    def from_dict(cls, registry: dict[str, ModelProfile], d: dict[str, Any]) -> "OrchestrationSpec":
        raw_profiles = d.get("profiles", {})
        profiles: dict[str, ModelProfile] = {}
        for name, prof in raw_profiles.items():
            if name in registry:
                merged = {
                    "model": prof.get("model") or registry[name].model,
                    "agent": prof.get("agent") or registry[name].agent,
                    "temperature": prof["temperature"] if "temperature" in prof else registry[name].temperature,
                    "max_tokens_default": prof.get("max_tokens_default") or registry[name].max_tokens_default,
                    "memory_gb": prof.get("memory_gb") or registry[name].memory_gb,
                    "degenerate_risk": prof.get("degenerate_risk", {}),
                }
                for k in ("low_temp", "long_prompt", "thinking_leak"):
                    if k not in merged["degenerate_risk"]:
                        merged["degenerate_risk"][k] = getattr(registry[name].degenerate_risk, k)
                profiles[name] = ModelProfile.from_dict(name, merged)
            else:
                profiles[name] = ModelProfile.from_dict(name, prof)
        return cls(
            task_id=d["task_id"],
            profiles=profiles,
            turns=[TurnSpec.from_dict(t) for t in d.get("turns", [])],
            phase_handlers={k: PhaseHandler.from_dict(v) for k, v in d.get("phase_handlers", {}).items()},
            escalation_policy=EscalationPolicy.from_dict(d.get("escalation_policy", {})),
        )

    def get_profile(self, turn: TurnSpec) -> ModelProfile:
        return self.profiles[turn.profile]


@dataclass
class OrchestrationResult:
    task_id: str
    status: str  # done | error | degraded
    outputs: list[TurnResult]
    final_output: str
    error: str | None = None


class Orchestrator:
    """Implements the pull-model phase-state protocol."""

    def __init__(
        self,
        transport: AcpxTransport,
        lifecycle: ModelLifecycleManager | None = None,
        registry: dict[str, ModelProfile] | None = None,
    ):
        self.transport = transport
        self.lifecycle = lifecycle or ModelLifecycleManager()
        self.registry = registry or {}
        self._phase_occurrences: dict[str, int] = {}

    async def run(self, spec: OrchestrationSpec, task_spec: str) -> OrchestrationResult:
        results: list[TurnResult] = []
        prior_output = ""
        consecutive_errors = 0

        for turn in spec.turns:
            profile = spec.get_profile(turn)

            if self.lifecycle.would_oom(profile):
                return OrchestrationResult(
                    task_id=spec.task_id,
                    status="error",
                    outputs=results,
                    final_output="",
                    error=f"Cannot load profile '{profile.name}' ({profile.memory_gb} GB exceeds usable RAM)",
                )

            retries = 0
            current_temp = turn.temperature if turn.temperature is not None else profile.temperature
            current_max_tokens = turn.max_tokens

            while retries <= spec.escalation_policy.max_retries:
                prompt = turn.render_prompt(task_spec, prior_output)
                logger.info("Turn %d (attempt %d) -> %s", turn.turn_number, retries, profile.model)
                result = await self.transport.dispatch(
                    agent=turn.agent or profile.agent,
                    prompt=prompt,
                    model=turn.model or profile.model,
                    temperature=current_temp,
                    max_tokens=current_max_tokens,
                )
                result = TurnResult(
                    text=result.text,
                    phase=result.phase,
                    turn_number=turn.turn_number,
                    metadata=result.metadata,
                )

                if is_degenerate(result.text):
                    logger.warning("Degenerate output detected on Turn %d", turn.turn_number)
                    handler = spec.phase_handlers.get("degraded") or PhaseHandler(
                        phase="degraded", action="raise_temp"
                    )
                    if not self._handler_ok(handler):
                        return OrchestrationResult(
                            task_id=spec.task_id,
                            status="degraded",
                            outputs=results + [result],
                            final_output=result.text,
                            error=f"Degenerate output on Turn {turn.turn_number}. Recovery exhausted.",
                        )
                    self._record_occurrence("degraded")
                    action = handler.action
                    if action == "raise_temp":
                        current_temp = min(1.0, current_temp + spec.escalation_policy.retry_temp_delta)
                        retries += 1
                        continue
                    elif action == "reduce_tokens":
                        current_max_tokens = max(50, current_max_tokens // 2)
                        retries += 1
                        continue
                    elif action == "switch_model":
                        msg = f"Degenerate output on Turn {turn.turn_number}. Switching model from {profile.model} to DeepSeek-Coder."
                        logger.warning(msg)
                        return OrchestrationResult(
                            task_id=spec.task_id,
                            status="degraded",
                            outputs=results + [result],
                            final_output=result.text,
                            error=msg,
                        )
                    elif action == "escalate_to_parent":
                        return OrchestrationResult(
                            task_id=spec.task_id,
                            status="degraded",
                            outputs=results + [result],
                            final_output=result.text,
                            error=f"Degenerate output on Turn {turn.turn_number}. Escalated to parent.",
                        )
                    retries += 1
                    continue

                if result.phase == "error":
                    consecutive_errors += 1
                    if consecutive_errors >= spec.escalation_policy.escalate_after:
                        return OrchestrationResult(
                            task_id=spec.task_id,
                            status="error",
                            outputs=results + [result],
                            final_output="",
                            error=f"Too many consecutive errors (>= {spec.escalation_policy.escalate_after}).",
                        )
                    retries += 1
                    continue

                consecutive_errors = 0
                results.append(result)
                prior_output += f"\n\n--- Turn {turn.turn_number} output ---\n{result.text}"
                break

            else:
                return OrchestrationResult(
                    task_id=spec.task_id,
                    status="error",
                    outputs=results,
                    final_output="",
                    error=f"Retries exhausted on Turn {turn.turn_number}.",
                )

        return OrchestrationResult(
            task_id=spec.task_id,
            status="done",
            outputs=results,
            final_output=results[-1].text if results else "",
        )

    def _record_occurrence(self, phase: str) -> None:
        self._phase_occurrences[phase] = self._phase_occurrences.get(phase, 0) + 1

    def _handler_ok(self, handler: PhaseHandler) -> bool:
        return self._phase_occurrences.get(handler.phase, 0) < handler.max_occurrences
