#!/bin/sh
# Stop hook: logs reply audit entry when model finishes responding.
# Never blocks (always exits 0).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
TOOL="$PLUGIN_ROOT/tools/dna-graph.py"

# Self-detection: skip if running inside the plugin source directory
[ -f "$PROJECT_DIR/.claude-plugin/plugin.json" ] && exit 0

# Require python3 and tool
command -v python3 >/dev/null 2>&1 || exit 0
[ -f "$TOOL" ] || exit 0

# Require .dna directory
[ -d "$PROJECT_DIR/.dna" ] || exit 0

# Read stdin (Stop hook JSON) — we use transcript_path to extract last reply
INPUT=$(cat)
TRANSCRIPT=$(printf '%s' "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('transcript_path', ''))
except:
    pass
" 2>/dev/null)

# Extract a summary of the last assistant message from the transcript
SUMMARY=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  SUMMARY=$(python3 -c "
import sys, json

try:
    last_assistant = ''
    with open('$TRANSCRIPT', 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                if msg.get('role') == 'assistant':
                    # Get text content
                    content = msg.get('content', '')
                    if isinstance(content, list):
                        texts = [b.get('text','') for b in content if b.get('type') == 'text']
                        content = ' '.join(texts)
                    if content:
                        last_assistant = content
            except:
                continue
    # Truncate to first 200 chars
    if last_assistant:
        summary = last_assistant[:200].replace('\n', ' ').strip()
        print(summary)
except:
    pass
" 2>/dev/null)
fi

# Fallback if no summary extracted
[ -z "$SUMMARY" ] && SUMMARY="(reply completed)"

# Log the reply audit entry
CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" audit log \
  --source conversation --event reply --detail "$SUMMARY" 2>/dev/null

exit 0
