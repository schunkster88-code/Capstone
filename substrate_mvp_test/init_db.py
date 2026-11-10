# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

"""Database initializer for SQLite WAL relational hypergraph substrate."""

import sqlite3
from pathlib import Path


def init_database(db_path: Path, schema_file: Path = Path(__file__).parent / "schema.sql") -> sqlite3.Connection:
    """Initialize a clean SQLite WAL database with substrate schema and compound B-tree indexes."""
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    schema_sql = schema_file.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.commit()
    return conn


if __name__ == "__main__":
    db = Path(__file__).parent / "test_substrate.db"
    conn = init_database(db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall()]
    cur.execute("PRAGMA journal_mode;")
    journal_mode = cur.fetchone()[0]
    conn.close()
    print(f"Initialized {db.name}: Tables={tables}, JournalMode={journal_mode.upper()}")
