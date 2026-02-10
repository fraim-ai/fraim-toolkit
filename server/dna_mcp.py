# /// script
# requires-python = ">=3.10"
# dependencies = ["fastmcp"]
# ///
"""MCP server wrapping dna-graph.py as native Claude Code tools.

Launched via: uv run --python 3.12 server/dna_mcp.py
Transport: stdio (JSON-RPC over stdin/stdout)
"""

import logging
import os
import subprocess
import sys

from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL_PATH = os.path.join(PLUGIN_ROOT, "tools", "dna-graph.py")
_raw_project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
PROJECT_DIR = _raw_project_dir if _raw_project_dir and not _raw_project_dir.startswith("$") else os.getcwd()

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
log = logging.getLogger("dna-mcp")

mcp = FastMCP("dna")

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _run(*args: str) -> str:
    """Run dna-graph.py with given arguments, return stdout or error string."""
    cmd = [sys.executable, TOOL_PATH] + list(args)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": PROJECT_DIR}
    log.info("Running: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        output = result.stdout
        if result.returncode != 0:
            err = result.stderr.strip()
            if err:
                output = f"{output}\nERROR: {err}" if output else f"ERROR: {err}"
        return output.strip() if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 30s"
    except Exception as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


@mcp.tool()
def dna_validate() -> str:
    """Validate all decisions — check frontmatter, graph topology, and body content. Returns errors and warnings."""
    return _run("validate")


@mcp.tool()
def dna_cascade(node_id: str, reverse: bool = False) -> str:
    """Compute propagation cascade from a decision. Returns JSON with waves of affected nodes.

    Args:
        node_id: Decision ID (e.g. DEC-005)
        reverse: If True, show upstream dependencies instead of downstream dependents
    """
    args = ["cascade", node_id, "--json"]
    if reverse:
        args.append("--reverse")
    return _run(*args)


@mcp.tool()
def dna_health() -> str:
    """Regenerate HEALTH.md and return a summary of system health."""
    return _run("health")


@mcp.tool()
def dna_index() -> str:
    """Regenerate INDEX.md for each decision directory."""
    return _run("index")


@mcp.tool()
def dna_compile_manifest(target: str = "") -> str:
    """Produce deterministic skeleton for contract compilation.

    Args:
        target: 'human', 'agent', or empty for both
    """
    args = ["compile-manifest", "--json"]
    if target:
        args.extend(["--target", target])
    return _run(*args)


@mcp.tool()
def dna_search(query: str) -> str:
    """Search decisions by title and body content. Returns matches with matched sections.

    Args:
        query: Space-separated search terms (OR-matched, case-insensitive)
    """
    args = ["search"] + query.split() + ["--json"]
    return _run(*args)


@mcp.tool()
def dna_frontier(top: int = 10) -> str:
    """Compute the decision frontier — what to think about next. Returns JSON with
    committable decisions, blocked decisions with critical paths, level gaps, and
    high-weight nodes.

    Args:
        top: Number of high-weight nodes to include (default 10)
    """
    args = ["frontier", "--json"]
    if top != 10:
        args.extend(["--top", str(top)])
    return _run(*args)


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------


@mcp.tool()
def dna_create(
    id: str,
    title: str,
    level: int,
    state: str = "suggested",
    stakes: str = "",
    depends_on: str = "",
    constitution: bool = False,
) -> str:
    """Create a new decision with pre-validated frontmatter.

    Args:
        id: Decision ID (e.g. DEC-057)
        title: Short descriptive title
        level: Hierarchy level (1=Identity, 2=Direction, 3=Strategy, 4=Tactics)
        state: Initial state (default: suggested)
        stakes: high, medium, or low (optional)
        depends_on: Comma-separated dependency IDs (e.g. "DEC-001,DEC-003")
        constitution: If True, create in constitution/ instead of dna/
    """
    args = ["create", id, "--title", title, "--level", str(level)]
    if state != "suggested":
        args.extend(["--state", state])
    if stakes:
        args.extend(["--stakes", stakes])
    if depends_on:
        args.extend(["--depends-on", depends_on])
    if constitution:
        args.append("--constitution")
    return _run(*args)


@mcp.tool()
def dna_set(id: str, field: str, value: str) -> str:
    """Update a single frontmatter field on an existing decision.

    Args:
        id: Decision ID (e.g. DEC-005)
        field: Field to update (state, depends_on, level, stakes, title)
        value: New value (for depends_on: comma-separated IDs or '[]')
    """
    return _run("set", id, field, value)


@mcp.tool()
def dna_edit(id: str, old_text: str, new_text: str) -> str:
    """Replace body text in a decision with pre/post validation delta.

    Args:
        id: Decision ID (e.g. DEC-029)
        old_text: Exact text to find in body (must be unique)
        new_text: Replacement text
    """
    return _run("edit", id, old_text, new_text)


# ---------------------------------------------------------------------------
# Scratchpad tools
# ---------------------------------------------------------------------------


@mcp.tool()
def scratchpad_add(type: str, content: str, links: str = "") -> str:
    """Add a pre-decision entry to the scratchpad.

    Args:
        type: Entry type — idea, constraint, question, or concern
        content: The entry content
        links: Comma-separated decision IDs to link (optional)
    """
    args = ["scratchpad", "add", "--type", type, content]
    if links:
        args.extend(["--links", links])
    return _run(*args)


@mcp.tool()
def scratchpad_list(type: str = "", json_output: bool = True) -> str:
    """List scratchpad entries (active and matured).

    Args:
        type: Filter by type (idea, constraint, question, concern). Empty for all.
        json_output: Return JSON format (default True)
    """
    args = ["scratchpad", "list"]
    if type:
        args.extend(["--type", type])
    if json_output:
        args.append("--json")
    return _run(*args)


@mcp.tool()
def scratchpad_mature(sp_id: str, dec_id: str) -> str:
    """Graduate a scratchpad entry to a decision.

    Args:
        sp_id: Scratchpad entry ID (e.g. SP-001)
        dec_id: Decision ID it matured into (e.g. DEC-057)
    """
    return _run("scratchpad", "mature", sp_id, dec_id)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
