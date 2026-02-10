#!/usr/bin/env python3
"""dna-graph: Graph operations for a decision system.

Parses dna/*.md and constitution/*.md frontmatter into a dependency graph.

Subcommands (read):
  validate              Check frontmatter, graph topology, and body content
  cascade NODE [--reverse]  Compute propagation (downstream, or upstream with --reverse)
  index                 Regenerate INDEX.md per directory
  health                Generate HEALTH.md from current state
  search TERM           Search decisions by title and body content
  frontier              Compute the decision frontier — what to think about next

Subcommands (write):
  create DEC-NNN        Create a new decision with pre-validated frontmatter
  set DEC-NNN FIELD VAL Update a single frontmatter field with pre-validation
  edit DEC-NNN OLD NEW  Replace body text with pre/post validation delta
  compile-manifest      Produce deterministic skeleton for contract compilation

Subcommands (scratchpad):
  scratchpad add        Add a pre-decision entry (idea, constraint, question, concern)
  scratchpad list       List scratchpad entries (active and matured)
  scratchpad mature     Graduate a scratchpad entry to a decision
  scratchpad-summary    One-line summary of active scratchpad entries
"""

import glob
import os
import re
import sys
import json
from collections import defaultdict
from datetime import date

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
DNA_DIR = os.path.join(PROJECT_ROOT, "dna")
CONSTITUTION_DIR = os.path.join(PROJECT_ROOT, "constitution")
CONTRACTS_DIR = os.path.join(PROJECT_ROOT, "contracts")
HEALTH_FILE = os.path.join(PROJECT_ROOT, "HEALTH.md")

VALID_STATES = {"suggested", "committed", "superseded"}
VALID_STAKES = {"high", "medium", "low"}
VALID_LEVELS = {1, 2, 3, 4}

SCRATCHPAD_FILE = os.path.join(PROJECT_ROOT, ".dna", "scratchpad.json")
VALID_SP_TYPES = {"idea", "constraint", "question", "concern"}

# Body content linter patterns (static — always active)
RE_STALE_INF = re.compile(r'\bINF-\d{3}\b')
RE_STALE_CTX = re.compile(r'\bCTX-\d{3}\b')
RE_DEC_BODY_REF = re.compile(r'\bDEC-(\d{3})\b')
RE_SUPERSEDES = re.compile(r'[Ss]upersedes?\s+(DEC-\d{3})')

# Config-driven linting (loaded from .dna/config.json)
_CONFIG = None


def load_config():
    """Load project config from .dna/config.json. Returns dict (empty if missing)."""
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG
    config_path = os.path.join(PROJECT_ROOT, ".dna", "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            _CONFIG = json.load(f)
    else:
        _CONFIG = {}
    return _CONFIG


def _get_terminology():
    """Return (RE_TERM, exemptions, exempt_ids) from config, or (None, [], set())."""
    cfg = load_config()
    term_cfg = cfg.get("terminology", {})
    flagged = term_cfg.get("flagged_term")
    if not flagged:
        return None, [], set()
    pattern = re.compile(r'\b' + re.escape(flagged) + r'\b', re.IGNORECASE)
    exemptions = [re.compile(e) for e in term_cfg.get("exemptions", [])]
    exempt_ids = set(term_cfg.get("exempt_ids", []))
    return pattern, exemptions, exempt_ids


def _get_deleted_artifacts():
    """Return list of (compiled_pattern, label) from config, or []."""
    cfg = load_config()
    entries = cfg.get("deleted_artifacts", [])
    result = []
    for entry in entries:
        pat = entry.get("pattern")
        label = entry.get("label", pat)
        if pat:
            result.append((re.compile(pat), label))
    return result


# ---------------------------------------------------------------------------
# Scratchpad helpers
# ---------------------------------------------------------------------------

def _load_scratchpad():
    """Read .dna/scratchpad.json, return entries list (empty if missing)."""
    if not os.path.exists(SCRATCHPAD_FILE):
        return []
    with open(SCRATCHPAD_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("entries", [])


def _save_scratchpad(entries):
    """Atomic write of scratchpad entries to .dna/scratchpad.json."""
    os.makedirs(os.path.dirname(SCRATCHPAD_FILE), exist_ok=True)
    tmp_path = SCRATCHPAD_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f, indent=2)
        f.write("\n")
    os.rename(tmp_path, SCRATCHPAD_FILE)


def _next_sp_id(entries):
    """Find max SP-NNN among entries, return SP-(N+1) zero-padded to 3 digits."""
    max_n = 0
    for e in entries:
        m = re.match(r'^SP-(\d{3})$', e.get("id", ""))
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"SP-{max_n + 1:03d}"


def _scratchpad_summary(entries):
    """Return type-count string for active (non-matured) entries."""
    active = [e for e in entries if not e.get("matured_to")]
    if not active:
        return ""
    counts = defaultdict(int)
    for e in active:
        counts[e.get("type", "unknown")] += 1
    parts = [f"{c} {t}(s)" for t, c in sorted(counts.items())]
    return f"{len(active)} active — {', '.join(parts)}"


# ---------------------------------------------------------------------------
# YAML frontmatter parser (no external deps)
# ---------------------------------------------------------------------------

def parse_frontmatter(filepath):
    """Parse YAML frontmatter from a markdown file. Returns (dict, body_text)."""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    if not text.startswith("---"):
        return None, text

    end = text.find("\n---", 3)
    if end == -1:
        return None, text

    yaml_block = text[4:end]
    body = text[end + 4:]
    fm = _parse_yaml_block(yaml_block)
    return fm, body


def _parse_yaml_block(block):
    """Minimal YAML parser sufficient for decision frontmatter."""
    result = {}
    lines = block.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        m = re.match(r'^(\w[\w_]*)\s*:\s*(.*)', line)
        if not m:
            i += 1
            continue

        key = m.group(1)
        value = m.group(2).strip()

        # List value starting on next lines
        if value == "" and i + 1 < len(lines) and lines[i + 1].strip().startswith("-"):
            items = []
            i += 1
            while i < len(lines) and lines[i].strip().startswith("-"):
                item_line = lines[i].strip()
                val = re.sub(r'^-\s*', '', item_line)
                items.append(_coerce(val))
                i += 1
            result[key] = items
        elif value == "[]":
            result[key] = []
            i += 1
        else:
            result[key] = _coerce(value)
            i += 1

    return result


def _coerce(val):
    """Coerce a YAML scalar string to Python type."""
    if val == "":
        return None
    if (val.startswith('"') and val.endswith('"')) or \
       (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    if val.lower() in ("null", "~"):
        return None
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------

_TITLE_NEEDS_QUOTING = re.compile(r'[:#\["\']|^[{>|*&!%@`]')


def serialize_decision(fm, body):
    """Serialize frontmatter dict + body text into a complete decision file.

    Uses template-based output (not general YAML) with fixed field order.
    """
    lines = ["---"]

    lines.append(f"id: {fm['id']}")

    title = fm.get("title", "")
    if _TITLE_NEEDS_QUOTING.search(title):
        escaped = title.replace('"', '\\"')
        lines.append(f'title: "{escaped}"')
    else:
        lines.append(f"title: {title}")

    lines.append(f"date: {fm.get('date', date.today().isoformat())}")
    lines.append(f"level: {fm['level']}")
    lines.append(f"state: {fm.get('state', 'suggested')}")

    if fm.get("stakes"):
        lines.append(f"stakes: {fm['stakes']}")

    deps = fm.get("depends_on", [])
    if not deps:
        lines.append("depends_on: []")
    else:
        lines.append("depends_on:")
        for dep in deps:
            lines.append(f"  - {dep}")

    lines.append("---")

    # Body: preserve exactly as-is, ensure single newline separator
    if body and not body.startswith("\n"):
        lines.append("")
    lines.append(body if body else "")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# State transition validator
# ---------------------------------------------------------------------------

LEGAL_TRANSITIONS = {
    ("suggested", "committed"),
    ("suggested", "superseded"),
    ("committed", "superseded"),
}


def validate_transition(old_state, new_state):
    """Returns (ok, error_msg). Same-state is a no-op (ok)."""
    if old_state == new_state:
        return True, None
    if (old_state, new_state) in LEGAL_TRANSITIONS:
        return True, None
    return False, f"Illegal state transition: {old_state} → {new_state}"


# ---------------------------------------------------------------------------
# Pre-mutation validators
# ---------------------------------------------------------------------------

def validate_for_create(nid, fm, nodes, target_dir):
    """Pre-validate a new node. Returns (errors, warnings)."""
    errors = []
    warnings = []

    # ID format
    if not re.match(r'^DEC-\d{3}$', nid):
        errors.append(f"{nid}: ID must match DEC-NNN (3 digits)")

    # ID uniqueness
    if nid in nodes:
        errors.append(f"{nid}: ID already exists at {nodes[nid].get('_filepath', '?')}")

    # Level vocabulary
    level = fm.get("level")
    if level not in VALID_LEVELS:
        errors.append(f"{nid}: invalid level '{level}' (must be 1-4)")

    # State vocabulary
    state = fm.get("state", "suggested")
    if state not in VALID_STATES:
        errors.append(f"{nid}: invalid state '{state}' (must be suggested/committed/superseded)")

    # Stakes vocabulary
    stakes = fm.get("stakes")
    if stakes and stakes not in VALID_STAKES:
        errors.append(f"{nid}: invalid stakes '{stakes}' (must be high/medium/low)")

    # Dependency checks
    deps = fm.get("depends_on", [])
    all_ids = set(nodes.keys())
    for dep_id in deps:
        if dep_id not in all_ids:
            errors.append(f"{nid}: depends_on references non-existent {dep_id}")
        elif dep_id == nid:
            errors.append(f"{nid}: self-dependency")
        else:
            # Level ordering
            dep_level = nodes[dep_id].get("level")
            if dep_level is not None and level is not None and dep_level > level:
                warnings.append(f"{nid} (level {level}): depends on {dep_id} (level {dep_level}) — level inversion")

    # Iron rule: constitution node cannot depend on project node
    is_constitution = (target_dir == CONSTITUTION_DIR)
    if is_constitution:
        for dep_id in deps:
            if dep_id in nodes and nodes[dep_id].get("_scope") == "project":
                errors.append(f"{nid}: constitution depends on project {dep_id} (iron rule violation)")

    # Upstream readiness: cannot create as committed if upstream deps aren't committed
    state = fm.get("state", "suggested")
    if state == "committed":
        for dep_id in deps:
            if dep_id in nodes:
                dep_state = nodes[dep_id].get("state", "unknown")
                if dep_state != "committed":
                    errors.append(f"{nid}: cannot create as committed — upstream {dep_id} is '{dep_state}'")

    # Cycle detection: would adding this node create a cycle?
    if deps and not errors:
        # Build adjacency including the new node
        adj = defaultdict(set)
        for existing_nid, n in nodes.items():
            for dep in get_deps_list(n):
                if dep in all_ids:
                    adj[existing_nid].add(dep)
        adj[nid] = set(deps)
        # Check reachability from any dep back to nid
        for dep_id in deps:
            visited = set()
            stack = [dep_id]
            while stack:
                current = stack.pop()
                if current == nid:
                    errors.append(f"{nid}: adding this node would create a cycle through {dep_id}")
                    break
                if current in visited:
                    continue
                visited.add(current)
                stack.extend(adj.get(current, set()))

    return errors, warnings


def validate_for_set(nid, field, value, nodes):
    """Pre-validate a field update on an existing node. Returns (errors, warnings)."""
    errors = []
    warnings = []

    if nid not in nodes:
        errors.append(f"{nid}: not found in graph")
        return errors, warnings

    node = nodes[nid]

    if field == "state":
        old_state = node.get("state", "suggested")
        ok, msg = validate_transition(old_state, value)
        if not ok:
            errors.append(f"{nid}: {msg}")
        if value == "committed" and not errors:
            for dep_id in get_deps_list(node):
                if dep_id in nodes:
                    dep_state = nodes[dep_id].get("state", "unknown")
                    if dep_state != "committed":
                        errors.append(f"{nid}: cannot commit — upstream {dep_id} is '{dep_state}'")

    elif field == "depends_on":
        # value is a list of dep IDs
        deps = value if isinstance(value, list) else []
        all_ids = set(nodes.keys())
        my_level = node.get("level")

        for dep_id in deps:
            if dep_id not in all_ids:
                errors.append(f"{nid}: depends_on references non-existent {dep_id}")
            elif dep_id == nid:
                errors.append(f"{nid}: self-dependency")
            else:
                dep_level = nodes[dep_id].get("level")
                if dep_level is not None and my_level is not None and dep_level > my_level:
                    warnings.append(f"{nid} (level {my_level}): depends on {dep_id} (level {dep_level}) — level inversion")

        # Iron rule
        if node.get("_scope") == "constitution":
            for dep_id in deps:
                if dep_id in nodes and nodes[dep_id].get("_scope") == "project":
                    errors.append(f"{nid}: constitution depends on project {dep_id} (iron rule violation)")

        # Cycle detection
        if deps and not errors:
            adj = defaultdict(set)
            for existing_nid, n in nodes.items():
                if existing_nid == nid:
                    continue  # skip old edges for this node
                for dep in get_deps_list(n):
                    if dep in all_ids:
                        adj[existing_nid].add(dep)
            adj[nid] = set(deps)
            for dep_id in deps:
                visited = set()
                stack = [dep_id]
                while stack:
                    current = stack.pop()
                    if current == nid:
                        errors.append(f"{nid}: this change would create a cycle through {dep_id}")
                        break
                    if current in visited:
                        continue
                    visited.add(current)
                    stack.extend(adj.get(current, set()))

    elif field == "level":
        if value not in VALID_LEVELS:
            errors.append(f"{nid}: invalid level '{value}' (must be 1-4)")
        else:
            # Check ordering against current deps
            for dep_id in get_deps_list(node):
                if dep_id in nodes:
                    dep_level = nodes[dep_id].get("level")
                    if dep_level is not None and dep_level > value:
                        warnings.append(f"{nid} (level {value}): depends on {dep_id} (level {dep_level}) — level inversion")

    elif field == "stakes":
        if value not in VALID_STAKES:
            errors.append(f"{nid}: invalid stakes '{value}' (must be high/medium/low)")

    elif field == "title":
        if not value or not value.strip():
            errors.append(f"{nid}: title cannot be empty")

    else:
        errors.append(f"Unknown field: {field} (valid: state, depends_on, level, stakes, title)")

    return errors, warnings


# ---------------------------------------------------------------------------
# Graph loading
# ---------------------------------------------------------------------------

def load_graph():
    """Load all decision nodes into a dict keyed by ID.

    Loads from both constitution/ (upstream) and dna/ (project),
    tracking scope per node. Errors on ID collision across directories.
    """
    dirs = []
    if os.path.isdir(CONSTITUTION_DIR):
        dirs.append(("constitution", CONSTITUTION_DIR))
    dirs.append(("project", DNA_DIR))

    nodes = {}
    for scope, dna_dir in dirs:
        for filepath in sorted(glob.glob(os.path.join(dna_dir, "DEC-*.md"))):
            fm, body = parse_frontmatter(filepath)
            if fm and "id" in fm:
                nid = fm["id"]
                if nid in nodes:
                    print(f"ERROR: ID collision — {nid} exists in both "
                          f"{nodes[nid]['_scope']} and {scope}",
                          file=sys.stderr)
                    sys.exit(1)
                fm["_filepath"] = filepath
                fm["_scope"] = scope
                fm["_body"] = body
                nodes[nid] = fm
    return nodes


def get_dependents(nodes, node_id):
    """Find nodes whose depends_on includes node_id."""
    dependents = []
    for nid, n in nodes.items():
        for dep in (n.get("depends_on") or []):
            dep_id = dep if isinstance(dep, str) else dep.get("id") if isinstance(dep, dict) else None
            if dep_id == node_id:
                dependents.append(nid)
    return dependents


def get_deps_list(node):
    """Extract flat list of dependency IDs from a node."""
    deps = []
    for dep in (node.get("depends_on") or []):
        if isinstance(dep, str):
            deps.append(dep)
        elif isinstance(dep, dict) and dep.get("id"):
            deps.append(dep["id"])
    return deps


# ---------------------------------------------------------------------------
# Frontier helpers
# ---------------------------------------------------------------------------


def _compute_transitive_downstream(nodes):
    """BFS from every node through the dependents graph.

    Returns dict[nid -> set of transitively dependent node IDs].
    """
    # Build reverse adjacency: dep_id -> set of nodes that depend on it
    reverse_adj = defaultdict(set)
    for nid, n in nodes.items():
        for dep_id in get_deps_list(n):
            if dep_id in nodes:
                reverse_adj[dep_id].add(nid)

    result = {}
    for nid in nodes:
        visited = set()
        queue = list(reverse_adj.get(nid, set()))
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            queue.extend(reverse_adj.get(current, set()) - visited)
        result[nid] = visited
    return result


def _critical_path(nodes, target_nid):
    """For a blocked suggested decision, find the longest chain of uncommitted upstream.

    BFS upstream from target through non-committed dependencies.
    Returns list of uncommitted decision IDs from deepest root toward target
    (excluding target itself). This is the critical path — commit these in order
    to unblock the target.
    """
    visited = {target_nid}
    queue = [(target_nid, 0)]
    depth = {target_nid: 0}
    parent = {}

    while queue:
        current, d = queue.pop(0)
        for dep_id in get_deps_list(nodes.get(current, {})):
            if dep_id in nodes and dep_id not in visited and nodes[dep_id].get("state") != "committed":
                visited.add(dep_id)
                depth[dep_id] = d + 1
                parent[dep_id] = current
                queue.append((dep_id, d + 1))

    if not parent:
        # Direct uncommitted deps only (no further chain)
        return [d for d in get_deps_list(nodes.get(target_nid, {}))
                if d in nodes and nodes[d].get("state") != "committed"]

    # Find the deepest node (root furthest from target)
    deepest = max(parent.keys(), key=lambda n: depth[n])

    # Reconstruct path from deepest back toward target
    path = []
    current = deepest
    while current != target_nid:
        path.append(current)
        current = parent.get(current, target_nid)

    return path  # deepest root first, toward target


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_validate(nodes):
    """Validate all decision nodes. Returns (errors, warnings)."""
    errors = []
    warnings = []
    all_ids = set(nodes.keys())

    for nid, n in sorted(nodes.items()):
        # 1. ID prefix
        if not nid.startswith("DEC-"):
            errors.append(f"{nid}: ID must start with DEC-")

        # 2. Required fields
        if not n.get("title"):
            warnings.append(f"{nid}: missing title")
        if not n.get("date"):
            warnings.append(f"{nid}: missing date")

        # 3. Level
        level = n.get("level")
        if level is None:
            errors.append(f"{nid}: missing level")
        elif level not in VALID_LEVELS:
            errors.append(f"{nid}: invalid level '{level}' (must be 1-4)")

        # 4. State
        state = n.get("state")
        if state and state not in VALID_STATES:
            errors.append(f"{nid}: invalid state '{state}' (must be suggested/committed/superseded)")
        elif not state:
            warnings.append(f"{nid}: missing state")

        # 5. Stakes
        stakes = n.get("stakes")
        if stakes and stakes not in VALID_STAKES:
            errors.append(f"{nid}: invalid stakes '{stakes}' (must be high/medium/low)")

        # 6. Reference integrity — depends_on targets exist
        for dep_id in get_deps_list(n):
            if dep_id not in all_ids:
                errors.append(f"{nid}: depends_on references non-existent {dep_id}")

        # 7. Required body sections
        body = n.get("_body", "")
        for section in ("Decision", "Reasoning", "Assumptions", "Tradeoffs"):
            if not re.search(rf'^## {section}\s*$', body, re.MULTILINE):
                warnings.append(f"{nid}: missing required section ## {section}")

    # 8. Cycle detection via DFS
    adj = defaultdict(list)
    for nid, n in nodes.items():
        for dep_id in get_deps_list(n):
            if dep_id in all_ids:
                adj[nid].append(dep_id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in nodes}

    def dfs(u, path):
        color[u] = GRAY
        for v in adj.get(u, []):
            if v not in color:
                continue
            if color[v] == GRAY:
                cycle_start = path.index(v)
                cycle = path[cycle_start:] + [v]
                errors.append(f"Cycle detected: {' → '.join(cycle)}")
                return
            if color[v] == WHITE:
                dfs(v, path + [v])
        color[u] = BLACK

    for nid in nodes:
        if color[nid] == WHITE:
            dfs(nid, [nid])

    # 9. Orphan detection: no depends_on AND no dependents
    for nid, n in sorted(nodes.items()):
        has_upstream = bool(get_deps_list(n))
        has_downstream = bool(get_dependents(nodes, nid))
        if not has_upstream and not has_downstream:
            warnings.append(f"{nid}: orphan (no upstream or downstream edges)")

    # 10. Level ordering: depends_on should not point to higher level numbers
    for nid, n in sorted(nodes.items()):
        my_level = n.get("level")
        if my_level is None:
            continue
        for dep_id in get_deps_list(n):
            if dep_id in nodes:
                dep_level = nodes[dep_id].get("level")
                if dep_level is not None and dep_level > my_level:
                    warnings.append(f"{nid} (level {my_level}): depends on {dep_id} (level {dep_level}) — level inversion")

    # 11. Cross-directory iron rule: constitution cannot depend on project
    for nid, n in sorted(nodes.items()):
        if n.get("_scope") != "constitution":
            continue
        for dep_id in get_deps_list(n):
            if dep_id in nodes and nodes[dep_id].get("_scope") == "project":
                errors.append(f"{nid}: constitution depends on project {dep_id} (iron rule violation)")

    # 12. State health: committed with non-committed upstream
    for nid, n in sorted(nodes.items()):
        if n.get("state") != "committed":
            continue
        for dep_id in get_deps_list(n):
            if dep_id in nodes:
                dep_state = nodes[dep_id].get("state")
                if dep_state == "superseded":
                    errors.append(f"{nid}: committed but upstream {dep_id} is superseded")
                elif dep_state == "suggested":
                    errors.append(f"{nid}: committed but upstream {dep_id} is still suggested")

    # --- Body content checks (B1–B6) ---

    for nid, n in sorted(nodes.items()):
        body = n.get("_body", "")
        if not body:
            continue

        # B1. Stale INF/CTX references
        stale_infs = sorted(set(RE_STALE_INF.findall(body)))
        if stale_infs:
            warnings.append(f"{nid} [stale-ref]: body references {len(stale_infs)} stale INF ID(s) ({', '.join(stale_infs)})")
        stale_ctxs = sorted(set(RE_STALE_CTX.findall(body)))
        if stale_ctxs:
            warnings.append(f"{nid} [stale-ref]: body references {len(stale_ctxs)} stale CTX ID(s) ({', '.join(stale_ctxs)})")

        # B2. DEC body reference validator — check all DEC-NNN in body exist
        dec_refs = set(RE_DEC_BODY_REF.findall(body))
        bad_refs = []
        for num in sorted(dec_refs):
            ref_id = f"DEC-{num}"
            if ref_id != nid and ref_id not in all_ids:
                bad_refs.append(ref_id)
        if bad_refs:
            warnings.append(f"{nid} [broken-ref]: body references non-existent {', '.join(bad_refs)}")

        # B3. Supersession cross-check
        for m in RE_SUPERSEDES.finditer(body):
            target_id = m.group(1)
            if target_id in nodes and nodes[target_id].get("state") != "superseded":
                target_state = nodes[target_id].get("state", "unknown")
                warnings.append(f"{nid} [supersession]: claims to supersede {target_id}, but {target_id} state is '{target_state}'")

        # B4. Terminology linter — config-driven
        re_term, term_exemptions, term_exempt_ids = _get_terminology()
        if re_term and nid not in term_exempt_ids:
            term_count = 0
            for line in body.split("\n"):
                if not re_term.search(line):
                    continue
                exempt = False
                for pat in term_exemptions:
                    if pat.search(line):
                        exempt = True
                        break
                if not exempt:
                    term_count += 1
            if term_count:
                flagged_word = load_config().get("terminology", {}).get("flagged_term", "?")
                warnings.append(f"{nid} [terminology]: {term_count} line(s) with unexempted '{flagged_word}' in body text")

        # B6. Deleted artifact references — config-driven
        deleted_artifacts = _get_deleted_artifacts()
        if deleted_artifacts:
            matched_artifacts = []
            for pat, label in deleted_artifacts:
                if pat.search(body):
                    matched_artifacts.append(label)
            if matched_artifacts:
                warnings.append(f"{nid} [deleted-artifact]: body references deleted artifacts: {', '.join(matched_artifacts)}")

    # B5. Strict orphan check — L2+ with no depends_on (not caught by existing orphan check #9)
    existing_orphans = set()
    for nid, n in nodes.items():
        if not get_deps_list(n) and not get_dependents(nodes, nid):
            existing_orphans.add(nid)
    for nid, n in sorted(nodes.items()):
        level = n.get("level")
        if level is not None and level >= 2 and not get_deps_list(n) and nid not in existing_orphans:
            warnings.append(f"{nid} [missing-dep]: no depends_on — L{level} decisions should have upstream dependencies")

    return errors, warnings


def cmd_cascade(nodes, start_node, json_output=False, markdown_output=False):
    """Compute propagation cascade from a changed node."""
    if start_node not in nodes:
        print(f"Error: {start_node} not found in graph", file=sys.stderr)
        return 1

    waves = []
    changed = {start_node}
    visited = set()
    wave_num = 0

    while changed:
        wave_num += 1
        wave_effects = []
        next_changed = set()

        for nid in sorted(changed):
            if nid in visited:
                continue
            visited.add(nid)

            dependents = get_dependents(nodes, nid)
            n_scope = nodes.get(nid, {}).get("_scope", "project")

            for dep_id in dependents:
                if dep_id not in visited:
                    dep_scope = nodes[dep_id].get("_scope", "project")
                    effect = {
                        "node": dep_id,
                        "current_state": nodes[dep_id].get("state", "unknown"),
                        "reason": f"depends on {nid}",
                    }
                    if n_scope != dep_scope:
                        effect["cross_directory"] = True
                    wave_effects.append(effect)
                    next_changed.add(dep_id)

        if wave_effects:
            waves.append({"wave": wave_num, "effects": wave_effects})
        changed = next_changed

    total = sum(len(w["effects"]) for w in waves)
    unique = len({e["node"] for w in waves for e in w["effects"]})

    if json_output:
        output = {
            "start_node": start_node,
            "waves": waves,
            "summary": {
                "total_affected": total,
                "unique_affected": unique,
                "wave_count": len(waves),
            }
        }
        print(json.dumps(output, indent=2))
        return 0

    if markdown_output:
        start_title = nodes[start_node].get("title", "(no title)")
        if not waves:
            print(f"### Cascade: {start_node} — {start_title}")
            print()
            print("No downstream dependents.")
            return 0
        print(f"### Cascade: {start_node} — {start_title}")
        print()
        print(f"**{total} decisions** need review across {len(waves)} wave(s).")
        print()
        for w in waves:
            print(f"#### Wave {w['wave']}")
            print()
            print("| Node | Title | State | Reason |")
            print("|------|-------|-------|--------|")
            for e in w["effects"]:
                title = nodes.get(e["node"], {}).get("title", "?")
                cross = " [cross-dir]" if e.get("cross_directory") else ""
                print(f"| {e['node']} | {title} | {e['current_state']} | {e['reason']}{cross} |")
            print()
        return 0

    # Default table output
    if not waves:
        print(f"No downstream dependents for {start_node}.")
        return 0

    for w in waves:
        print(f"\n=== Wave {w['wave']} ===")
        print(f"{'Node':<12} {'State':<14} Reason")
        print("-" * 60)
        for e in w["effects"]:
            cross = " [cross-dir]" if e.get("cross_directory") else ""
            print(f"{e['node']:<12} {e['current_state']:<14} {e['reason']}{cross}")

    print(f"\nTotal: {total} decisions need review across {len(waves)} wave(s).")
    return 0


def cmd_cascade_reverse(nodes, start_node, json_output=False, markdown_output=False):
    """Compute upstream cascade — what constrains a given node."""
    if start_node not in nodes:
        print(f"Error: {start_node} not found in graph", file=sys.stderr)
        return 1

    waves = []
    current = {start_node}
    visited = set()
    wave_num = 0

    while current:
        wave_num += 1
        wave_effects = []
        next_current = set()

        for nid in sorted(current):
            if nid in visited:
                continue
            visited.add(nid)

            for dep_id in get_deps_list(nodes.get(nid, {})):
                if dep_id in nodes and dep_id not in visited:
                    dep_scope = nodes[dep_id].get("_scope", "project")
                    n_scope = nodes.get(nid, {}).get("_scope", "project")
                    effect = {
                        "node": dep_id,
                        "current_state": nodes[dep_id].get("state", "unknown"),
                        "reason": f"{nid} depends on this",
                    }
                    if n_scope != dep_scope:
                        effect["cross_directory"] = True
                    wave_effects.append(effect)
                    next_current.add(dep_id)

        if wave_effects:
            waves.append({"wave": wave_num, "effects": wave_effects})
        current = next_current

    total = sum(len(w["effects"]) for w in waves)
    unique = len({e["node"] for w in waves for e in w["effects"]})

    if json_output:
        output = {
            "start_node": start_node,
            "direction": "upstream",
            "waves": waves,
            "summary": {
                "total_affected": total,
                "unique_affected": unique,
                "wave_count": len(waves),
            }
        }
        print(json.dumps(output, indent=2))
        return 0

    if markdown_output:
        start_title = nodes[start_node].get("title", "(no title)")
        if not waves:
            print(f"### Upstream: {start_node} — {start_title}")
            print()
            print("No upstream dependencies.")
            return 0
        print(f"### Upstream: {start_node} — {start_title}")
        print()
        print(f"**{unique} upstream decisions** across {len(waves)} wave(s).")
        print()
        for w in waves:
            print(f"#### Wave {w['wave']}")
            print()
            print("| Node | Title | State | Reason |")
            print("|------|-------|-------|--------|")
            for e in w["effects"]:
                title = nodes.get(e["node"], {}).get("title", "?")
                cross = " [cross-dir]" if e.get("cross_directory") else ""
                print(f"| {e['node']} | {title} | {e['current_state']} | {e['reason']}{cross} |")
            print()
        return 0

    # Default table output
    if not waves:
        print(f"No upstream dependencies for {start_node}.")
        return 0

    for w in waves:
        print(f"\n=== Wave {w['wave']} ===")
        print(f"{'Node':<12} {'State':<14} Reason")
        print("-" * 60)
        for e in w["effects"]:
            cross = " [cross-dir]" if e.get("cross_directory") else ""
            print(f"{e['node']:<12} {e['current_state']:<14} {e['reason']}{cross}")

    print(f"\nTotal: {unique} upstream decisions across {len(waves)} wave(s).")
    return 0


def cmd_index(nodes):
    """Regenerate INDEX.md per directory."""
    constitution_nodes = {nid: n for nid, n in nodes.items() if n.get("_scope") == "constitution"}
    project_nodes = {nid: n for nid, n in nodes.items() if n.get("_scope") != "constitution"}

    def write_index(node_subset, target_dir, title):
        lines = [f"# {title}", "",
                 "Derived index. Regenerate via `dna-graph index`. Do not edit directly.", ""]

        lines.append(f"**Total:** {len(node_subset)} decisions")
        lines.append("")
        lines.append("| ID | Title | Level | State | Stakes | Depends On |")
        lines.append("|----|-------|-------|-------|--------|------------|")

        for nid in sorted(node_subset.keys()):
            n = node_subset[nid]
            deps = ", ".join(get_deps_list(n)) or "—"
            title = (n.get('title', '') or '').replace('|', '\\|')
            lines.append(f"| {nid} | {title} | {n.get('level', '')} | {n.get('state', '')} | {n.get('stakes', '')} | {deps} |")

        lines.append("")
        path = os.path.join(target_dir, "INDEX.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    if os.path.isdir(CONSTITUTION_DIR) and constitution_nodes:
        write_index(constitution_nodes, CONSTITUTION_DIR, "Constitution Index")
        print(f"constitution/INDEX.md: {len(constitution_nodes)} decisions")

    write_index(project_nodes, DNA_DIR, "DNA Index")
    print(f"dna/INDEX.md: {len(project_nodes)} decisions")
    return 0


def _read_manual_flags():
    """Read ## Manual Flags section from existing HEALTH.md."""
    if not os.path.exists(HEALTH_FILE):
        return ""
    with open(HEALTH_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'^## Manual Flags\s*\n(.*?)(?=^## |\Z)', content, re.MULTILINE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def cmd_health(nodes):
    """Generate HEALTH.md from current state."""
    constitution_nodes = {nid: n for nid, n in nodes.items() if n.get("_scope") == "constitution"}
    project_nodes = {nid: n for nid, n in nodes.items() if n.get("_scope") != "constitution"}

    # State counts
    def state_summary(node_dict):
        states = defaultdict(list)
        for nid, n in node_dict.items():
            states[n.get("state", "unknown")].append(nid)
        parts = []
        for s in sorted(states.keys()):
            count = len(states[s])
            if count == len(node_dict):
                parts.append(f"all `{s}`")
            else:
                parts.append(f"{count} `{s}`")
        return ", ".join(parts) if parts else "—"

    # Level counts
    def level_summary(node_dict):
        levels = defaultdict(int)
        for nid, n in node_dict.items():
            levels[n.get("level", "?")] += 1
        parts = [f"L{l}: {c}" for l, c in sorted(levels.items())]
        return ", ".join(parts)

    lines = ["# System Health", "",
             f"Last updated: {date.today().isoformat()}", "",
             "## Node Counts", ""]

    if constitution_nodes:
        lines.append("### Constitution")
        lines.append(f"- Decisions: {len(constitution_nodes)} — {state_summary(constitution_nodes)}")
        lines.append(f"- Levels: {level_summary(constitution_nodes)}")
        lines.append("")

    lines.append("### DNA" if constitution_nodes else "")
    lines.append(f"- Decisions: {len(project_nodes)} — {state_summary(project_nodes)}")
    lines.append(f"- Levels: {level_summary(project_nodes)}")
    lines.append(f"- **Total: {len(nodes)} decisions**")
    lines.append("")

    # Flagged items
    flagged = []
    for state in ("suggested", "superseded"):
        ids = [nid for nid, n in nodes.items() if n.get("state") == state]
        if ids:
            flagged.append(f"{len(ids)} decisions at `{state}` ({', '.join(sorted(ids))})")

    errors, warnings = cmd_validate(nodes)
    if errors:
        flagged.append(f"{len(errors)} validation error(s) — run `dna-graph validate` for details")

    lines.append("## Flagged Items")
    lines.append("")
    if flagged:
        for item in flagged:
            lines.append(f"- {item}")
    else:
        lines.append("- No issues found.")
    lines.append("")

    manual_flags = _read_manual_flags()
    if manual_flags:
        lines.append("## Manual Flags")
        lines.append("")
        lines.append(manual_flags)
        lines.append("")

    lines.append("## Last Session")
    lines.append("")
    lines.append(f"{date.today().isoformat()} — Health regenerated by dna-graph")
    lines.append("")

    with open(HEALTH_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"HEALTH.md updated: {len(nodes)} decisions, {len(flagged)} flagged items")
    return 0


# ---------------------------------------------------------------------------
# Search subcommand
# ---------------------------------------------------------------------------

BODY_SECTIONS = ("Decision", "Reasoning", "Assumptions", "Tradeoffs", "Detail")


def cmd_search(args):
    """Search decisions by title and body content.

    Usage: dna-graph search TERM [TERM ...] [--json]
    Case-insensitive. Multiple terms are OR-matched.
    Returns: id, title, level, state, scope, matched_sections.
    """
    json_output = "--json" in args
    terms = [a.lower() for a in args if a != "--json"]

    if not terms:
        print("Usage: dna-graph search TERM [TERM ...] [--json]", file=sys.stderr)
        return 1

    nodes = load_graph()
    results = []

    for nid in sorted(nodes.keys()):
        n = nodes[nid]
        title = (n.get("title") or "").lower()
        body = (n.get("_body") or "")
        body_lower = body.lower()

        # Check if any term matches title or body
        matched = False
        for term in terms:
            if term in title or term in body_lower:
                matched = True
                break

        if not matched:
            continue

        # Determine which body sections matched
        matched_sections = []
        # Check title separately
        for term in terms:
            if term in title:
                matched_sections.append("title")
                break

        # Parse body into sections and check each
        for section_name in BODY_SECTIONS:
            pattern = rf'^## {section_name}\s*$(.*?)(?=^## |\Z)'
            m = re.search(pattern, body, re.MULTILINE | re.DOTALL)
            if m:
                section_text = m.group(1).lower()
                for term in terms:
                    if term in section_text:
                        matched_sections.append(section_name)
                        break

        results.append({
            "id": nid,
            "title": n.get("title", ""),
            "level": n.get("level"),
            "state": n.get("state", "unknown"),
            "scope": n.get("_scope", "project"),
            "matched_sections": matched_sections,
        })

    if json_output:
        print(json.dumps({"query": terms, "count": len(results), "results": results}, indent=2))
        return 0

    if not results:
        print(f"No decisions match: {' '.join(terms)}")
        return 0

    print(f"Found {len(results)} decision(s) matching: {' '.join(terms)}")
    print()
    print(f"{'ID':<12} {'Level':<7} {'State':<12} {'Sections':<30} Title")
    print("-" * 90)
    for r in results:
        sections = ", ".join(r["matched_sections"]) if r["matched_sections"] else "—"
        print(f"{r['id']:<12} L{r['level']:<6} {r['state']:<12} {sections:<30} {r['title']}")

    return 0


# ---------------------------------------------------------------------------
# Frontier subcommand
# ---------------------------------------------------------------------------


def cmd_frontier(args):
    """Compute the decision frontier — what to think about next.

    Usage: dna-graph frontier [--json] [--markdown] [--top N]

    Sections:
    1. Committable Now — suggested with all upstream committed
    2. Blocked — suggested with uncommitted upstream + critical path
    3. Level Gaps — per-level state breakdown
    4. High-Weight Nodes — most transitive downstream dependents
    """
    json_output = "--json" in args
    markdown_output = "--markdown" in args
    top_n = 10

    i = 0
    while i < len(args):
        if args[i] == "--top" and i + 1 < len(args):
            try:
                top_n = int(args[i + 1])
            except ValueError:
                print(f"Error: --top must be a number, got '{args[i + 1]}'", file=sys.stderr)
                return 1
            i += 2
        else:
            i += 1

    nodes = load_graph()
    downstream = _compute_transitive_downstream(nodes)

    # Partition suggested decisions (exclude superseded)
    committable_now = []
    blocked = []

    for nid in sorted(nodes.keys()):
        n = nodes[nid]
        state = n.get("state", "unknown")
        if state != "suggested":
            continue

        deps = get_deps_list(n)
        uncommitted_deps = [
            d for d in deps
            if d in nodes and nodes[d].get("state") != "committed"
        ]

        entry = {
            "id": nid,
            "title": n.get("title", ""),
            "level": n.get("level"),
            "stakes": n.get("stakes"),
            "scope": n.get("_scope", "project"),
            "downstream_weight": len(downstream.get(nid, set())),
            "downstream_ids": sorted(downstream.get(nid, set())),
        }

        if not uncommitted_deps:
            committable_now.append(entry)
        else:
            entry["blockers"] = uncommitted_deps
            entry["critical_path"] = _critical_path(nodes, nid)
            entry["critical_path_length"] = len(entry["critical_path"])
            blocked.append(entry)

    # Sort
    committable_now.sort(key=lambda x: (-x["downstream_weight"], x.get("level") or 99))
    blocked.sort(key=lambda x: (x["critical_path_length"], -x["downstream_weight"]))

    # Level gaps
    level_gaps = []
    for lvl in (1, 2, 3, 4):
        committed = 0
        suggested = 0
        superseded = 0
        for n in nodes.values():
            if n.get("level") != lvl:
                continue
            s = n.get("state", "unknown")
            if s == "committed":
                committed += 1
            elif s == "suggested":
                suggested += 1
            elif s == "superseded":
                superseded += 1
        total = committed + suggested + superseded
        flags = []
        if suggested > committed:
            flags.append("more suggested than committed")
        if committed == 0 and total > 0:
            flags.append("no committed decisions")
        level_gaps.append({
            "level": lvl,
            "level_name": LEVEL_NAMES[lvl],
            "committed": committed,
            "suggested": suggested,
            "superseded": superseded,
            "total": total,
            "flags": flags,
        })

    # High-weight nodes
    high_weight = []
    for nid, n in nodes.items():
        dw = len(downstream.get(nid, set()))
        high_weight.append({
            "id": nid,
            "title": n.get("title", ""),
            "level": n.get("level"),
            "state": n.get("state", "unknown"),
            "stakes": n.get("stakes"),
            "scope": n.get("_scope", "project"),
            "downstream_weight": dw,
            "direct_dependents": sorted(get_dependents(nodes, nid)),
        })
    high_weight.sort(key=lambda x: -x["downstream_weight"])
    high_weight = high_weight[:top_n]

    # Summary
    flagged_levels = sum(1 for lg in level_gaps if lg["flags"])
    summary = {
        "total_decisions": len(nodes),
        "suggested": sum(1 for n in nodes.values() if n.get("state") == "suggested"),
        "committable_count": len(committable_now),
        "blocked_count": len(blocked),
        "level_gap_count": flagged_levels,
    }

    # --- JSON output ---
    if json_output:
        output = {
            "frontier": {
                "committable_now": committable_now,
                "blocked": blocked,
                "level_gaps": level_gaps,
                "high_weight": high_weight,
            },
            "summary": summary,
        }
        print(json.dumps(output, indent=2))
        return 0

    # --- Markdown output ---
    if markdown_output:
        print("# Decision Frontier")
        print()
        print(f"**{summary['total_decisions']} decisions** — "
              f"{summary['suggested']} suggested, "
              f"{summary['committable_count']} committable, "
              f"{summary['blocked_count']} blocked")
        print()

        print("## Committable Now")
        print()
        if committable_now:
            print("| ID | Title | Level | Stakes | Downstream |")
            print("|----|-------|-------|--------|------------|")
            for c in committable_now:
                stakes = c["stakes"] or "—"
                print(f"| {c['id']} | {c['title']} | L{c['level']} | {stakes} | {c['downstream_weight']} |")
        else:
            print("None — all suggested decisions have uncommitted upstream.")
        print()

        print("## Blocked")
        print()
        if blocked:
            print("| ID | Title | Level | Blockers | Critical Path |")
            print("|----|-------|-------|----------|---------------|")
            for b in blocked:
                blockers = ", ".join(b["blockers"])
                cp = " → ".join(b["critical_path"]) + f" → {b['id']}" if b["critical_path"] else "—"
                print(f"| {b['id']} | {b['title']} | L{b['level']} | {blockers} | {cp} |")
        else:
            print("None — all suggested decisions are committable.")
        print()

        print("## Level Gaps")
        print()
        print("| Level | Name | Committed | Suggested | Flags |")
        print("|-------|------|-----------|-----------|-------|")
        for lg in level_gaps:
            flags = ", ".join(lg["flags"]) if lg["flags"] else "—"
            print(f"| L{lg['level']} | {lg['level_name']} | {lg['committed']} | {lg['suggested']} | {flags} |")
        print()

        print(f"## High-Weight Nodes (top {top_n})")
        print()
        print("| ID | Title | Level | State | Downstream |")
        print("|----|-------|-------|-------|------------|")
        for hw in high_weight:
            print(f"| {hw['id']} | {hw['title']} | L{hw['level']} | {hw['state']} | {hw['downstream_weight']} |")

        return 0

    # --- Default table output ---
    print(f"Decision Frontier — {summary['total_decisions']} decisions, "
          f"{summary['suggested']} suggested, "
          f"{summary['committable_count']} committable, "
          f"{summary['blocked_count']} blocked")

    print(f"\n=== Committable Now ({len(committable_now)}) ===")
    if committable_now:
        print(f"{'ID':<12} {'Level':<7} {'Stakes':<8} {'Weight':<8} Title")
        print("-" * 70)
        for c in committable_now:
            stakes = c["stakes"] or "—"
            print(f"{c['id']:<12} L{c['level']:<6} {stakes:<8} {c['downstream_weight']:<8} {c['title']}")
    else:
        print("  None — all suggested decisions have uncommitted upstream.")

    print(f"\n=== Blocked ({len(blocked)}) ===")
    if blocked:
        print(f"{'ID':<12} {'Level':<7} {'Path Len':<10} {'Blockers':<25} Critical Path")
        print("-" * 90)
        for b in blocked:
            blockers = ", ".join(b["blockers"])
            cp = " → ".join(b["critical_path"]) + f" → {b['id']}" if b["critical_path"] else "—"
            print(f"{b['id']:<12} L{b['level']:<6} {b['critical_path_length']:<10} {blockers:<25} {cp}")
    else:
        print("  None — all suggested decisions are committable.")

    print(f"\n=== Level Gaps ===")
    print(f"{'Level':<8} {'Name':<12} {'Committed':<11} {'Suggested':<11} Flags")
    print("-" * 60)
    for lg in level_gaps:
        flags = ", ".join(lg["flags"]) if lg["flags"] else "—"
        print(f"L{lg['level']:<7} {lg['level_name']:<12} {lg['committed']:<11} {lg['suggested']:<11} {flags}")

    print(f"\n=== High-Weight Nodes (top {top_n}) ===")
    if high_weight:
        print(f"{'ID':<12} {'Level':<7} {'State':<12} {'Weight':<8} Title")
        print("-" * 70)
        for hw in high_weight:
            print(f"{hw['id']:<12} L{hw['level']:<6} {hw['state']:<12} {hw['downstream_weight']:<8} {hw['title']}")

    return 0


# ---------------------------------------------------------------------------
# Write subcommands
# ---------------------------------------------------------------------------

LEVEL_NAMES = {1: "Identity", 2: "Direction", 3: "Strategy", 4: "Tactics"}

SCAFFOLD_BODY = """\

## Decision



## Reasoning



## Assumptions



## Tradeoffs

"""


def cmd_create(args):
    """Create a new decision with pre-validated frontmatter.

    Usage: dna-graph create DEC-NNN --title "..." --level N
               [--state suggested] [--stakes medium]
               [--depends-on DEC-001,DEC-003] [--constitution]
    """
    if len(args) < 1:
        print("Usage: dna-graph create DEC-NNN --title \"...\" --level N "
              "[--state suggested] [--stakes medium] "
              "[--depends-on DEC-001,DEC-003] [--constitution]", file=sys.stderr)
        return 1

    nid = args[0]
    # Parse flags
    title = None
    level = None
    state = "suggested"
    stakes = None
    depends_on = []
    constitution = False

    i = 1
    while i < len(args):
        flag = args[i]
        if flag == "--title" and i + 1 < len(args):
            i += 1
            title = args[i]
        elif flag == "--level" and i + 1 < len(args):
            i += 1
            try:
                level = int(args[i])
            except ValueError:
                print(f"Error: --level must be a number, got '{args[i]}'", file=sys.stderr)
                return 1
        elif flag == "--state" and i + 1 < len(args):
            i += 1
            state = args[i]
        elif flag == "--stakes" and i + 1 < len(args):
            i += 1
            stakes = args[i]
        elif flag == "--depends-on" and i + 1 < len(args):
            i += 1
            depends_on = [d.strip() for d in args[i].split(",") if d.strip()]
        elif flag == "--constitution":
            constitution = True
        else:
            print(f"Error: unknown flag '{flag}'", file=sys.stderr)
            return 1
        i += 1

    # Required fields
    if not title:
        print("Error: --title is required", file=sys.stderr)
        return 1
    if level is None:
        print("Error: --level is required", file=sys.stderr)
        return 1

    # Build frontmatter
    fm = {
        "id": nid,
        "title": title,
        "date": date.today().isoformat(),
        "level": level,
        "state": state,
        "stakes": stakes,
        "depends_on": depends_on,
    }

    target_dir = CONSTITUTION_DIR if constitution else DNA_DIR

    # Load graph and validate
    nodes = load_graph()
    errors, warnings = validate_for_create(nid, fm, nodes, target_dir)

    if warnings:
        for w in warnings:
            print(f"WARNING: {w}", file=sys.stderr)

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Serialize and write
    content = serialize_decision(fm, SCAFFOLD_BODY)
    filepath = os.path.join(target_dir, f"{nid}.md")

    os.makedirs(target_dir, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    scope = "constitution" if constitution else "dna"
    print(f"Created {nid} (level {level}, {state}) in {scope}/")
    return 0


def cmd_set(args):
    """Update a single frontmatter field with pre-validation.

    Usage: dna-graph set DEC-NNN field value
           dna-graph set DEC-NNN depends_on DEC-001,DEC-003
           dna-graph set DEC-NNN depends_on []
           dna-graph set DEC-NNN title New Title Here
    """
    if len(args) < 3:
        print("Usage: dna-graph set DEC-NNN field value", file=sys.stderr)
        return 1

    nid = args[0]
    field = args[1]

    # Load graph
    nodes = load_graph()
    if nid not in nodes:
        print(f"Error: {nid} not found in graph", file=sys.stderr)
        return 1

    node = nodes[nid]
    filepath = node["_filepath"]

    # Parse value based on field type
    if field == "depends_on":
        raw = args[2]
        if raw in ("[]", ""):
            value = []
        else:
            value = [d.strip() for d in raw.split(",") if d.strip()]
    elif field == "level":
        try:
            value = int(args[2])
        except ValueError:
            print(f"Error: level must be a number, got '{args[2]}'", file=sys.stderr)
            return 1
    elif field == "title":
        # Title can be multiple words
        value = " ".join(args[2:])
    else:
        value = args[2]

    # Validate
    errors, warnings = validate_for_set(nid, field, value, nodes)

    if warnings:
        for w in warnings:
            print(f"WARNING: {w}", file=sys.stderr)

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Read current file to preserve body
    fm, body = parse_frontmatter(filepath)
    if fm is None:
        print(f"Error: could not parse frontmatter from {filepath}", file=sys.stderr)
        return 1

    # Record old value for display
    old_value = fm.get(field, None)

    # Update the field
    fm[field] = value

    # Serialize and write atomically
    content = serialize_decision(fm, body)
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.rename(tmp_path, filepath)

    # Display change
    if field == "depends_on":
        old_display = ", ".join(old_value) if old_value else "[]"
        new_display = ", ".join(value) if value else "[]"
    else:
        old_display = old_value
        new_display = value
    print(f"{nid}: {field} {old_display} → {new_display}")
    return 0


def cmd_edit(args):
    """Replace body text in a decision with pre/post validation delta.

    Usage: dna-graph edit DEC-NNN "old text" "new text"

    Only modifies body content (below the frontmatter). Frontmatter is never
    touched. Runs validate before and after, reporting any NEW warnings
    introduced by the edit.
    """
    if len(args) < 3:
        print('Usage: dna-graph edit DEC-NNN "old text" "new text"', file=sys.stderr)
        return 1

    nid = args[0]
    old_text = args[1]
    new_text = args[2]

    # Load graph and pre-validate
    nodes = load_graph()
    if nid not in nodes:
        print(f"Error: {nid} not found in graph", file=sys.stderr)
        return 1

    node = nodes[nid]
    filepath = node["_filepath"]

    # Read current file
    fm, body = parse_frontmatter(filepath)
    if fm is None:
        print(f"Error: could not parse frontmatter from {filepath}", file=sys.stderr)
        return 1

    # Verify old_text exists in body (not frontmatter)
    if old_text not in body:
        print(f"Error: old text not found in body of {nid}", file=sys.stderr)
        return 1

    # Count occurrences — must be unique
    if body.count(old_text) > 1:
        print(f"Error: old text matches {body.count(old_text)} locations in {nid} body — must be unique", file=sys.stderr)
        return 1

    # Snapshot pre-edit warnings
    pre_errors, pre_warnings = cmd_validate(nodes)
    pre_warning_set = set(pre_warnings)

    # Apply the edit (body only — frontmatter untouched)
    new_body = body.replace(old_text, new_text, 1)

    # Serialize with original frontmatter + new body
    content = serialize_decision(fm, new_body)
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.rename(tmp_path, filepath)

    # Post-edit validation
    nodes_after = load_graph()
    post_errors, post_warnings = cmd_validate(nodes_after)
    post_warning_set = set(post_warnings)

    # Delta
    new_warnings = sorted(post_warning_set - pre_warning_set)
    resolved_warnings = sorted(pre_warning_set - post_warning_set)
    new_errors = sorted(set(post_errors) - set(pre_errors))

    # Report
    chars_removed = len(old_text)
    chars_added = len(new_text)
    print(f"{nid}: body edited ({chars_removed} chars → {chars_added} chars)")

    if resolved_warnings:
        print(f"  Resolved {len(resolved_warnings)} warning(s):")
        for w in resolved_warnings:
            print(f"    - {w}")

    if new_warnings:
        print(f"  Introduced {len(new_warnings)} new warning(s):")
        for w in new_warnings:
            print(f"    + {w}")

    if new_errors:
        print(f"  INTRODUCED {len(new_errors)} new ERROR(s):")
        for e in new_errors:
            print(f"    ! {e}")
        return 1

    if not new_warnings and not new_errors:
        print("  No new issues introduced.")

    return 0


def cmd_compile_manifest(args):
    """Produce deterministic skeleton for contract compilation.

    Usage: dna-graph compile-manifest [--target human|agent] [--json]
    """
    target = None
    json_output = False

    i = 0
    while i < len(args):
        if args[i] == "--target" and i + 1 < len(args):
            i += 1
            target = args[i]
            if target not in ("human", "agent"):
                print(f"Error: --target must be 'human' or 'agent', got '{target}'", file=sys.stderr)
                return 1
        elif args[i] == "--json":
            json_output = True
        i += 1

    nodes = load_graph()

    # Counts
    by_level = defaultdict(int)
    by_state = defaultdict(int)
    for n in nodes.values():
        by_level[n.get("level", "?")] += 1
        by_state[n.get("state", "unknown")] += 1

    counts = {
        "total": len(nodes),
        "committed": by_state.get("committed", 0),
        "suggested": by_state.get("suggested", 0),
        "superseded": by_state.get("superseded", 0),
        "by_level": {str(k): v for k, v in sorted(by_level.items())},
    }

    targets = [target] if target else ["human", "agent"]

    for t in targets:
        if t == "human":
            _compile_manifest_human(nodes, counts, json_output)
        elif t == "agent":
            _compile_manifest_agent(nodes, counts, json_output)

    return 0


def _node_summary(node):
    """Compact summary dict for manifest output."""
    return {
        "id": node.get("id"),
        "title": node.get("title", ""),
        "level": node.get("level"),
        "state": node.get("state", "unknown"),
        "stakes": node.get("stakes"),
    }


def _compile_manifest_human(nodes, counts, json_output):
    """Human contract manifest: decisions grouped by level."""
    levels = {}
    for lvl in (1, 2, 3, 4):
        committed = []
        suggested = []
        for nid in sorted(nodes.keys()):
            n = nodes[nid]
            if n.get("level") != lvl:
                continue
            summary = _node_summary(n)
            if n.get("state") == "committed":
                committed.append(summary)
            elif n.get("state") == "suggested":
                suggested.append(summary)
        entry = {"name": LEVEL_NAMES[lvl], "committed": committed}
        if suggested:
            entry["suggested"] = suggested
        levels[str(lvl)] = entry

    manifest = {"target": "human", "levels": levels, "counts": counts}

    if json_output:
        print(json.dumps(manifest, indent=2))
    else:
        print("# Compile Manifest — Human Contract")
        print()
        for lvl in ("1", "2", "3", "4"):
            entry = levels[lvl]
            print(f"## {entry['name']} (Level {lvl})")
            print()
            if entry["committed"]:
                for d in entry["committed"]:
                    stakes_tag = f" [{d['stakes']}]" if d.get("stakes") else ""
                    print(f"  - {d['id']}: {d['title']}{stakes_tag}")
            if entry.get("suggested"):
                print(f"  Suggested:")
                for d in entry["suggested"]:
                    stakes_tag = f" [{d['stakes']}]" if d.get("stakes") else ""
                    print(f"  - {d['id']}: {d['title']}{stakes_tag}")
            print()
        print(f"Total: {counts['total']} decisions "
              f"({counts['committed']} committed, {counts['suggested']} suggested)")


def _compile_manifest_agent(nodes, counts, json_output):
    """Agent contract manifest: classified lists by stakes and state."""
    constitution = []
    high_stakes = []
    all_committed = []
    all_suggested = []

    for nid in sorted(nodes.keys()):
        n = nodes[nid]
        summary = _node_summary(n)

        if n.get("_scope") == "constitution":
            constitution.append(summary)

        if n.get("stakes") == "high":
            high_stakes.append(summary)

        if n.get("state") == "committed":
            all_committed.append(summary)
        elif n.get("state") == "suggested":
            all_suggested.append(summary)

    manifest = {
        "target": "agent",
        "constitution": constitution,
        "high_stakes": high_stakes,
        "all_committed": all_committed,
        "all_suggested": all_suggested,
        "counts": counts,
    }

    if json_output:
        print(json.dumps(manifest, indent=2))
    else:
        print("# Compile Manifest — Agent Contract")
        print()
        print(f"## Constitution ({len(constitution)} decisions)")
        for d in constitution:
            print(f"  - {d['id']}: {d['title']} [{d['state']}]")
        print()
        print(f"## High Stakes ({len(high_stakes)} decisions)")
        for d in high_stakes:
            print(f"  - {d['id']}: {d['title']} [{d['state']}]")
        print()
        print(f"## All Committed ({len(all_committed)} decisions)")
        for d in all_committed:
            stakes_tag = f" [{d['stakes']}]" if d.get("stakes") else ""
            print(f"  - {d['id']}: {d['title']}{stakes_tag}")
        print()
        if all_suggested:
            print(f"## All Suggested ({len(all_suggested)} decisions)")
            for d in all_suggested:
                stakes_tag = f" [{d['stakes']}]" if d.get("stakes") else ""
                print(f"  - {d['id']}: {d['title']}{stakes_tag}")
            print()
        print(f"Total: {counts['total']} decisions "
              f"({counts['committed']} committed, {counts['suggested']} suggested)")


# ---------------------------------------------------------------------------
# Scratchpad subcommands
# ---------------------------------------------------------------------------

def cmd_scratchpad(args):
    """Dispatcher for scratchpad add/list/mature subcommands."""
    if not args:
        print("Usage: dna-graph scratchpad {add|list|mature} ...", file=sys.stderr)
        return 1

    sub = args[0]
    if sub == "add":
        return _sp_add(args[1:])
    elif sub == "list":
        return _sp_list(args[1:])
    elif sub == "mature":
        return _sp_mature(args[1:])
    else:
        print(f"Unknown scratchpad subcommand: {sub}", file=sys.stderr)
        print("Usage: dna-graph scratchpad {add|list|mature} ...", file=sys.stderr)
        return 1


def _sp_add(args):
    """Add a scratchpad entry.

    Usage: dna-graph scratchpad add --type TYPE "content" [--links DEC-NNN,DEC-NNN]
    """
    sp_type = None
    links = []
    content = None

    i = 0
    while i < len(args):
        if args[i] == "--type" and i + 1 < len(args):
            i += 1
            sp_type = args[i]
        elif args[i] == "--links" and i + 1 < len(args):
            i += 1
            links = [l.strip() for l in args[i].split(",") if l.strip()]
        elif not args[i].startswith("--"):
            content = args[i]
        else:
            print(f"Error: unknown flag '{args[i]}'", file=sys.stderr)
            return 1
        i += 1

    if not sp_type:
        print("Error: --type is required", file=sys.stderr)
        return 1
    if sp_type not in VALID_SP_TYPES:
        print(f"Error: invalid type '{sp_type}' (must be one of: {', '.join(sorted(VALID_SP_TYPES))})", file=sys.stderr)
        return 1
    if not content:
        print("Error: content string is required", file=sys.stderr)
        return 1

    # Validate links exist in graph
    if links:
        nodes = load_graph()
        for link in links:
            if link not in nodes:
                print(f"Error: linked decision {link} not found in graph", file=sys.stderr)
                return 1

    entries = _load_scratchpad()
    sp_id = _next_sp_id(entries)

    entry = {
        "id": sp_id,
        "type": sp_type,
        "content": content,
        "created": date.today().isoformat(),
        "links": links,
        "matured_to": None,
    }
    entries.append(entry)
    _save_scratchpad(entries)

    link_display = f" (links: {', '.join(links)})" if links else ""
    print(f"Added {sp_id} [{sp_type}]: {content}{link_display}")
    return 0


def _sp_list(args):
    """List scratchpad entries.

    Usage: dna-graph scratchpad list [--type TYPE] [--json]
    """
    filter_type = None
    json_output = False

    i = 0
    while i < len(args):
        if args[i] == "--type" and i + 1 < len(args):
            i += 1
            filter_type = args[i]
        elif args[i] == "--json":
            json_output = True
        i += 1

    entries = _load_scratchpad()

    active = [e for e in entries if not e.get("matured_to")]
    matured = [e for e in entries if e.get("matured_to")]

    if filter_type:
        active = [e for e in active if e.get("type") == filter_type]
        matured = [e for e in matured if e.get("type") == filter_type]

    if json_output:
        print(json.dumps({"active": active, "matured": matured}, indent=2))
        return 0

    # Human-readable table
    if not active and not matured:
        print("Scratchpad is empty.")
        return 0

    if active:
        print(f"Active ({len(active)}):")
        print(f"{'ID':<10} {'Type':<12} {'Created':<12} Content")
        print("-" * 70)
        for e in active:
            links = f" → {', '.join(e['links'])}" if e.get("links") else ""
            print(f"{e['id']:<10} {e['type']:<12} {e['created']:<12} {e['content']}{links}")

    if matured:
        print(f"\nMatured ({len(matured)}):")
        for e in matured:
            print(f"  {e['id']} [{e['type']}] → {e['matured_to']}")

    return 0


def _sp_mature(args):
    """Graduate a scratchpad entry to a decision.

    Usage: dna-graph scratchpad mature SP-NNN DEC-NNN
    """
    if len(args) < 2:
        print("Usage: dna-graph scratchpad mature SP-NNN DEC-NNN", file=sys.stderr)
        return 1

    sp_id = args[0]
    dec_id = args[1]

    entries = _load_scratchpad()
    entry = None
    for e in entries:
        if e.get("id") == sp_id:
            entry = e
            break

    if not entry:
        print(f"Error: {sp_id} not found in scratchpad", file=sys.stderr)
        return 1

    if entry.get("matured_to"):
        print(f"Error: {sp_id} already matured to {entry['matured_to']}", file=sys.stderr)
        return 1

    # Validate decision exists
    nodes = load_graph()
    if dec_id not in nodes:
        print(f"Error: {dec_id} not found in graph", file=sys.stderr)
        return 1

    entry["matured_to"] = dec_id
    _save_scratchpad(entries)

    print(f"Matured {sp_id} [{entry['type']}] → {dec_id}")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    cmd = sys.argv[1]

    if cmd == "validate":
        nodes = load_graph()
        errors, warnings = cmd_validate(nodes)
        if errors:
            print(f"ERRORS ({len(errors)}):")
            for e in sorted(errors):
                print(f"  {e}")
        if warnings:
            print(f"\nWARNINGS ({len(warnings)}):")
            for w in sorted(warnings):
                print(f"  {w}")
        if not errors and not warnings:
            print(f"Validation passed: {len(nodes)} decisions, 0 errors, 0 warnings.")
        return 1 if errors else 0

    elif cmd == "cascade":
        if len(sys.argv) < 3:
            print("Usage: dna-graph cascade NODE-ID [--json|--markdown] [--reverse]", file=sys.stderr)
            return 1
        nodes = load_graph()
        json_flag = "--json" in sys.argv[3:]
        md_flag = "--markdown" in sys.argv[3:]
        reverse_flag = "--reverse" in sys.argv[3:]
        if reverse_flag:
            return cmd_cascade_reverse(nodes, sys.argv[2], json_output=json_flag, markdown_output=md_flag)
        return cmd_cascade(nodes, sys.argv[2], json_output=json_flag, markdown_output=md_flag)

    elif cmd == "index":
        nodes = load_graph()
        return cmd_index(nodes)

    elif cmd == "health":
        nodes = load_graph()
        return cmd_health(nodes)

    elif cmd == "search":
        return cmd_search(sys.argv[2:])

    elif cmd == "frontier":
        return cmd_frontier(sys.argv[2:])

    elif cmd == "create":
        return cmd_create(sys.argv[2:])

    elif cmd == "set":
        return cmd_set(sys.argv[2:])

    elif cmd == "edit":
        return cmd_edit(sys.argv[2:])

    elif cmd == "compile-manifest":
        return cmd_compile_manifest(sys.argv[2:])

    elif cmd == "scratchpad":
        return cmd_scratchpad(sys.argv[2:])

    elif cmd == "scratchpad-summary":
        entries = _load_scratchpad()
        summary = _scratchpad_summary(entries)
        if summary:
            print(f"Scratchpad: {summary}")
        return 0

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
