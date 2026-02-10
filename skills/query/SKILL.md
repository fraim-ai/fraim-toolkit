---
description: Search and synthesize from decisions. Auto-invoked on understanding signals like "what does...", "how does...", "explain..."
---

# /dna:query — Explore the Decision System

The person wants to understand what the decision system says about a concept, term, or design area.

**Auto-invocation signals:** "what does...", "how does...", "explain...", "what is...", "where is..."

## What to do

### 1. Search

Call `dna_search` (MCP) with key terms to find matching decisions quickly. Then read matching decisions fully for detail.

For structural queries, read `dna/INDEX.md` and/or `constitution/INDEX.md` first for fast triage.

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

### 4. Scratchpad Check

When searching for a concept, also call `scratchpad_list` (MCP) or `dna-graph scratchpad list --json` (Bash fallback) and report any relevant pre-decision entries alongside formal decisions. This surfaces ideas, constraints, questions, and concerns that haven't yet crystallized into decisions.

### 5. What-If Analysis

When the person asks "what if X changes":
1. Call `dna_cascade` (MCP) or `dna-graph cascade NODE --json` (Bash) to get affected nodes
2. Read the **Assumptions** section of each affected decision
3. Reason about whether the proposed change breaks any assumptions
4. Report: which assumptions hold, which break, and what cascade effects follow

### 6. Overlap Alerting

When surfacing decisions on a topic, assess whether the person seems to be forming an opinion or heading toward a new decision. If so, proactively note:

"There are existing decisions in this space: DEC-XXX, DEC-YYY. If you're heading toward a new decision here, it would interact with these."

This bridges naturally into /dna:apply if the person crystallizes intent.

### 7. Scratchpad Suggestion

When the person is exploring but hasn't crystallized intent, suggest capture:

"Want me to capture this as a scratchpad [idea/question/concern] for now? You can formalize it later."

Use judgment — don't suggest this on every query, only when the person is clearly thinking through something that isn't ready to be a decision yet.

## Context

- Constitution: `constitution/` directory
- DNA: `dna/` directory
- Project config: `.dna/config.json`
- **Preferred:** MCP tools (`dna_search`, `dna_validate`, `dna_cascade`, `dna_health`, `scratchpad_list`, etc.)
- **Fallback:** Bash with `dna-graph.py` (use the DNA tool path shown in session health output)
- Format spec: see `format.md` in the dna plugin
