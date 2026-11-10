"""
id: lens_navigator
name: Lens Navigator
description: Bundled Python simulation routine
default_params: {}
"""

import sqlite3
import sys
from pathlib import Path

coord = sys.argv[1] if len(sys.argv) > 1 else "node://code/mark/routers/flightdeck"
lens = sys.argv[2] if len(sys.argv) > 2 else "all"

db_path = Path(__file__).resolve().parent.parent / "project.db"
conn = sqlite3.connect(str(db_path))

node = conn.execute("SELECT coordinate, domain, title, state, summary, body FROM substrate_nodes WHERE coordinate = ?", (coord,)).fetchone()

if not node:
    print(f"Error: Node {coord} not found.")
    sys.exit(1)

print(f"=== SYMBOL METADATA: {node[0]} ===")
print(f"Title: {node[2]} ({node[1]}) | State: {node[3]}")
print(f"Summary: {node[4]}")
print(f"Body: {node[5]}")
print("-" * 75)

outbound_query = """
SELECT e.target_coordinate, e.edge_type, e.lens, e.weight, n.title, n.summary
FROM hyper_edges e
JOIN substrate_nodes n ON e.target_coordinate = n.coordinate
WHERE e.source_coordinate = ?
  AND (? = 'all' OR e.lens = ?);
"""
outbounds = conn.execute(outbound_query, (coord, lens, lens)).fetchall()

print(f"=== OUTBOUND RELATIONS (Lens: {lens}) ===")
if not outbounds:
    print("  (None)")
for target, edge_type, edge_lens, weight, title, summary in outbounds:
    print(f"  --[{edge_type}:{edge_lens} (w={weight})]--> {target} ({title})")
    print(f"     Preview: {summary}")

inbound_query = """
SELECT e.source_coordinate, e.edge_type, e.lens, e.weight, n.title, n.summary
FROM hyper_edges e
JOIN substrate_nodes n ON e.source_coordinate = n.coordinate
WHERE e.target_coordinate = ?
  AND (? = 'all' OR e.lens = ?);
"""
inbounds = conn.execute(inbound_query, (coord, lens, lens)).fetchall()

print(f"\n=== INBOUND DEPENDENTS / CALLERS (Lens: {lens}) ===")
if not inbounds:
    print("  (None)")
for source, edge_type, edge_lens, weight, title, summary in inbounds:
    print(f"  <--[{edge_type}:{edge_lens} (w={weight})]-- {source} ({title})")
    print(f"     Preview: {summary}")

conn.close()
