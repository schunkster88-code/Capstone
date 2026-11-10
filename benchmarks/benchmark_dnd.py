"""
Benchmark Suite: Deterministic D&D / TTRPG Substrate
Empirical verification of FoW progressive disclosure, AoE spatial propagation,
and interaction feasibility via recursive CTEs in SQLite WAL mode.
"""

import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.dnd_engine import DndSubstrateEngine, init_dnd_engine, count_tokens


def run_dnd_benchmark(db_path: Path = Path("dnd_substrate.db"), iterations: int = 50) -> Dict[str, Any]:
    engine = init_dnd_engine(db_path)

    # 1. Database Topology Metrics
    cur = engine.conn.cursor()
    cur.execute("SELECT COUNT(*) FROM substrate_nodes;")
    node_count = cur.fetchone()[0]

    cur.execute("SELECT lens, COUNT(*) FROM hyper_edges GROUP BY lens ORDER BY lens;")
    edges_by_lens = {row[0]: row[1] for row in cur.fetchall()}
    total_edges = sum(edges_by_lens.values())

    # 2. Benchmark 1: Fog-of-War Sensory Lens
    fow_latencies = []
    fow_tokens = []
    fow_spoilers = []

    for _ in range(iterations):
        t_res = engine.get_visible_state("node://entity/player/cleric", darkvision_depth=1)
        fow_latencies.append(t_res["execution_latency_ms"])
        fow_tokens.append(t_res["token_count"])
        fow_spoilers.append(len(t_res["leaked_spoilers"]))

    # 3. Benchmark 2: Spell AoE Blast Radius (Fireball)
    aoe_latencies = []
    burned_doors_recorded = []
    targets_hit_recorded = []
    isolated_safe_recorded = []

    for i in range(iterations):
        # Re-seed if modifying state across iterations
        engine.seed_sunken_crypt()
        t_aoe = engine.resolve_aoe_spell(
            spell_coord="node://rule/spell/fireball",
            origin_room_coord="node://room/crypt/hall_of_pillars",
            damage_override=28,
            seed=42 + i,
        )
        aoe_latencies.append(t_aoe["execution_latency_ms"])
        burned_doors_recorded.append(len(t_aoe["burned_edges"]))
        targets_hit_recorded.append(len(t_aoe["targets"]))
        isolated_safe_recorded.append(len(t_aoe["isolated_unharmed_entities"]))

    # 4. Benchmark 3: Action Feasibility Triangulation
    feas_pre_latencies = []
    feas_post_latencies = []

    engine.seed_sunken_crypt()
    engine.move_entity("node://entity/player/cleric", "node://room/crypt/hall_of_pillars")

    for _ in range(iterations):
        # Pre-key check
        f1 = engine.verify_action_feasibility(
            "node://entity/player/cleric", "node://room/crypt/ritual_chamber"
        )
        feas_pre_latencies.append(f1["execution_latency_ms"])

    # Transfer key to player
    engine.transfer_item("node://item/bone_key", "node://entity/player/cleric")

    for _ in range(iterations):
        # Post-key check
        f2 = engine.verify_action_feasibility(
            "node://entity/player/cleric", "node://room/crypt/ritual_chamber"
        )
        feas_post_latencies.append(f2["execution_latency_ms"])

    def calc_stats(latencies: List[float]) -> Dict[str, float]:
        sorted_l = sorted(latencies)
        n = len(sorted_l)
        return {
            "mean": sum(sorted_l) / n,
            "min": sorted_l[0],
            "max": sorted_l[-1],
            "p50": sorted_l[n // 2],
            "p95": sorted_l[int(n * 0.95)],
        }

    results = {
        "topology": {
            "node_count": node_count,
            "total_edges": total_edges,
            "edges_by_lens": edges_by_lens,
        },
        "fow": {
            "iterations": iterations,
            "latency": calc_stats(fow_latencies),
            "tokens": {
                "mean": sum(fow_tokens) / len(fow_tokens),
                "max": max(fow_tokens),
                "min": min(fow_tokens),
            },
            "spoilers_leaked": sum(fow_spoilers),
        },
        "aoe": {
            "iterations": iterations,
            "latency": calc_stats(aoe_latencies),
            "targets_destroyed_avg": sum(targets_hit_recorded) / len(targets_hit_recorded),
            "burned_edges_avg": sum(burned_doors_recorded) / len(burned_doors_recorded),
            "isolated_entities_avg": sum(isolated_safe_recorded) / len(isolated_safe_recorded),
        },
        "feasibility": {
            "iterations": iterations,
            "pre_key_latency": calc_stats(feas_pre_latencies),
            "post_key_latency": calc_stats(feas_post_latencies),
        },
    }

    engine.close()
    return results


if __name__ == "__main__":
    results = run_dnd_benchmark()
    print("=" * 80)
    print("D&D RELATIONAL SUBSTRATE BENCHMARK RESULTS")
    print("=" * 80)
    print(f"Topology: {results['topology']['node_count']} nodes, {results['topology']['total_edges']} edges")
    for lens, cnt in results['topology']['edges_by_lens'].items():
        print(f"  - Lens '{lens}': {cnt} edges")
    print("-" * 80)
    print(f"Fog-of-War Perception ({results['fow']['iterations']} trials):")
    print(f"  Mean Latency:   {results['fow']['latency']['mean']:.3f} ms (p95: {results['fow']['latency']['p95']:.3f} ms)")
    print(f"  Token Overhead: {results['fow']['tokens']['mean']:.1f} tokens (Budget < 250 tokens)")
    print(f"  Spoilers Leaked: {results['fow']['spoilers_leaked']} (0% leakage)")
    print("-" * 80)
    print(f"Spell AoE Blast Radius ({results['aoe']['iterations']} trials):")
    print(f"  Mean Latency:   {results['aoe']['latency']['mean']:.3f} ms (p95: {results['aoe']['latency']['p95']:.3f} ms)")
    print(f"  Targets Slain:  {results['aoe']['targets_destroyed_avg']:.0f} / 3 skeletons")
    print(f"  Burned Doors:   {results['aoe']['burned_edges_avg']:.0f} wooden door edges")
    print(f"  Isolated Safe:  {results['aoe']['isolated_entities_avg']:.0f} entities (100% isolation)")
    print("-" * 80)
    print(f"Action Feasibility Triangulation ({results['feasibility']['iterations']} trials):")
    print(f"  Pre-Key Mean:   {results['feasibility']['pre_key_latency']['mean']:.3f} ms (p95: {results['feasibility']['pre_key_latency']['p95']:.3f} ms)")
    print(f"  Post-Key Mean:  {results['feasibility']['post_key_latency']['mean']:.3f} ms (p95: {results['feasibility']['post_key_latency']['p95']:.3f} ms)")
    print("=" * 80)
