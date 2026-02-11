---
description: Activate the DNA decision capture plugin for the current project.
disable-model-invocation: true
---

# /dna:init — Activate DNA for this project

Enables the DNA plugin for the current project and bootstraps the decision graph.

**Usage:** `/dna:init`

## What to do

1. **Check if already active.** Read the project's `.claude/settings.local.json` (if it exists). If `enabledPlugins` already has `"dna@fraim-plugins": true`, tell the person it's already active and stop.

2. **Enable the plugin for this project.** Write or merge `enabledPlugins` into `.claude/settings.local.json`:
   ```json
   {
     "enabledPlugins": {
       "dna@fraim-plugins": true
     }
   }
   ```
   Preserve any existing keys in the file — only add/update the `enabledPlugins` entry.

3. **Tell the person** the plugin is now active and they need to start a new session for it to take effect.

## Constraints

- Never modify global settings (`~/.claude/settings.json`)
- Preserve existing project settings — only add the plugin enablement
- This skill only enables the plugin. The SessionStart hook handles bootstrapping `.dna/`, `dna/`, `constitution/`, and `contracts/` directories automatically on first run.
