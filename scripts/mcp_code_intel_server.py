#!/usr/bin/env python3
"""MCP server for runpod-flash code intelligence.

Provides tools for querying the SQLite code intelligence database.
Claude Code automatically discovers and uses these tools.
"""

import asyncio
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions

CODE_INTEL_DIR = Path.cwd() / ".code-intel"
DB_PATH = CODE_INTEL_DIR / "flash.db"
INDEXER_SCRIPT = Path.cwd() / "scripts" / "ast_to_sqlite.py"
SRC_DIR = Path.cwd() / "src"

# Query result limits
MAX_SYMBOL_RESULTS = 50
MAX_CLASS_RESULTS = 100
MAX_DECORATOR_RESULTS = 100

# Query result limits
MAX_SYMBOL_RESULTS = 50
MAX_CLASS_RESULTS = 100
MAX_DECORATOR_RESULTS = 100

# Initialize MCP server
server = Server("tetra-code-intel")


def should_reindex() -> bool:
    """Check if code index is stale and needs rebuilding.

    Returns True if:
    1. Database doesn't exist
    2. Any Python file in src/**/*.py is newer than index timestamp
    3. The indexer script itself has been modified after indexing

    Returns:
        True if index should be rebuilt, False otherwise.
    """
    # Database doesn't exist
    if not DB_PATH.exists():
        return True

    # Get index timestamp from database
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute(
            "SELECT value FROM metadata WHERE key = 'index_timestamp'"
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            return True

        index_timestamp = int(result[0])
    except (sqlite3.Error, ValueError, TypeError):
        return True

    # Check if any Python file in src/ is newer than index timestamp
    if SRC_DIR.exists():
        try:
            python_files = list(SRC_DIR.glob("**/*.py"))
            for py_file in python_files:
                if py_file.stat().st_mtime > index_timestamp:
                    return True
        except (OSError, IOError):
            return True

    # Check if indexer script itself has changed
    try:
        if INDEXER_SCRIPT.exists():
            if INDEXER_SCRIPT.stat().st_mtime > index_timestamp:
                return True
    except (OSError, IOError):
        return True

    return False


def parse_test_output(output: str) -> dict[str, Any]:
    """Parse pytest output and extract failures, errors, and summary.

    Args:
        output: Raw pytest output text.

    Returns:
        Dictionary with test summary, failed tests list, and coverage stats.
    """
    result: dict[str, Any] = {
        "summary": {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "deselected": 0,
            "skipped": 0,
            "total": 0,
        },
        "failed_tests": [],
        "coverage": {"total_pct": None, "threshold": None, "passed": None},
    }

    # Parse summary line: "X passed, Y failed, Z errors" etc.
    # Handle various formats: "123 passed", "1 failed in 5.23s", "456 deselected, 78 passed in 10.45s"
    summary_patterns = [
        (r"(\d+)\s+passed", "passed"),
        (r"(\d+)\s+failed", "failed"),
        (r"(\d+)\s+error", "errors"),
        (r"(\d+)\s+deselected", "deselected"),
        (r"(\d+)\s+skipped", "skipped"),
    ]

    for pattern, key in summary_patterns:
        match = re.search(pattern, output)
        if match:
            result["summary"][key] = int(match.group(1))

    # Calculate total
    result["summary"]["total"] = sum(
        result["summary"][k]
        for k in ["passed", "failed", "errors", "deselected", "skipped"]
    )

    # Extract failed tests: look for "FAILED" or "ERROR" lines with file paths
    # Pattern: "FAILED tests/unit/... - error message"
    # or: "ERROR tests/unit/..."
    failed_pattern = r"(FAILED|ERROR)\s+([\w/\-\.]+::\w+)\s*(?:-\s+(.+))?$"
    for match in re.finditer(failed_pattern, output, re.MULTILINE):
        test_type, test_id, error_msg = match.groups()
        result["failed_tests"].append(
            {
                "test_id": test_id,
                "type": test_type.lower(),
                "error": (error_msg or "").strip(),
            }
        )

    # Extract coverage info from the coverage summary line
    # Look for "TOTAL ... XY.ZZ%" pattern
    coverage_match = re.search(r"^TOTAL\s+.*?(\d+\.\d+)%", output, re.MULTILINE)
    if not coverage_match:
        # Fallback: look for "coverage: XY.ZZ%" pattern
        coverage_match = re.search(r"coverage:\s*(\d+\.\d+)%", output)
    if coverage_match:
        result["coverage"]["total_pct"] = float(coverage_match.group(1))

    # Check for coverage threshold failure: "FAILED Required test coverage of X.XX%"
    threshold_match = re.search(r"Required test coverage of (\d+\.\d+)%", output)
    if threshold_match:
        result["coverage"]["threshold"] = float(threshold_match.group(1))
        if result["coverage"]["total_pct"] is not None:
            result["coverage"]["passed"] = (
                result["coverage"]["total_pct"] >= result["coverage"]["threshold"]
            )

    return result


def format_test_summary(parsed: dict[str, Any]) -> str:
    """Format parsed test output as markdown.

    Args:
        parsed: Parsed test output dictionary.

    Returns:
        Markdown-formatted summary.
    """
    output = "# Test Results Summary\n\n"

    # Test summary
    summary = parsed["summary"]
    total = summary["total"]
    if total > 0:
        output += "## Test Summary\n"
        output += f"- **Passed**: {summary['passed']}\n"
        if summary["failed"] > 0:
            output += f"- **Failed**: {summary['failed']} ❌\n"
        if summary["errors"] > 0:
            output += f"- **Errors**: {summary['errors']} ⚠️\n"
        if summary["deselected"] > 0:
            output += f"- **Deselected**: {summary['deselected']}\n"
        if summary["skipped"] > 0:
            output += f"- **Skipped**: {summary['skipped']}\n"
        output += f"- **Total**: {total}\n\n"
    else:
        output += "No tests found in output.\n\n"

    # Failed tests
    if parsed["failed_tests"]:
        output += "## Failed Tests\n\n"
        for test in parsed["failed_tests"]:
            output += f"### {test['test_id']}\n"
            output += f"**Type**: {test['type'].upper()}\n"
            if test["error"]:
                output += f"**Error**: {test['error']}\n"
            output += "\n"

    # Coverage
    if parsed["coverage"]["total_pct"] is not None:
        output += "## Coverage\n"
        output += f"- **Coverage**: {parsed['coverage']['total_pct']:.2f}%\n"
        if parsed["coverage"]["threshold"] is not None:
            status = "✅" if parsed["coverage"]["passed"] else "❌"
            output += (
                f"- **Threshold**: {parsed['coverage']['threshold']:.2f}% {status}\n"
            )
        output += "\n"

    return output


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Code intelligence database not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available code intelligence tools."""
    return [
        types.Tool(
            name="find_symbol",
            description="Search for a symbol (class, function, method) by name in the runpod-flash framework. "
            "Returns symbol name, kind, signature, file location, and docstring. "
            "Use this instead of reading full files when exploring code structure.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name to search for (supports partial matching)",
                    }
                },
                "required": ["symbol"],
            },
        ),
        types.Tool(
            name="list_classes",
            description="List all classes in the runpod-flash framework with their signatures and locations. "
            "Use this to understand the framework's class hierarchy without reading files.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_class_interface",
            description="Get a class's methods and properties without implementations. "
            "Returns method signatures, decorators, and docstrings. "
            "Use this to understand a class's API surface without reading the full file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "class_name": {
                        "type": "string",
                        "description": "Name of the class to inspect",
                    }
                },
                "required": ["class_name"],
            },
        ),
        types.Tool(
            name="list_file_symbols",
            description="List all symbols (classes, functions, methods) defined in a file. "
            "Returns a tokenized view of the file structure without full implementations. "
            "Use this instead of reading the full file to understand file structure.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative file path from project root (e.g., 'core/resources/serverless.py')",
                    }
                },
                "required": ["file_path"],
            },
        ),
        types.Tool(
            name="find_by_decorator",
            description="Find all functions/methods with a specific decorator (e.g., '@remote', '@property'). "
            "Returns decorated symbols with their signatures and locations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "decorator": {
                        "type": "string",
                        "description": "Decorator name (e.g., 'remote', 'property', 'staticmethod')",
                    }
                },
                "required": ["decorator"],
            },
        ),
        types.Tool(
            name="parse_test_output",
            description=(
                "Parse pytest test output to extract failures, errors, and summary statistics. "
                "Use this INSTEAD of manually reading test output with tail/grep/head. "
                "\n\n"
                "When to use:\n"
                "- After running pytest commands (make test, make test-unit, pytest tests/, etc.)\n"
                "- When you need to analyze test failures or check coverage status\n"
                "- Instead of using 'tail -n 100' or grepping through test results\n"
                "\n"
                "What it returns:\n"
                "- Test summary (passed/failed/errors/deselected counts)\n"
                "- List of failed tests with file locations and error messages\n"
                "- Coverage statistics if present in output\n"
                "- Formatted as concise markdown for easy reading\n"
                "\n"
                "Benefits:\n"
                "- Saves tokens: returns only actionable info, not full output\n"
                "- Structured: easy to identify which tests failed and why\n"
                "- Fast: no need to tail/grep large output files\n"
                "\n"
                "Example:\n"
                "After running: pytest tests/unit/ -v\n"
                "Pass the output to this tool to get which tests failed, why, and coverage status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "output": {
                        "type": "string",
                        "description": "Raw pytest output text (from stdout/stderr or file)",
                    }
                },
                "required": ["output"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution."""

    if name == "find_symbol":
        symbol = arguments["symbol"]
        conn = get_db()
        cursor = conn.execute(
            f"""
            SELECT file_path, symbol_name, kind, signature, start_line, docstring
            FROM symbols
            WHERE symbol_name LIKE ?
            ORDER BY symbol_name, file_path
            LIMIT {MAX_SYMBOL_RESULTS}
            """,
            (f"%{symbol}%",),
        )
        results = cursor.fetchall()
        conn.close()

        if not results:
            return [
                types.TextContent(
                    type="text", text=f"No symbols found matching '{symbol}'"
                )
            ]

        # Format results as markdown
        output = f"# Symbol Search: '{symbol}' ({len(results)} found)\n\n"
        for row in results:
            file_path, name_val, kind, sig, line, docstring = (
                row["file_path"],
                row["symbol_name"],
                row["kind"],
                row["signature"],
                row["start_line"],
                row["docstring"],
            )
            output += f"## {name_val} ({kind})\n"
            output += f"**Location**: `{file_path}:{line}`\n"
            output += f"**Signature**: `{sig}`\n"
            if docstring:
                doc_preview = (
                    docstring[:150] + "..." if len(docstring) > 150 else docstring
                )
                output += f"**Docstring**: {doc_preview}\n"
            output += "\n"

        return [types.TextContent(type="text", text=output)]

    elif name == "list_classes":
        conn = get_db()
        cursor = conn.execute(
            f"""
            SELECT file_path, symbol_name, signature, start_line, docstring
            FROM symbols
            WHERE kind = 'class'
            ORDER BY file_path, start_line
            LIMIT {MAX_CLASS_RESULTS}
            """
        )
        results = cursor.fetchall()
        conn.close()

        output = f"# Classes in runpod-flash Framework ({len(results)} found)\n\n"
        current_file = None
        for row in results:
            file_path, name_val, sig, line, docstring = (
                row["file_path"],
                row["symbol_name"],
                row["signature"],
                row["start_line"],
                row["docstring"],
            )
            if file_path != current_file:
                output += f"\n## File: {file_path}\n\n"
                current_file = file_path
            output += f"- **{name_val}** (line {line}): `{sig}`\n"
            if docstring:
                doc_preview = (
                    docstring[:100] + "..." if len(docstring) > 100 else docstring
                )
                output += f"  {doc_preview}\n"

        return [types.TextContent(type="text", text=output)]

    elif name == "get_class_interface":
        class_name = arguments["class_name"]
        conn = get_db()

        # Get class info
        cursor = conn.execute(
            """
            SELECT file_path, signature, docstring, start_line
            FROM symbols
            WHERE symbol_name = ? AND kind = 'class'
            """,
            (class_name,),
        )
        class_info = cursor.fetchone()

        if not class_info:
            conn.close()
            return [
                types.TextContent(type="text", text=f"Class '{class_name}' not found")
            ]

        file_path, sig, docstring, line = (
            class_info["file_path"],
            class_info["signature"],
            class_info["docstring"],
            class_info["start_line"],
        )

        # Get methods
        cursor = conn.execute(
            """
            SELECT symbol_name, signature, docstring, decorator_json, start_line
            FROM symbols
            WHERE parent_symbol = ? AND kind = 'method'
            ORDER BY start_line
            """,
            (class_name,),
        )
        methods = cursor.fetchall()
        conn.close()

        output = f"# {sig}\n\n"
        output += f"**Location**: `{file_path}:{line}`\n\n"
        if docstring:
            output += f"{docstring}\n\n"

        output += f"## Methods ({len(methods)})\n\n"
        for row in methods:
            name_val, method_sig, doc, decorators, method_line = (
                row["symbol_name"],
                row["signature"],
                row["docstring"],
                row["decorator_json"],
                row["start_line"],
            )
            dec_list = json.loads(decorators) if decorators else []
            dec_str = " ".join(dec_list) if dec_list else ""

            output += f"### {name_val}\n"
            if dec_str:
                output += f"**Decorators**: {dec_str}\n"
            output += f"**Signature**: `{method_sig}`\n"
            output += f"**Line**: {method_line}\n"
            if doc:
                doc_preview = doc[:150] + "..." if len(doc) > 150 else doc
                output += f"{doc_preview}\n"
            output += "\n"

        return [types.TextContent(type="text", text=output)]

    elif name == "list_file_symbols":
        file_path = arguments["file_path"]
        conn = get_db()
        cursor = conn.execute(
            """
            SELECT symbol_name, kind, signature, start_line, decorator_json
            FROM symbols
            WHERE file_path LIKE ?
            ORDER BY start_line
            """,
            (f"%{file_path}%",),
        )
        results = cursor.fetchall()
        conn.close()

        if not results:
            return [
                types.TextContent(
                    type="text",
                    text=f"No symbols found in file matching '{file_path}'",
                )
            ]

        output = f"# Symbols in {file_path} ({len(results)} found)\n\n"
        for row in results:
            name_val, kind, sig, line, decorators = (
                row["symbol_name"],
                row["kind"],
                row["signature"],
                row["start_line"],
                row["decorator_json"],
            )
            dec_list = json.loads(decorators) if decorators else []
            dec_str = " ".join(dec_list) if dec_list else ""

            output += f"**Line {line}**: `{name_val}` ({kind})\n"
            if dec_str:
                output += f"  Decorators: {dec_str}\n"
            output += f"  Signature: `{sig}`\n\n"

        return [types.TextContent(type="text", text=output)]

    elif name == "find_by_decorator":
        decorator = arguments["decorator"]
        decorator_pattern = f"%{decorator}%"

        conn = get_db()
        cursor = conn.execute(
            f"""
            SELECT file_path, symbol_name, kind, signature, start_line, decorator_json
            FROM symbols
            WHERE decorator_json LIKE ?
            ORDER BY file_path, start_line
            LIMIT {MAX_DECORATOR_RESULTS}
            """,
            (decorator_pattern,),
        )
        results = cursor.fetchall()
        conn.close()

        if not results:
            return [
                types.TextContent(
                    type="text",
                    text=f"No symbols found with @{decorator} decorator",
                )
            ]

        output = f"# Symbols with @{decorator} decorator ({len(results)} found)\n\n"
        current_file = None
        for row in results:
            file_path, name_val, kind, sig, line, decorators = (
                row["file_path"],
                row["symbol_name"],
                row["kind"],
                row["signature"],
                row["start_line"],
                row["decorator_json"],
            )
            if file_path != current_file:
                output += f"\n## {file_path}\n\n"
                current_file = file_path
            output += f"- **{name_val}** ({kind}, line {line})\n"
            output += f"  `{sig}`\n\n"

        return [types.TextContent(type="text", text=output)]

    elif name == "parse_test_output":
        output_text = arguments["output"]
        parsed = parse_test_output(output_text)
        formatted = format_test_summary(parsed)
        return [types.TextContent(type="text", text=formatted)]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    """Run the MCP server using stdio transport."""
    # Check if code index needs rebuilding
    if should_reindex():
        print("🔄 Code index stale, rebuilding...", file=sys.stderr)
        try:
            result = subprocess.run(
                ["uv", "run", "python", "scripts/ast_to_sqlite.py"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                print(
                    f"⚠️  Code index rebuild failed: {result.stderr}",
                    file=sys.stderr,
                )
            else:
                print("✅ Code index updated", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print("⚠️  Code index rebuild timed out", file=sys.stderr)
        except Exception as e:
            print(f"⚠️  Code index rebuild error: {e}", file=sys.stderr)

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="tetra-code-intel",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
