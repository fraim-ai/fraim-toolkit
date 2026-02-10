# fraim-toolkit (dna plugin)

Decision DNA toolkit for fraim projects. Provides graph validation, governance hooks, and skills for managing decisions as markdown files.

## What's Included

```
.claude-plugin/
  plugin.json               Plugin metadata
  marketplace.json          Marketplace definition (fraim-plugins)
hooks/
  hooks.json                Hook configuration (SessionStart, PreToolUse, PostToolUse)
scripts/
  session-start.sh          SessionStart: regenerate health, show summary
  protect-contracts.sh      PreToolUse: block contract edits, warn on governance files
  validate-frontmatter.sh   PreToolUse: validate decision frontmatter
  post-edit-validate.sh     PostToolUse: advisory validation after edits
skills/
  query/SKILL.md            Search and synthesize from decisions
  apply/SKILL.md            Confirm → Mutate → Cascade → Commit
  compile/SKILL.md          Compile decisions to contracts
tools/
  dna-graph.py              CLI: validate, cascade, index, health, create, set, edit, compile-manifest
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

## Skills

| Command | Purpose | Invocation |
|---------|---------|------------|
| `/dna:query` | Search and synthesize from decisions | Auto on understanding signals |
| `/dna:apply` | Confirm → Mutate → Cascade → Commit | Explicit only |
| `/dna:compile` | Compile decisions to contracts | Explicit only |

## Project Requirements

- `.dna/config.json` at project root (project name, optional terminology/deleted artifact config)
- `decisions/` and/or `constitution/` directories
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
