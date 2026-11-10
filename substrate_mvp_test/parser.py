# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

"""AST Codebase Ingestion Parser for Relational Substrate."""

import ast
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class CodebaseVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str, source_text: str):
        self.rel_path = rel_path
        self.source_lines = source_text.splitlines(keepends=True)
        self.imports: Dict[str, Tuple[str, str]] = {}  # local_alias -> (module_path, symbol)
        self.nodes: List[Dict[str, str]] = []
        self.edges: List[Tuple[str, str, str]] = []
        self.current_func_coord: Optional[str] = None
        self.local_functions: Set[str] = set()

    def _canonical_uri(self, symbol: str) -> str:
        return f"node://code/{self.rel_path}:{symbol}"

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            mod_path = alias.name.replace(".", "/") + ".py"
            name = alias.asname or alias.name
            self.imports[name] = (mod_path, "")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if not node.module:
            return
        mod_path = node.module.replace(".", "/") + ".py"
        for alias in node.names:
            local_name = alias.asname or alias.name
            self.imports[local_name] = (mod_path, alias.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        coord = self._canonical_uri(node.name)
        self.local_functions.add(node.name)

        # Slice exact source body
        body_lines = self.source_lines[node.lineno - 1 : node.end_lineno]
        body = "".join(body_lines)

        # Generate concise summary (< 30 tokens)
        docstring = ast.get_docstring(node) or ""
        first_doc = docstring.strip().split("\n")[0] if docstring else ""
        args = [a.arg for a in node.args.args]
        summary = f"def {node.name}({', '.join(args)}): {first_doc}"[:120]

        self.nodes.append({
            "coordinate": coord,
            "node_type": "function",
            "summary": summary,
            "body": body,
        })

        # Traverse body to capture calls
        prev_func = self.current_func_coord
        self.current_func_coord = coord
        for item in node.body:
            self.visit(item)
        self.current_func_coord = prev_func

    def visit_Call(self, node: ast.Call):
        if not self.current_func_coord:
            return

        target_coord: Optional[str] = None

        # Pattern 1: Direct name call: save_record(...)
        if isinstance(node.func, ast.Name):
            callee_name = node.func.id
            if callee_name in self.imports:
                mod_path, sym = self.imports[callee_name]
                target_coord = f"node://code/{mod_path}:{sym or callee_name}"
            elif callee_name in self.local_functions:
                target_coord = self._canonical_uri(callee_name)

        # Pattern 2: Attribute call: db.save_record(...)
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            mod_alias = node.func.value.id
            attr_name = node.func.attr
            if mod_alias in self.imports:
                mod_path, _ = self.imports[mod_alias]
                target_coord = f"node://code/{mod_path}:{attr_name}"

        if target_coord:
            self.edges.append((self.current_func_coord, target_coord, "call_graph"))

        self.generic_visit(node)


def parse_and_ingest_fixture(fixture_dir: Path, db_path: Path) -> Dict[str, int]:
    """Parse entire fixture directory and ingest nodes & edges into SQLite substrate."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")

    all_nodes: List[Dict[str, str]] = []
    all_edges: List[Tuple[str, str, str]] = []

    py_files = sorted(fixture_dir.rglob("*.py"))
    for py_file in py_files:
        if py_file.name == "__init__.py":
            continue
        rel_path = str(py_file.relative_to(fixture_dir))
        content = py_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(py_file))
        visitor = CodebaseVisitor(rel_path, content)
        visitor.visit(tree)
        all_nodes.extend(visitor.nodes)
        all_edges.extend(visitor.edges)

    # Ingest nodes
    with conn:
        for n in all_nodes:
            conn.execute(
                """INSERT OR REPLACE INTO substrate_nodes (coordinate, node_type, summary, body)
                   VALUES (?, ?, ?, ?);""",
                (n["coordinate"], n["node_type"], n["summary"], n["body"]),
            )

        # Ingest edges (only where target exists in substrate_nodes to satisfy foreign key)
        valid_coords = {n["coordinate"] for n in all_nodes}
        edge_count = 0
        for src, tgt, lens in all_edges:
            if src in valid_coords and tgt in valid_coords:
                conn.execute(
                    """INSERT OR IGNORE INTO hyper_edges (source, target, lens)
                       VALUES (?, ?, ?);""",
                    (src, tgt, lens),
                )
                edge_count += 1

    conn.close()
    return {"nodes_indexed": len(all_nodes), "edges_indexed": edge_count}


if __name__ == "__main__":
    from init_db import init_database
    base = Path(__file__).parent
    db = base / "test_substrate.db"
    init_database(db)
    stats = parse_and_ingest_fixture(base / "fixture", db)
    print("Ingestion Complete:", stats)

    # Print sample edges
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    print("\nRecorded Call Graph Edges:")
    for row in cur.execute("SELECT source, target, lens FROM hyper_edges WHERE lens = 'call_graph';").fetchall():
        print(f"  {row[0]} -> {row[1]}")
    conn.close()
