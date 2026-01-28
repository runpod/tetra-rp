#!/usr/bin/env python3
"""Code intelligence query interface for tetra-rp framework.

Fast symbol lookup for exploring framework codebase. Reduces token usage by ~85%
when exploring tetra-rp framework structure with Claude Code.

Usage:
    uv run python scripts/code_intel.py find <symbol>
    uv run python scripts/code_intel.py list-all [--kind class|function|method]
    uv run python scripts/code_intel.py interface <ClassName>
    uv run python scripts/code_intel.py file <file_path>
"""

import json
import sqlite3
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="code-intel",
    help="Query tetra-rp code intelligence index",
    no_args_is_help=True,
)
console = Console()

CODE_INTEL_DIR = Path.cwd() / ".code-intel"
DB_PATH = CODE_INTEL_DIR / "flash.db"


def get_db() -> sqlite3.Connection:
    """Get database connection with error handling."""
    if not DB_PATH.exists():
        console.print(
            "[red]Error:[/red] Index not found at "
            f"{DB_PATH}\nRun: [cyan]make index[/cyan] to generate index"
        )
        raise typer.Exit(code=1)

    return sqlite3.connect(DB_PATH)


@app.command()
def list_all(
    kind: str = typer.Option(None, help="Filter by kind: class, function, method"),
) -> None:
    """List all symbols, optionally filtered by kind."""
    conn = get_db()

    if kind:
        cursor = conn.execute(
            """
            SELECT file_path, symbol_name, kind, signature, start_line
            FROM symbols
            WHERE kind = ?
            ORDER BY file_path, start_line
            """,
            (kind,),
        )
        title = f"{kind.title()}s in Codebase"
    else:
        cursor = conn.execute(
            """
            SELECT file_path, symbol_name, kind, signature, start_line
            FROM symbols
            ORDER BY file_path, start_line
            """
        )
        title = "All Symbols in Codebase"

    results = cursor.fetchall()
    conn.close()

    if not results:
        filter_msg = f" for kind: {kind}" if kind else ""
        console.print(f"[yellow]No symbols found{filter_msg}[/yellow]")
        return

    table = Table(title=f"{title} ({len(results)} found)")
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Kind", style="green")
    table.add_column("Signature", style="yellow", max_width=60)
    table.add_column("Location", style="magenta")

    for row in results:
        file_path, name, kind_val, sig, line = row
        location = f"{file_path}:{line}"
        sig_display = sig[:60] + "..." if sig and len(sig) > 60 else (sig or "")
        table.add_row(name, kind_val, sig_display, location)

    console.print(table)


@app.command()
def find(symbol: str) -> None:
    """Find symbol by name across codebase."""
    conn = get_db()
    cursor = conn.execute(
        """
        SELECT file_path, symbol_name, kind, signature, start_line, docstring
        FROM symbols
        WHERE symbol_name LIKE ?
        ORDER BY symbol_name, file_path
        """,
        (f"%{symbol}%",),
    )

    results = cursor.fetchall()
    conn.close()

    if not results:
        console.print(f"[yellow]No symbols found matching '{symbol}'[/yellow]")
        return

    table = Table(title=f"Symbol Search: '{symbol}' ({len(results)} found)")
    table.add_column("Symbol", style="cyan")
    table.add_column("Kind", style="green")
    table.add_column("Signature", style="yellow", max_width=50)
    table.add_column("Location", style="magenta")

    for row in results:
        file_path, name, kind, sig, line, docstring = row
        location = f"{file_path}:{line}"
        # Truncate long signatures
        sig_display = sig[:50] + "..." if sig and len(sig) > 50 else (sig or "")
        table.add_row(name, kind, sig_display, location)

    console.print(table)

    # Show first result's docstring if available
    if results[0][5]:  # docstring
        console.print("\n[bold]First result docstring:[/bold]")
        doc = results[0][5]
        doc_display = doc[:200] + "..." if len(doc) > 200 else doc
        console.print(doc_display)


@app.command()
def interface(class_name: str) -> None:
    """Show class methods and properties without implementations."""
    conn = get_db()

    # Find class definition
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
        console.print(f"[yellow]Class '{class_name}' not found[/yellow]")
        conn.close()
        return

    file_path, sig, docstring, line = class_info

    # Print class header
    console.print(f"\n[bold cyan]{sig}[/bold cyan]")
    console.print(f"[dim]{file_path}:{line}[/dim]\n")

    if docstring:
        doc_display = docstring[:150] + "..." if len(docstring) > 150 else docstring
        console.print(f"[italic]{doc_display}[/italic]\n")

    # Find all methods
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

    if not methods:
        console.print("[yellow]No methods found[/yellow]")
        return

    # Print methods
    table = Table(title=f"Methods ({len(methods)})")
    table.add_column("Method", style="cyan")
    table.add_column("Signature", style="yellow", max_width=60)
    table.add_column("Decorators", style="green")

    for name, sig, doc, decorators, line in methods:
        dec_list = json.loads(decorators) if decorators else []
        dec_str = ", ".join(dec_list) if dec_list else ""
        sig_display = sig[:60] + "..." if sig and len(sig) > 60 else (sig or "")
        table.add_row(name, sig_display, dec_str)

    console.print(table)


@app.command()
def file(file_path: str) -> None:
    """List all symbols defined in a file."""
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
        console.print(f"[yellow]No symbols found in '{file_path}'[/yellow]")
        return

    table = Table(title=f"Symbols in {file_path} ({len(results)} found)")
    table.add_column("Line", style="dim", width=6)
    table.add_column("Symbol", style="cyan")
    table.add_column("Kind", style="green")
    table.add_column("Signature", style="yellow", max_width=50)
    table.add_column("Decorators", style="magenta")

    for name, kind, sig, line, decorators in results:
        dec_list = json.loads(decorators) if decorators else []
        dec_str = ", ".join(dec_list)[:30] if dec_list else ""
        sig_display = sig[:50] + "..." if sig and len(sig) > 50 else (sig or "")
        table.add_row(str(line), name, kind, sig_display, dec_str)

    console.print(table)


if __name__ == "__main__":
    app()
