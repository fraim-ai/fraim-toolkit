# fraim-toolkit

Reusable meta-tooling for decision-based project governance. Provides a CLI graph tool, Claude Code hooks, skill templates, and a format specification for managing decisions as markdown files.

## What's Included

```
tools/dna-graph.py          CLI: validate, cascade, index, health, create, set, edit, compile-manifest
hooks/
  session-start.sh          SessionStart: regenerate health, show summary
  protect-contracts.sh      PreToolUse: block direct edits to contracts/
  validate-frontmatter.sh   PreToolUse: validate decision frontmatter
  post-edit-validate.sh     PostToolUse: advisory validation after edits
skills/
  query/SKILL.md            Search and synthesize from decisions
  apply/SKILL.md            Confirm → Mutate → Cascade → Commit
  compile/SKILL.md          Compile decisions to contracts ({PROJECT_NAME} template)
format.md                   Decision format specification
settings.template.json      Claude Code settings with hook paths
bootstrap.sh                Project initialization and skill update
```

## Quick Start

### New Project

```sh
# 1. Initialize your project repo
git init my-project && cd my-project

# 2. Add the toolkit as a submodule
git submodule add <toolkit-url> .claude/dna

# 3. Run bootstrap
.claude/dna/bootstrap.sh init

# 4. Create your CLAUDE.md (see below)

# 5. Create your first decision
CLAUDE_PROJECT_DIR="$PWD" python3 .claude/dna/tools/dna-graph.py create DEC-001 --title "Project purpose" --level 1
```

### Existing Project

```sh
git submodule add <toolkit-url> .claude/dna
.claude/dna/bootstrap.sh init
# Migrate existing decisions to the format in format.md
```

## Project Structure

After initialization, your project will have:

```
.dna/
  config.json             Project-specific config (name, terminology, deleted artifacts)
.claude/
  CLAUDE.md               Project-owned (not generated)
  settings.json           Hook configuration (from template)
  dna/                    ← git submodule (this repo)
  skills/                 Project-owned copies (from templates)
    {query,apply,compile}/SKILL.md
constitution/             Behavioral governance decisions (portable)
decisions/                Project-specific decisions
contracts/                Compiled output (human.md, agent.md)
HEALTH.md                 Generated system health summary
```

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

All config sections are optional. Without `terminology`, term linting is skipped. Without `deleted_artifacts`, stale reference checks are skipped. Core graph operations always work.

## CLAUDE.md Skeleton

Create `.claude/CLAUDE.md` in your project with at minimum:

```markdown
# CLAUDE.md — [Project Name]

## What This Is

[Brief description]. Two directories — `constitution/` and `decisions/` — are the source of truth.
Format spec: `.claude/dna/format.md`.

## The Iron Rule

**Upstream commitments eliminate more possibility.**

## Session Start

Automated by SessionStart hook.

## Skills

| Command | Purpose | Loaded when |
|---------|---------|-------------|
| `/query` | Search and synthesize | Auto on understanding signals |
| `/apply` | Confirm → Mutate → Cascade → Commit | Explicit only |
| `/compile` | Compile decisions to contracts | Explicit only |

## Write Boundary

**All decision changes go through `dna-graph`** — never use Edit/Write directly on decision files.
```

## Updating Skills

When skill templates change in the toolkit:

```sh
.claude/dna/bootstrap.sh update-skills
```

This re-copies from templates with `{PROJECT_NAME}` substituted. Prompts before overwriting.
