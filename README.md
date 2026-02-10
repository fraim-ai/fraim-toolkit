# fraim-toolkit (dna plugin)

Decision DNA toolkit for fraim projects. Provides graph validation, governance hooks, MCP server, and skills for managing decisions as markdown files.

## What's Included

```
.claude-plugin/
  plugin.json               Plugin metadata
  marketplace.json          Marketplace definition (fraim-plugins)
.mcp.json                   MCP server configuration
hooks/
  hooks.json                Hook configuration (SessionStart, PreToolUse, PostToolUse)
scripts/
  session-start.sh          SessionStart: regenerate health, show summary
  protect-contracts.sh      PreToolUse: block contract edits, warn on governance files
  validate-frontmatter.sh   PreToolUse: validate decision frontmatter
  post-edit-validate.sh     PostToolUse: advisory validation after edits
server/
  dna_mcp.py                MCP server: dna-graph as native Claude Code tools
skills/
  query/SKILL.md            Search and synthesize from decisions
  apply/SKILL.md            Confirm → Mutate → Cascade → Commit
  compile/SKILL.md          Compile decisions to contracts
tools/
  dna-graph.py              CLI: validate, cascade, index, health, create, set, edit,
                            compile-manifest, scratchpad, scratchpad-summary
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

## MCP Server

The plugin includes an MCP server that exposes dna-graph commands as native Claude Code tools. Requires `uv` (auto-installs `fastmcp` on first run).

| MCP Tool | Wraps | Purpose |
|----------|-------|---------|
| `dna_validate` | `validate` | Check frontmatter, topology, body content |
| `dna_cascade` | `cascade` | Propagation preview (downstream or upstream) |
| `dna_health` | `health` | Regenerate HEALTH.md + summary |
| `dna_index` | `index` | Regenerate INDEX.md per directory |
| `dna_compile_manifest` | `compile-manifest` | Deterministic skeleton for contracts |
| `dna_create` | `create` | Create a new decision |
| `dna_set` | `set` | Update frontmatter field |
| `dna_edit` | `edit` | Replace body text with delta reporting |
| `scratchpad_add` | `scratchpad add` | Add pre-decision entry |
| `scratchpad_list` | `scratchpad list` | List scratchpad entries |
| `scratchpad_mature` | `scratchpad mature` | Graduate entry to decision |

## Skills

| Command | Purpose | Invocation |
|---------|---------|------------|
| `/dna:query` | Search and synthesize from decisions | Auto on understanding signals |
| `/dna:apply` | Confirm → Mutate → Cascade → Commit | Explicit only |
| `/dna:compile` | Compile decisions to contracts | Explicit only |

## Scratchpad

Pre-decision artifact storage for ideas that haven't crystallized into formal decisions. Stored in `.dna/scratchpad.json`.

**4 types:** idea, constraint, question, concern

**Lifecycle:** add → (optional link to decisions) → mature to a decision

```sh
dna-graph scratchpad add --type idea "Consider event sourcing for audit trail"
dna-graph scratchpad add --type constraint "Must support offline mode" --links DEC-010
dna-graph scratchpad list
dna-graph scratchpad mature SP-001 DEC-057
dna-graph scratchpad-summary
```

## Project Requirements

- `.dna/config.json` at project root (project name, optional terminology/deleted artifact config)
- `dna/` and/or `constitution/` directories
- `contracts/` directory for compiled output

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
