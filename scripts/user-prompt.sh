#!/bin/sh
# UserPromptSubmit hook: runs audit, check, and inbox on every user message.
# Outputs context as additionalContext so the model sees DNA results.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
TOOL="$PLUGIN_ROOT/tools/dna-graph.py"

# Self-detection: skip if running inside the plugin source directory
[ -f "$PROJECT_DIR/.claude-plugin/plugin.json" ] && exit 0

# Require python3 and tool
command -v python3 >/dev/null 2>&1 || exit 0
[ -f "$TOOL" ] || exit 0

# Require .dna directory (not bootstrapped = not active)
[ -d "$PROJECT_DIR/.dna" ] || exit 0

# Read stdin JSON and extract prompt
INPUT=$(cat)
USER_PROMPT=$(printf '%s' "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('prompt', ''))
except:
    pass
" 2>/dev/null)

[ -z "$USER_PROMPT" ] && exit 0

# Extract keywords (first few significant words, skip short ones)
KEYWORDS=$(printf '%s' "$USER_PROMPT" | python3 -c "
import sys, re
text = sys.stdin.read().strip()
words = re.findall(r'[a-zA-Z]{3,}', text)
# Skip common filler words
skip = {'the','and','but','for','are','was','were','been','have','has','had',
        'will','would','could','should','can','may','might','this','that',
        'with','from','what','how','when','where','why','who','which','just',
        'not','all','any','some','each','every','about','into','over','also',
        'than','then','them','they','their','there','here','very','much',
        'more','most','other','only','your','you','let','please','want',
        'need','like','does','did','make','know'}
keywords = [w.lower() for w in words if w.lower() not in skip][:4]
print(' '.join(keywords))
" 2>/dev/null)

# 1. Audit log: person message
DETAIL=$(printf '%s' "$USER_PROMPT" | head -c 200)
CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" audit log \
  --source conversation --event person --detail "$DETAIL" 2>/dev/null

# 2. Check for relevant decisions
CHECK_OUTPUT=""
if [ -n "$KEYWORDS" ]; then
  CHECK_OUTPUT=$(CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" check "$KEYWORDS" --json 2>/dev/null)
fi

# 3. Inbox: undelivered messages
INBOX_OUTPUT=$(CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" inbox list --undelivered --json 2>/dev/null)

# Build context block for the model
CONTEXT=""

if [ -n "$CHECK_OUTPUT" ] && [ "$CHECK_OUTPUT" != "{}" ] && [ "$CHECK_OUTPUT" != "null" ]; then
  CONTEXT="${CONTEXT}[DNA-CHECK] ${CHECK_OUTPUT}
"
fi

if [ -n "$INBOX_OUTPUT" ]; then
  # Only include if there are actual messages
  HAS_MSGS=$(printf '%s' "$INBOX_OUTPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    msgs = d.get('messages', [])
    if msgs: print('yes')
except: pass
" 2>/dev/null)
  if [ "$HAS_MSGS" = "yes" ]; then
    CONTEXT="${CONTEXT}[DNA-INBOX] ${INBOX_OUTPUT}
"
  fi
fi

# Output as JSON with additionalContext if we have anything
if [ -n "$CONTEXT" ]; then
  python3 -c "
import json, sys
ctx = sys.stdin.read().strip()
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'UserPromptSubmit',
        'additionalContext': ctx
    }
}))
" <<EOF
$CONTEXT
EOF
fi

exit 0
