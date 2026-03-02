# lobster-skill-openpencil

**Inspect, search, and export `.fig` design files — and run the OpenPencil web UI — powered by [OpenPencil](https://openpencil.dev).**

This Lobster skill gives your AI assistant the ability to work with Figma `.fig` files from the command line, no GUI required. It wraps the [OpenPencil headless CLI](https://github.com/open-pencil/open-pencil) (`@open-pencil/cli`) as MCP tools, and can also spin up the full OpenPencil web UI on demand.

## What You Can Do

- **"What's in this design.fig file?"** — Get node counts, fonts used, frame names, canvas dimensions
- **"Show me the layer tree of design.fig"** — Visual hierarchy of all layers and groups
- **"Find all Button components in design.fig"** — Search by node name or type
- **"Export all frames from design.fig as PNG"** — Render frames to PNG or JPG without opening a GUI
- **"Export the Login screen at 2x scale"** — Retina-quality exports by node ID
- **"Start openpencil"** — Launch the OpenPencil web UI in the background; get a browser-ready URL
- **"Stop openpencil"** — Cleanly shut down the web UI

## Installation

### Prerequisites

- [Bun](https://bun.sh) (the installer will install it if missing)
- Python 3.11+ with Lobster's virtual environment
- Claude CLI (`claude`)

### Install

```bash
bash ~/lobster/lobster-shop/openpencil/install.sh
```

If you've cloned this repo directly:

```bash
bash install.sh
```

The installer:
1. Checks for (and installs) Bun
2. Verifies `@open-pencil/cli` is accessible via `bunx`
3. Installs the Python MCP server dependencies
4. Registers the MCP server with Claude

### Adding to Lobster Shop

To make this skill available in your Lobster installation:

```bash
# Clone into your lobster-shop directory
cd ~/lobster/lobster-shop
git clone https://github.com/aeschylus/lobster-skill-openpencil openpencil

# Then install
bash openpencil/install.sh
```

After installation, activate the skill:

```
activate_skill('openpencil')
```

## Tools

| Tool | What It Does |
|------|--------------|
| `openpencil_info` | Document stats: node count, types, fonts, frame names |
| `openpencil_tree` | Full visual layer hierarchy |
| `openpencil_find` | Search nodes by name or type |
| `openpencil_export` | Render frames/nodes to PNG or JPG |
| `openpencil_start_server` | Start the OpenPencil web UI in the background |
| `openpencil_stop_server` | Cleanly shut down the web UI |

### `openpencil_export` Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `file` | required | Absolute path to `.fig` file |
| `output_dir` | same dir as `.fig` | Where to write exported images |
| `format` | `png` | `png` or `jpg` |
| `scale` | `1` | Scale factor (2 = Retina/2x) |
| `quality` | `90` | JPEG quality 0-100 (JPG only) |
| `node_id` | all frames | Export a specific node by ID |

### `openpencil_start_server` Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `port` | `1420` | Port for the web UI |
| `repo_path` | `~/lobster-workspace/projects/open-pencil` | Path to OpenPencil source checkout |

The server runs as a detached background process — it survives MCP restarts and does not block the Lobster system. Output is logged to `~/.lobster/openpencil-server.log`. The PID is tracked in `~/.lobster/openpencil-server.pid`.

Calling `openpencil_start_server` when a server is already running returns the existing URL without starting a second instance.

### `openpencil_stop_server`

No parameters required. Reads the tracked PID, sends SIGTERM (then SIGKILL if needed), and removes the state file. Safe to call even when nothing is running — it is fully idempotent.

Only the tracked OpenPencil process group is terminated. No other Lobster processes are affected.

## Preferences

Set via Lobster's `set_skill_preference` tool:

| Key | Default | Description |
|-----|---------|-------------|
| `default_export_format` | `png` | Default image format |
| `default_scale` | `1` | Default export scale |
| `default_export_dir` | `""` | Default output directory |
| `bun_path` | `bun` | Path to bun if not on PATH |

The server port and repo path can also be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENPENCIL_PORT` | `1420` | Default port for the web UI |
| `OPENPENCIL_REPO_PATH` | `~/lobster-workspace/projects/open-pencil` | Default path to OpenPencil source |

## Architecture

```
Lobster (Claude Code)
  |
  |-- MCP: openpencil_info, openpencil_tree, openpencil_find, openpencil_export
  |-- MCP: openpencil_start_server, openpencil_stop_server
  |
  v
openpencil_mcp_server.py  (Python MCP wrapper — runs in Lobster's venv)
  |
  |-- subprocess (CLI tools)
  |   v
  |   bunx @open-pencil/cli  (OpenPencil headless CLI — fresh subprocess per call)
  |     v
  |     .fig file  (local Figma design file)
  |
  |-- subprocess.Popen (web UI — detached, start_new_session=True)
      v
      bun run dev  (OpenPencil web UI — survives MCP restarts)
        v
        http://localhost:1420
```

CLI tools spin up a fresh subprocess per invocation — no persistent state. The web UI is a long-lived detached process tracked by PID file.

## About OpenPencil

[OpenPencil](https://openpencil.dev) is an open-source, MIT-licensed Figma alternative.

- Opens `.fig` files natively with round-trip fidelity via the Kiwi codec
- Fully local — no account, no subscription, no internet required
- AI-native with built-in chat (bring your own API key)
- ~7 MB install

The headless CLI (`@open-pencil/cli`) is the component used by the inspection/export tools. The `bun run dev` command starts the full interactive web UI for browser-based design editing.

## License

MIT — same as OpenPencil itself.
