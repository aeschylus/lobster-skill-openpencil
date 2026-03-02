## OpenPencil Context

**What OpenPencil is:** An open-source, MIT-licensed Figma alternative. It opens `.fig` files natively with round-trip fidelity via the Kiwi codec. Runs entirely locally — no account, no subscription, no network required.

**Why it matters for Lobster:** Designers often share `.fig` files. With OpenPencil's headless CLI (`@open-pencil/cli`), Lobster can inspect and export design files without any GUI, making it possible to answer questions about design files programmatically.

**CLI package:** `@open-pencil/cli` (published to npm, run via `bunx @open-pencil/cli`)

**Available commands:**

| Command | Purpose |
|---------|---------|
| `info`  | Document stats: node count, node types, fonts used, canvas dimensions |
| `tree`  | Visual node hierarchy tree |
| `find`  | Search nodes by name or type |
| `export`| Render to PNG/JPG with scale and quality options |

**All commands support `--json`** for machine-readable output.

**Export options:**
- `-f, --format`: `png` (default) or `jpg`
- `-s, --scale`: Scale factor (e.g., `2` for 2x/Retina)
- `-q, --quality`: JPEG quality 0-100 (only for JPG)
- `--node-id`: Export a specific node rather than all top-level frames

**Project links:**
- Website: https://openpencil.dev
- GitHub: https://github.com/open-pencil/open-pencil
- License: MIT
