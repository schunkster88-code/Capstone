"""
Query Point-of-View Fog-of-War Horizon for a Character.
Usage: python scripts/fow_query.py [character_coord]
Default: node://character/kaelen
"""
import sqlite3
import sys
from pathlib import Path

target_coord = sys.argv[1] if len(sys.argv) > 1 else "node://character/kaelen"
db_path = Path(__file__).resolve().parent.parent / "project.db"

conn = sqlite3.connect(str(db_path))

query = """
WITH char_horizon AS (
    SELECT ? AS coord, 'self' AS relation, 'identity' AS lens
    UNION
    SELECT target_coordinate, edge_type, lens
    FROM hyper_edges
    WHERE source_coordinate = ? AND lens = 'epistemic'
    UNION
    SELECT target_coordinate, edge_type, lens
    FROM hyper_edges
    WHERE source_coordinate = ? AND lens = 'spatial'
    UNION
    SELECT target_coordinate, edge_type, lens
    FROM hyper_edges
    WHERE source_coordinate = ? AND lens = 'dramatic'
)
SELECT 
    h.coord,
    h.relation,
    h.lens,
    n.domain,
    CASE 
        WHEN h.coord = 'node://character/morwen' AND h.relation = 'believes_deceased'
        THEN 'Morwen (Deceased Sister)'
        ELSE n.title
    END AS perceived_title,
    CASE 
        WHEN h.coord = 'node://character/morwen' AND h.relation = 'believes_deceased'
        THEN 'deceased (presumed)'
        ELSE n.state
    END AS perceived_state,
    CASE 
        WHEN h.coord = 'node://character/morwen' AND h.relation = 'believes_deceased'
        THEN 'Exiled sister, believed dead in the Sump ten years ago.'
        ELSE n.summary
    END AS perceived_summary
FROM char_horizon h
JOIN substrate_nodes n ON h.coord = n.coordinate;
"""

rows = conn.execute(query, (target_coord, target_coord, target_coord, target_coord)).fetchall()

print(f"=== FOG-OF-WAR HORIZON FOR {target_coord} ===")
for r in rows:
    print(f"[{r[0]}] ({r[1]} via {r[2]}) {r[4]} (State: {r[5]}): {r[6]}")

conn.close()

