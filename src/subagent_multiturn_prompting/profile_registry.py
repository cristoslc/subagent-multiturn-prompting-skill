"""Model profile registry."""
from dataclasses import dataclass
from typing import Any


@dataclass
class DegenerateRisk:
    low_temp: bool = False
    long_prompt: bool = False
    thinking_leak: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DegenerateRisk":
        return cls(
            low_temp=d.get("low_temp", False),
            long_prompt=d.get("long_prompt", False),
            thinking_leak=d.get("thinking_leak", False),
        )


@dataclass
class ModelProfile:
    name: str
    model: str
    agent: str
    temperature: float
    max_tokens_default: int
    memory_gb: float
    degenerate_risk: DegenerateRisk
    max_tokens_synthesis: int | None = None

    @classmethod
    def from_dict(cls, name: str, d: dict[str, Any]) -> "ModelProfile":
        return cls(
            name=name,
            model=d["model"],
            agent=d["agent"],
            temperature=d["temperature"],
            max_tokens_default=d["max_tokens_default"],
            memory_gb=d["memory_gb"],
            degenerate_risk=DegenerateRisk.from_dict(d.get("degenerate_risk", {})),
            max_tokens_synthesis=d.get("max_tokens_synthesis"),
        )


def default_registry() -> dict[str, ModelProfile]:
    raw = {
        "explorer": {
            "model": "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
            "agent": "explore",
            "temperature": 0.3,
            "max_tokens_default": 400,
            "memory_gb": 8.85,
            "degenerate_risk": {
                "low_temp": False,
                "long_prompt": False,
                "thinking_leak": False,
            },
        },
        "critic": {
            "model": "mlx-community/gemma-4-26b-a4b-it-4bit",
            "agent": "general",
            "temperature": 0.4,
            "max_tokens_default": 400,
            "max_tokens_synthesis": 1000,
            "memory_gb": 15.0,
            "degenerate_risk": {
                "low_temp": True,
                "long_prompt": True,
                "thinking_leak": False,
            },
        },
        "thinker": {
            "model": "mlx-community/gemma-4-26b-a4b-it-4bit",
            "agent": "general",
            "temperature": 0.5,
            "max_tokens_default": 600,
            "memory_gb": 15.0,
            "degenerate_risk": {
                "low_temp": True,
                "long_prompt": False,
                "thinking_leak": False,
            },
        },
        "fast_code": {
            "model": "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
            "agent": "build",
            "temperature": 0.2,
            "max_tokens_default": 1200,
            "memory_gb": 8.85,
            "degenerate_risk": {
                "low_temp": False,
                "long_prompt": False,
                "thinking_leak": False,
            },
        },
    }
    return {k: ModelProfile.from_dict(k, v) for k, v in raw.items()}
