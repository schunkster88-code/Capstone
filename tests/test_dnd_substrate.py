"""
Verification Gauntlet for Deterministic D&D / TTRPG Relational Substrate.
Validates:
1. Fog-of-War Leakage & Progressive Disclosure (0% spoiler leakage)
2. Spell AoE Blast Radius (spatial spread, damage, environmental edge mutation)
3. Action & Interaction Feasibility (downstream CTE INTERSECT / EXCEPT)
4. Sub-2ms Latency & Sub-250 Token Context Bounds
"""

import sqlite3
import time
from pathlib import Path

import pytest
from core.dnd_engine import DndSubstrateEngine, count_tokens, init_dnd_engine


@pytest.fixture
def dnd_engine(tmp_path):
    """Fixture providing an isolated Sunken Crypt instance."""
    db_file = tmp_path / "test_dnd.db"
    engine = init_dnd_engine(db_file)
    yield engine
    engine.close()


def test_fog_of_war_leakage(dnd_engine):
    """
    Test 1: Fog-of-War Leakage.
    Assert that hidden rooms, traps, and enemies in ritual_chamber return 0 tokens
    when player is in entrance.
    """
    res = dnd_engine.get_visible_state("node://entity/player/cleric", darkvision_depth=1)

    assert res["player_room"] == "node://room/crypt/entrance"
    assert len(res["visible_rooms"]) == 1
    assert res["visible_rooms"][0]["coordinate"] == "node://room/crypt/entrance"

    # Entities visible should only be the cleric
    visible_entity_coords = [e["coordinate"] for e in res["visible_entities"]]
    assert visible_entity_coords == ["node://entity/player/cleric"]

    # Items visible should only be cleric's equipment (mace, torch)
    visible_item_coords = [i["coordinate"] for i in res["visible_items"]]
    assert set(visible_item_coords) == {"node://item/mace", "node://item/torch"}

    # Zero spoiler leakage
    assert len(res["leaked_spoilers"]) == 0
    narration = res["narration_context"]
    assert "ritual_chamber" not in narration
    assert "trapped_alcove" not in narration
    assert "lich_apprentice" not in narration
    assert "relic_of_dawn" not in narration
    assert "skeleton" not in narration
    assert "bone_key" not in narration

    # Token bounds
    assert res["token_count"] < 250
    assert res["execution_latency_ms"] < 2.0


def test_aoe_blast_radius(dnd_engine):
    """
    Test 2: AoE Blast Radius.
    Cast Fireball at hall_of_pillars; assert damage calculation applies to all 3 skeletons
    and burns the wooden door edge while leaving entities in isolated rooms unharmed.
    """
    res = dnd_engine.resolve_aoe_spell(
        spell_coord="node://rule/spell/fireball",
        origin_room_coord="node://room/crypt/hall_of_pillars",
        max_radius=1,
        damage_override=28,
        seed=42,
    )

    assert res["spell_coord"] == "node://rule/spell/fireball"
    assert "node://room/crypt/hall_of_pillars" in res["affected_rooms"]
    assert "node://room/crypt/chasm" in res["affected_rooms"]

    # All 3 skeletons in hall_of_pillars are damaged and destroyed
    target_coords = {t["coordinate"] for t in res["targets"]}
    assert target_coords == {
        "node://entity/npc/skeleton_1",
        "node://entity/npc/skeleton_2",
        "node://entity/npc/skeleton_leader",
    }
    for t in res["targets"]:
        assert t["old_hp"] in (13, 22)
        assert t["new_hp"] == 0
        assert t["is_destroyed"] is True

    # Wooden door edge between hall of pillars and chasm is incinerated
    assert len(res["burned_edges"]) >= 1
    edge_types = [e[3] for e in res["burned_edges"]]
    assert "wooden_door" in edge_types

    # Entities in isolated rooms (entrance & ritual_chamber) remain unharmed
    isolated_coords = {e["coordinate"] for e in res["isolated_unharmed_entities"]}
    assert "node://entity/player/cleric" in isolated_coords
    assert "node://entity/npc/lich_apprentice" in isolated_coords

    # Verify database nodes directly
    cur = dnd_engine.conn.cursor()
    cur.execute(
        "SELECT coordinate, body FROM substrate_nodes WHERE coordinate IN ('node://entity/player/cleric', 'node://entity/npc/lich_apprentice');"
    )
    rows = cur.fetchall()
    for row in rows:
        import json
        body = json.loads(row["body"])
        if row["coordinate"] == "node://entity/player/cleric":
            assert body["hp"] == 24
        elif row["coordinate"] == "node://entity/npc/lich_apprentice":
            assert body["hp"] == 45

    assert res["execution_latency_ms"] < 2.0


def test_action_feasibility_triangulation(dnd_engine):
    """
    Test 3: Action Feasibility.
    - Attempt to enter ritual_chamber without key -> Fails with missing prerequisite node://item/bone_key.
    - Defeat skeleton, transfer bone_key to player via containment edge -> Feasibility returns True.
    """
    # Move player into hall_of_pillars (adjacent to ritual_chamber)
    dnd_engine.move_entity("node://entity/player/cleric", "node://room/crypt/hall_of_pillars")

    # Step A: Attempt to enter ritual_chamber without bone_key
    f1 = dnd_engine.verify_action_feasibility(
        entity_coord="node://entity/player/cleric",
        target_node_coord="node://room/crypt/ritual_chamber",
    )
    assert f1["is_feasible"] is False
    assert f1["spatial_in_reach"] is True
    assert f1["total_prerequisites"] == 1
    assert "node://item/bone_key" in f1["missing_prerequisites"]
    assert f1["execution_latency_ms"] < 2.0

    # Step B: Defeat skeleton and transfer bone_key to player
    dnd_engine.transfer_item("node://item/bone_key", "node://entity/player/cleric")

    # Step C: Re-verify feasibility
    f2 = dnd_engine.verify_action_feasibility(
        entity_coord="node://entity/player/cleric",
        target_node_coord="node://room/crypt/ritual_chamber",
    )
    assert f2["is_feasible"] is True
    assert f2["spatial_in_reach"] is True
    assert len(f2["missing_prerequisites"]) == 0
    assert "node://item/bone_key" in f2["satisfied_prerequisites"]
    assert f2["execution_latency_ms"] < 2.0


def test_latency_and_token_efficiency_gauntlet(dnd_engine):
    """
    Test 4: Latency & Token Efficiency.
    Assert all queries execute in < 2 ms (average < 1 ms).
    Assert total context handed to the DM narration prompt is < 250 tokens per turn.
    """
    fow_latencies = []
    aoe_latencies = []
    feasibility_latencies = []

    # Run 25 iterations of each operation to gather empirical distributions
    for _ in range(25):
        t_fow = dnd_engine.get_visible_state("node://entity/player/cleric")
        fow_latencies.append(t_fow["execution_latency_ms"])
        assert t_fow["token_count"] < 250
        assert t_fow["execution_latency_ms"] < 2.0

        t_feas = dnd_engine.verify_action_feasibility(
            "node://entity/player/cleric", "node://room/crypt/ritual_chamber"
        )
        feasibility_latencies.append(t_feas["execution_latency_ms"])
        assert t_feas["execution_latency_ms"] < 2.0

    # Benchmark AoE spell
    for _ in range(25):
        t_aoe = dnd_engine.resolve_aoe_spell(
            "node://rule/spell/fireball",
            "node://room/crypt/hall_of_pillars",
            damage_override=28,
        )
        aoe_latencies.append(t_aoe["execution_latency_ms"])
        assert t_aoe["execution_latency_ms"] < 2.0

    avg_fow = sum(fow_latencies) / len(fow_latencies)
    avg_feas = sum(feasibility_latencies) / len(feasibility_latencies)
    avg_aoe = sum(aoe_latencies) / len(aoe_latencies)

    assert avg_fow < 1.0, f"Average FoW latency too high: {avg_fow:.3f} ms"
    assert avg_feas < 1.0, f"Average Feasibility latency too high: {avg_feas:.3f} ms"
    assert avg_aoe < 1.5, f"Average AoE latency too high: {avg_aoe:.3f} ms"
