---
name: compile
description: Compile decisions to human contract, agent contract, or both
user_invocable: true
auto_invocable: false
---

# /compile — Compile Contracts

Compile decisions into human contract, agent contract, or both.

**Usage:** `/compile human`, `/compile agent`, `/compile` (both)

## Targets

### Human Contract (`contracts/human.md`)

Organized by level. Narrative prose. What people agree on.

```markdown
# Human Contract — {PROJECT_NAME}

## Identity (Level 1)
[compiled from level 1 decisions]

## Direction (Level 2)
[compiled from level 2 decisions]

## Strategy (Level 3)
[compiled from level 3 decisions]

## Tactics (Level 4)
[compiled from level 4 decisions]
```

For each level section:
1. Read all committed decisions at that level
2. Weave into coherent narrative — decisions, reasoning, tradeoffs
3. Note any suggested decisions as "Under consideration: ..."
4. Include key Detail sections inline where they ground the narrative

### Agent Contract (`contracts/agent.md`)

Structured for agent consumption. Constitution + project decisions.

```markdown
# Agent Contract — {PROJECT_NAME}

## Principles
[from constitution decisions]

## Boundaries
[assumptions + constraints from all levels]

## Authority
[what's autonomous vs HITL — from stakes + tradeoffs]

## Context
[key decisions the agent needs, with Detail inline]

## Rules
[concrete enforcement rules from high-stakes decisions]
```

## What to do

0. Run `dna-graph compile-manifest --target {target} --json` to get the deterministic skeleton
1. Read decisions listed in the manifest (not all decisions — the manifest provides the exact set)
2. Sort by level, then by dependency order within level
3. Compile the target contract(s) following the structure above
4. Present compiled output for human approval
5. Write to `contracts/` on approval

## Constraints

- Never invent content not grounded in decisions
- If a decision's state is `suggested`, mark it clearly in the output
- Respect the iron rule: committed language only for committed decisions
- Include `<!-- Compiled from: DEC-001, DEC-003, ... -->` comments per section

## Context

- Constitution: `constitution/` directory
- Decisions: `decisions/` directory
- Contracts: `contracts/` directory
- Format: `.claude/dna/format.md`
- Graph tool: `CLAUDE_PROJECT_DIR="$PWD" python3 .claude/dna/tools/dna-graph.py`
