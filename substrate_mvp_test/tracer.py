# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

"""Recursive Common Table Expression (CTE) Upstream Dependency Tracer."""

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def trace_upstream_dependencies(
    target_coord: str,
    db_path: Path,
    max_depth: int = 3,
    lens: str = "call_graph",
    fetch_bodies: bool = False,
) -> Dict[str, Any]:
    """Execute a reverse recursive CTE across hyper_edges to locate all upstream callers up to max_depth."""
    t0 = time.perf_counter()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = conn.cursor()

    query = """
    WITH RECURSIVE upstream(source, target, lens, depth, path) AS (
        SELECT source, target, lens, 1, source || ' -[' || lens || ']-> ' || target
        FROM hyper_edges
        WHERE target = :target_coord
          AND lens = :lens
        UNION ALL
        SELECT e.source, e.target, e.lens, u.depth + 1,
               e.source || ' -[' || e.lens || ']-> ' || u.path
        FROM hyper_edges e
        JOIN upstream u ON e.target = u.source
        WHERE u.depth < :max_depth
          AND e.lens = :lens
          AND INSTR(u.path, e.source) = 0
    )
    SELECT DISTINCT source, depth, path
    FROM upstream
    ORDER BY depth ASC, source ASC;
    """

    cur.execute(query, {"target_coord": target_coord, "lens": lens, "max_depth": max_depth})
    raw_results = cur.fetchall()

    callers = []
    seen = set()
    for row in raw_results:
        src, depth, path = row[0], row[1], row[2]
        if src in seen:
            continue
        seen.add(src)

        # Retrieve node metadata
        cur.execute("SELECT summary, body FROM substrate_nodes WHERE coordinate = ?;", (src,))
        node_row = cur.fetchone()
        summary = node_row[0] if node_row else ""
        body = node_row[1] if (node_row and fetch_bodies) else ""

        callers.append({
            "coordinate": src,
            "depth": depth,
            "path": path,
            "summary": summary,
            "body": body,
        })

    conn.close()
    elapsed_ms = (time.perf_counter() - t0) * 1000

    return {
        "target": target_coord,
        "max_depth_configured": max_depth,
        "callers_found": callers,
        "total_callers": len(callers),
        "execution_latency_ms": elapsed_ms,
    }


if __name__ == "__main__":
    base = Path(__file__).parent
    db = base / "test_substrate.db"
    target = "node://code/storage/db.py:save_record"

    res = trace_upstream_dependencies(target, db, max_depth=3)
    print(f"\n3-Hop Upstream Dependency Trace for '{target}':")
    print(f"Latency: {res['execution_latency_ms']:.4f} ms | Callers Discovered: {res['total_callers']}")
    for c in res["callers_found"]:
        print(f"  [Hop {c['depth']}] {c['coordinate']}")
        print(f"         Path: {c['path']}")
        print(f"         Summary: {c['summary']}")
