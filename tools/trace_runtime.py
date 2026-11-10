# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

"""
Runtime Call Tracer for Relational Substrate.
Captures dynamic runtime dispatch edges using sys.setprofile / threading.setprofile
during test execution and writes them into code_substrate.db under lens = 'runtime_trace'.

Usage:
  python tools/trace_runtime.py
  python tools/trace_runtime.py --tests tests/test_void.py tests/test_projects.py
  python tools/trace_runtime.py --dry-run
"""

import argparse
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import pytest


class RuntimeTracer:
    def __init__(self, db_path: Optional[Path] = None, repo_root: Optional[Path] = None):
        if repo_root is None:
            repo_root = Path.cwd().resolve()
        self.repo_root = repo_root

        if db_path is None:
            db_path = repo_root / "code_substrate.db"
        self.db_path = db_path

        self.known_nodes: Set[str] = set()
        self.static_call_edges: Set[Tuple[str, str]] = set()
        self.captured_edges: Set[Tuple[str, str]] = set()
        self.call_count: int = 0
        self.current_test: Optional[str] = None

        self._load_substrate_metadata()

    def _load_substrate_metadata(self):
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Substrate database not found at {self.db_path}. Run tools/map_codebase.py first."
            )

        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")

        # Load all valid coordinates
        for row in conn.execute("SELECT coordinate FROM substrate_nodes"):
            self.known_nodes.add(row[0])

        # Load existing static call_graph edges
        for row in conn.execute("SELECT source, target FROM hyper_edges WHERE lens = 'call_graph'"):
            self.static_call_edges.add((row[0], row[1]))

        conn.close()

    def _resolve_frame_to_coord(self, frame) -> Optional[str]:
        if not frame:
            return None

        code = getattr(frame, "f_code", None)
        if not code:
            return None

        fn = getattr(code, "co_filename", "")
        if not fn:
            return None

        try:
            rel = str(Path(fn).resolve().relative_to(self.repo_root))
        except (ValueError, OSError):
            return None

        # Filter strictly to core/, api/, server.py, and tests/
        if not (rel.startswith("core/") or rel.startswith("api/") or rel == "server.py" or rel.startswith("tests/")):
            return None

        func_name = code.co_name
        if func_name in ("<lambda>", "<listcomp>", "<dictcomp>", "<setcomp>", "<genexpr>"):
            # Try resolving to enclosing caller
            parent = frame.f_back
            if parent:
                parent_code = getattr(parent, "f_code", None)
                if parent_code and parent_code.co_filename == fn:
                    func_name = parent_code.co_name

        if func_name == "<module>":
            mod_coord = f"node://code/{rel}"
            return mod_coord if mod_coord in self.known_nodes else None

        # Check if method on self or cls
        f_locals = getattr(frame, "f_locals", {})
        if "self" in f_locals:
            cls_name = type(f_locals["self"]).__name__
            method_coord = f"node://code/{rel}:{cls_name}.{func_name}"
            if method_coord in self.known_nodes:
                return method_coord

        if "cls" in f_locals and isinstance(f_locals["cls"], type):
            cls_name = f_locals["cls"].__name__
            method_coord = f"node://code/{rel}:{cls_name}.{func_name}"
            if method_coord in self.known_nodes:
                return method_coord

        func_coord = f"node://code/{rel}:{func_name}"
        if func_coord in self.known_nodes:
            return func_coord

        # Fallback to module coordinate if function itself is an unindexed inner helper
        mod_coord = f"node://code/{rel}"
        if mod_coord in self.known_nodes:
            return mod_coord

        return None

    def trace_profile(self, frame, event: str, arg):
        if event == "call":
            self.call_count += 1
            code = getattr(frame, "f_code", None)
            if code:
                fn = getattr(code, "co_filename", "")
                name = getattr(code, "co_name", "")
                if "tests/" in fn and name.startswith("test_"):
                    test_coord = self._resolve_frame_to_coord(frame)
                    if test_coord:
                        self.current_test = test_coord

            callee_coord = self._resolve_frame_to_coord(frame)
            if callee_coord and not callee_coord.startswith("node://code/tests/"):
                # Walk up call stack to find nearest caller inside our monitored application domain
                curr = frame.f_back
                caller_coord = None
                while curr:
                    caller_coord = self._resolve_frame_to_coord(curr)
                    if caller_coord and caller_coord != callee_coord:
                        self.captured_edges.add((caller_coord, callee_coord))
                        break
                    curr = curr.f_back

                # If no direct caller found in thread stack (e.g. AnyIO worker thread), bridge to current active test
                if not caller_coord and self.current_test:
                    self.captured_edges.add((self.current_test, callee_coord))
        return self.trace_profile

    def run_tests_and_trace(self, test_targets: Optional[List[str]] = None) -> int:
        if not test_targets:
            # Default to all test files in tests/ directory
            test_dir = self.repo_root / "tests"
            test_targets = sorted(
                str(p.relative_to(self.repo_root))
                for p in test_dir.glob("test_*.py")
            )

        # Install profiling hook in main thread and background threads
        sys.setprofile(self.trace_profile)
        threading.setprofile(self.trace_profile)

        pytest_args = ["-q", "--disable-warnings"] + test_targets
        t0 = time.perf_counter()
        exit_code = pytest.main(pytest_args)
        elapsed_sec = time.perf_counter() - t0

        # Uninstall profiling hook
        sys.setprofile(None)
        threading.setprofile(None)

        return exit_code

    def save_edges_to_db(self) -> Tuple[int, int]:
        """Save captured runtime edges into hyper_edges under lens = 'runtime_trace'.
        Returns (total_saved, new_edges_count).
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")

        # Delete old runtime_trace edges before inserting fresh trace
        conn.execute("DELETE FROM hyper_edges WHERE lens = 'runtime_trace'")

        insert_rows = [
            (source, target, "runtime_trace")
            for source, target in self.captured_edges
        ]

        conn.executemany(
            "INSERT OR IGNORE INTO hyper_edges (source, target, lens) VALUES (?, ?, ?)",
            insert_rows,
        )
        conn.commit()

        # Count how many are completely invisible in call_graph
        new_dynamic_edges = [
            (s, t) for s, t in self.captured_edges if (s, t) not in self.static_call_edges
        ]

        total_saved = len(self.captured_edges)
        conn.close()
        return total_saved, len(new_dynamic_edges)


def main():
    parser = argparse.ArgumentParser(description="Trace runtime function calls and record runtime_trace lens.")
    parser.add_argument("--tests", nargs="*", help="Pytest target files or directories")
    parser.add_argument("--dry-run", action="store_true", help="Print edges without writing to database")
    parser.add_argument("--db", type=str, default="code_substrate.db", help="Path to code_substrate.db")
    args = parser.parse_args()

    repo_root = Path.cwd().resolve()
    db_path = (repo_root / args.db).resolve()

    tracer = RuntimeTracer(db_path=db_path, repo_root=repo_root)

    print("=" * 75)
    print("RUNTIME TRACE CAPTURE ENGINE")
    print(f"Target Substrate DB: {db_path.name}")
    print(f"Known Substrate Nodes: {len(tracer.known_nodes)}")
    print(f"Existing Static Call Edges: {len(tracer.static_call_edges)}")
    print("-" * 75)

    test_targets = args.tests if args.tests else None
    t0 = time.perf_counter()
    exit_code = tracer.run_tests_and_trace(test_targets=test_targets)
    elapsed = time.perf_counter() - t0

    print("-" * 75)
    print(f"Pytest Execution Finished (Exit Code: {exit_code}, Elapsed: {elapsed:.2f}s)")
    print(f"Total Call Events Processed: {tracer.call_count}")
    print(f"Unique Runtime Call Edges Captured: {len(tracer.captured_edges)}")

    new_dynamic_edges = [
        (s, t) for s, t in tracer.captured_edges if (s, t) not in tracer.static_call_edges
    ]
    overlap_edges = [
        (s, t) for s, t in tracer.captured_edges if (s, t) in tracer.static_call_edges
    ]

    print(f"  * Overlapping with Static AST (Verified at runtime): {len(overlap_edges)}")
    print(f"  * Invisible Edges Recovered (Dynamic dispatch only): {len(new_dynamic_edges)}")
    print("-" * 75)

    if not args.dry_run:
        total_saved, new_count = tracer.save_edges_to_db()
        print(f"Successfully committed {total_saved} edges to code_substrate.db (lens = 'runtime_trace')")
    else:
        print("[Dry Run] Database was not modified.")

    print("\nRecovered Invisible Dynamic Edges Sample:")
    for s, t in sorted(new_dynamic_edges)[:15]:
        print(f"  [dynamic:runtime_trace] {s} -> {t}")
    if len(new_dynamic_edges) > 15:
        print(f"  ... and {len(new_dynamic_edges) - 15} more dynamic edges.")
    print("=" * 75)


if __name__ == "__main__":
    main()
