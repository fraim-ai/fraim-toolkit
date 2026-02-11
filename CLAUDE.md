# fraim-toolkit — DNA Plugin Source Repo

This is the source repository for the **DNA** Claude Code plugin, distributed via the `fraim-plugins` marketplace (`https://github.com/fraim-ai/fraim-toolkit.git`).

## Important

- The plugin's self-detection guard prevents hooks from running here (checks for `.claude-plugin/plugin.json`)
- Do NOT run DNA commands (dna-graph, audit, check, inbox, etc.) against this repo
- This repo is for plugin development only — not a DNA-managed project

## Dev Workflow

1. Edit source files in this repo
2. Commit changes
3. Run `./scripts/bump-version.sh X.Y.Z` (commits, pushes, syncs marketplace clone)
4. Click **Update** in Claude Desktop
5. Test in `~/Test` (the test project where the plugin is enabled)

## Structure

- `hooks/hooks.json` — Hook definitions (SessionStart, PreToolUse, PostToolUse, UserPromptSubmit, Stop)
- `scripts/` — Hook handler scripts
- `tools/dna-graph.py` — Core DNA graph tool
- `agents/` — Background agent definitions
- `skills/` — Slash command skill definitions
- `.claude-plugin/` — Plugin and marketplace metadata (version must match in both files)
