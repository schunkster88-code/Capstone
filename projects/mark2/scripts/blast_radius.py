"""
id: blast_radius
name: Blast Radius
description: Bundled Python simulation routine
default_params: {}
"""

import sqlite3
import sys
from pathlib import Path

target_coord = sys.argv[1] if len(sys.argv) > 1 else "node://code/mark/core/engine/run_task"
lens_filter = sys.argv[2] if len(sys.argv) > 2 else "call_graph"

db_path = Path(__file__).resolve().parent.parent / "project.db"
conn = sqlite3.connect(str(db_path))

query = """
WITH RECURSIVE blast_radius(step_node, impacted_caller, relation, lens, depth, path) AS (
    -- Anchor: Find immediate inbound callers / dependents of the target symbol
    SELECT e.target_coordinate, e.source_coordinate, e.edge_type, e.lens, 1,
           e.target_coordinate || ' <-[' || e.edge_type || ':' || e.lens || ']- ' || e.source_coordinate
    FROM hyper_edges e
    WHERE e.target_coordinate = ?
      AND (? = 'all' OR e.lens = ?)
    
    UNION ALL
    
    -- Recursive: Trace callers of the callers
    SELECT b.impacted_caller, e.source_coordinate, e.edge_type, e.lens, b.depth + 1,
           b.path || ' <-[' || e.edge_type || ':' || e.lens || ']- ' || e.source_coordinate
    FROM hyper_edges e
    JOIN blast_radius b ON e.target_coordinate = b.impacted_caller
    WHERE b.depth < 10
      AND (? = 'all' OR e.lens = ?)
)
SELECT b.depth, b.impacted_caller, n.domain, n.title, b.relation, b.lens, b.path
FROM blast_radius b
JOIN substrate_nodes n ON b.impacted_caller = n.coordinate
ORDER BY b.depth ASC;
"""

rows = conn.execute(query, (target_coord, lens_filter, lens_filter, lens_filter, lens_filter)).fetchall()

print(f"=== BLAST RADIUS IMPACT ANALYSIS FOR: {target_coord} ===")
print(f"Lens Filter: {lens_filter}")
print(f"Total Impacted Upstream Symbols: {len(rows)}")
print("-" * 75)
for depth, caller, domain, title, rel, lens, path in rows:
    print(f"[Depth {depth}] ({domain}) {title} [{caller}]")
    print(f"  Causal Lineage: {path}")

conn.close()
