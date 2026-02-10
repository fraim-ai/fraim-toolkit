#!/bin/sh
# PreToolUse hook: validates frontmatter for dna/ and constitution/ writes.
# Blocking (exit 2) on structural violations. Graceful degradation (exit 0) if parsing fails.

command -v python3 >/dev/null 2>&1 || exit 0

python3 -c "
import sys, json, re, os

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

file_path = data.get('file_path', '')
content = data.get('content', '')
old_string = data.get('old_string', '')
new_string = data.get('new_string', '')

if not file_path:
    sys.exit(0)

# Reconstruct content for Edit tool
if not content and old_string:
    try:
        if not os.path.exists(file_path):
            sys.exit(0)
        with open(file_path, 'r') as f:
            existing = f.read()
        if old_string not in existing:
            sys.exit(0)  # Edit would fail anyway
        content = existing.replace(old_string, new_string, 1)
    except Exception:
        sys.exit(0)

if not content:
    sys.exit(0)

basename = os.path.basename(file_path)

# Only check dna/ and constitution/ DEC files
if '/dna/' not in file_path and '/constitution/' not in file_path:
    sys.exit(0)
if not basename.startswith('DEC-'):
    sys.exit(0)

errors = []

def get_field(name):
    m = re.search(r'^' + name + r':\s*(\S.*)', content, re.MULTILINE)
    return m.group(1).strip() if m else None

level = get_field('level')
state = get_field('state')
stakes = get_field('stakes')

# 1. Level must be 1-4
if level:
    if level not in ('1', '2', '3', '4'):
        errors.append(f'Invalid level \"{level}\" (must be 1-4)')
else:
    errors.append('Missing level field')

# 2. State vocabulary
if state:
    if state not in ('suggested', 'committed', 'superseded'):
        errors.append(f'Invalid state \"{state}\" (must be suggested/committed/superseded)')

# 3. Stakes vocabulary
if stakes and stakes not in ('high', 'medium', 'low'):
    errors.append(f'Invalid stakes \"{stakes}\" (must be high/medium/low)')

# 4. State transition legality
try:
    if state and os.path.exists(file_path):
        with open(file_path, 'r') as f:
            existing = f.read()
        m = re.search(r'^state:\s*(\S+)', existing, re.MULTILINE)
        if m:
            old = m.group(1)
            if old != state:
                legal = {('suggested','committed'),('suggested','superseded'),('committed','superseded')}
                if (old, state) not in legal:
                    errors.append(f'Illegal transition: {old} -> {state}')
except Exception:
    pass  # graceful degradation

if errors:
    print(f'BLOCKED: Frontmatter validation failed for {basename}:')
    for e in errors:
        print(f'  - {e}')
    sys.exit(2)
" 2>/dev/null

exit $?
