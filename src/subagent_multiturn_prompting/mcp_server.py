"""MCP server — pull-model progressive disclosure for subagents."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from subagent_multiturn_prompting.acpx_transport import TurnResult
from subagent_multiturn_prompting.degenerate_detector import is_degenerate
from subagent_multiturn_prompting.orchestrator import (
    OrchestrationSpec,
    Orchestrator,
    PhaseHandler,
)
from subagent_multiturn_prompting.profile_registry import default_registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-server")

mcp = FastMCP("subagent-multiturn-prompting")

_registry = default_registry()
_sessions: dict[str, "RunSession"] = {}


@dataclass
class RunSession:
    spec: OrchestrationSpec
    task_spec: str
    current_turn_index: int = 0
    prior_output: str = ""
    outputs: list[TurnResult] = field(default_factory=list)
    status: str = "running"
    error: str | None = None

    @property
    def is_done(self) -> bool:
        return self.status in ("done", "error")

    @property
    def current_turn(self):
        if self.current_turn_index >= len(self.spec.turns):
            return None
        return self.spec.turns[self.current_turn_index]

    def render_next_prompt(self) -> str:
        turn = self.current_turn
        if turn is None:
            return ""
        return turn.render_prompt(self.task_spec, self.prior_output)

    def record_output(self, text: str, phase: str = "verify_complete"):
        turn = self.current_turn
        result = TurnResult(
            text=text,
            phase=phase,
            turn_number=turn.turn_number if turn else 0,
            metadata={},
        )
        self.outputs.append(result)
        self.prior_output += f"\n\n--- Turn {turn.turn_number} output ---\n{text}"
        self.current_turn_index += 1

    def advance_to_done(self):
        self.current_turn_index = len(self.spec.turns)
        self.status = "done"


def _resolve_spec(raw: str) -> OrchestrationSpec:
    try:
        data = json.loads(raw)
        return OrchestrationSpec.from_dict(_registry, data)
    except (json.JSONDecodeError, ValueError):
        pass
    path = Path(raw)
    if path.exists():
        text = path.read_text()
        data = json.loads(text)
        return OrchestrationSpec.from_dict(_registry, data)
    raise ValueError(f"Invalid spec: neither valid JSON nor existing file path: {raw[:100]}")


@mcp.tool()
def multiturn_run(spec: str, task_spec: str) -> str:
    """Start a new progressive-disclosure run. spec is JSON or file path. Returns run_id."""
    try:
        parsed = _resolve_spec(spec)
    except Exception as exc:
        return json.dumps({"error": f"Invalid spec: {exc}"})

    session = RunSession(spec=parsed, task_spec=task_spec)
    _sessions[parsed.task_id] = session
    logger.info("Started run %s (%d turns)", parsed.task_id, len(parsed.turns))
    return json.dumps({"run_id": parsed.task_id, "status": "running", "total_turns": len(parsed.turns)})


@mcp.tool()
def multiturn_prompt(run_id: str) -> str:
    """Pull the next turn's prompt. Subagent calls this to receive incremental context."""
    session = _sessions.get(run_id)
    if session is None:
        return json.dumps({"run_id": run_id, "error": "Run not found"})
    if session.is_done:
        return json.dumps({"run_id": run_id, "status": session.status, "error": session.error})

    turn = session.current_turn
    if turn is None:
        session.status = "done"
        return json.dumps({"run_id": run_id, "status": "done"})

    prompt = session.render_next_prompt()
    profile = session.spec.get_profile(turn)
    return json.dumps({
        "run_id": run_id,
        "turn_number": turn.turn_number,
        "prompt": prompt,
        "profile": turn.profile,
        "model": turn.model or profile.model,
        "temperature": turn.temperature if turn.temperature is not None else profile.temperature,
        "max_tokens": turn.max_tokens,
        "phase": "serving",
    })


@mcp.tool()
def multiturn_complete(run_id: str, output: str, phase: str = "verify_complete") -> str:
    """Submit output for the current turn. Signals the subagent is done with this turn."""
    session = _sessions.get(run_id)
    if session is None:
        return json.dumps({"run_id": run_id, "error": "Run not found"})
    if session.is_done:
        return json.dumps({"run_id": run_id, "status": "already_done"})

    turn = session.current_turn
    if turn is None:
        return json.dumps({"run_id": run_id, "error": "No turn in progress"})

    if is_degenerate(output):
        handler = session.spec.phase_handlers.get("degraded") or PhaseHandler(
            phase="degraded", action="raise_temp"
        )
        if handler.action == "raise_temp":
            logger.warning("Degenerate output on Turn %d, retrying with higher temp", turn.turn_number)
            return json.dumps({
                "run_id": run_id,
                "turn_number": turn.turn_number,
                "action": "retry",
                "message": "Degenerate output detected. Please retry with higher temperature or different approach.",
            })
        elif handler.action == "switch_model":
            return json.dumps({
                "run_id": run_id,
                "turn_number": turn.turn_number,
                "action": "switch_model",
                "message": f"Degenerate output detected. Switching from {turn.profile}.",
            })
        elif handler.action == "escalate_to_parent":
            session.status = "degraded"
            session.error = f"Degenerate output on Turn {turn.turn_number}. Escalated."
            return json.dumps({
                "run_id": run_id,
                "turn_number": turn.turn_number,
                "action": "escalated",
                "message": session.error,
            })

    session.record_output(output, phase)

    next_turn = session.current_turn
    if next_turn is None:
        session.status = "done"
        return json.dumps({
            "run_id": run_id,
            "status": "done",
            "turns_completed": len(session.outputs),
            "final_output": session.outputs[-1].text if session.outputs else "",
        })

    return json.dumps({
        "run_id": run_id,
        "status": "continue",
        "next_turn": next_turn.turn_number,
        "action": "serve_next_turn",
    })


@mcp.tool()
def multiturn_cancel(run_id: str) -> str:
    """Cancel a run and free its session state."""
    session = _sessions.pop(run_id, None)
    if session is None:
        return json.dumps({"run_id": run_id, "status": "not_found"})
    session.status = "cancelled"
    return json.dumps({"run_id": run_id, "status": "cancelled"})


@mcp.tool()
def multiturn_status(run_id: str) -> str:
    """Check the current state of a run."""
    session = _sessions.get(run_id)
    if session is None:
        return json.dumps({"run_id": run_id, "error": "Run not found"})
    return json.dumps({
        "run_id": run_id,
        "status": session.status,
        "current_turn": (session.current_turn.turn_number if session.current_turn else None),
        "turns_completed": len(session.outputs),
        "total_turns": len(session.spec.turns),
        "error": session.error,
    })


if __name__ == "__main__":
    mcp.run()
