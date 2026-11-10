"""
Codebase Indexer: Maps Python source files into a two-table relational substrate.
Outputs:
  - code_substrate.db (SQLite database with WAL mode)
Tables:
  - substrate_nodes (coordinate TEXT PRIMARY KEY, node_type TEXT, summary TEXT, body TEXT)
  - hyper_edges (source TEXT, target TEXT, lens TEXT)
Lenses:
  - structural: file -> class/function, class -> method
  - imports: file -> imported module
  - call_graph: caller function -> callee function
"""

import ast
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


def truncate_summary(text: str, max_words: int = 28) -> str:
    """Ensure summary is a concise 1-line preview strictly under max_words."""
    single_line = " ".join(text.strip().split())
    words = single_line.split()
    if len(words) <= max_words:
        return single_line
    return " ".join(words[:max_words]) + "..."


def get_docstring_first_line(node: ast.AST) -> str:
    """Extract first line of docstring if present."""
    doc = ast.get_docstring(node)
    if not doc:
        return ""
    lines = doc.strip().splitlines()
    return lines[0].strip() if lines else ""


class CodebaseIndexer:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.nodes: Dict[str, Tuple[str, str, str]] = {}  # coord -> (node_type, summary, body)
        self.edges: Set[Tuple[str, str, str]] = set()     # (source, target, lens)

        # Registry for symbol resolution
        # module_dotpath -> module_coord (e.g. 'core.project_manager' -> 'node://code/core/project_manager.py')
        self.module_registry: Dict[str, str] = {}
        # (module_dotpath, symbol_name) -> symbol_coord (e.g. ('core.project_manager', 'create_project') -> coord)
        self.symbol_registry: Dict[Tuple[str, str], str] = {}
        # simple symbol name -> list of coords (for fallback heuristic matching)
        self.name_to_coords: Dict[str, List[str]] = {}

        # Per-file parse info
        self.file_trees: Dict[Path, ast.AST] = {}
        self.file_sources: Dict[Path, str] = {}
        self.file_module_paths: Dict[Path, str] = {}  # path -> dotpath
        self.file_imports: Dict[Path, Dict[str, Tuple[str, Optional[str]]]] = {}  # alias -> (module_dotpath, symbol_name)

    def init_db(self):
        if self.db_path.exists():
            self.db_path.unlink()
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS substrate_nodes (
            coordinate TEXT PRIMARY KEY,
            node_type TEXT,
            summary TEXT,
            body TEXT
        );

        CREATE TABLE IF NOT EXISTS hyper_edges (
            source TEXT,
            target TEXT,
            lens TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_edges_source_lens ON hyper_edges(source, lens);
        CREATE INDEX IF NOT EXISTS idx_edges_target_lens ON hyper_edges(target, lens);
        CREATE INDEX IF NOT EXISTS idx_nodes_coord ON substrate_nodes(coordinate);
        """)
        conn.close()

    def discover_files(self, targets: List[Path]) -> List[Path]:
        """Find all relevant Python files from target paths, excluding caches and environments."""
        ignore_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", "site-packages"}
        py_files: List[Path] = []
        for target in targets:
            if target.is_file() and target.suffix == ".py":
                py_files.append(target.resolve())
            elif target.is_dir():
                for root, dirs, files in os.walk(target):
                    dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
                    for f in files:
                        if f.endswith(".py"):
                            py_files.append((Path(root) / f).resolve())
        return sorted(list(set(py_files)))

    def compute_module_dotpath(self, file_path: Path, repo_root: Path) -> str:
        """Compute importable dotpath relative to repo root (e.g. core/project_manager.py -> core.project_manager)."""
        try:
            rel = file_path.relative_to(repo_root)
        except ValueError:
            rel = file_path
        parts = list(rel.parts)
        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        if parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)

    def pass1_extract_nodes(self, py_files: List[Path], repo_root: Path):
        """Pass 1: Parse all files, extract module/class/function nodes and register symbols."""
        for file_path in py_files:
            try:
                source = file_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(file_path))
            except Exception as e:
                print(f"[!] Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
                continue

            self.file_trees[file_path] = tree
            self.file_sources[file_path] = source

            rel_path = file_path.relative_to(repo_root) if file_path.is_relative_to(repo_root) else file_path
            module_dotpath = self.compute_module_dotpath(file_path, repo_root)
            self.file_module_paths[file_path] = module_dotpath

            module_coord = f"node://code/{rel_path}"
            self.module_registry[module_dotpath] = module_coord

            # Module docstring and summary
            mod_doc = get_docstring_first_line(tree)
            line_count = len(source.splitlines())
            mod_summary = f"module {rel_path} ({line_count} lines)"
            if mod_doc:
                mod_summary += f" — {mod_doc}"
            self.nodes[module_coord] = ("module", truncate_summary(mod_summary), source)

            # Traverse top-level classes and functions
            for item in tree.body:
                if isinstance(item, ast.ClassDef):
                    self._extract_class(item, module_coord, module_dotpath, source)
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._extract_func(item, module_coord, module_dotpath, source, parent_class=None)

    def _extract_class(self, cls_node: ast.ClassDef, module_coord: str, module_dotpath: str, source: str):
        class_coord = f"{module_coord}:{cls_node.name}"
        doc = get_docstring_first_line(cls_node)
        bases = [ast.unparse(b) for b in cls_node.bases]
        base_str = f"({', '.join(bases)})" if bases else ""
        class_summary = f"class {cls_node.name}{base_str}"
        if doc:
            class_summary += f": {doc}"

        cls_source = ast.get_source_segment(source, cls_node) or ast.unparse(cls_node)
        self.nodes[class_coord] = ("class", truncate_summary(class_summary), cls_source)

        # Structural edge: module -> class
        self.edges.add((module_coord, class_coord, "structural"))

        # Register in symbol registry
        self.symbol_registry[(module_dotpath, cls_node.name)] = class_coord
        self.name_to_coords.setdefault(cls_node.name, []).append(class_coord)

        # Extract methods
        for item in cls_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_func(item, module_coord, module_dotpath, source, parent_class=cls_node.name)
                method_coord = f"{module_coord}:{cls_node.name}.{item.name}"
                # Structural edge: class -> method
                self.edges.add((class_coord, method_coord, "structural"))

    def _extract_func(
        self,
        fn_node: ast.AST,
        module_coord: str,
        module_dotpath: str,
        source: str,
        parent_class: Optional[str] = None,
    ):
        fn_name = fn_node.name  # type: ignore
        symbol_name = f"{parent_class}.{fn_name}" if parent_class else fn_name
        func_coord = f"{module_coord}:{symbol_name}"
        node_type = "method" if parent_class else "function"

        # Generate signature preview
        doc = get_docstring_first_line(fn_node)
        try:
            # Reconstruct def line without body
            args_unparsed = ast.unparse(fn_node.args)  # type: ignore
            returns_unparsed = f" -> {ast.unparse(fn_node.returns)}" if getattr(fn_node, "returns", None) else ""
            sig = f"def {fn_name}({args_unparsed}){returns_unparsed}"
        except Exception:
            sig = f"def {fn_name}(...)"

        summary_text = sig
        if doc:
            summary_text += f": {doc}"

        fn_source = ast.get_source_segment(source, fn_node) or ast.unparse(fn_node)
        self.nodes[func_coord] = (node_type, truncate_summary(summary_text), fn_source)

        if not parent_class:
            # Structural edge: module -> function
            self.edges.add((module_coord, func_coord, "structural"))

        # Register in symbol registry
        self.symbol_registry[(module_dotpath, symbol_name)] = func_coord
        if parent_class:
            self.symbol_registry[(module_dotpath, fn_name)] = func_coord
        self.name_to_coords.setdefault(fn_name, []).append(func_coord)

    def pass2_extract_edges(self, repo_root: Path):
        """Pass 2: Parse import statements and call graph invocations."""
        for file_path, tree in self.file_trees.items():
            rel_path = file_path.relative_to(repo_root) if file_path.is_relative_to(repo_root) else file_path
            module_coord = f"node://code/{rel_path}"
            module_dotpath = self.file_module_paths[file_path]
            imports: Dict[str, Tuple[str, Optional[str]]] = {}

            # 1. Collect imports
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        asname = alias.asname or alias.name
                        imports[asname] = (alias.name, None)
                        # Import edge: file -> imported module
                        if alias.name in self.module_registry:
                            self.edges.add((module_coord, self.module_registry[alias.name], "imports"))
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    # Handle relative imports
                    if node.level > 0:
                        parts = module_dotpath.split(".")
                        base_parts = parts[:-node.level] if len(parts) >= node.level else []
                        if mod:
                            base_parts.append(mod)
                        mod = ".".join(base_parts)

                    if mod in self.module_registry:
                        self.edges.add((module_coord, self.module_registry[mod], "imports"))

                    for alias in node.names:
                        asname = alias.asname or alias.name
                        imports[asname] = (mod, alias.name)

            self.file_imports[file_path] = imports

            # 2. Extract call graph edges from each function and method
            # Skip test files from static call_graph to keep production blast radius pure
            if len(rel_path.parts) > 0 and rel_path.parts[0] == "tests":
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    parent_cls = self._find_parent_class(tree, node)
                    caller_symbol = f"{parent_cls}.{node.name}" if parent_cls else node.name
                    caller_coord = f"{module_coord}:{caller_symbol}"

                    self._extract_calls_from_function(node, caller_coord, module_dotpath, imports, parent_cls)

    def _find_parent_class(self, tree: ast.AST, fn_node: ast.AST) -> Optional[str]:
        for item in tree.body:
            if isinstance(item, ast.ClassDef):
                if fn_node in item.body:
                    return item.name
        return None

    def _extract_calls_from_function(
        self,
        fn_node: ast.AST,
        caller_coord: str,
        module_dotpath: str,
        imports: Dict[str, Tuple[str, Optional[str]]],
        current_class: Optional[str] = None,
    ):
        for child in ast.walk(fn_node):
            if isinstance(child, ast.Call):
                target_coord = self._resolve_call(child.func, module_dotpath, imports, current_class)
                if target_coord and target_coord != caller_coord:
                    self.edges.add((caller_coord, target_coord, "call_graph"))

    def _resolve_call(
        self,
        func_expr: ast.AST,
        module_dotpath: str,
        imports: Dict[str, Tuple[str, Optional[str]]],
        current_class: Optional[str] = None,
    ) -> Optional[str]:
        # Case A: Direct function call `create_project(...)`
        if isinstance(func_expr, ast.Name):
            name = func_expr.id
            # 1. Check local file definitions first
            if (module_dotpath, name) in self.symbol_registry:
                return self.symbol_registry[(module_dotpath, name)]

            # 2. Check explicit imports
            if name in imports:
                target_mod, target_sym = imports[name]
                if target_sym:
                    if (target_mod, target_sym) in self.symbol_registry:
                        return self.symbol_registry[(target_mod, target_sym)]
                else:
                    if target_mod in self.module_registry:
                        return self.module_registry[target_mod]

            # 3. Heuristic: if name matches a unique known function in our codebase
            if name in self.name_to_coords:
                candidates = self.name_to_coords[name]
                if len(candidates) == 1:
                    return candidates[0]

        # Case B: Attribute call `sim_telemetry.init_sim_db(...)` or `self.some_method(...)`
        elif isinstance(func_expr, ast.Attribute):
            attr = func_expr.attr
            val = func_expr.value

            # self.method(...) or cls.method(...)
            if isinstance(val, ast.Name) and val.id in ("self", "cls") and current_class:
                candidate = f"{current_class}.{attr}"
                if (module_dotpath, candidate) in self.symbol_registry:
                    return self.symbol_registry[(module_dotpath, candidate)]

            # module.function(...)
            if isinstance(val, ast.Name):
                prefix = val.id
                if prefix in imports:
                    target_mod, _ = imports[prefix]
                    if (target_mod, attr) in self.symbol_registry:
                        return self.symbol_registry[(target_mod, attr)]

            # Chained calls e.g. core.sim_telemetry.init_sim_db(...)
            try:
                unparsed_val = ast.unparse(val)
                if unparsed_val in self.module_registry:
                    if (unparsed_val, attr) in self.symbol_registry:
                        return self.symbol_registry[(unparsed_val, attr)]
            except Exception:
                pass

        return None

    def save_to_db(self) -> Tuple[int, int]:
        """Commit all nodes and edges to SQLite."""
        conn = sqlite3.connect(str(self.db_path))
        with conn:
            conn.executemany(
                "INSERT OR REPLACE INTO substrate_nodes (coordinate, node_type, summary, body) VALUES (?, ?, ?, ?)",
                [(coord, n_type, summ, body) for coord, (n_type, summ, body) in self.nodes.items()],
            )
            conn.executemany(
                "INSERT INTO hyper_edges (source, target, lens) VALUES (?, ?, ?)",
                list(self.edges),
            )
        node_count = conn.execute("SELECT COUNT(*) FROM substrate_nodes").fetchone()[0]
        edge_count = conn.execute("SELECT COUNT(*) FROM hyper_edges").fetchone()[0]
        conn.close()
        return node_count, edge_count


def index_codebase(
    target_dirs: Optional[List[str]] = None,
    db_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    if repo_root is None:
        repo_root = Path.cwd().resolve()
    if db_path is None:
        db_path = repo_root / "code_substrate.db"

    if not target_dirs:
        # Default to core source directories and test directories if none provided
        candidates = ["core", "api", "server.py", "tests"]
        target_dirs = [c for c in candidates if (repo_root / c).exists()]

    targets = [(repo_root / p).resolve() if not Path(p).is_absolute() else Path(p) for p in target_dirs]

    indexer = CodebaseIndexer(db_path)
    indexer.init_db()

    py_files = indexer.discover_files(targets)
    indexer.pass1_extract_nodes(py_files, repo_root)
    indexer.pass2_extract_edges(repo_root)
    node_count, edge_count = indexer.save_to_db()

    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Count edges by lens
    conn = sqlite3.connect(str(db_path))
    lens_counts = dict(
        conn.execute("SELECT lens, COUNT(*) FROM hyper_edges GROUP BY lens").fetchall()
    )
    conn.close()

    result = {
        "status": "success",
        "db_path": str(db_path),
        "files_scanned": len(py_files),
        "nodes_indexed": node_count,
        "edges_indexed": edge_count,
        "lens_counts": lens_counts,
        "indexing_time_ms": round(elapsed_ms, 2),
    }
    return result


if __name__ == "__main__":
    args = sys.argv[1:]
    target_list = None
    if args:
        target_list = [a for a in args if not a.startswith("--")]

    res = index_codebase(target_dirs=target_list)
    print("=" * 65)
    print("CODEBASE RELATIONAL SUBSTRATE INDEXER")
    print("=" * 65)
    print(f"Database:      {res['db_path']}")
    print(f"Files Scanned: {res['files_scanned']}")
    print(f"Nodes Indexed: {res['nodes_indexed']}")
    print(f"Edges Indexed: {res['edges_indexed']}")
    print(f"Lens Breakdown: {res['lens_counts']}")
    print(f"Indexing Time: {res['indexing_time_ms']} ms")
    print("=" * 65)
