#!/bin/sh
# SessionStart hook: show health summary + last commit.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
HEALTH_FILE="$PROJECT_DIR/HEALTH.md"
TOOL="$PLUGIN_ROOT/tools/dna-graph.py"

# Try live health via dna-graph
if command -v python3 >/dev/null 2>&1 && [ -f "$TOOL" ]; then
  CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" health 2>/dev/null
fi

# Read HEALTH.md for display
if [ ! -f "$HEALTH_FILE" ]; then
  echo "HEALTH.md not found — run dna-graph health to generate."
  exit 0
fi

echo "=== Session Health ==="
echo ""

# Node counts
sed -n '/^## Node Counts/,/^## /{ /^## Node Counts/d; /^## /d; /^$/d; p; }' "$HEALTH_FILE"

echo ""

# Flagged items
FLAGGED=$(sed -n '/^## Flagged Items/,/^## /{ /^## /d; /^$/d; p; }' "$HEALTH_FILE")
MANUAL=$(sed -n '/^## Manual Flags/,/^## /{ /^## /d; /^$/d; p; }' "$HEALTH_FILE")

if echo "$FLAGGED" | grep -qv "No issues found"; then
  echo "Flags:"
  echo "$FLAGGED"
fi

if [ -n "$MANUAL" ]; then
  echo ""
  echo "Manual flags:"
  echo "$MANUAL"
fi

# Scratchpad summary
if command -v python3 >/dev/null 2>&1 && [ -f "$TOOL" ]; then
  SP_SUMMARY=$(CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" scratchpad-summary 2>/dev/null)
  if [ -n "$SP_SUMMARY" ]; then
    echo ""
    echo "$SP_SUMMARY"
  fi
fi

# Frontier summary
if command -v python3 >/dev/null 2>&1 && [ -f "$TOOL" ]; then
  FRONTIER_LINE=$(CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" frontier --json 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    s = d['summary']
    print(f\"Frontier: {s['committable_count']} committable, {s['blocked_count']} blocked\")
except: pass
" 2>/dev/null)
  if [ -n "$FRONTIER_LINE" ]; then
    echo "$FRONTIER_LINE"
  fi
fi

echo ""

# Last commit
if command -v git >/dev/null 2>&1; then
  LAST_COMMIT=$(git -C "$PROJECT_DIR" log -1 --oneline 2>/dev/null)
  if [ -n "$LAST_COMMIT" ]; then
    echo "Last commit: $LAST_COMMIT"
  fi
fi

echo "DNA tool: $TOOL"
echo "==================="

exit 0
