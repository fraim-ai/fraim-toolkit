#!/bin/sh
# bootstrap.sh — Initialize or update a project using fraim-toolkit.
#
# Usage:
#   bootstrap.sh init          Set up a new project
#   bootstrap.sh update-skills Re-copy skill templates with substitution

set -e

TOOLKIT_DIR="$(cd "$(dirname "$0")" && pwd)"

usage() {
  echo "Usage: bootstrap.sh <command>"
  echo ""
  echo "Commands:"
  echo "  init            Initialize a new project"
  echo "  update-skills   Re-copy skill templates (warns before overwriting)"
  exit 1
}

# Read project name from .dna/config.json
get_project_name() {
  if [ -f ".dna/config.json" ]; then
    python3 -c "import json; print(json.load(open('.dna/config.json')).get('project',{}).get('name',''))" 2>/dev/null
  fi
}

# Copy skill templates with {PROJECT_NAME} substitution
copy_skills() {
  local project_name="$1"
  local warn_overwrite="$2"

  mkdir -p .claude/skills/query .claude/skills/apply .claude/skills/compile

  for skill in query apply compile; do
    local src="$TOOLKIT_DIR/skills/$skill/SKILL.md"
    local dst=".claude/skills/$skill/SKILL.md"

    if [ -f "$dst" ] && [ "$warn_overwrite" = "true" ]; then
      printf "Overwrite %s? [y/N] " "$dst"
      read -r answer
      case "$answer" in
        [yY]*) ;;
        *) echo "  Skipped $dst"; continue ;;
      esac
    fi

    if [ -n "$project_name" ]; then
      sed "s/{PROJECT_NAME}/$project_name/g" "$src" > "$dst"
    else
      cp "$src" "$dst"
    fi
    echo "  Copied $dst"
  done
}

cmd_init() {
  printf "Project name: "
  read -r PROJECT_NAME

  if [ -z "$PROJECT_NAME" ]; then
    echo "Error: project name is required."
    exit 1
  fi

  # Create .dna/config.json
  mkdir -p .dna
  cat > .dna/config.json <<ENDJSON
{
  "project": {
    "name": "$PROJECT_NAME"
  },
  "terminology": {},
  "deleted_artifacts": []
}
ENDJSON
  echo "Created .dna/config.json"

  # Create .claude directory structure
  mkdir -p .claude

  # Copy settings.template.json → .claude/settings.json
  if [ -f ".claude/settings.json" ]; then
    echo "WARNING: .claude/settings.json already exists — skipping."
  else
    cp "$TOOLKIT_DIR/settings.template.json" .claude/settings.json
    echo "Created .claude/settings.json"
  fi

  # Copy skill templates
  echo "Copying skill templates..."
  copy_skills "$PROJECT_NAME" "false"

  # Create content directories
  mkdir -p constitution decisions contracts
  echo "Created constitution/, decisions/, contracts/"

  echo ""
  echo "Done! Next steps:"
  echo "  1. Add fraim-toolkit as a git submodule at .claude/dna/"
  echo "     git submodule add <toolkit-url> .claude/dna"
  echo "  2. Create .claude/CLAUDE.md for your project (see toolkit README)"
  echo "  3. Create your first decision:"
  echo "     CLAUDE_PROJECT_DIR=\"\$PWD\" python3 .claude/dna/tools/dna-graph.py create DEC-001 --title \"...\" --level 1"
}

cmd_update_skills() {
  PROJECT_NAME="$(get_project_name)"
  if [ -z "$PROJECT_NAME" ]; then
    echo "Error: could not read project name from .dna/config.json"
    exit 1
  fi

  echo "Updating skill templates for project: $PROJECT_NAME"
  copy_skills "$PROJECT_NAME" "true"
  echo "Done."
}

# Main dispatch
case "${1:-}" in
  init) cmd_init ;;
  update-skills) cmd_update_skills ;;
  *) usage ;;
esac
