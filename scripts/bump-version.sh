#!/bin/sh
# Bump the plugin version in both plugin.json and marketplace.json.
# Usage: ./scripts/bump-version.sh 2.2.0

set -e

VERSION="$1"
if [ -z "$VERSION" ]; then
  echo "Usage: bump-version.sh <version>" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

# Update plugin.json
sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$ROOT/.claude-plugin/plugin.json"

# Update marketplace.json
sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$ROOT/.claude-plugin/marketplace.json"

echo "Bumped to $VERSION"
grep '"version"' "$ROOT/.claude-plugin/plugin.json" "$ROOT/.claude-plugin/marketplace.json"
