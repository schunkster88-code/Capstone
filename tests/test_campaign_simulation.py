"""
Verification Suite: Autonomous Multi-Agent Campaign Simulation.
Tests:
1. Automated run execution through at least 25 consecutive ticks.
2. 0 invariant watchdog failures.
3. Verification that party cannot bypass the locked gate without both keys.
4. Watchdog assertion sensitivity to matter, epistemic, lifecycle, and topological violations.
"""

import json
from pathlib import Path

import pytest
from core.dnd_engine import DndSubstrateEngine, init_dnd_engine
from tools.simulate_campaign import AutonomousCampaignSimulator, run_standalone_simulation


@pytest.fixture
def expanded_engine(tmp_path):
    """Fixture providing an isolated 8-room Expanded Crypt instance."""
    db_file = tmp_path / "test_campaign.db"
    engine = init_dnd_engine(db_file, expanded=True)
    yield engine
    engine.close()


def test_automated_campaign_run_25_ticks(tmp_path):
    """
    Test 1: Automated Run Execution.
    Assert automated run executes through at least 25 consecutive ticks,
    achieves terminal victory, slays boss, loots relic, and maintains 0 invariant violations.
    """
    db_file = tmp_path / "test_run_25.db"
    result = run_standalone_simulation(db_file, max_ticks=60, min_ticks=25)

    assert result["total_ticks"] >= 25, f"Expected >= 25 ticks, got {result['total_ticks']}"
    assert result["terminal_reason"] == "VICTORY_BOSS_DEFEATED"
    assert result["invariant_violations"] == 0
    assert result["lich_slain"] is True
    assert result["relic_recovered"] is True
    assert len(result["visited_rooms"]) == 8
    assert result["avg_tick_latency_ms"] < 3.0
    assert "node://item/bone_key" in result["looted_items"]
    assert "node://item/iron_key" in result["looted_items"]
    assert "node://item/relic_of_dawn" in result["looted_items"]


def test_locked_gate_prerequisite_enforcement(expanded_engine):
    """
    Test 2: Prerequisite Gate Verification.
    Assert that party CANNOT enter sanctum_of_the_lich without BOTH keys.
    """
    # Move rogue to antechamber
    expanded_engine.move_entity("node://entity/player/rogue", "node://room/crypt/antechamber")

    # Case A: Rogue holds neither key
    f0 = expanded_engine.verify_action_feasibility(
        "node://entity/player/rogue", "node://room/crypt/sanctum_of_the_lich"
    )
    assert f0["is_feasible"] is False
    assert f0["total_prerequisites"] == 2
    assert "node://item/bone_key" in f0["missing_prerequisites"]
    assert "node://item/iron_key" in f0["missing_prerequisites"]

    # Case B: Rogue holds ONLY bone_key
    expanded_engine.transfer_item("node://item/bone_key", "node://entity/player/rogue")
    f1 = expanded_engine.verify_action_feasibility(
        "node://entity/player/rogue", "node://room/crypt/sanctum_of_the_lich"
    )
    assert f1["is_feasible"] is False
    assert "node://item/iron_key" in f1["missing_prerequisites"]
    assert "node://item/bone_key" in f1["satisfied_prerequisites"]

    # Case C: Rogue holds ONLY iron_key (transfer bone_key back to ghoul)
    expanded_engine.transfer_item("node://item/bone_key", "node://entity/npc/ghoul")
    expanded_engine.transfer_item("node://item/iron_key", "node://entity/player/rogue")
    f2 = expanded_engine.verify_action_feasibility(
        "node://entity/player/rogue", "node://room/crypt/sanctum_of_the_lich"
    )
    assert f2["is_feasible"] is False
    assert "node://item/bone_key" in f2["missing_prerequisites"]
    assert "node://item/iron_key" in f2["satisfied_prerequisites"]

    # Case D: Rogue holds BOTH keys
    expanded_engine.transfer_item("node://item/bone_key", "node://entity/player/rogue")
    f3 = expanded_engine.verify_action_feasibility(
        "node://entity/player/rogue", "node://room/crypt/sanctum_of_the_lich"
    )
    assert f3["is_feasible"] is True
    assert len(f3["missing_prerequisites"]) == 0
    assert set(f3["satisfied_prerequisites"]) == {"node://item/bone_key", "node://item/iron_key"}

    # Attempting to interact when both keys are held unlocks the gate
    res = expanded_engine.execute_interact(
        "node://entity/player/rogue", "node://room/crypt/sanctum_of_the_lich"
    )
    assert res["success"] is True
    assert res["action"] == "unlocked_and_opened"


def test_step_by_step_25_consecutive_ticks(expanded_engine):
    """
    Test 3: Step-by-Step Consecutive Ticks.
    Step simulator manually for 25 consecutive ticks, validating zero watchdog errors.
    """
    sim = AutonomousCampaignSimulator(expanded_engine, seed=123)
    for tick_num in range(1, 26):
        summary = sim.step_tick()
        assert summary["tick"] == tick_num
        assert summary["latency_ms"] < 10.0
        assert summary["tokens"] > 0
        # Watchdog asserted internally in step_tick()
        expanded_engine.assert_invariants()

    assert sim.tick_count == 25


def test_watchdog_invariants_direct(expanded_engine):
    """
    Test 4: Watchdog Invariants Sensitivity.
    Directly verify that violating any of the 4 physical invariants triggers an AssertionError.
    """
    cur = expanded_engine.conn.cursor()

    # Baseline: Invariants pass
    assert expanded_engine.assert_invariants()["valid"] is True

    # 1. Matter Invariant: Add duplicate containment edge to an item
    cur.execute(
        "INSERT INTO hyper_edges (source, target, lens, edge_type) VALUES ('node://item/greatsword', 'node://room/crypt/armory', 'containment', 'duplicate');"
    )
    expanded_engine.conn.commit()
    with pytest.raises(AssertionError, match="Matter Invariant Violated"):
        expanded_engine.assert_invariants()

    # Revert duplicate
    cur.execute("DELETE FROM hyper_edges WHERE edge_type = 'duplicate';")
    expanded_engine.conn.commit()
    assert expanded_engine.assert_invariants()["valid"] is True

    # 2. Life Cycle Invariant: Dead entity with active hostile edge
    cur.execute(
        "UPDATE substrate_nodes SET body = json_set(body, '$.hp', 0) WHERE coordinate = 'node://entity/npc/skeleton_1';"
    )
    expanded_engine.conn.commit()
    with pytest.raises(AssertionError, match="Life Cycle Invariant Violated"):
        expanded_engine.assert_invariants()

    # Revert HP
    cur.execute(
        "UPDATE substrate_nodes SET body = json_set(body, '$.hp', 13) WHERE coordinate = 'node://entity/npc/skeleton_1';"
    )
    expanded_engine.conn.commit()
    assert expanded_engine.assert_invariants()["valid"] is True

    # 3. Topological Consistency: Add one-way spatial edge
    cur.execute(
        "INSERT INTO hyper_edges (source, target, lens, edge_type) VALUES ('node://room/crypt/entrance', 'node://room/crypt/sanctum_of_the_lich', 'spatial', 'portal');"
    )
    expanded_engine.conn.commit()
    with pytest.raises(AssertionError, match="Topological Consistency Violated"):
        expanded_engine.assert_invariants()

    # Revert portal
    cur.execute("DELETE FROM hyper_edges WHERE edge_type = 'portal';")
    expanded_engine.conn.commit()
    assert expanded_engine.assert_invariants()["valid"] is True

    # 4. Epistemic Invariant: Target node outside visible_coords
    last_action = {
        "agent_coord": "node://entity/player/fighter",
        "target_coord": "node://room/crypt/sanctum_of_the_lich",
        "visible_coords": {"node://room/crypt/entrance", "node://room/crypt/hall_of_pillars"},
    }
    with pytest.raises(AssertionError, match="Epistemic Invariant Violated"):
        expanded_engine.assert_invariants(last_action)
