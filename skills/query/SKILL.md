---
name: query
description: Search and synthesize from decisions
user_invocable: true
auto_invocable: true
---

# /query — Explore the Decision System

The person wants to understand what the decision system says about a concept, term, or design area.

**Auto-invocation signals:** "what does...", "how does...", "explain...", "what is...", "where is..."

## What to do

### 1. Search

Read decision files directly. Use Grep to find nodes mentioning the concept across `decisions/` and `constitution/`. Read matching nodes fully.

For structural queries, read `decisions/INDEX.md` and/or `constitution/INDEX.md` first for fast triage.

### 2. Synthesize

Report what the decisions say:
- What's decided and committed
- What's still suggested
- What alternatives were considered (in Reasoning sections)
- What assumptions are in play
- What tradeoffs were accepted
- Tensions between decisions

Don't just summarize — synthesize across the graph.

### 3. Health

For each relevant decision:
- Report its **state** and **level**
- Flag **Assumptions** that reference changed concepts
- Check **depends_on** — are upstream decisions healthy?

## Context

- Constitution: `constitution/` directory
- Decisions: `decisions/` directory
- Format: `.claude/dna/format.md`
- Graph tool: `CLAUDE_PROJECT_DIR="$PWD" python3 .claude/dna/tools/dna-graph.py`
