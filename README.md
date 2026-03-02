# lobster-skill-openpencil

**Inspect, search, and export `.fig` design files — powered by [OpenPencil](https://openpencil.dev).**

This Lobster skill gives your AI assistant the ability to work with Figma `.fig` files from the command line, no GUI required. It wraps the [OpenPencil headless CLI](https://github.com/open-pencil/open-pencil) (`@open-pencil/cli`) as MCP tools.

## What You Can Do

- **"What's in this design.fig file?"** — Get node counts, fonts used, frame names, canvas dimensions
- **"Show me the layer tree of design.fig"** — Visual hierarchy of all layers and groups
- **"Find all Button components in design.fig"** — Search by node name or type
- **"Export all frames from design.fig as PNG"** — Render frames to PNG or JPG without opening a GUI
- **"Export the Login screen at 2x scale"** — Retina-quality exports by node ID

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
|------|-------------|
| `openpencil_info` | Document stats: node count, types, fonts, frame names |
| `openpencil_tree` | Full visual layer hierarchy |
| `openpencil_find` | Search nodes by name or type |
| `openpencil_export` | Render frames/nodes to PNG or JPG |

All tools accept a `json: true` parameter for machine-readable output.

### `openpencil_export` Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `file` | required | Absolute path to `.fig` file |
| `output_dir` | same dir as `.fig` | Where to write exported images |
| `format` | `png` | `png` or `jpg` |
| `scale` | `1` | Scale factor (2 = Retina/2x) |
| `quality` | `90` | JPEG quality 0-100 (JPG only) |
| `node_id` | all frames | Export a specific node by ID |

## Preferences

Set via Lobster's `set_skill_preference` tool:

| Key | Default | Description |
|-----|---------|-------------|
| `default_export_format` | `png` | Default image format |
| `default_scale` | `1` | Default export scale |
| `default_export_dir` | `""` | Default output directory |
| `bun_path` | `bun` | Path to bun if not on PATH |

## Architecture

```
Lobster (Claude Code)
  |
  |-- MCP: openpencil_info, openpencil_tree, openpencil_find, openpencil_export
  |
  v
openpencil_mcp_server.py  (Python MCP wrapper — runs in Lobster's venv)
  |
  |-- subprocess
  |
  v
bunx @open-pencil/cli  (OpenPencil headless CLI — runs via Bun)
  |
  v
.fig file  (local Figma design file)
```

No server process needed — each CLI call is a fresh subprocess invocation.

## About OpenPencil

[OpenPencil](https://openpencil.dev) is an open-source, MIT-licensed Figma alternative.

- Opens `.fig` files natively with round-trip fidelity via the Kiwi codec
- Fully local — no account, no subscription, no internet required
- AI-native with built-in chat (bring your own API key)
- ~7 MB install

The headless CLI (`@open-pencil/cli`) is the component this skill uses — it enables scriptable design file operations in CI/CD pipelines, automation, and AI assistant workflows.

## License

MIT — same as OpenPencil itself.
