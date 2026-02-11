#!/bin/sh
# PreToolUse hook: protects compiled contracts and structured files.
# Contracts: BLOCKING (exit 2) — compile from decisions, don't edit directly.
# Structured files (HEALTH.md, INDEX.md): advisory (exit 0).

command -v python3 >/dev/null 2>&1 || exit 0

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
TOOL="$PLUGIN_ROOT/tools/dna-graph.py"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Skip if running inside the plugin source directory
[ -f "$PROJECT_DIR/.claude-plugin/plugin.json" ] && exit 0

FILE_PATH=$(cat | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null) || exit 0

[ -z "$FILE_PATH" ] && exit 0

BASENAME=$(basename "$FILE_PATH")

# Contracts are compiled output — block direct edits
if echo "$FILE_PATH" | grep -q "/contracts/"; then
  echo "BLOCKED: $BASENAME is compiled from DNA. Use /dna:compile to regenerate."
  CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" audit log \
    --source hook --event protect-contracts --detail "BLOCKED $BASENAME" 2>/dev/null
  exit 2
fi

# Advisory: warn on governance files (don't block — user may need to edit)
if echo "$FILE_PATH" | grep -q "/.claude/settings\.json"; then
  echo "WARNING: .claude/settings.json controls plugin configuration. Edits may disable governance hooks."
fi
if echo "$FILE_PATH" | grep -q "/.claude/CLAUDE\.md"; then
  echo "WARNING: CLAUDE.md is the project operating manual. Verify this change is intentional."
fi

# Structured files — warn but allow
if [ "$BASENAME" = "HEALTH.md" ]; then
  echo "NOTE: HEALTH.md is maintained by dna-graph health. Manual edits may be overwritten."
fi

if [ "$BASENAME" = "INDEX.md" ]; then
  echo "NOTE: INDEX.md is derived. Regenerate via dna-graph index."
fi

CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" audit log \
  --source hook --event protect-contracts --detail "PASS $BASENAME" 2>/dev/null
exit 0
