"""Async wrapper around the headless Claude Code CLI.

Spawns `claude -p ... --output-format stream-json` in the homelab repo and yields
normalized events as they arrive, so the cog can show live status and capture the
final answer + session id. Auth, skills, MCP servers (incl. Home Assistant) and the
project CLAUDE.md are all picked up from the mounted ~/.claude config + the cwd.
"""

import asyncio
import json
from typing import AsyncIterator

# The homelab monorepo, mounted into the container at the same path. Running the CLI
# here means it loads this repo's CLAUDE.md, skills, and settings automatically.
REPO_DIR = "/home/avalon/repos/homelab"

# StreamReader line buffer. Tool results / final answers can be large, so bump well
# past the 64 KiB default to avoid LimitOverrunError on long lines.
_STREAM_LIMIT = 16 * 1024 * 1024


def _summarize_tool(name: str, tool_input: dict) -> str:
    """Short human-readable summary of a tool call for the live status line."""
    if not isinstance(tool_input, dict):
        return name
    for key in ("command", "file_path", "path", "pattern", "query", "url"):
        val = tool_input.get(key)
        if isinstance(val, str) and val.strip():
            snippet = " ".join(val.split())
            if len(snippet) > 120:
                snippet = snippet[:117] + "..."
            return f"{name}: {snippet}"
    return name


async def run_claude(
    prompt: str,
    session_id: str | None,
) -> AsyncIterator[dict]:
    """Run the CLI and yield normalized events.

    Yields dicts of shape:
      {"kind": "init",   "session_id": str}
      {"kind": "tool",   "summary": str}
      {"kind": "result", "text": str, "session_id": str, "is_error": bool}
      {"kind": "error",  "text": str}
    """
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",  # required for stream-json
        "--dangerously-skip-permissions",
    ]
    if session_id:
        cmd += ["--resume", session_id]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=REPO_DIR,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=_STREAM_LIMIT,
    )
    assert proc.stdout is not None and proc.stderr is not None

    saw_result = False
    try:
        async for raw in proc.stdout:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type")

            if etype == "system" and event.get("subtype") == "init":
                yield {"kind": "init", "session_id": event.get("session_id")}

            elif etype == "assistant":
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "tool_use":
                        yield {
                            "kind": "tool",
                            "summary": _summarize_tool(
                                block.get("name", "tool"), block.get("input", {})
                            ),
                        }

            elif etype == "result":
                saw_result = True
                yield {
                    "kind": "result",
                    "text": event.get("result", "") or "",
                    "session_id": event.get("session_id"),
                    "is_error": bool(event.get("is_error")),
                }
    finally:
        # Make sure the process is reaped even if the consumer stops early.
        if proc.returncode is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
        stderr = (await proc.stderr.read()).decode("utf-8", "replace").strip()
        await proc.wait()

    if not saw_result:
        msg = stderr or f"claude exited with code {proc.returncode} and no result"
        yield {"kind": "error", "text": msg}
