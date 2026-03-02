#!/usr/bin/env python3
"""
OpenPencil MCP Server for Lobster

Wraps the @open-pencil/cli headless CLI as MCP tools that Claude Code can use
to inspect and export .fig (Figma) design files.

The CLI runs via `bunx @open-pencil/cli` — no server process needed.
Bun must be installed: https://bun.sh

Tools provided:
- openpencil_info:         Document stats, node types, fonts
- openpencil_tree:         Visual node hierarchy tree
- openpencil_find:         Search nodes by name or type
- openpencil_export:       Render frames/nodes to PNG or JPG
- openpencil_start_server: Spin up the OpenPencil web UI
- openpencil_stop_server:  Shut down the OpenPencil web UI
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configuration from environment (set by preferences or install.sh)
BUN_PATH = os.environ.get("OPENPENCIL_BUN_PATH", "bun")
DEFAULT_EXPORT_FORMAT = os.environ.get("OPENPENCIL_EXPORT_FORMAT", "png")
DEFAULT_SCALE = int(os.environ.get("OPENPENCIL_SCALE", "1"))
DEFAULT_EXPORT_DIR = os.environ.get("OPENPENCIL_EXPORT_DIR", "")

# Server hosting configuration
DEFAULT_PORT = int(os.environ.get("OPENPENCIL_PORT", "1420"))
OPENPENCIL_REPO_PATH = os.environ.get(
    "OPENPENCIL_REPO_PATH",
    str(Path.home() / "lobster-workspace" / "projects" / "open-pencil"),
)

# State file paths
LOBSTER_STATE_DIR = Path.home() / ".lobster"
PID_FILE = LOBSTER_STATE_DIR / "openpencil-server.pid"
LOG_FILE = LOBSTER_STATE_DIR / "openpencil-server.log"

CLI_PACKAGE = "@open-pencil/cli"

server = Server("openpencil")


# =============================================================================
# Helpers
# =============================================================================

def text_result(data: Any) -> list[TextContent]:
    if isinstance(data, str):
        return [TextContent(type="text", text=data)]
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def error_result(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=f"Error: {msg}")]


def _find_bun() -> str | None:
    """Locate bun: prefer configured path, then PATH, then ~/.bun/bin/bun."""
    if BUN_PATH != "bun":
        if shutil.which(BUN_PATH):
            return BUN_PATH
        if Path(BUN_PATH).is_file():
            return BUN_PATH

    found = shutil.which("bun")
    if found:
        return found

    home_bun = Path.home() / ".bun" / "bin" / "bun"
    if home_bun.is_file():
        return str(home_bun)

    return None


def _run_cli(args: list[str], timeout: int = 60) -> tuple[int, str, str]:
    """Run the OpenPencil CLI via bunx and return (returncode, stdout, stderr)."""
    bun = _find_bun()
    if not bun:
        return 1, "", (
            "bun not found. Install from https://bun.sh or set bun_path preference.\n"
            "Quick install: curl -fsSL https://bun.sh/install | bash"
        )

    cmd = [bun, "x", CLI_PACKAGE] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"CLI timed out after {timeout}s"
    except FileNotFoundError as e:
        return 1, "", f"Could not run bun: {e}"
    except Exception as e:
        return 1, "", f"{type(e).__name__}: {e}"


def _validate_fig_file(file_path: str) -> str | None:
    """Return error string if the file is invalid, None if OK."""
    p = Path(file_path)
    if not p.exists():
        return f"File not found: {file_path}"
    if not p.is_file():
        return f"Not a file: {file_path}"
    if p.suffix.lower() != ".fig":
        return f"Expected a .fig file, got: {p.suffix}"
    return None


# =============================================================================
# Server lifecycle helpers
# =============================================================================

def _read_pid() -> int | None:
    """Read the stored PID from the state file. Returns None if absent or invalid."""
    if not PID_FILE.exists():
        return None
    try:
        raw = PID_FILE.read_text().strip()
        return int(raw) if raw else None
    except (ValueError, OSError):
        return None


def _write_pid(pid: int) -> None:
    """Persist a PID to the state file, creating the parent directory if needed."""
    LOBSTER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(pid))


def _remove_pid_file() -> None:
    """Delete the PID file if it exists."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _pid_is_alive(pid: int) -> bool:
    """Return True if a process with the given PID currently exists."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we cannot signal it — treat as alive
        return True


def _kill_process_group(pid: int) -> str:
    """
    Terminate the process group rooted at pid.

    Sends SIGTERM to the entire process group, waits up to 5 seconds, then
    sends SIGKILL if the leader is still alive. Returns a human-readable
    summary of what happened.

    Only operates on the group associated with the tracked PID — never touches
    any other Lobster system processes.
    """
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return f"Process {pid} already gone"
    except OSError as exc:
        return f"Could not determine process group for PID {pid}: {exc}"

    # SIGTERM to the whole group
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return f"Process group {pgid} already gone"
    except PermissionError as exc:
        return f"Permission denied killing process group {pgid}: {exc}"

    # Wait up to 5 s for the leader to exit
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if not _pid_is_alive(pid):
            return f"Stopped (PID {pid}, group {pgid}) via SIGTERM"
        time.sleep(0.2)

    # Escalate to SIGKILL if still alive
    try:
        os.killpg(pgid, signal.SIGKILL)
        return f"Stopped (PID {pid}, group {pgid}) via SIGKILL after SIGTERM timeout"
    except ProcessLookupError:
        return f"Stopped (PID {pid}, group {pgid}) — exited before SIGKILL"
    except PermissionError as exc:
        return f"Could not SIGKILL process group {pgid}: {exc}"


# =============================================================================
# Tool definitions
# =============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="openpencil_info",
            description=(
                "Get stats about a .fig design file: node count, node types, "
                "fonts used, canvas dimensions, and top-level frame names. "
                "Good first step before deeper inspection."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Absolute path to the .fig file",
                    },
                    "json": {
                        "type": "boolean",
                        "description": "Return machine-readable JSON output",
                        "default": False,
                    },
                },
                "required": ["file"],
            },
        ),
        Tool(
            name="openpencil_tree",
            description=(
                "Show the full node hierarchy of a .fig design file as a visual tree. "
                "Useful for understanding layer structure and nesting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Absolute path to the .fig file",
                    },
                    "json": {
                        "type": "boolean",
                        "description": "Return machine-readable JSON output",
                        "default": False,
                    },
                },
                "required": ["file"],
            },
        ),
        Tool(
            name="openpencil_find",
            description=(
                "Search for nodes in a .fig file by name or node type. "
                "Examples: find all nodes named 'Button', or find all 'COMPONENT' nodes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Absolute path to the .fig file",
                    },
                    "name": {
                        "type": "string",
                        "description": "Search by node name (partial match)",
                    },
                    "type": {
                        "type": "string",
                        "description": (
                            "Search by node type: FRAME, COMPONENT, INSTANCE, "
                            "TEXT, RECTANGLE, GROUP, etc."
                        ),
                    },
                    "json": {
                        "type": "boolean",
                        "description": "Return machine-readable JSON output",
                        "default": False,
                    },
                },
                "required": ["file"],
            },
        ),
        Tool(
            name="openpencil_export",
            description=(
                "Export frames or nodes from a .fig file to PNG or JPG images. "
                "By default exports all top-level frames. "
                "Use node_id to export a specific node."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Absolute path to the .fig file",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": (
                            "Directory to write exported images. "
                            "Defaults to the same directory as the .fig file."
                        ),
                    },
                    "format": {
                        "type": "string",
                        "enum": ["png", "jpg"],
                        "description": "Export format (default: png)",
                        "default": "png",
                    },
                    "scale": {
                        "type": "number",
                        "description": "Scale factor: 1 = 1x, 2 = Retina/2x (default: 1)",
                        "default": 1,
                    },
                    "quality": {
                        "type": "integer",
                        "description": "JPEG quality 0-100 (only applies when format=jpg, default: 90)",
                        "default": 90,
                    },
                    "node_id": {
                        "type": "string",
                        "description": "Export a specific node by ID instead of all top-level frames",
                    },
                    "json": {
                        "type": "boolean",
                        "description": "Return machine-readable JSON output listing exported files",
                        "default": False,
                    },
                },
                "required": ["file"],
            },
        ),
        Tool(
            name="openpencil_start_server",
            description=(
                "Start the OpenPencil web UI (bun run dev) as a background process "
                "detached from the MCP server lifecycle. "
                "Returns the local URL once the server is running. "
                "If the server is already running, returns the existing URL without "
                "starting a second instance. "
                "Output is logged to ~/.lobster/openpencil-server.log."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "port": {
                        "type": "integer",
                        "description": "Port to run the web UI on (default: 1420)",
                        "default": 1420,
                    },
                    "repo_path": {
                        "type": "string",
                        "description": (
                            "Absolute path to the OpenPencil source checkout. "
                            "Defaults to ~/lobster-workspace/projects/open-pencil "
                            "or OPENPENCIL_REPO_PATH env var."
                        ),
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="openpencil_stop_server",
            description=(
                "Stop the OpenPencil web UI that was started by openpencil_start_server. "
                "Sends SIGTERM then SIGKILL to the tracked process group and removes the "
                "PID state file. Safe to call even if the server is not running (idempotent). "
                "Only terminates the OpenPencil process — never touches other Lobster processes."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


# =============================================================================
# Tool handler
# =============================================================================

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:

    file_path = arguments.get("file", "")
    use_json = arguments.get("json", False)

    # Validate .fig file for file-based tools
    if name in ("openpencil_info", "openpencil_tree", "openpencil_find", "openpencil_export"):
        err = _validate_fig_file(file_path)
        if err:
            return error_result(err)

    try:
        if name == "openpencil_info":
            args = ["info", file_path]
            if use_json:
                args.append("--json")
            rc, stdout, stderr = _run_cli(args)
            if rc != 0:
                return error_result(stderr or f"CLI exited with code {rc}")
            return text_result(stdout.strip())

        elif name == "openpencil_tree":
            args = ["tree", file_path]
            if use_json:
                args.append("--json")
            rc, stdout, stderr = _run_cli(args)
            if rc != 0:
                return error_result(stderr or f"CLI exited with code {rc}")
            return text_result(stdout.strip())

        elif name == "openpencil_find":
            args = ["find", file_path]
            if "name" in arguments:
                args += ["--name", arguments["name"]]
            if "type" in arguments:
                args += ["--type", arguments["type"]]
            if use_json:
                args.append("--json")
            rc, stdout, stderr = _run_cli(args)
            if rc != 0:
                return error_result(stderr or f"CLI exited with code {rc}")
            return text_result(stdout.strip())

        elif name == "openpencil_export":
            fig_path = Path(file_path)
            output_dir = arguments.get("output_dir") or DEFAULT_EXPORT_DIR or str(fig_path.parent)
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            fmt = arguments.get("format", DEFAULT_EXPORT_FORMAT)
            scale = arguments.get("scale", DEFAULT_SCALE)
            quality = arguments.get("quality", 90)
            node_id = arguments.get("node_id")

            args = [
                "export", file_path,
                "--output", output_dir,
                "-f", fmt,
                "-s", str(scale),
            ]
            if fmt == "jpg":
                args += ["-q", str(quality)]
            if node_id:
                args += ["--node-id", node_id]
            if use_json:
                args.append("--json")

            rc, stdout, stderr = _run_cli(args, timeout=120)
            if rc != 0:
                return error_result(stderr or f"CLI exited with code {rc}")

            out = stdout.strip()
            return text_result(f"Export complete. Files written to: {output_dir}\n\n{out}")

        elif name == "openpencil_start_server":
            return _handle_start_server(arguments)

        elif name == "openpencil_stop_server":
            return _handle_stop_server()

        else:
            return error_result(f"Unknown tool: {name}")

    except Exception as e:
        return error_result(f"{type(e).__name__}: {e}")


# =============================================================================
# Server tool implementations
# =============================================================================

def _handle_start_server(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Start the OpenPencil web UI as a detached background process.

    Uses start_new_session=True so the child process gets its own session and
    survives MCP server restarts. The PID is stored in ~/.lobster/openpencil-server.pid
    and all output (stdout + stderr) is appended to ~/.lobster/openpencil-server.log.

    If a live process is already tracked, returns immediately with the existing URL.
    """
    port = int(arguments.get("port", DEFAULT_PORT))
    repo_path = Path(arguments.get("repo_path") or OPENPENCIL_REPO_PATH)
    url = f"http://localhost:{port}"

    # Check whether a previously started server is still alive
    existing_pid = _read_pid()
    if existing_pid is not None:
        if _pid_is_alive(existing_pid):
            return text_result(
                f"OpenPencil server is already running (PID {existing_pid}).\n"
                f"URL: {url}\n"
                f"Log: {LOG_FILE}"
            )
        else:
            # Stale PID — clean it up and start fresh
            _remove_pid_file()

    # Validate the repo directory
    if not repo_path.is_dir():
        return error_result(
            f"OpenPencil repo not found at: {repo_path}\n"
            "Set the repo_path argument or the OPENPENCIL_REPO_PATH environment variable "
            "to the directory containing the OpenPencil source checkout."
        )

    bun = _find_bun()
    if not bun:
        return error_result(
            "bun not found. Install from https://bun.sh or set the bun_path preference.\n"
            "Quick install: curl -fsSL https://bun.sh/install | bash"
        )

    # Prepare environment: forward current env and inject the port
    env = os.environ.copy()
    env["PORT"] = str(port)

    # Open log file in append mode
    LOBSTER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        log_fd = open(LOG_FILE, "a")
    except OSError as exc:
        return error_result(f"Cannot open log file {LOG_FILE}: {exc}")

    try:
        proc = subprocess.Popen(
            [bun, "run", "dev"],
            cwd=str(repo_path),
            env=env,
            stdout=log_fd,
            stderr=log_fd,
            # Detach from the MCP server's process group so the child survives
            # an MCP restart without being caught by SIGHUP or group signals.
            start_new_session=True,
            # Ensure stdin is not inherited (avoids blocking on terminal input)
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        log_fd.close()
        return error_result(f"Could not execute bun at: {bun}")
    except OSError as exc:
        log_fd.close()
        return error_result(f"Failed to start server: {exc}")
    finally:
        # The child has inherited the fd; close our copy so we don't leak it.
        log_fd.close()

    _write_pid(proc.pid)

    return text_result(
        f"OpenPencil server started (PID {proc.pid}).\n"
        f"URL:  {url}\n"
        f"Log:  {LOG_FILE}\n"
        f"Repo: {repo_path}\n"
        "\n"
        "The server runs detached — it will survive MCP restarts.\n"
        "Call openpencil_stop_server to shut it down."
    )


def _handle_stop_server() -> list[TextContent]:
    """
    Stop the tracked OpenPencil server process.

    Reads the PID from ~/.lobster/openpencil-server.pid, terminates the entire
    process group (SIGTERM, then SIGKILL after 5 s if needed), and removes the
    state file. Safe to call when nothing is running.
    """
    pid = _read_pid()

    if pid is None:
        return text_result(
            "OpenPencil server is not running (no PID file found). Nothing to stop."
        )

    if not _pid_is_alive(pid):
        _remove_pid_file()
        return text_result(
            f"OpenPencil server (PID {pid}) was already stopped. Cleaned up stale PID file."
        )

    summary = _kill_process_group(pid)
    _remove_pid_file()

    return text_result(
        f"OpenPencil server stopped.\n"
        f"Details: {summary}\n"
        f"Log preserved at: {LOG_FILE}"
    )


# =============================================================================
# Entry point
# =============================================================================

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
