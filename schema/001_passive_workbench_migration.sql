BEGIN TRANSACTION;

-- 1. Strip involuntary synchronous reflex triggers
DROP TRIGGER IF EXISTS trg_autonomic_dispatch;
DROP TRIGGER IF EXISTS trg_dag_sensory_feedback;
DROP TRIGGER IF EXISTS trg_predictive_priming;

-- 2. Flush pending auto-generated repair tasks from the DAG queue
DELETE FROM task_dag_ledger
WHERE status = 'ready'
  AND task_id LIKE 'task_auto_%';

-- 3. Provision ephemeral scratchpad table for freeform LLM simulation payloads
CREATE TABLE IF NOT EXISTS cognitive_scratchpad (
    session_id TEXT NOT NULL,
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_tag TEXT NOT NULL,
    payload_type TEXT NOT NULL CHECK (payload_type IN ('graph_fragment', 'tabular_sim', 'raw_hypothesis')),
    data_payload TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Record passive workbench state transition in working memory
INSERT OR REPLACE INTO memories (category, key, value, access_count)
VALUES (
    'invariant',
    'state:passive_workbench_active',
    'Autonomous SQL triggers removed. Substrate governed externally via transactional savepoints and batched Wake/Sleep consolidation.',
    1
);

COMMIT;

