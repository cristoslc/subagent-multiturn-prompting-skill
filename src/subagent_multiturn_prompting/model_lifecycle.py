"""Model lifecycle manager."""
from dataclasses import dataclass
from typing import Optional

from .profile_registry import ModelProfile


@dataclass
class LifecycleState:
    active_model: Optional[str] = None
    active_memory_gb: float = 0.0
    system_ram_gb: float = 36.0
    system_overhead_gb: float = 4.0

    @property
    def usable_ram_gb(self) -> float:
        return self.system_ram_gb - self.system_overhead_gb


class ModelLifecycleManager:
    """Tracks which model is loaded and manages hot-switching."""

    def __init__(self, state: Optional[LifecycleState] = None):
        self.state = state or LifecycleState()

    def can_load_together(self, a: ModelProfile, b: ModelProfile) -> bool:
        combined = a.memory_gb + b.memory_gb
        return combined <= self.state.usable_ram_gb

    def would_oom(self, profile: ModelProfile) -> bool:
        return profile.memory_gb > self.state.usable_ram_gb

    def recommend_sequence(self, profiles: list[ModelProfile]) -> list[ModelProfile]:
        """Sort profiles by memory footprint descending to fit largest first."""
        return sorted(profiles, key=lambda p: p.memory_gb, reverse=True)
