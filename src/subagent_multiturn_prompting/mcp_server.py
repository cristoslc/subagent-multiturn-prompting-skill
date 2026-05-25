"""MCP server entry point using FastMCP."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from subagent_multiturn_prompting.acpx_transport import AcpxTransport
from subagent_multiturn_prompting.model_lifecycle import ModelLifecycleManager
from subagent_multiturn_prompting.orchestrator import Orchestrator, OrchestrationSpec, OrchestrationResult
from subagent_multiturn_prompting.profile_registry import default_registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-server")

mcp = FastMCP("subagent-multiturn-prompting")

# In-memory store for active runs
_run_results: dict[str, OrchestrationResult] = {}
_run_futures: dict[str, asyncio.Task] = {}

_registry = default_registry()


def _resolve_spec(raw: str) -> OrchestrationSpec:
    # Try JSON first to avoid treating long JSON strings as file paths
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
def orchestrate_run(spec: str, task_spec: str) -> str:
    """Start a new orchestrated run. spec is either a JSON blob or a file path. Returns run_id."""
    try:
        parsed = _resolve_spec(spec)
    except Exception as exc:
        return json.dumps({"error": f"Invalid spec: {exc}"})

    run_id = parsed.task_id
    transport = AcpxTransport()
    orchestrator = Orchestrator(transport)

    async def _do_run() -> OrchestrationResult:
        return await orchestrator.run(parsed, task_spec)

    task = asyncio.create_task(_do_run())
    _run_futures[run_id] = task

    def _on_done(t: asyncio.Task) -> None:
        try:
            _run_results[run_id] = t.result()
        except Exception as exc:
            _run_results[run_id] = OrchestrationResult(
                task_id=run_id,
                status="error",
                outputs=[],
                final_output="",
                error=str(exc),
            )
        if run_id in _run_futures:
            del _run_futures[run_id]

    task.add_done_callback(_on_done)
    return json.dumps({"run_id": run_id, "status": "started"})


@mcp.tool()
def orchestrate_status(run_id: str) -> str:
    """Query current phase, turn number, and status."""
    if run_id in _run_futures:
        return json.dumps({"run_id": run_id, "phase": "running"})
    result = _run_results.get(run_id)
    if result is None:
        return json.dumps({"run_id": run_id, "error": "Run not found"})
    return json.dumps({
        "run_id": run_id,
        "status": result.status,
        "final_output": result.final_output,
        "error": result.error,
        "turns_completed": len(result.outputs),
    })


@mcp.tool()
def orchestrate_cancel(run_id: str) -> str:
    """Kill an active subagent session."""
    task = _run_futures.pop(run_id, None)
    if task is not None:
        task.cancel()
        return json.dumps({"run_id": run_id, "status": "cancelled"})
    return json.dumps({"run_id": run_id, "status": "not_found"})


@mcp.tool()
def orchestrate_result(run_id: str, timeout: int = 300) -> str:
    """Block until run completes and return final output."""
    task = _run_futures.get(run_id)
    if task is None:
        result = _run_results.get(run_id)
        if result is None:
            return json.dumps({"run_id": run_id, "error": "Run not found"})
        return json.dumps(result.__dict__)

    try:
        result = asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(task, timeout=timeout)
        )
    except asyncio.TimeoutError:
        return json.dumps({"run_id": run_id, "error": f"Timed out after {timeout}s"})
    except asyncio.CancelledError:
        return json.dumps({"run_id": run_id, "error": "Run was cancelled"})
    return json.dumps(result.__dict__)


if __name__ == "__main__":
    mcp.run()
