"""Smoke tests: MCP server starts, tools register, basic connectivity."""
import asyncio
import json
import subprocess
import sys
import unittest.mock as mock
import time
from pathlib import Path

import pytest

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp.server.fastmcp import FastMCP

from subagent_multiturn_prompting.mcp_server import mcp, _resolve_spec, _run_results, _run_futures
from subagent_multiturn_prompting.orchestrator import OrchestrationSpec
from tests.conftest import FakeTransport


class TestMcpServerSmoke:
    def test_fastmcp_instance_exists(self):
        assert isinstance(mcp, FastMCP)
        assert mcp.name == "subagent-multiturn-prompting"

    def test_tools_registered(self):
        tools = mcp._tool_manager._tools
        assert "orchestrate_run" in tools
        assert "orchestrate_status" in tools
        assert "orchestrate_cancel" in tools
        assert "orchestrate_result" in tools

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

    def test_orchestrate_run_invalid_spec(self):
        result = mcp._tool_manager._tools["orchestrate_run"].fn("not-json", "task")
        data = json.loads(result)
        assert "error" in data
        assert "Invalid spec" in data["error"]

    def test_orchestrate_run_success(self):
        spec_json = json.dumps({
            "task_id": "run-success",
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
                    "prompt_template": "Run {task_spec}",
                    "requires_prior_context": False,
                }
            ],
            "phase_handlers": {},
            "escalation_policy": {"max_retries": 2, "retry_temp_delta": 0.1, "escalate_after": 3},
        })
        with mock.patch("subagent_multiturn_prompting.mcp_server.asyncio.create_task") as mock_create:
            result = mcp._tool_manager._tools["orchestrate_run"].fn(spec_json, "test task")
        data = json.loads(result)
        assert data["run_id"] == "run-success"
        assert data["status"] == "started"
        mock_create.assert_called_once()

    def test_orchestrate_status_not_found(self):
        result = mcp._tool_manager._tools["orchestrate_status"].fn("nonexistent-id")
        data = json.loads(result)
        assert "error" in data
        assert data["error"] == "Run not found"

    def test_orchestrate_cancel_not_found(self):
        result = mcp._tool_manager._tools["orchestrate_cancel"].fn("nonexistent-id")
        data = json.loads(result)
        assert data["status"] == "not_found"

    def test_module_imports(self):
        """Ensure all submodules import without errors."""
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
