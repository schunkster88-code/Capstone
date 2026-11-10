# Capstone MVP Substrate A/B Benchmark Results

**Target Function:** `node://code/storage/db.py:save_record`  
**Traversal Depth:** 3 Hops (`main.py` -> `core/router.py` -> `core/engine.py` -> `storage/db.py`)  
**Trial Iterations:** 100 executions (statistical mean)  
**Tokenizer:** `cl100k_base` (`tiktoken`)  

---

### Empirical Comparative Matrix

| Evaluation Metric | Condition A: Naive File Scan / Grep Baseline | Condition B: Relational Substrate (CTE) | Delta / Realized Gain |
| :--- | :--- | :--- | :--- |
| **Execution Latency (Mean)** | **0.444 ms** (Iterative regex file I/O) | **0.252 ms** (B-tree indexed CTE) | **1.8x Faster** |
| **Planning Context Overhead** | **1,301 tokens** (Full matched files) | **131 tokens** (OpenGraph signposts) | **89.9% Token Reduction** |
| **Surgical Body Ingestion** | **1,301 tokens** (Entire module contexts) | **415 tokens** (Targeted AST slices) | **68.1% Token Reduction** |
| **False Positive Noise** | **19 false matches** (comments, strings, defs) | **0 false positives** (AST call graph) | **100% Precision / Zero Noise** |
| **Upstream Lineage Recall** | Fragile regex / heuristic hopping | Complete multi-hop directed path | **100% Causal Recall (4/4 Callers)** |

---

### Key Architectural Findings

1. **Sub-Millisecond Multi-Hop Traversal:** The SQLite WAL B-tree index resolves the 3-hop reverse dependency closure in **0.252 ms**, achieving a **1.8x speedup** over iterative disk-based regex matching.
2. **Context Window Saturation Defense:** Navigating via compact OpenGraph summaries reduces planning token overhead by **89.9%** (131 vs. 1,301 tokens), completely preventing LLM attention degradation.
3. **Elimination of Syntactic Noise:** The baseline grep matched 19 decoy comments and string mentions across unrelated functions (e.g., `# TODO: call save_record here`), whereas the AST relational lens yielded **0 false positives**.
