#!/bin/sh
# Bump plugin version, commit, push, and sync the local marketplace clone.
# Usage: ./scripts/bump-version.sh 2.3.0
# Usage: ./scripts/bump-version.sh 2.3.0 "optional commit message"

set -e

VERSION="$1"
if [ -z "$VERSION" ]; then
  echo "Usage: bump-version.sh <version> [commit message]" >&2
  exit 1
fi

MSG="${2:-chore: bump to v$VERSION}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
MARKETPLACE_CLONE="$HOME/.claude/plugins/marketplaces/fraim-plugins"

# 1. Bump versions
sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$ROOT/.claude-plugin/plugin.json"
sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$ROOT/.claude-plugin/marketplace.json"
echo "Bumped to $VERSION"

# 2. Commit and push
git -C "$ROOT" add .claude-plugin/plugin.json .claude-plugin/marketplace.json
git -C "$ROOT" commit -m "$MSG"
git -C "$ROOT" push origin master
echo "Pushed to GitHub"

# 3. Sync marketplace clone so Desktop sees the update
if [ -d "$MARKETPLACE_CLONE/.git" ]; then
  git -C "$MARKETPLACE_CLONE" pull origin master --quiet
  echo "Marketplace clone synced — click Update in Desktop"
else
  echo "Warning: marketplace clone not found at $MARKETPLACE_CLONE"
  echo "Re-add the marketplace in Desktop, then click Update"
fi
