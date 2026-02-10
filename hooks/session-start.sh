#!/bin/sh
# SessionStart hook: show health summary + last commit.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
HEALTH_FILE="$PROJECT_DIR/HEALTH.md"
TOOL="$PROJECT_DIR/.claude/dna/tools/dna-graph.py"
[ -f "$TOOL" ] || TOOL="$PROJECT_DIR/.claude/tools/dna-graph.py"

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

echo ""

# Last commit
if command -v git >/dev/null 2>&1; then
  LAST_COMMIT=$(git -C "$PROJECT_DIR" log -1 --oneline 2>/dev/null)
  if [ -n "$LAST_COMMIT" ]; then
    echo "Last commit: $LAST_COMMIT"
  fi
fi

echo "==================="

exit 0
