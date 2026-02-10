---
description: Confirm, mutate, cascade, and commit changes to decisions. Explicit only — never auto-invoked.
disable-model-invocation: true
---

# /dna:apply — Commit Changes

The human has decided on a change. Apply it by updating decisions, cascading through the graph, and committing.

**/dna:apply is always explicit.** Never auto-invoked.

## Steps

### Step 1. Confirm

**Inputs:** Changed decision ID(s), proposed change description.

Run `dna-graph cascade NODE --markdown` (via Bash) to preview impact.

Present a confirmation block:

```
┌─ CONFIRMATION ────────────────────────────────────
│ Change: [one-line description]
│ Affected: [node IDs] ([N] total)
│ Proceed? [yes / modify / abort]
└────────────────────────────────────────────────────
```

Human must confirm before proceeding.

### Step 2. Mutate

Use `dna-graph` write commands for structural changes, Edit tool for content:

- **New decisions:** `dna-graph create DEC-NNN --title "..." --level N [--depends-on DEC-001,DEC-003]`
- **State changes:** `dna-graph set DEC-NNN state committed`
- **Dependency changes:** `dna-graph set DEC-NNN depends_on DEC-001,DEC-003`
- **Other frontmatter:** `dna-graph set DEC-NNN field value`
- **Body content:** Edit tool for Decision, Reasoning, Assumptions, Tradeoffs, Detail sections

Never manually edit frontmatter — use `dna-graph set`.

### Step 3. Cascade

Run `dna-graph cascade NODE --markdown` for each modified decision.

For each affected decision in the cascade:
- Read its Assumptions + the upstream change
- Assess whether assumptions still hold
- If broken: draft revision, present to human
- Human approves → update. Human contests → flag for later.

### Step 4. Commit

Run `dna-graph index` and `dna-graph health` (via Bash).

Run `dna-graph validate` (via Bash). If errors: stop and report. If clean: offer to commit.

**Git conventions:**
```
<verb> <scope>: <what changed>
```
Verbs: `add`, `revise`, `restructure`, `merge`, `clarify`

## Constraints

- Iron rule: don't commit a downstream decision if upstream deps aren't committed
- Contracts are compiled output — use /dna:compile, don't patch directly

## Context

- Constitution: `constitution/` directory
- DNA: `dna/` directory
- Project config: `.dna/config.json`
- Graph tool: use the DNA tool path shown in session health output
- Format spec: see `format.md` in the dna plugin
