# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

import re
import sqlite3
from typing import Any, Dict, List, Optional

SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class CognitiveWorkbench:
    """Deterministic SQLite externalization sandbox with savepoint branching and LRU eviction."""

    def __init__(self, db_path: str = ":memory:", max_active_nodes: int = 30) -> None:
        self.db_path = db_path
        self.max_active_nodes = max_active_nodes
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.execute("PRAGMA busy_timeout = 2000;")

    def _validate_identifier(self, name: str) -> str:
        if not SAFE_IDENTIFIER.match(name):
            raise ValueError(f"Invalid SQLite savepoint identifier: {name}")
        return name

    def branch_savepoint(self, name: str) -> str:
        """Create a transactional savepoint for transfactual hypothesis testing."""
        sp = self._validate_identifier(name)
        self.conn.execute(f"SAVEPOINT {sp};")
        return sp

    def rollback_savepoint(self, name: str) -> str:
        """Revert failed experimental mutations back to the named savepoint with zero residue."""
        sp = self._validate_identifier(name)
        self.conn.execute(f"ROLLBACK TO SAVEPOINT {sp};")
        self.conn.execute(f"RELEASE SAVEPOINT {sp};")
        return sp

    def release_savepoint(self, name: str) -> str:
        """Commit a verified experimental branch into the active substrate state."""
        sp = self._validate_identifier(name)
        self.conn.execute(f"RELEASE SAVEPOINT {sp};")
        return sp

    def mutate_substrate(self, sql_batch: str) -> Dict[str, Any]:
        """Execute DDL/DML mutations while forbidding autonomous trigger creation."""
        if "CREATE TRIGGER" in sql_batch.upper():
            raise PermissionError("Autonomous SQL triggers are forbidden in the passive workbench.")
        self.conn.executescript(sql_batch)
        return self.enforce_working_memory_cap()

    def query_lens(self, origin_key: Optional[str] = None, custom_select: Optional[str] = None) -> List[Dict[str, Any]]:
        """Traverse v_context_horizon_canonical or execute a read-only diagnostic lens."""
        cur = self.conn.cursor()
        if origin_key:
            cur.execute(
                """
                SELECT origin, reachable_concept, category, min_depth, max_conductance, unique_path_permutations
                FROM v_context_horizon_canonical
                WHERE origin = ?
                ORDER BY max_conductance DESC;
                """,
                (origin_key,),
            )
        elif custom_select:
            if not custom_select.lstrip().upper().startswith(("SELECT", "WITH")):
                raise PermissionError("query_lens permits read-only SELECT or WITH queries only.")
            cur.execute(custom_select)
        else:
            cur.execute("SELECT * FROM v_substrate_health;")
        return [dict(row) for row in cur.fetchall()]

    def enforce_working_memory_cap(self, epoch_number: int = 3) -> Dict[str, int]:
        """Evict lowest-salience working nodes to epoch_archive when active count exceeds max_active_nodes."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM memories;")
        active_count = cur.fetchone()["cnt"]
        evicted = 0

        if active_count > self.max_active_nodes:
            overflow = active_count - self.max_active_nodes
            cur.execute(
                """
                SELECT key FROM memories
                WHERE category NOT IN ('invariant', 'semantic_landmark')
                ORDER BY access_count ASC, rowid ASC
                LIMIT ?;
                """,
                (overflow,),
            )
            evict_keys = [r["key"] for r in cur.fetchall()]
            for key in evict_keys:
                cur.execute(
                    """
                    INSERT INTO epoch_archive (epoch_number, original_key, category, value, final_access_count)
                    SELECT ?, key, category, value, access_count FROM memories WHERE key = ?;
                    """,
                    (epoch_number, key),
                )
                cur.execute("DELETE FROM memory_edges WHERE source_key = ? OR target_key = ?;", (key, key))
                cur.execute("DELETE FROM memories WHERE key = ?;", (key,))
                evicted += 1
            self.conn.commit()

        return {"active_nodes": active_count - evicted, "evicted_nodes": evicted}

    def crystallize_invariant(
        self,
        axiom_id: str,
        statement: str,
        crystallized_from: str,
        prune_keys: Optional[List[str]] = None,
        epoch_number: int = 3,
    ) -> Dict[str, Any]:
        """Commit a proven invariant to the vault and archive temporary experimental scaffolding."""
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO system_invariants (id, statement, crystallized_from, confidence)
            VALUES (?, ?, ?, 1.0);
            """,
            (axiom_id, statement, crystallized_from),
        )
        for key in (prune_keys or []):
            cur.execute(
                """
                INSERT INTO epoch_archive (epoch_number, original_key, category, value, final_access_count)
                SELECT ?, key, category, value, access_count FROM memories WHERE key = ?;
                """,
                (epoch_number, key),
            )
            cur.execute("DELETE FROM memory_edges WHERE source_key = ? OR target_key = ?;", (key, key))
            cur.execute("DELETE FROM memories WHERE key = ?;", (key,))
        self.conn.commit()
        cap_state = self.enforce_working_memory_cap(epoch_number=epoch_number)
        return {
            "crystallized": axiom_id,
            "archived_scaffolding": len(prune_keys or []),
            "active_nodes": cap_state["active_nodes"],
        }

