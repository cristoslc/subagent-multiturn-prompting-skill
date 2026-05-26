"""Smoke tests: MCP server tools register and basic connectivity."""
import asyncio
import json
import subprocess
import sys
import unittest.mock as mock
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp.server.fastmcp import FastMCP

from subagent_multiturn_prompting.mcp_server import (
    mcp,
    _resolve_spec,
    _sessions,
    RunSession,
)
from subagent_multiturn_prompting.orchestrator import OrchestrationSpec
from tests.conftest import FakeTransport


class TestMcpServerSmoke:
    def test_fastmcp_instance_exists(self):
        assert isinstance(mcp, FastMCP)
        assert mcp.name == "subagent-multiturn-prompting"

    def test_tools_registered(self):
        tools = mcp._tool_manager._tools
        assert "multiturn_run" in tools
        assert "multiturn_prompt" in tools
        assert "multiturn_complete" in tools
        assert "multiturn_status" in tools

    def test_resolve_spec_from_json_string(self, registry):
        spec_json = json.dumps({
            "task_id": "smoke-test",
            "profiles": {
                "explorer": {
                    "model": "test-model",
                    "agent": "explore",
                    "temperature": 0.3,
                    "max_tokens_default": 400,
                    "memory_gb": 8.85,
                    "degenerate_risk": {"low_temp": False, "long_prompt": False, "thinking_leak": False},
                }
            },
            "turns": [
                {
                    "turn_number": 1,
                    "profile": "explorer",
                    "max_tokens": 400,
                    "prompt_template": "Hello {task_spec}",
                    "requires_prior_context": False,
                }
            ],
            "phase_handlers": {},
            "escalation_policy": {"max_retries": 2, "retry_temp_delta": 0.1, "escalate_after": 3},
        })
        result = _resolve_spec(spec_json)
        assert isinstance(result, OrchestrationSpec)
        assert result.task_id == "smoke-test"
        assert len(result.turns) == 1
        assert result.profiles["explorer"].model == "test-model"

    def test_resolve_spec_from_file(self, registry, tmp_path):
        spec_path = tmp_path / "spec.json"
        spec_path.write_text(json.dumps({
            "task_id": "file-test",
            "profiles": {
                "explorer": {
                    "model": "file-model",
                    "agent": "explore",
                    "temperature": 0.3,
                    "max_tokens_default": 400,
                    "memory_gb": 8.85,
                    "degenerate_risk": {"low_temp": False, "long_prompt": False, "thinking_leak": False},
                }
            },
            "turns": [],
            "phase_handlers": {},
            "escalation_policy": {"max_retries": 2, "retry_temp_delta": 0.1, "escalate_after": 3},
        }))
        result = _resolve_spec(str(spec_path))
        assert result.task_id == "file-test"

    def test_multiturn_run_invalid_spec(self):
        result = mcp._tool_manager._tools["multiturn_run"].fn("not-json", "task")
        data = json.loads(result)
        assert "error" in data
        assert "Invalid spec" in data["error"]

    def test_multiturn_run_and_prompt_flow(self):
        spec_json = json.dumps({
            "task_id": "pull-flow",
            "profiles": {
                "explorer": {
                    "model": "test-model",
                    "agent": "explore",
                    "temperature": 0.3,
                    "max_tokens_default": 400,
                    "memory_gb": 8.85,
                    "degenerate_risk": {"low_temp": False, "long_prompt": False, "thinking_leak": False},
                }
            },
            "turns": [
                {
                    "turn_number": 1,
                    "profile": "explorer",
                    "max_tokens": 400,
                    "prompt_template": "Research: {{ task_spec }}",
                    "requires_prior_context": False,
                },
                {
                    "turn_number": 2,
                    "profile": "explorer",
                    "max_tokens": 400,
                    "prompt_template": "Continue: {{ task_spec }}\nPrior: {{ prior_output }}",
                    "requires_prior_context": True,
                },
            ],
            "phase_handlers": {},
            "escalation_policy": {"max_retries": 2, "retry_temp_delta": 0.1, "escalate_after": 3},
        })

        run_result = mcp._tool_manager._tools["multiturn_run"].fn(spec_json, "test task")
        run_data = json.loads(run_result)
        assert run_data["run_id"] == "pull-flow"
        assert run_data["total_turns"] == 2

        prompt1 = json.loads(mcp._tool_manager._tools["multiturn_prompt"].fn("pull-flow"))
        assert prompt1["turn_number"] == 1
        assert prompt1["profile"] == "explorer"
        assert "Research:" in prompt1["prompt"]
        assert "test task" in prompt1["prompt"]

        complete1 = json.loads(mcp._tool_manager._tools["multiturn_complete"].fn("pull-flow", "Found results."))
        assert complete1["status"] == "continue"
        assert complete1["next_turn"] == 2

        prompt2 = json.loads(mcp._tool_manager._tools["multiturn_prompt"].fn("pull-flow"))
        assert prompt2["turn_number"] == 2
        assert "Continue:" in prompt2["prompt"]
        assert "Found results." in prompt2["prompt"]

        complete2 = json.loads(mcp._tool_manager._tools["multiturn_complete"].fn("pull-flow", "Synthesis done."))
        assert complete2["status"] == "done"
        assert complete2["final_output"] == "Synthesis done."
        assert complete2["turns_completed"] == 2

    def test_multiturn_prompt_not_found(self):
        result = json.loads(mcp._tool_manager._tools["multiturn_prompt"].fn("nonexistent"))
        assert "error" in result
        assert result["error"] == "Run not found"

    def test_multiturn_status(self):
        spec_json = json.dumps({
            "task_id": "status-test",
            "profiles": {
                "explorer": {
                    "model": "test-model",
                    "agent": "explore",
                    "temperature": 0.3,
                    "max_tokens_default": 400,
                    "memory_gb": 8.85,
                    "degenerate_risk": {"low_temp": False, "long_prompt": False, "thinking_leak": False},
                }
            },
            "turns": [],
            "phase_handlers": {},
            "escalation_policy": {"max_retries": 2, "retry_temp_delta": 0.1, "escalate_after": 3},
        })
        mcp._tool_manager._tools["multiturn_run"].fn(spec_json, "task")
        status = json.loads(mcp._tool_manager._tools["multiturn_status"].fn("status-test"))
        assert status["run_id"] == "status-test"
        assert status["status"] == "running"

    def test_multiturn_cancel(self):
        spec_json = json.dumps({
            "task_id": "cancel-test",
            "profiles": {
                "explorer": {
                    "model": "test-model",
                    "agent": "explore",
                    "temperature": 0.3,
                    "max_tokens_default": 400,
                    "memory_gb": 8.85,
                    "degenerate_risk": {"low_temp": False, "long_prompt": False, "thinking_leak": False},
                }
            },
            "turns": [],
            "phase_handlers": {},
            "escalation_policy": {"max_retries": 2, "retry_temp_delta": 0.1, "escalate_after": 3},
        })
        mcp._tool_manager._tools["multiturn_run"].fn(spec_json, "task")
        result = json.loads(mcp._tool_manager._tools["multiturn_cancel"].fn("cancel-test"))
        assert result["status"] == "cancelled"
        # Cancel again should be not_found
        result2 = json.loads(mcp._tool_manager._tools["multiturn_cancel"].fn("cancel-test"))
        assert result2["status"] == "not_found"

    def test_multiturn_status_not_found(self):
        result = json.loads(mcp._tool_manager._tools["multiturn_status"].fn("nonexistent-id"))
        assert result["error"] == "Run not found"

    def test_module_imports(self):
        from subagent_multiturn_prompting import acpx_transport, degenerate_detector, model_lifecycle, orchestrator, profile_registry, mcp_server
        assert acpx_transport
        assert degenerate_detector
        assert model_lifecycle
        assert orchestrator
        assert profile_registry
        assert mcp_server

    def test_default_registry_has_all_profiles(self):
        from subagent_multiturn_prompting.profile_registry import default_registry
        reg = default_registry()
        assert set(reg.keys()) == {"explorer", "critic", "thinker", "fast_code"}
        for name, prof in reg.items():
            assert prof.model
            assert prof.agent
            assert prof.max_tokens_default > 0
            assert prof.memory_gb > 0
            assert prof.degenerate_risk is not None

    def test_orchestrator_instantiation(self):
        from subagent_multiturn_prompting.orchestrator import Orchestrator, OrchestrationSpec, TurnSpec, EscalationPolicy
        from subagent_multiturn_prompting.profile_registry import default_registry
        from subagent_multiturn_prompting.acpx_transport import AcpxTransport
        reg = default_registry()
        spec = OrchestrationSpec(
            task_id="instantiate",
            profiles=reg,
            turns=[TurnSpec(turn_number=1, profile="explorer", max_tokens=400, prompt_template="hi")],
            phase_handlers={},
            escalation_policy=EscalationPolicy(),
        )
        transport = AcpxTransport(acpx_bin="/bin/true")
        orch = Orchestrator(transport)
        assert orch.lifecycle is not None
        assert orch.transport is transport
