#!/bin/bash
set -e

# colours
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Obsidian + Claude Code Skills Setup    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Vault path ────────────────────────────────────────────────────────────

# Smart default: iCloud Obsidian on macOS
DEFAULT_VAULT=""
if [[ "$OSTYPE" == "darwin"* ]]; then
  ICLOUD_OBSIDIAN="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents"
  if [[ -d "$ICLOUD_OBSIDIAN" ]]; then
    # Pick first vault folder found
    FIRST=$(ls "$ICLOUD_OBSIDIAN" 2>/dev/null | head -1)
    [[ -n "$FIRST" ]] && DEFAULT_VAULT="$ICLOUD_OBSIDIAN/$FIRST"
  fi
fi

if [[ -n "$DEFAULT_VAULT" ]]; then
  echo -e "Detected vault: ${GREEN}$DEFAULT_VAULT${NC}"
  read -rp "Use this vault? [Y/n] " USE_DEFAULT
  if [[ "$USE_DEFAULT" =~ ^[Nn] ]]; then
    DEFAULT_VAULT=""
  fi
fi

if [[ -z "$DEFAULT_VAULT" ]]; then
  read -rp "Enter your Obsidian vault path: " VAULT_PATH
  VAULT_PATH="${VAULT_PATH/#\~/$HOME}"
else
  VAULT_PATH="$DEFAULT_VAULT"
fi

if [[ ! -d "$VAULT_PATH" ]]; then
  echo -e "${YELLOW}Vault directory not found — creating it.${NC}"
  mkdir -p "$VAULT_PATH"
fi

echo ""

# ── 2. Obsidian Local REST API ────────────────────────────────────────────────

echo "You need the Obsidian 'Local REST API' community plugin installed and enabled."
echo "Once enabled, go to plugin settings to find your API key and port."
echo ""
read -rp "Obsidian API key: " API_KEY
read -rp "Port (default 27124 for HTTPS, 27123 for HTTP): " API_PORT
API_PORT="${API_PORT:-27124}"
read -rp "Protocol [https/http] (default https): " API_PROTOCOL
API_PROTOCOL="${API_PROTOCOL:-https}"

echo ""

# ── 3. Create vault folder structure ─────────────────────────────────────────

echo -e "${BLUE}Creating vault structure...${NC}"

mkdir -p \
  "$VAULT_PATH/+Inbox" \
  "$VAULT_PATH/Areas/Work/Projects" \
  "$VAULT_PATH/Areas/Work/Meetings" \
  "$VAULT_PATH/Areas/Work/Session-Logs" \
  "$VAULT_PATH/Areas/Personal" \
  "$VAULT_PATH/Areas/Health" \
  "$VAULT_PATH/Calendar/Daily" \
  "$VAULT_PATH/Calendar/Weekly" \
  "$VAULT_PATH/Calendar/Monthly" \
  "$VAULT_PATH/System/Templates" \
  "$VAULT_PATH/System/Dashboards" \
  "$VAULT_PATH/System/Scripts"

echo -e "  ${GREEN}✓${NC} Vault folders created"

# ── 4. Install memory engine ──────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 &>/dev/null; then
  echo -e "  ${YELLOW}⚠${NC}  python3 not found — the /remember, /memory-gc, /memory-conflicts and"
  echo "     /memory-health skills need it. Install python3 and re-run this script."
fi

cp "$SCRIPT_DIR/scripts/memory.py" "$VAULT_PATH/System/Scripts/memory.py"
echo -e "  ${GREEN}✓${NC} Memory engine installed to System/Scripts/memory.py"

if command -v python3 &>/dev/null; then
  python3 "$VAULT_PATH/System/Scripts/memory.py" --vault "$VAULT_PATH" init >/dev/null
  echo -e "  ${GREEN}✓${NC} Memory store initialised at Memory/"
fi

# ── 5. Install CLAUDE.md ──────────────────────────────────────────────────────

if [[ -f "$VAULT_PATH/CLAUDE.md" ]]; then
  echo -e "  ${YELLOW}⚠${NC}  CLAUDE.md already exists — leaving it as-is."
  echo "     Run 'python3 \"$VAULT_PATH/System/Scripts/memory.py\" --vault \"$VAULT_PATH\" migrate-claude-md'"
  echo "     to extract its bullets into the memory store (non-destructive), then /resume once to"
  echo "     see the pipeline take over."
else
  sed "s|VAULT_PATH|$VAULT_PATH|g" \
    "$SCRIPT_DIR/vault-template/CLAUDE.md" \
    > "$VAULT_PATH/CLAUDE.md"
  echo -e "  ${GREEN}✓${NC} CLAUDE.md created at vault root"
fi

# ── 6. Install skills ─────────────────────────────────────────────────────────

COMMANDS_DIR="$HOME/.claude/commands"
mkdir -p "$COMMANDS_DIR"

for SKILL in "$SCRIPT_DIR/commands/"*.md; do
  FILENAME=$(basename "$SKILL")
  sed "s|VAULT_PATH|$VAULT_PATH|g" "$SKILL" > "$COMMANDS_DIR/$FILENAME"
done

echo -e "  ${GREEN}✓${NC} Skills installed to ~/.claude/commands/"

# ── 7. Register MCP server ────────────────────────────────────────────────────

echo ""
echo -e "${BLUE}Registering obsidian-mcp server...${NC}"

if command -v claude &>/dev/null; then
  # Remove existing entry if any
  claude mcp remove obsidian 2>/dev/null || true

  claude mcp add obsidian \
    --scope user \
    -e OBSIDIAN_API_KEY="$API_KEY" \
    -e OBSIDIAN_HOST="127.0.0.1" \
    -e OBSIDIAN_PORT="$API_PORT" \
    -e OBSIDIAN_PROTOCOL="$API_PROTOCOL" \
    -- npx -y obsidian-mcp

  echo -e "  ${GREEN}✓${NC} MCP server registered"
else
  echo -e "  ${YELLOW}⚠${NC}  Claude Code CLI not found — add this to ~/.claude.json manually:"
  echo ""
  echo '  "mcpServers": {'
  echo '    "obsidian": {'
  echo '      "type": "stdio",'
  echo '      "command": "npx",'
  echo '      "args": ["-y", "obsidian-mcp"],'
  echo '      "env": {'
  echo "        \"OBSIDIAN_API_KEY\": \"$API_KEY\","
  echo '        "OBSIDIAN_HOST": "127.0.0.1",'
  echo "        \"OBSIDIAN_PORT\": \"$API_PORT\","
  echo "        \"OBSIDIAN_PROTOCOL\": \"$API_PROTOCOL\""
  echo '      }'
  echo '    }'
  echo '  }'
fi

# ── 8. Done ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Setup complete!             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "Restart Claude Code, then try:"
echo ""
echo -e "  ${BLUE}/daily-note${NC}         → create today's note"
echo -e "  ${BLUE}/resume${NC}             → load relevant memory + recent session logs"
echo -e "  ${BLUE}/compress${NC}           → save a session before closing (captures memory too)"
echo -e "  ${BLUE}/remember${NC} <fact>    → pin a durable fact to memory right now"
echo -e "  ${BLUE}/memory-health${NC}      → check the memory store's health"
echo ""
echo "Your vault: $VAULT_PATH"
echo ""
