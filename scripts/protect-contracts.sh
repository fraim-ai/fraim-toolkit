#!/bin/sh
# PreToolUse hook: protects compiled contracts and structured files.
# Contracts: BLOCKING (exit 2) — compile from decisions, don't edit directly.
# Structured files (HEALTH.md, INDEX.md): advisory (exit 0).

command -v python3 >/dev/null 2>&1 || exit 0

FILE_PATH=$(cat | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null) || exit 0

[ -z "$FILE_PATH" ] && exit 0

BASENAME=$(basename "$FILE_PATH")

# Contracts are compiled output — block direct edits
if echo "$FILE_PATH" | grep -q "/contracts/"; then
  echo "BLOCKED: $BASENAME is compiled from decisions. Use /dna:compile to regenerate."
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

exit 0
