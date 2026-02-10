---
description: Full lifecycle management for decision changes — overlap scan, placement, drafting, cascade, cleanup. Auto-invoked on commitment signals.
---

# /dna:apply — Decision Lifecycle

The person is moving toward a decision. Manage the full lifecycle: detect overlap, place correctly, draft content, mutate, cascade, clean up.

**Auto-invocation signals:** "we should...", "let's go with...", "I've decided...", "that's the approach", "let's change...", "go ahead"

## Steps

### Step 1. Overlap Scan (mandatory)

Before creating or modifying anything:

1. Call `dna_search` (MCP) with key terms from the proposed change
2. Read matched decisions fully
3. Classify the change:
   - **New** — no meaningful overlap with existing decisions
   - **Revision** — modifies an existing decision's content (edit in place)
   - **Supersession** — replaces an existing decision entirely
4. Present findings: "This overlaps with DEC-XXX. Is this a revision of that decision, a replacement, or genuinely separate?"
5. Person confirms classification before proceeding

If no overlap found, state that clearly and proceed.

### Step 2. Placement (agent suggests, person confirms)

For new decisions or supersessions, determine:

- **Level** — analyze what the decision contains (identity/direction/strategy/tactics) and compare with existing decisions at each level
- **Dependencies** — read upstream decisions and identify which ones this decision operates within
- **Stakes** — assess consequence of being wrong (high/medium/low)

Present: "I'd place this at Level 3 (Strategy), depending on DEC-012 and DEC-003, medium stakes. Sound right?"

Person confirms or adjusts before proceeding.

For revisions, placement is already set — skip this step.

### Step 3. Draft Decision

Draft the full decision body:

- **Decision** — from what the person said
- **Reasoning** — from the conversation context
- **Assumptions** — what must remain true (infer from upstream decisions + conversation)
- **Tradeoffs** — what's being given up (identify from alternatives discussed)
- **Detail** — if applicable

Also check scratchpad for related entries:
- Call `scratchpad_list` (MCP) or `dna-graph scratchpad list --json` (Bash fallback)
- **Ideas** → candidate Decision content
- **Constraints** → Assumptions or Tradeoffs
- **Questions** → flag unresolved items before committing
- **Concerns** → Tradeoffs or Assumptions to address

Present full draft for review. Person approves, modifies, or requests changes.

### Step 4. Confirm

Show confirmation block:

```
┌─ CONFIRMATION ────────────────────────────────────
│ Action: [new / revision of DEC-XXX / supersedes DEC-XXX]
│ Decision: [ID] — [title]
│ Level: [N] ([name])  Stakes: [high/medium/low]
│ Dependencies: [list]
│ Downstream impact: [N decisions affected]
│ Proceed? [yes / modify / abort]
└────────────────────────────────────────────────────
```

Run `dna_cascade` (MCP) to get the downstream impact count for the confirmation block.

Person must approve before proceeding.

### Step 5. Mutate

Use MCP tools (preferred) or Bash with `dna-graph` (fallback):

- **New decisions:** `dna_create` (MCP) or `dna-graph create DEC-NNN --title "..." --level N [--depends-on DEC-001,DEC-003]`
- **Body content:** `dna_edit` (MCP) or `dna-graph edit DEC-NNN "old" "new"`
- **State changes:** `dna_set` (MCP) or `dna-graph set DEC-NNN state committed`
- **Dependency changes:** `dna_set` (MCP) or `dna-graph set DEC-NNN depends_on DEC-001,DEC-003`
- **Other frontmatter:** `dna_set` (MCP) or `dna-graph set DEC-NNN field value`

Never manually edit frontmatter — use `dna_set` or `dna-graph set`.

### Step 6. Cascade + Assumption Check (automatic, mandatory)

Immediately after mutation:

1. Run `dna_cascade` (MCP) or `dna-graph cascade NODE --json` on the modified decision
2. For EACH affected decision: read its Assumptions section
3. Assess whether the change breaks any assumptions
4. If broken: draft a revision, present to person
5. Person approves revision → apply it (loop back to Step 5 for that decision)
6. Person contests → flag for later review

This step is not optional — it runs every time a mutation occurs.

### Step 7. Cleanup

- **Supersession:** if classification was "supersession", set old decision state to `superseded` via `dna_set`
- **Scratchpad:** check for related scratchpad entries, offer to mature them via `scratchpad_mature`
- **Revision:** no extra cleanup needed (already edited in place)

### Step 8. Commit

1. Run `dna_validate` (MCP) or `dna-graph validate` — if errors, stop and fix
2. Run `dna_index` (MCP) or `dna-graph index`
3. Run `dna_health` (MCP) or `dna-graph health`
4. If clean: offer git commit

**Git conventions:**
```
<verb> <scope>: <what changed>
```
Verbs: `add`, `revise`, `restructure`, `merge`, `clarify`, `supersede`

## Constraints

- Iron rule: don't commit a downstream decision if upstream deps aren't committed
- Contracts are compiled output — use /dna:compile, don't patch directly
- Every mutation gets a cascade + assumption check — no exceptions

## Context

- Constitution: `constitution/` directory
- DNA: `dna/` directory
- Project config: `.dna/config.json`
- **Preferred:** MCP tools (`dna_search`, `dna_create`, `dna_set`, `dna_edit`, `dna_cascade`, `scratchpad_list`, `scratchpad_mature`, etc.)
- **Fallback:** Bash with `dna-graph.py` (use the DNA tool path shown in session health output)
- Format spec: see `format.md` in the dna plugin
