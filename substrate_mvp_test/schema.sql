-- Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
-- SPDX-License-Identifier: AGPL-3.0-only
-- Relational Hypergraph Substrate Schema

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS substrate_nodes (
    coordinate TEXT PRIMARY KEY, -- Canonical URI: node://code/module.py:symbol
    node_type  TEXT NOT NULL,    -- function, method, class, module
    summary    TEXT NOT NULL,    -- Compact OpenGraph signpost (< 30 tokens)
    body       TEXT NOT NULL     -- Source code slice
);

CREATE TABLE IF NOT EXISTS hyper_edges (
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    lens   TEXT NOT NULL,        -- Multiplex discriminator: call_graph, runtime_trace, etc.
    PRIMARY KEY (source, target, lens),
    FOREIGN KEY (source) REFERENCES substrate_nodes(coordinate) ON DELETE CASCADE,
    FOREIGN KEY (target) REFERENCES substrate_nodes(coordinate) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_edges_forward ON hyper_edges(source, lens);
CREATE INDEX IF NOT EXISTS idx_edges_reverse ON hyper_edges(target, lens);
