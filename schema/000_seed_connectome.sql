-- Seed schema for Epoch 03 connectome before passive workbench migration

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memory_edges (
    source_key TEXT NOT NULL,
    target_key TEXT NOT NULL,
    relation TEXT DEFAULT 'associated',
    weight REAL DEFAULT 1.0,
    PRIMARY KEY (source_key, target_key)
);

CREATE TABLE IF NOT EXISTS system_invariants (
    id TEXT PRIMARY KEY,
    statement TEXT NOT NULL,
    crystallized_from TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS epoch_archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epoch_number INTEGER NOT NULL,
    original_key TEXT NOT NULL,
    category TEXT NOT NULL,
    value TEXT NOT NULL,
    final_access_count INTEGER NOT NULL,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_dag_ledger (
    task_id TEXT PRIMARY KEY,
    description TEXT,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_landmarks (
    landmark_key TEXT PRIMARY KEY,
    description TEXT,
    prominence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS sensory_inputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    data TEXT NOT NULL,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS active_contexts (
    context_id TEXT PRIMARY KEY,
    description TEXT,
    salience REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS activation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_key TEXT NOT NULL,
    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS substrate_state (
    parameter TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE VIEW IF NOT EXISTS v_context_horizon_canonical AS
SELECT 
    m.key AS origin,
    e.target_key AS reachable_concept,
    m.category AS category,
    1 AS min_depth,
    e.weight AS max_conductance,
    1 AS unique_path_permutations
FROM memories m
LEFT JOIN memory_edges e ON m.key = e.source_key;

CREATE VIEW IF NOT EXISTS v_substrate_health AS
SELECT 
    (SELECT COUNT(*) FROM memories) AS active_nodes,
    (SELECT COUNT(*) FROM memory_edges) AS edge_count,
    (SELECT COUNT(*) FROM system_invariants) AS invariant_count,
    'healthy' AS status;

CREATE TRIGGER IF NOT EXISTS trg_autonomic_dispatch 
AFTER INSERT ON memories 
BEGIN 
    INSERT INTO task_dag_ledger (task_id, description, status) 
    VALUES ('task_auto_dispatch_' || hex(randomblob(4)), 'Autonomic dispatch', 'ready'); 
END;

CREATE TRIGGER IF NOT EXISTS trg_dag_sensory_feedback 
AFTER UPDATE ON memory_edges 
BEGIN 
    INSERT INTO task_dag_ledger (task_id, description, status) 
    VALUES ('task_auto_sensory_' || hex(randomblob(4)), 'Sensory feedback', 'ready'); 
END;

CREATE TRIGGER IF NOT EXISTS trg_predictive_priming 
AFTER INSERT ON task_dag_ledger 
BEGIN 
    UPDATE memories SET access_count = access_count + 1 WHERE key = 'seed_prime'; 
END;

