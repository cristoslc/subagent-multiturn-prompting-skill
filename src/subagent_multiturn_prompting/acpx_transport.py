"""ACP transport adapter using local acpx CLI."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TurnResult:
    text: str
    phase: str
    turn_number: int
    metadata: dict[str, Any]


class AcpxTransport:
    """Wraps the local `acpx` binary."""

    def __init__(self, acpx_bin: str | None = None, cwd: str | None = None):
        self.cwd = cwd or str(Path.cwd())
        if acpx_bin:
            self.acpx = acpx_bin
        else:
            local = Path(self.cwd) / "node_modules" / ".bin" / "acpx"
            self.acpx = str(local) if local.exists() else "acpx"

    async def dispatch(
        self,
        agent: str,
        prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        allowed_tools: list[str] | None = None,
        timeout: int = 120,
    ) -> TurnResult:
        args = [
            self.acpx,
            agent,
            "--cwd", self.cwd,
            "--format", "json",
            "--timeout", str(timeout),
        ]
        if model:
            args += ["--model", model]
        if temperature is not None:
            args += ["--system-prompt", f"{{\"temperature\":{temperature}}}"]
        if max_tokens:
            args += ["--max-turns", str(max_tokens)]  # acpx calls tokens turns; not great but closest
        if allowed_tools:
            args += ["--allowed-tools", ",".join(allowed_tools)]
        args += ["--", prompt]

        logger.debug("acpx dispatch: %s", " ".join(args))
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        text = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()

        phase = "done"
        metadata: dict[str, Any] = {}

        # Try to parse structured JSON from acpx if available
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                text = parsed.get("text", text)
                metadata = {k: v for k, v in parsed.items() if k != "text"}
                phase = metadata.pop("phase", "done")
        except json.JSONDecodeError:
            pass

        # Heuristic: if acpx exited non-zero, treat as error phase
        if proc.returncode != 0:
            phase = "error"
            metadata["acpx_exit_code"] = proc.returncode
            if err:
                metadata["acpx_stderr"] = err[:500]

        return TurnResult(
            text=text,
            phase=phase,
            turn_number=0,  # filled by orchestrator
            metadata=metadata,
        )
