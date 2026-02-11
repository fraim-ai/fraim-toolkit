# fraim-toolkit (dna plugin v2.0)

Invisible decision capture for fraim projects. Decisions are captured as you talk — the person never needs to know the system exists.

## How It Works

The person talks naturally. The plugin runs two loops:

**Main Loop (every turn):** The main agent checks for conflicts with existing decisions, processes inbox messages from background agents, and spawns background work when the person says something substantive.

**Background Agent (on demand, haiku):** A lightweight agent that either maintains the decision graph (capturing new decisions, detecting contradictions) or synthesizes information across the graph. Communicates findings back through an inbox.

The person never sees decision IDs, levels, states, or any internal machinery. They just have a design conversation.

## What's Included

```
.claude-plugin/
  plugin.json               Plugin metadata (v2.0.0)
  marketplace.json          Marketplace definition (fraim-plugins)
agents/
  dna-agent.md              Background agent: maintain + analyze modes
hooks/
  hooks.json                Hook configuration (SessionStart, PreToolUse, PostToolUse)
scripts/
  session-start.sh          SessionStart: auto-bootstrap, behavior rules, briefing
  protect-contracts.sh      PreToolUse: block contract edits, warn on governance files
  validate-frontmatter.sh   PreToolUse: validate decision frontmatter
  post-edit-validate.sh     PostToolUse: advisory validation after edits
skills/
  compile/SKILL.md          Compile decisions to contracts (explicit only)
tools/
  dna-graph.py              CLI: 15 commands for graph operations
format.md                   Decision format specification
```

## Install

### Local development

```sh
claude --plugin-dir ~/Desktop/fraim-toolkit
```

### From marketplace (when published)

```
/plugin marketplace add <marketplace-url>
/plugin install dna@fraim-plugins
```

## dna-graph Commands

### Read

| Command | Purpose |
|---------|---------|
| `validate` | Check frontmatter, graph topology, and body content |
| `cascade NODE [--reverse]` | Propagation preview (downstream or upstream) |
| `index` | Regenerate INDEX.md per directory |
| `health` | Regenerate HEALTH.md + summary |
| `search TERM [...]` | Search decisions by title and body content |
| `frontier` | Compute the decision frontier |
| `check "keywords"` | Fast scope/conflict check (committed only) |
| `progress` | Mechanical counts for progress reporting |

### Write

| Command | Purpose |
|---------|---------|
| `create DEC-NNN` | Create a new decision |
| `set DEC-NNN field value` | Update frontmatter field |
| `edit DEC-NNN "old" "new"` | Replace body text with delta reporting |
| `compile-manifest` | Deterministic skeleton for contracts |
| `bootstrap` | Auto-scaffold project structure |

### Inbox

| Command | Purpose |
|---------|---------|
| `inbox add` | Add a message (background → main agent) |
| `inbox list [--undelivered]` | List messages |
| `inbox deliver MSG-NNN` | Mark messages as delivered |
| `inbox clear [--delivered\|--all]` | Clear messages |

### Scratchpad

| Command | Purpose |
|---------|---------|
| `scratchpad add` | Add pre-decision entry |
| `scratchpad list` | List entries |
| `scratchpad mature SP-NNN DEC-NNN` | Graduate entry to decision |
| `scratchpad-summary` | One-line summary of active entries |

## Background Agent Modes

| Mode | Triggered By | Actions |
|------|-------------|---------|
| **Maintain** | Opinions, decisions, preferences | Create decisions (always `suggested`), enrich existing, scratchpad, detect conflicts |
| **Analyze** | Questions needing synthesis, gap detection | Search across graph, synthesize relationships, identify gaps |

Both modes report findings via the inbox. The main agent weaves them into subsequent responses.

## Project Requirements

- `.dna/config.json` at project root (auto-created by `bootstrap`)
- `dna/` and/or `constitution/` directories
- `contracts/` directory for compiled output

Fresh projects are auto-bootstrapped on first session start.

## Configuration

`.dna/config.json` controls project-specific linting:

```json
{
  "project": {
    "name": "MyProject"
  },
  "terminology": {
    "flagged_term": "user",
    "replacement": "person",
    "exemptions": ["\"user\"", "`user`"],
    "exempt_ids": ["DEC-005"]
  },
  "deleted_artifacts": [
    {"pattern": "\\bOLD_FILE\\.md\\b", "label": "OLD_FILE.md (archived)"}
  ]
}
```

All config sections are optional. Core graph operations always work without configuration.
