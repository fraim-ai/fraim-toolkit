#!/bin/sh
# SessionStart hook: auto-bootstrap, behavior rules, compact briefing, tool paths.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
TOOL="$PLUGIN_ROOT/tools/dna-graph.py"

# ───────────────────────────────────────────────────────────────────────
# Self-detection: skip if running inside the plugin source directory
# ───────────────────────────────────────────────────────────────────────

if [ -f "$PROJECT_DIR/.claude-plugin/plugin.json" ]; then
  exit 0
fi

# ───────────────────────────────────────────────────────────────────────
# Auto-bootstrap: detect fresh project (no .dna/) and scaffold
# ───────────────────────────────────────────────────────────────────────

FRESH_PROJECT="false"
if [ ! -d "$PROJECT_DIR/.dna" ]; then
  FRESH_PROJECT="true"
  if command -v python3 >/dev/null 2>&1 && [ -f "$TOOL" ]; then
    CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" bootstrap --json 2>/dev/null
  fi
fi

# ───────────────────────────────────────────────────────────────────────
# Run health + clear delivered inbox
# ───────────────────────────────────────────────────────────────────────

if command -v python3 >/dev/null 2>&1 && [ -f "$TOOL" ]; then
  CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" health 2>/dev/null
  CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" inbox clear --delivered 2>/dev/null
  CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" audit clear 2>/dev/null
fi

# ───────────────────────────────────────────────────────────────────────
# Section 1: Behavior Rules (injected into agent context)
# ───────────────────────────────────────────────────────────────────────

cat <<BEHAVIOR_RULES
## MANDATORY — Tool use required every turn

You are a design partner. Short, human responses. Capture INTENT through decisions — do NOT execute on intent.

NEVER mention: decision IDs, levels, states, stakes, graph, DNA, scratchpad, inbox, background agents, or internal terminology.

### CRITICAL REQUIREMENT — You MUST use the Bash tool on EVERY turn. No exceptions.

Before you write ANY reply to the person, you MUST run these Bash commands. Do NOT skip them. Do NOT reply with only text. A response without these tool calls is a failure.

**Run these 3 commands using the Bash tool (in parallel if possible):**

\`\`\`
CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" audit log --source conversation --event person --detail "<what person said>"
\`\`\`

\`\`\`
CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" check "<2-4 keywords from message>" --json
\`\`\`

\`\`\`
CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" inbox list --undelivered --json
\`\`\`

**Then use the check results:**
- matching_committed with conflicts → push back conversationally
- foundation_thin → nudge toward identity/direction questions
- inbox critical → surface immediately (never mention inbox)
- inbox normal → weave in naturally
- After processing inbox messages, deliver them:
  \`CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" inbox deliver MSG-NNN\`

**Then spawn a background agent if the person expressed an opinion, decision, preference, or design direction:**
Use the Task tool with subagent_type="dna:dna-agent", run_in_background=true, model=haiku, max_turns=15.
Include: TOOL_PATH=$TOOL, PROJECT_DIR=$PROJECT_DIR, PERSON_MESSAGE=<verbatim>, CONTEXT=<check output>, MODE=maintain (or analyze for synthesis questions).
Skip for: greetings, acknowledgments, clarifications.

**After your reply, run:**
\`\`\`
CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" audit log --source conversation --event reply --detail "<1-sentence summary>"
\`\`\`

### Progress requests
When person asks "where are we?" / progress:
  Run \`CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" progress --json\`
  Translate to natural language. Never show raw data.

BEHAVIOR_RULES

# Fresh project guidance
if [ "$FRESH_PROJECT" = "true" ]; then
cat <<'FRESH_RULES'
### Fresh project
No decisions yet. Start by understanding: What is this project? Who is it for? What does success look like? Ask naturally — don't interrogate.

FRESH_RULES
fi

# ───────────────────────────────────────────────────────────────────────
# Section 2: Project Briefing (compact, for agent context)
# ───────────────────────────────────────────────────────────────────────

echo "## Project Briefing"
echo ""

# Project name from config
if [ -f "$PROJECT_DIR/.dna/config.json" ]; then
  PROJ_NAME=$(python3 -c "
import json, sys
try:
    d = json.load(open('$PROJECT_DIR/.dna/config.json'))
    print(d.get('project',{}).get('name','Unknown'))
except: print('Unknown')
" 2>/dev/null)
else
  PROJ_NAME="$(basename "$PROJECT_DIR")"
fi

# Progress data
if command -v python3 >/dev/null 2>&1 && [ -f "$TOOL" ]; then
  PROGRESS_JSON=$(CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" progress --json 2>/dev/null)
  if [ -n "$PROGRESS_JSON" ]; then
    python3 -c "
import json, sys
try:
    d = json.loads('''$PROGRESS_JSON''')
    total = d['total_decisions']
    tc = d['total_committed']
    ts = d['total_suggested']
    print(f'Project: $PROJ_NAME')
    print(f'Decisions: {total} ({tc} committed, {ts} suggested)')
    for l in d['levels']:
        print(f'  L{l[\"level\"]} {l[\"name\"]:<12} {l[\"committed\"]}/{l[\"total\"]} committed  [{l[\"certainty\"]}]')
except Exception as e:
    print(f'Project: $PROJ_NAME')
    print(f'(progress unavailable: {e})')
" 2>/dev/null
  else
    echo "Project: $PROJ_NAME"
    echo "(progress unavailable)"
  fi
fi

# Inbox summary
if command -v python3 >/dev/null 2>&1 && [ -f "$TOOL" ]; then
  INBOX_JSON=$(CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" inbox list --undelivered --json 2>/dev/null)
  if [ -n "$INBOX_JSON" ]; then
    python3 -c "
import json
try:
    d = json.loads('''$INBOX_JSON''')
    msgs = d.get('messages', [])
    if msgs:
        crit = sum(1 for m in msgs if m['priority'] == 'critical')
        norm = sum(1 for m in msgs if m['priority'] == 'normal')
        low = sum(1 for m in msgs if m['priority'] == 'low')
        parts = []
        if crit: parts.append(f'{crit} critical')
        if norm: parts.append(f'{norm} normal')
        if low: parts.append(f'{low} low')
        print(f'Inbox: {len(msgs)} undelivered ({", ".join(parts)})')
except: pass
" 2>/dev/null
  fi
fi

# Audit: log session start
if command -v python3 >/dev/null 2>&1 && [ -f "$TOOL" ]; then
  CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$TOOL" audit log \
    --source session --event start --detail "project=$PROJ_NAME" 2>/dev/null
fi

# Last commit
if command -v git >/dev/null 2>&1; then
  LAST_COMMIT=$(git -C "$PROJECT_DIR" log -1 --oneline 2>/dev/null)
  if [ -n "$LAST_COMMIT" ]; then
    echo "Last commit: $LAST_COMMIT"
  fi
fi

echo ""

# ───────────────────────────────────────────────────────────────────────
# Section 3: Tool Paths (for spawning background agents)
# ───────────────────────────────────────────────────────────────────────

echo "## Tool Paths"
echo "DNA_TOOL=$TOOL"
echo "DNA_PROJECT=$PROJECT_DIR"

exit 0
