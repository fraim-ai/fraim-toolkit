#!/bin/sh
# PostToolUse hook: runs dna-graph validate after any Edit/Write to decision files.
# Advisory only (exit 0) — warns about issues but does not block.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
export PLUGIN_ROOT

command -v python3 >/dev/null 2>&1 || exit 0

python3 -c "
import sys, json, os, subprocess

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

file_path = data.get('file_path', '')
if not file_path:
    sys.exit(0)

# Only check dna/ and constitution/ DEC files
if '/dna/' not in file_path and '/constitution/' not in file_path:
    sys.exit(0)

basename = os.path.basename(file_path)
if not basename.startswith('DEC-'):
    sys.exit(0)

# Run validate quietly
plugin_root = os.environ.get('PLUGIN_ROOT', '')
tool_path = os.path.join(plugin_root, 'tools', 'dna-graph.py') if plugin_root else None
if not tool_path or not os.path.exists(tool_path):
    sys.exit(0)

result = subprocess.run(
    [sys.executable, tool_path, 'validate'],
    capture_output=True, text=True, timeout=10
)

# Extract errors only (warnings are advisory)
errors = []
for line in result.stdout.split('\n'):
    line = line.strip()
    if line.startswith('ERRORS'):
        continue
    # Lines under ERRORS section are indented
    if errors is not None and line and not line.startswith('WARNING'):
        pass

# Simpler: just check exit code and report errors
if result.returncode != 0:
    error_lines = []
    in_errors = False
    for line in result.stdout.split('\n'):
        if 'ERRORS' in line:
            in_errors = True
            continue
        if 'WARNINGS' in line:
            in_errors = False
        if in_errors and line.strip():
            error_lines.append(line.strip())
    if error_lines:
        print(f'POST-EDIT WARNING: {basename} edit introduced validation errors:')
        for e in error_lines:
            print(f'  {e}')
        print('Run: dna-graph validate for full report')
        print('Prefer: dna-graph edit DEC-NNN \"old\" \"new\" (validates automatically)')
" 2>/dev/null

exit 0
