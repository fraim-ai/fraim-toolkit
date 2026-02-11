---
description: Initialize a new project with the DNA decision system. Scaffolds directories, config, and CLAUDE.md.
disable-model-invocation: true
---

# /dna:init — Initialize Project

Set up a new project to use the DNA decision system.

**Usage:** `/dna:init` or `/dna:init [project name]`

## What This Creates

```
project-root/
  .claude/
    CLAUDE.md          # Agent instructions — routing, lifecycle, write boundary
  .dna/
    config.json        # Project config — name, terminology
    scratchpad.json    # Empty scratchpad
  dna/                 # Project decisions (empty)
  constitution/        # Governance decisions (empty)
  contracts/           # Compiled output (empty)
```

## Steps

### 1. Check Preconditions

- If `.dna/config.json` already exists, STOP and warn: "This project is already initialized. Use the DNA tools directly."
- If `.claude/CLAUDE.md` already exists, ask whether to overwrite or skip.

### 2. Get Project Name

- If passed as argument, use it
- Otherwise ask: "What's the project name?"

### 3. Create Directories

Create these directories (skip any that exist):
- `.claude/`
- `.dna/`
- `dna/`
- `constitution/`
- `contracts/`

### 4. Write `.dna/config.json`

```json
{
  "project": {
    "name": "<PROJECT_NAME>"
  },
  "terminology": {},
  "deleted_artifacts": []
}
```

### 5. Write `.dna/scratchpad.json`

```json
{
  "entries": [],
  "next_id": 1
}
```

### 6. Write `.claude/CLAUDE.md`

Write exactly this content, replacing `<PROJECT_NAME>` with the actual project name:

````markdown
# CLAUDE.md — <PROJECT_NAME>

## What This Is

Design DNA for <PROJECT_NAME>. Two directories — `constitution/` (behavioral governance, portable) and `dna/` (project-specific) — are the single source of truth. One node type: **decisions** with reasoning, assumptions, tradeoffs, and optional detail.

Constitution is always upstream of project decisions (iron rule). 4-level hierarchy: Identity → Direction → Strategy → Tactics.

Compiled into: **human contract** (`contracts/human.md`) and **agent contract** (`contracts/agent.md`). Format spec: see `format.md` in the dna plugin.

## The Iron Rule

**Upstream commitments eliminate more possibility. You cannot collapse fine-grained possibility until coarse-grained possibility is collapsed first.**

Level N decisions depend only on levels 1 through N-1. Constitution decisions are always upstream of project decisions.

## Session Start

Automated by SessionStart hook. If hook output is missing, manually read `HEALTH.md` and check `git log -1`.

## Conversational Routing

The person just talks. The agent recognizes which phase the conversation is in and acts accordingly.

| Phase | Routes to | Signals | Auto? |
|-------|-----------|---------|-------|
| Exploring | /dna:query | "what does...", "how does...", "explain..." | Yes |
| Forming | scratchpad capture | "maybe we should...", "I'm thinking...", "what about..." | Yes — agent suggests capture |
| Crystallizing | /dna:apply | "we should...", "let's go with...", "I've decided...", "that's the approach" | Yes — agent proposes, person confirms |
| Recompiling | /dna:compile | "recompile...", "rebuild contracts" | Explicit |

Phase transitions happen naturally. No commands needed — the person just talks, and the agent manages the lifecycle:
- **Exploring → Forming:** Person starts expressing opinions. Agent offers scratchpad capture.
- **Forming → Crystallizing:** Person commits to a direction. Agent initiates /dna:apply (overlap scan, placement, drafting, cascade).
- Any phase → **Exploring:** Person asks a question. Agent switches to /dna:query.

## Skills

| Command | Purpose | Loaded when |
|---------|---------|-------------|
| `/dna:query` | Search, synthesize, alert on overlap, suggest scratchpad | Auto on understanding signals |
| `/dna:apply` | Overlap scan → Placement → Draft → Confirm → Mutate → Cascade → Cleanup → Commit | Auto on commitment signals, person confirms before mutation |
| `/dna:compile` | Compile decisions to human/agent contracts | Explicit only |

## Write Boundary

**All decision changes go through `dna-graph`** — never use Edit/Write directly on decision files. Use the DNA tool path shown in session health output, or use the MCP tools (dna_create, dna_set, dna_edit).

| Change Type | Tool | Example |
|-------------|------|---------|
| Frontmatter field | `dna_set` | `dna_set DEC-005 depends_on DEC-006` |
| Body content | `dna_edit` | `dna_edit DEC-029 "old text" "new text"` |
| New decision | `dna_create` | `dna_create DEC-001 --title "..." --level 3` |

## Key Terms

- **Person**, not "user." The human working with the agent.
````

### 7. Initialize Git (if not already a repo)

- If `.git/` does not exist, run `git init`
- Create `.gitignore` if it doesn't exist, containing:
  ```
  .DS_Store
  ```

### 8. Confirm

Output a summary:

```
Project "<PROJECT_NAME>" initialized.

Created:
  .claude/CLAUDE.md       — agent instructions
  .dna/config.json        — project config
  .dna/scratchpad.json    — pre-decision scratchpad
  dna/                    — project decisions
  constitution/           — governance decisions
  contracts/              — compiled contracts

Next steps:
  - Start talking about your project — the agent will guide you through capturing decisions
  - Use /dna:query to explore existing decisions
  - Decisions flow: scratchpad → suggested → committed → compiled to contracts
```

## Constraints

- Never overwrite existing decisions or config without explicit confirmation
- The CLAUDE.md template is generic — the person can customize it after init
- Do not create any sample decisions — start empty
