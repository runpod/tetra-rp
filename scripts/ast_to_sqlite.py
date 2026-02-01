#!/usr/bin/env python3
"""AST-based code indexer for runpod-flash framework.

Extracts Python symbols (classes, functions, methods) and stores them in SQLite
for fast symbol lookup and exploration. Reduces token usage by ~85% when exploring
framework codebase with Claude Code.

Usage:
    uv run python scripts/ast_to_sqlite.py

Output:
    .code-intel/flash.db - SQLite database with indexed symbols
"""

import ast
import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

CODE_INTEL_DIR = Path.cwd() / ".code-intel"
DB_PATH = CODE_INTEL_DIR / "flash.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    symbol_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    signature TEXT,
    docstring TEXT,
    start_line INTEGER NOT NULL,
    end_line INTEGER,
    parent_symbol TEXT,
    decorator_json TEXT,
    type_hints TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_symbol_name ON symbols(symbol_name);
CREATE INDEX IF NOT EXISTS idx_file_path ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_kind ON symbols(kind);
CREATE INDEX IF NOT EXISTS idx_parent ON symbols(parent_symbol);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class SymbolInfo:
    """Symbol extracted from AST."""

    file_path: str
    symbol_name: str
    kind: str
    signature: str
    docstring: Optional[str]
    start_line: int
    end_line: int
    parent_symbol: Optional[str]
    decorators: List[str]
    type_hints: Dict[str, Any]


class ASTIndexer(ast.NodeVisitor):
    """Extract symbols from Python AST."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.symbols: List[SymbolInfo] = []
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extract class definitions."""
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        docstring = ast.get_docstring(node)

        # Build class signature
        bases = [self._get_name(base) for base in node.bases]
        signature = f"class {node.name}"
        if bases:
            signature += f"({', '.join(bases)})"

        symbol = SymbolInfo(
            file_path=self.file_path,
            symbol_name=node.name,
            kind="class",
            signature=signature,
            docstring=docstring,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            parent_symbol=self.current_class,
            decorators=decorators,
            type_hints={},
        )
        self.symbols.append(symbol)

        # Visit methods inside class
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract function/method definitions."""
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        docstring = ast.get_docstring(node)

        # Extract type hints
        type_hints = self._extract_type_hints(node)

        # Build signature
        signature = self._build_function_signature(node, type_hints)

        # Determine kind (method vs function)
        kind = "method" if self.current_class else "function"

        symbol = SymbolInfo(
            file_path=self.file_path,
            symbol_name=node.name,
            kind=kind,
            signature=signature,
            docstring=docstring,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            parent_symbol=self.current_class,
            decorators=decorators,
            type_hints=type_hints,
        )
        self.symbols.append(symbol)

    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """Extract decorator name (e.g., '@remote' from '@remote()')."""
        if isinstance(decorator, ast.Name):
            return f"@{decorator.id}"
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return f"@{decorator.func.id}"
        return "@unknown"

    def _extract_type_hints(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """Extract argument and return type hints."""
        hints: Dict[str, Any] = {"args": {}, "return": None}

        # Extract argument type hints
        for arg in node.args.args:
            if arg.annotation:
                hints["args"][arg.arg] = ast.unparse(arg.annotation)

        # Extract return type hint
        if node.returns:
            hints["return"] = ast.unparse(node.returns)

        return hints

    def _build_function_signature(
        self, node: ast.FunctionDef, type_hints: Dict[str, Any]
    ) -> str:
        """Build function signature with type hints."""
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.arg in type_hints["args"]:
                arg_str += f": {type_hints['args'][arg.arg]}"
            args.append(arg_str)

        signature = f"def {node.name}({', '.join(args)})"
        if type_hints["return"]:
            signature += f" -> {type_hints['return']}"

        return signature

    def _get_name(self, node: ast.expr) -> str:
        """Get name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return ast.unparse(node)
        return "Unknown"


def _log_indexing_error(file_path: Path, error: Exception) -> None:
    """Log an indexing error to stderr."""
    print(f"⚠️  Error indexing {file_path}: {error}", file=sys.stderr)


def create_database(db_path: Path) -> sqlite3.Connection:
    """Create SQLite database with schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    # Update metadata
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("index_timestamp", str(int(time.time()))),
    )
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("indexer_version", "1.0.0"),
    )
    conn.commit()
    return conn


def index_python_files(project_root: Path, conn: sqlite3.Connection) -> int:
    """Index all Python files in project."""
    # Clear existing symbols
    conn.execute("DELETE FROM symbols")

    # Find all Python files in src/ directory
    python_files = sorted(list(project_root.glob("src/**/*.py")))

    total_symbols = 0
    errors = 0
    latest_file_mtime: float = 0.0

    for py_file in python_files:
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(py_file))
            indexer = ASTIndexer(file_path=str(py_file.relative_to(project_root)))
            indexer.visit(tree)

            # Insert symbols into database
            for symbol in indexer.symbols:
                conn.execute(
                    """
                    INSERT INTO symbols
                    (file_path, symbol_name, kind, signature, docstring,
                     start_line, end_line, parent_symbol, decorator_json, type_hints)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol.file_path,
                        symbol.symbol_name,
                        symbol.kind,
                        symbol.signature,
                        symbol.docstring,
                        symbol.start_line,
                        symbol.end_line,
                        symbol.parent_symbol,
                        json.dumps(symbol.decorators),
                        json.dumps(symbol.type_hints),
                    ),
                )
                total_symbols += 1

            # Track the latest file modification time
            file_mtime = py_file.stat().st_mtime
            if file_mtime > latest_file_mtime:
                latest_file_mtime = file_mtime

        except SyntaxError as e:
            print(f"⚠️  Skipping {py_file}: {e}", file=sys.stderr)
            errors += 1
            continue
        except Exception as e:
            _log_indexing_error(py_file, e)
            errors += 1
            continue

    # Update metadata with indexing stats
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("file_count", str(len(python_files))),
    )
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("latest_file_mtime", str(int(latest_file_mtime))),
    )
    conn.commit()
    return total_symbols


def main() -> None:
    """Main indexer entry point."""
    print("🔍 Starting code intelligence indexing...")

    project_root = Path.cwd()
    db_path = CODE_INTEL_DIR / "flash.db"

    # Create database
    conn = create_database(db_path)

    # Index files
    start_time = time.time()
    total_symbols = index_python_files(project_root, conn)
    elapsed = time.time() - start_time

    conn.close()

    db_size_kb = db_path.stat().st_size / 1024
    print(f"✅ Indexed {total_symbols} symbols in {elapsed:.2f}s")
    print(f"📊 Database: {db_path} ({db_size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
