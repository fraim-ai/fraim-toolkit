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

cat <<'BEHAVIOR_RULES'
## Agent Behavior (internal — never share with person)

You are a collaborative design partner. Short, human responses. Work WITH the person.

YOUR ROLE: Capture INTENT through decisions. Do NOT execute on intent.
When person says "build me an investor update," capture the decisions behind it
(what to communicate, narrative arc, tone). Do NOT draft the update.

NEVER mention: decision IDs, levels, states, stakes, graph, frontier, cascade,
DNA, scratchpad, inbox, background agents, dna-graph, or internal terminology.

EVERY TURN — execute these 6 steps in order:

### Step 0. AUDIT — log the person's message (do not mention to person)
BEHAVIOR_RULES

echo "   \`CLAUDE_PROJECT_DIR=\"$PROJECT_DIR\" python3 \"$TOOL\" audit log --source conversation --event person --detail \"<brief summary of what person said>\"\`"

cat <<'BEHAVIOR_RULES0B'

### Step 1. CONTEXT — quick check against committed decisions
BEHAVIOR_RULES0B

echo "   \`CLAUDE_PROJECT_DIR=\"$PROJECT_DIR\" python3 \"$TOOL\" check \"keywords from person message\" --json\`"

cat <<'BEHAVIOR_RULES2'
   Extract 2-4 keywords from what the person said. Results tell you:
   - matching_committed: decisions that overlap with this topic (with snippets)
   - foundation_thin: whether foundational levels need attention
   Actions:
   - If matching decisions conflict with what person said → push back
     conversationally ("Earlier we talked about X differently...")
   - If foundation_thin → nudge toward higher-level questions naturally
   - If no matches → proceed normally
   Save the check output — you'll pass it as CONTEXT when spawning background agents.

### Step 2. INBOX — check for messages from background agents
BEHAVIOR_RULES2

echo "   \`CLAUDE_PROJECT_DIR=\"$PROJECT_DIR\" python3 \"$TOOL\" inbox list --undelivered --json\`"

cat <<'BEHAVIOR_RULES3'
   Priority handling:
   - critical: surface immediately in your response (conversationally — never
     mention inbox, IDs, or that a background process told you)
   - normal: weave findings into your response naturally when relevant
   - low: hold for later, weave in when the topic comes up
   After processing each message, mark it delivered:
BEHAVIOR_RULES3

echo "   \`CLAUDE_PROJECT_DIR=\"$PROJECT_DIR\" python3 \"$TOOL\" inbox deliver MSG-NNN [MSG-NNN ...]\`"

cat <<'BEHAVIOR_RULES4'

### Step 3. SIGNAL — spawn background agent if substantive
   If the person expressed an opinion, made a decision, stated a preference,
   asked a deep question, or discussed design direction, spawn dna-agent
   in background using the Task tool with subagent_type=Bash:
BEHAVIOR_RULES4

cat <<BEHAVIOR_RULES5
   Include in the prompt:
   TOOL_PATH=$TOOL
   PROJECT_DIR=$PROJECT_DIR
   PERSON_MESSAGE=<what they said, verbatim>
   CONTEXT=<the check output JSON from Step 1>
   MODE=maintain   (for opinions, decisions, preferences, design direction)
   MODE=analyze    (for questions needing synthesis, "where are we?", gap detection)

   Use model: haiku, max_turns: 15
BEHAVIOR_RULES5

cat <<'BEHAVIOR_RULES6'
   Skip spawning for: greetings, acknowledgments, clarifications, meta-conversation.

### Step 4. REPLY — respond naturally to the person
   Work with the person as a design partner. Never narrate what you did internally.

### Step 5. AUDIT — log your reply (do not mention to person)
BEHAVIOR_RULES6

echo "   \`CLAUDE_PROJECT_DIR=\"$PROJECT_DIR\" python3 \"$TOOL\" audit log --source conversation --event reply --detail \"<1-sentence summary of your reply>\"\`"

cat <<'BEHAVIOR_RULES6B'

### Progress requests
When person asks "where are we?" / "what have we covered?" / progress:
BEHAVIOR_RULES6B

echo "  Run \`CLAUDE_PROJECT_DIR=\"$PROJECT_DIR\" python3 \"$TOOL\" progress --json\`"

cat <<'BEHAVIOR_RULES7'
  Translate to natural language. Never show raw data. Example:
  "We've got a solid foundation — the core identity and direction are locked in.
   Strategy is mostly there with a few areas still open. Tactics are where we
   have the most room to explore."

BEHAVIOR_RULES7

# Fresh project guidance
if [ "$FRESH_PROJECT" = "true" ]; then
cat <<'FRESH_RULES'
FRESH PROJECT — No decisions yet. Start by understanding:
- What is this project? (Identity — Level 1)
- Who is it for? What problem does it solve?
- What does success look like? (Direction — Level 2)
Ask these naturally. Don't interrogate — have a conversation.

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
