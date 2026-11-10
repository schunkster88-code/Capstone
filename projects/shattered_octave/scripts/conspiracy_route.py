"""
Find multi-hop conspiracy routes between two nodes across dramatic and spatial lenses.
Usage: python scripts/conspiracy_route.py [source] [target]
Default: morwen -> vaelen
"""
import sqlite3
import sys
from pathlib import Path

source = sys.argv[1] if len(sys.argv) > 1 else "node://character/morwen"
target = sys.argv[2] if len(sys.argv) > 2 else "node://character/vaelen"
db_path = Path(__file__).resolve().parent.parent / "project.db"

conn = sqlite3.connect(str(db_path))

query = """
WITH RECURSIVE conspiracy_route(step_node, target, path, edge_types, depth) AS (
    SELECT source_coordinate, target_coordinate, 
           source_coordinate || ' -> ' || target_coordinate,
           edge_type,
           1
    FROM hyper_edges 
    WHERE source_coordinate = ? AND lens IN ('dramatic', 'spatial')
    UNION ALL
    SELECT e.source_coordinate, e.target_coordinate, 
           c.path || ' -> ' || e.target_coordinate,
           c.edge_types || ' -> ' || e.edge_type,
           c.depth + 1
    FROM hyper_edges e
    JOIN conspiracy_route c ON e.source_coordinate = c.target
    WHERE c.depth < 4 AND e.lens IN ('dramatic', 'spatial')
)
SELECT path, edge_types, depth 
FROM conspiracy_route 
WHERE target = ?;
"""

rows = conn.execute(query, (source, target)).fetchall()

print(f"=== CONSPIRACY ROUTES FROM {source} TO {target} ===")
if not rows:
    print("No route found within depth limit.")
for path, types, depth in rows:
    print(f"Path (depth {depth}): {path}")
    print(f"  Edge types: {types}")

conn.close()

