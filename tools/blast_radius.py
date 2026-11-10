# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

"""
Upstream Blast Radius Tool (Multiplex Lens Support).
Traces all upstream callers that depend on a target function/method
by executing a reverse recursive Common Table Expression (CTE)
on hyper_edges across single or multiple lenses (e.g. 'call_graph', 'runtime_trace').

Usage:
  python tools/blast_radius.py "node://code/core/project_manager.py:create_project"
  python tools/blast_radius.py "node://code/core/void_engine.py:handle_create_project_cmd" --multiplex
  python tools/blast_radius.py "node://code/core/void_engine.py:handle_create_project_cmd" --lens call_graph,runtime_trace
  python tools/blast_radius.py "node://code/core/void_engine.py:handle_create_project_cmd" --multiplex --fetch-bodies --json
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def trace_upstream_blast_radius(
    target_coord: str,
    db_path: Optional[Path] = None,
    fetch_bodies: bool = False,
    max_depth: int = 10,
    lenses: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if db_path is None:
        db_path = Path.cwd() / "code_substrate.db"

    if not db_path.exists():
        raise FileNotFoundError(
            f"Substrate database not found at {db_path}. Run tools/map_codebase.py first."
        )

    if lenses is None or len(lenses) == 0:
        lenses = ["call_graph"]

    # Deduplicate while preserving order
    lenses = list(dict.fromkeys(lenses))

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode = WAL;")

    # Check target node exists
    target_row = conn.execute(
        "SELECT coordinate, node_type, summary, body FROM substrate_nodes WHERE coordinate = ?",
        (target_coord,),
    ).fetchone()

    if not target_row:
        conn.close()
        raise ValueError(f"Target coordinate '{target_coord}' not found in substrate_nodes.")

    target_info = {
        "coordinate": target_row[0],
        "node_type": target_row[1],
        "summary": target_row[2],
        "body": target_row[3] if fetch_bodies else None,
    }

    placeholders = ",".join("?" for _ in lenses)

    # Reverse recursive CTE: trace callers of the target across specified lenses
    # instr(b.path, e.source) = 0 guarantees cycle prevention
    query = f"""
    WITH RECURSIVE blast_radius(source, target, lens, depth, path) AS (
        -- Anchor: Immediate callers of target
        SELECT e.source, e.target, e.lens, 1, e.source || ' -[' || e.lens || ']-> ' || e.target
        FROM hyper_edges e
        WHERE e.target = ? AND e.lens IN ({placeholders})
        
        UNION ALL
        
        -- Recursive Step: Callers that call the discovered sources
        SELECT e.source, e.target, e.lens, b.depth + 1, e.source || ' -[' || e.lens || ']-> ' || b.path
        FROM hyper_edges e
        JOIN blast_radius b ON e.target = b.source
        WHERE e.lens IN ({placeholders}) AND b.depth < ? AND instr(b.path, e.source) = 0
    )
    SELECT b.depth, b.source, n.node_type, n.summary, n.body, b.lens, b.path
    FROM blast_radius b
    JOIN substrate_nodes n ON b.source = n.coordinate
    ORDER BY b.depth ASC, b.source ASC;
    """

    params = [target_coord] + lenses + lenses + [max_depth]
    rows = conn.execute(query, params).fetchall()
    conn.close()

    callers_map: Dict[str, Dict[str, Any]] = {}
    provenance_map: Dict[str, Set[str]] = {}

    for depth, source, node_type, summary, body, lens, path in rows:
        provenance_map.setdefault(source, set()).add(lens)
        if source not in callers_map or depth < callers_map[source]["depth"]:
            callers_map[source] = {
                "depth": depth,
                "coordinate": source,
                "node_type": node_type,
                "summary": summary,
                "body": body if fetch_bodies else None,
                "path": path,
                "lens": lens,
            }

    # Format callers with provenance tags
    formatted_callers: List[Dict[str, Any]] = []
    for source in sorted(callers_map.keys(), key=lambda s: (callers_map[s]["depth"], s)):
        caller = callers_map[source]
        prov_set = provenance_map[source]
        if "call_graph" in prov_set and "runtime_trace" in prov_set:
            prov_tag = "multiplex:verified"
        elif "runtime_trace" in prov_set:
            prov_tag = "dynamic:runtime_trace"
        elif "call_graph" in prov_set:
            prov_tag = "static:call_graph"
        else:
            prov_tag = f"lens:{list(prov_set)[0]}"

        caller["provenance"] = prov_tag
        caller["lenses_discovered"] = sorted(list(prov_set))
        formatted_callers.append(caller)

    # Summary and token estimates
    total_summary_chars = sum(len(c["summary"]) for c in formatted_callers) + len(target_info["summary"])
    total_body_chars = (
        sum(len(c["body"]) for c in formatted_callers if c["body"]) + len(target_info["body"] or "")
        if fetch_bodies
        else 0
    )

    return {
        "target": target_info,
        "lenses_queried": lenses,
        "multiplex_mode": len(lenses) > 1,
        "upstream_count": len(formatted_callers),
        "upstream_callers": formatted_callers,
        "token_estimate": {
            "summary_tokens": round(total_summary_chars / 4.0, 1),
            "body_tokens": round(total_body_chars / 4.0, 1),
            "total_tokens": round((total_summary_chars + total_body_chars) / 4.0, 1),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Upstream blast radius with multiplex lens support.")
    parser.add_argument("target", help="Target node coordinate (e.g. node://code/core/void_engine.py:handle_create_project_cmd)")
    parser.add_argument("--lens", type=str, default=None, help="Comma-separated lenses to query (e.g. call_graph or call_graph,runtime_trace)")
    parser.add_argument("--multiplex", action="store_true", help="Query across both static (call_graph) and dynamic (runtime_trace) lenses")
    parser.add_argument("--fetch-bodies", action="store_true", help="Fetch complete node source bodies")
    parser.add_argument("--json", action="store_true", help="Output results formatted as JSON")
    parser.add_argument("--db", type=str, default="code_substrate.db", help="Path to SQLite substrate database")
    parser.add_argument("--max-depth", type=int, default=10, help="Maximum traversal depth")
    args = parser.parse_args()

    lenses: List[str]
    if args.multiplex:
        lenses = ["call_graph", "runtime_trace"]
    elif args.lens:
        lenses = [l.strip() for l in args.lens.split(",") if l.strip()]
    else:
        lenses = ["call_graph"]

    db_path = (Path.cwd() / args.db).resolve()

    try:
        res = trace_upstream_blast_radius(
            target_coord=args.target,
            db_path=db_path,
            fetch_bodies=args.fetch_bodies,
            max_depth=args.max_depth,
            lenses=lenses,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(res, indent=2))
        return

    mode_str = "MULTIPLEX" if res["multiplex_mode"] else "SINGLE-LENS"
    print("=" * 75)
    print(f"UPSTREAM BLAST RADIUS ANALYSIS [{mode_str} MODE]")
    print(f"Target:   {res['target']['coordinate']} ({res['target']['node_type']})")
    print(f"Summary:  {res['target']['summary']}")
    print(f"Lenses:   {', '.join(res['lenses_queried'])}")
    print("-" * 75)
    print(f"Discovered {res['upstream_count']} upstream dependent callers:")
    for c in res["upstream_callers"]:
        tag = f"[{c['provenance']}]"
        print(f"[Depth {c['depth']}] {tag:<24} {c['coordinate']} ({c['node_type']})")
        print(f"  Summary: {c['summary']}")
        print(f"  Lineage: {c['path']}")
    print("-" * 75)
    print(
        f"Token Budget: Summaries={res['token_estimate']['summary_tokens']} tokens | "
        f"Bodies={res['token_estimate']['body_tokens']} tokens | "
        f"Total={res['token_estimate']['total_tokens']} tokens"
    )
    print("=" * 75)


if __name__ == "__main__":
    main()
