#!/usr/bin/env python3
"""
OpenPencil MCP Server for Lobster

Wraps the @open-pencil/cli headless CLI as MCP tools that Claude Code can use
to inspect and export .fig (Figma) design files.

The CLI runs via `bunx @open-pencil/cli` — no server process needed.
Bun must be installed: https://bun.sh

Tools provided:
- openpencil_info:   Document stats, node types, fonts
- openpencil_tree:   Visual node hierarchy tree
- openpencil_find:   Search nodes by name or type
- openpencil_export: Render frames/nodes to PNG or JPG
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
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
    ]


# =============================================================================
# Tool handler
# =============================================================================

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:

    file_path = arguments.get("file", "")
    use_json = arguments.get("json", False)

    # Validate .fig file for all tools
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

        else:
            return error_result(f"Unknown tool: {name}")

    except Exception as e:
        return error_result(f"{type(e).__name__}: {e}")


# =============================================================================
# Entry point
# =============================================================================

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
