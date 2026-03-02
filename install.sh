#!/bin/bash
#===============================================================================
# OpenPencil Skill Installer for Lobster
#
# Sets up the OpenPencil headless CLI as a Lobster skill.
# This gives Lobster tools to inspect and export .fig design files.
#
# Usage: bash ~/lobster/lobster-shop/openpencil/install.sh
#   or:  bash install.sh  (from within this skill directory)
#===============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; }
step()    { echo -e "\n${CYAN}${BOLD}--- $1${NC}"; }

# Paths
LOBSTER_DIR="${LOBSTER_INSTALL_DIR:-$HOME/lobster}"
# Support running from skill dir OR from lobster-shop
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
VENV_DIR="$LOBSTER_DIR/.venv"
PYTHON_PATH="$VENV_DIR/bin/python"

echo ""
echo -e "${BOLD}OpenPencil Skill Installer${NC}"
echo "=========================="
echo ""
echo "This will set up OpenPencil CLI for Lobster, enabling it to inspect"
echo "and export .fig (Figma) design files without a GUI."
echo ""

#===============================================================================
# Step 1: Check for bun
#===============================================================================
step "Checking prerequisites"

BUN_PATH=""
if command -v bun &>/dev/null; then
    BUN_PATH="$(command -v bun)"
    success "bun found: $BUN_PATH ($(bun --version))"
elif [ -f "$HOME/.bun/bin/bun" ]; then
    BUN_PATH="$HOME/.bun/bin/bun"
    success "bun found at ~/.bun/bin/bun ($(\"$BUN_PATH\" --version))"
else
    warn "bun not found — installing now..."
    curl -fsSL https://bun.sh/install | bash
    # Re-source to pick up bun
    export PATH="$HOME/.bun/bin:$PATH"
    if command -v bun &>/dev/null; then
        BUN_PATH="$(command -v bun)"
        success "bun installed: $(bun --version)"
    else
        error "bun installation failed. Install manually: https://bun.sh"
        exit 1
    fi
fi

# Check Python
if [ -f "$PYTHON_PATH" ]; then
    success "Lobster Python venv found: $PYTHON_PATH"
elif command -v python3 &>/dev/null; then
    PYTHON_PATH="python3"
    success "Python 3 found: $(python3 --version)"
else
    error "Python 3 is required but not installed."
    exit 1
fi

# Check Claude CLI
if ! command -v claude &>/dev/null; then
    error "Claude CLI is required but not installed."
    exit 1
fi
success "Claude CLI found"

#===============================================================================
# Step 2: Verify the CLI works
#===============================================================================
step "Verifying @open-pencil/cli"

info "Running: $BUN_PATH x @open-pencil/cli --version"
if "$BUN_PATH" x @open-pencil/cli --version 2>/dev/null; then
    success "@open-pencil/cli is accessible via bunx"
else
    warn "Could not verify @open-pencil/cli version — may still work at runtime"
fi

#===============================================================================
# Step 3: Install Python MCP dependencies
#===============================================================================
step "Installing Python MCP dependencies"

if [ -f "$VENV_DIR/bin/pip" ]; then
    "$VENV_DIR/bin/pip" install --quiet "mcp>=1.0" 2>&1 || warn "mcp install had issues"
    success "Python dependencies installed in Lobster venv"
else
    pip3 install --quiet "mcp>=1.0" 2>&1 || warn "mcp install had issues"
    success "Python dependencies installed"
fi

#===============================================================================
# Step 4: Register MCP server with Claude
#===============================================================================
step "Registering MCP server with Claude"

# Remove old registration if it exists
claude mcp remove openpencil 2>/dev/null || true

ENV_ARGS=""
if [ "$BUN_PATH" != "bun" ]; then
    ENV_ARGS="-e OPENPENCIL_BUN_PATH=$BUN_PATH"
fi

if claude mcp add openpencil -s user $ENV_ARGS -- "$PYTHON_PATH" "$SRC_DIR/openpencil_mcp_server.py" 2>/dev/null; then
    success "MCP server registered: openpencil"
else
    warn "Could not register MCP server automatically."
    echo "  Register manually with:"
    echo "  claude mcp add openpencil -s user -- $PYTHON_PATH $SRC_DIR/openpencil_mcp_server.py"
fi

#===============================================================================
# Done
#===============================================================================
echo ""
echo -e "${GREEN}${BOLD}OpenPencil skill installed!${NC}"
echo ""
echo "  Tools available to Lobster:"
echo "    openpencil_info    - Document stats (nodes, fonts, frames)"
echo "    openpencil_tree    - Visual layer hierarchy"
echo "    openpencil_find    - Search nodes by name or type"
echo "    openpencil_export  - Render frames/nodes to PNG or JPG"
echo ""
echo "  Example: Ask Lobster to 'show me what's in design.fig'"
echo "  Example: Ask Lobster to 'export all frames from design.fig as PNG'"
echo ""
echo "  To activate the skill in Lobster, run:"
echo "    activate_skill('openpencil')"
echo ""
echo "  Or restart Lobster to pick up the new MCP tools."
echo ""
