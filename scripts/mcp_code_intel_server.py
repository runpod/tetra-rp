#!/usr/bin/env python3
"""MCP server for tetra-rp code intelligence.

Provides tools for querying the SQLite code intelligence database.
Claude Code automatically discovers and uses these tools.
"""

import asyncio
import json
import sqlite3
from pathlib import Path

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions

CODE_INTEL_DIR = Path.cwd() / ".code-intel"
DB_PATH = CODE_INTEL_DIR / "flash.db"

# Query result limits
MAX_SYMBOL_RESULTS = 50
MAX_CLASS_RESULTS = 100
MAX_DECORATOR_RESULTS = 100

# Initialize MCP server
server = Server("tetra-code-intel")


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
            description="Search for a symbol (class, function, method) by name in the tetra-rp framework. "
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
            description="List all classes in the tetra-rp framework with their signatures and locations. "
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

        output = f"# Classes in tetra-rp Framework ({len(results)} found)\n\n"
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

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    """Run the MCP server using stdio transport."""
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
