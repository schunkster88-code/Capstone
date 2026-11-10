"""
Causal Fault Triangulation Tool.
Identifies the single root-cause function when multiple disparate test suites fail
by computing the recursive downstream callee set intersection across multi-lens edges
('call_graph', 'runtime_trace') on code_substrate.db.

Usage:
  python tools/triangulate_fault.py <test_coord_1> <test_coord_2> <test_coord_3>
  python tools/triangulate_fault.py <test_coord_1> <test_coord_2> --fetch-body
  python tools/triangulate_fault.py <test_coord_1> <test_coord_2> --culprit-only
  python tools/triangulate_fault.py <test_coord_1> <test_coord_2> --json
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def triangulate_fault(
    failing_test_coords: List[str],
    db_path: Optional[Path] = None,
    fetch_body: bool = False,
    max_depth: int = 15,
) -> Dict[str, Any]:
    if db_path is None:
        db_path = Path.cwd() / "code_substrate.db"

    if not db_path.exists():
        raise FileNotFoundError(
            f"Substrate database not found at {db_path}. Run tools/map_codebase.py first."
        )

    if not failing_test_coords:
        raise ValueError("At least one failing test coordinate is required for triangulation.")

    # Deduplicate while preserving order
    test_roots = list(dict.fromkeys(failing_test_coords))
    total_roots = len(test_roots)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode = WAL;")

    # Verify test roots exist in substrate_nodes
    placeholders = ",".join("?" for _ in test_roots)
    found_rows = conn.execute(
        f"SELECT coordinate FROM substrate_nodes WHERE coordinate IN ({placeholders})",
        test_roots,
    ).fetchall()
    found_coords = {r[0] for r in found_rows}

    missing_coords = [c for c in test_roots if c not in found_coords]
    if missing_coords:
        conn.close()
        raise ValueError(f"Test coordinate(s) not found in substrate_nodes: {missing_coords}")

    # Downstream recursive CTE with cycle prevention and callee intersection
    query = f"""
    WITH RECURSIVE downstream(root, target, depth, path) AS (
        -- Anchor: Immediate downstream callees of each failing test root
        SELECT e.source AS root, e.target AS target, 1 AS depth, e.source || ' -> ' || e.target AS path
        FROM hyper_edges e
        WHERE e.source IN ({placeholders}) AND e.lens IN ('call_graph', 'runtime_trace')
        
        UNION ALL
        
        -- Recursive Step: Downstream callees of the discovered targets
        SELECT d.root, e.target, d.depth + 1, d.path || ' -> ' || e.target
        FROM hyper_edges e
        JOIN downstream d ON e.source = d.target
        WHERE e.lens IN ('call_graph', 'runtime_trace')
          AND d.depth < ?
          AND instr(d.path, e.target) = 0
    )
    SELECT 
        d.target,
        COUNT(DISTINCT d.root) AS root_hits,
        MAX(d.depth) AS max_depth,
        MIN(d.depth) AS min_depth,
        ROUND(AVG(d.depth), 2) AS avg_depth,
        n.node_type,
        n.summary,
        n.body
    FROM downstream d
    JOIN substrate_nodes n ON d.target = n.coordinate
    GROUP BY d.target
    HAVING root_hits = ?
    ORDER BY max_depth DESC, min_depth DESC;
    """

    params = test_roots + [max_depth, total_roots]

    t0 = time.perf_counter()
    rows = conn.execute(query, params).fetchall()
    elapsed_ms = (time.perf_counter() - t0) * 1000

    conn.close()

    candidates: List[Dict[str, Any]] = []
    for rank, (target, root_hits, max_d, min_d, avg_d, node_type, summary, body) in enumerate(rows, 1):
        candidates.append({
            "rank": rank,
            "coordinate": target,
            "root_hits": root_hits,
            "max_depth": max_d,
            "min_depth": min_d,
            "avg_depth": avg_d,
            "node_type": node_type,
            "summary": summary,
            "body": body if fetch_body else None,
            "body_char_length": len(body or ""),
            "body_tokens_estimate": round(len(body or "") / 4.0, 1),
        })

    culprit = candidates[0] if candidates else None

    return {
        "failing_tests": test_roots,
        "failing_test_count": total_roots,
        "query_latency_ms": round(elapsed_ms, 3),
        "total_intersection_candidates": len(candidates),
        "culprit": culprit,
        "candidates": candidates,
    }


def main():
    parser = argparse.ArgumentParser(description="Triangulate causal fault across failing test coordinates.")
    parser.add_argument("test_coords", nargs="+", help="Failing test coordinates from substrate_nodes")
    parser.add_argument("--db", type=str, default="code_substrate.db", help="Path to SQLite substrate database")
    parser.add_argument("--max-depth", type=int, default=15, help="Maximum recursive downstream traversal depth")
    parser.add_argument("--fetch-body", action="store_true", help="Fetch complete source body of candidate nodes")
    parser.add_argument("--culprit-only", action="store_true", help="Output only the #1 culprit coordinate")
    parser.add_argument("--json", action="store_true", help="Output full results as JSON")
    args = parser.parse_args()

    db_path = (Path.cwd() / args.db).resolve()

    try:
        res = triangulate_fault(
            failing_test_coords=args.test_coords,
            db_path=db_path,
            fetch_body=args.fetch_body or args.culprit_only,
            max_depth=args.max_depth,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.culprit_only:
        if res["culprit"]:
            print(res["culprit"]["coordinate"])
        else:
            print("NO_INTERSECTION_FOUND", file=sys.stderr)
            sys.exit(1)
        return

    if args.json:
        print(json.dumps(res, indent=2))
        return

    print("=" * 80)
    print("CAUSAL FAULT TRIANGULATION ENGINE")
    print(f"Substrate Database: {db_path.name}")
    print(f"Query Execution Latency: {res['query_latency_ms']} ms")
    print("-" * 80)
    print(f"Input Failing Test Roots ({res['failing_test_count']}):")
    for t in res["failing_tests"]:
        print(f"  [!] {t}")
    print("-" * 80)
    print(f"Downstream Callee Intersection Candidates: {res['total_intersection_candidates']}")

    if not res["candidates"]:
        print("No common downstream callee intersection found across all failing tests.")
        print("=" * 80)
        return

    print("\nIntersection Candidates Ranked by Downstream Call Depth:")
    for c in res["candidates"]:
        print(f"  #{c['rank']:2d} [MaxD={c['max_depth']}, MinD={c['min_depth']}] ({c['node_type']}) {c['coordinate']}")
        print(f"      Summary: {c['summary']}")

    culprit = res["culprit"]
    print("-" * 80)
    print("TRIANGULATED ROOT-CAUSE CULPRIT (#1 CANDIDATE):")
    print(f"Coordinate:    {culprit['coordinate']}")
    print(f"Node Type:     {culprit['node_type']}")
    print(f"Max Depth:     {culprit['max_depth']} hops downstream")
    print(f"Min Depth:     {culprit['min_depth']} hops downstream")
    print(f"Token Budget:  {culprit['body_tokens_estimate']} tokens (Body: {culprit['body_char_length']} chars)")
    print(f"Summary:       {culprit['summary']}")
    if args.fetch_body and culprit["body"]:
        print("\nCulprit Source Code Body (Surgical Inspection):")
        print("-" * 40)
        print(culprit["body"])
        print("-" * 40)
    print("=" * 80)


if __name__ == "__main__":
    main()
