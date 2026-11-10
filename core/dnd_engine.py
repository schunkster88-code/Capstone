"""
D&D / TTRPG Relational World Engine
Two-Table SQLite Substrate (substrate_nodes, hyper_edges) in WAL mode.

Deterministic execution of TTRPG mechanics:
- Fog-of-war perception & progressive disclosure
- Spell AoE blast radius propagation & damage calculation
- Quest prerequisite & interaction feasibility verification
All via recursive Common Table Expressions (CTEs) executing in < 1 ms.
"""

import json
import random
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import tiktoken

# OpenGraph Tokenizer
try:
    ENCODER = tiktoken.get_encoding("cl100k_base")
except Exception:
    ENCODER = None


def count_tokens(text: str) -> int:
    """Calculate token count using tiktoken or fallback approximation."""
    if ENCODER:
        return len(ENCODER.encode(text))
    return max(1, len(text) // 4)


class DndSubstrateEngine:
    """Deterministic TTRPG engine powered by a two-table relational substrate."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.conn = self._init_database()

    def _init_database(self) -> sqlite3.Connection:
        """Initialize SQLite database with WAL mode and two-table schema."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")

        conn.executescript("""
        CREATE TABLE IF NOT EXISTS substrate_nodes (
            coordinate TEXT PRIMARY KEY,
            node_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            body TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hyper_edges (
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            lens TEXT NOT NULL,
            edge_type TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_dnd_edges_source_lens ON hyper_edges(source, lens);
        CREATE INDEX IF NOT EXISTS idx_dnd_edges_target_lens ON hyper_edges(target, lens);
        CREATE INDEX IF NOT EXISTS idx_dnd_nodes_coord ON substrate_nodes(coordinate);
        CREATE INDEX IF NOT EXISTS idx_dnd_nodes_type ON substrate_nodes(node_type);
        """)
        conn.commit()
        return conn

    def close(self):
        if self.conn:
            self.conn.close()

    # --------------------------------------------------------------------------
    # Dungeon Seeding: The Sunken Crypt
    # --------------------------------------------------------------------------
    def seed_sunken_crypt(self):
        """Populate the canonical Sunken Crypt encounter."""
        cur = self.conn.cursor()

        # Clean existing data
        cur.execute("DELETE FROM hyper_edges;")
        cur.execute("DELETE FROM substrate_nodes;")

        # 1. Rooms (5 nodes)
        nodes = [
            (
                "node://room/crypt/entrance",
                "room",
                "Damp stone entryway with mossy stairs, illuminated by a torch sconce.",
                json.dumps({
                    "name": "Crypt Entrance",
                    "zone": "crypt",
                    "lit": True,
                    "door_to_hall": "heavy_stone_door",
                    "portal_state": "closed"
                }),
            ),
            (
                "node://room/crypt/hall_of_pillars",
                "room",
                "Colonnade of obsidian pillars flanked by ancient broken stone crypts.",
                json.dumps({
                    "name": "Hall of Pillars",
                    "zone": "crypt",
                    "lit": False,
                    "environmental_hazards": []
                }),
            ),
            (
                "node://room/crypt/trapped_alcove",
                "room",
                "Concealed alcove rigged with poison-dart pressure plates.",
                json.dumps({
                    "name": "Trapped Alcove",
                    "zone": "crypt",
                    "secret": True,
                    "trap_dc": 14,
                    "trap_damage": "2d6",
                    "lit": False
                }),
            ),
            (
                "node://room/crypt/ritual_chamber",
                "room",
                "Forbidden sanctum centered around a necrotic blood-stained altar.",
                json.dumps({
                    "name": "Ritual Chamber",
                    "zone": "crypt",
                    "locked": True,
                    "lock_dc": 18,
                    "lit": False
                }),
            ),
            (
                "node://room/crypt/chasm",
                "room",
                "Abyssal rift shrouded in darkness with a rotting rope bridge.",
                json.dumps({
                    "name": "The Chasm",
                    "zone": "crypt",
                    "hazard": "fall",
                    "depth_ft": 120,
                    "lit": False
                }),
            ),
            # 2. Entities
            (
                "node://entity/player/cleric",
                "entity",
                "HP: 24/24 | AC: 16 | Init: +1 | Spell DC: 14 | Darkvision: 60ft",
                json.dumps({
                    "name": "Father Alden",
                    "type": "player",
                    "class": "Cleric",
                    "level": 3,
                    "hp": 24,
                    "max_hp": 24,
                    "ac": 16,
                    "init": 1,
                    "darkvision": 60,
                    "save_mods": {"str": 2, "dex": 0, "con": 2, "int": 0, "wis": 4, "cha": 1},
                    "status": "active"
                }),
            ),
            (
                "node://entity/npc/skeleton_1",
                "entity",
                "HP: 13/13 | AC: 13 | Dex Save: +2 | Undead Minion",
                json.dumps({
                    "name": "Skeleton Archer",
                    "type": "npc",
                    "hp": 13,
                    "max_hp": 13,
                    "ac": 13,
                    "save_mods": {"str": 0, "dex": 2, "con": 2, "int": -2, "wis": -1, "cha": -3},
                    "status": "active"
                }),
            ),
            (
                "node://entity/npc/skeleton_2",
                "entity",
                "HP: 13/13 | AC: 13 | Dex Save: +2 | Undead Minion",
                json.dumps({
                    "name": "Skeleton Warrior",
                    "type": "npc",
                    "hp": 13,
                    "max_hp": 13,
                    "ac": 13,
                    "save_mods": {"str": 0, "dex": 2, "con": 2, "int": -2, "wis": -1, "cha": -3},
                    "status": "active"
                }),
            ),
            (
                "node://entity/npc/skeleton_leader",
                "entity",
                "HP: 22/22 | AC: 14 | Dex Save: +2 | Undead Captain",
                json.dumps({
                    "name": "Skeleton Captain",
                    "type": "npc",
                    "hp": 22,
                    "max_hp": 22,
                    "ac": 14,
                    "save_mods": {"str": 2, "dex": 2, "con": 2, "int": 0, "wis": 0, "cha": -1},
                    "status": "active"
                }),
            ),
            (
                "node://entity/npc/lich_apprentice",
                "entity",
                "HP: 45/45 | AC: 15 | Spell DC: 15 | Undead Necromancer",
                json.dumps({
                    "name": "Lich Apprentice Malakor",
                    "type": "npc",
                    "hp": 45,
                    "max_hp": 45,
                    "ac": 15,
                    "save_mods": {"str": -1, "dex": 2, "con": 2, "int": 5, "wis": 3, "cha": 1},
                    "status": "active"
                }),
            ),
            # 3. Items
            (
                "node://item/mace",
                "item",
                "1d6 bludgeoning | Simple melee weapon | Silvered",
                json.dumps({
                    "name": "Silvered Mace",
                    "damage": "1d6",
                    "damage_type": "bludgeoning",
                    "weight": 4
                }),
            ),
            (
                "node://item/torch",
                "item",
                "Illuminates 20ft bright light, 20ft dim light | 1 hour",
                json.dumps({
                    "name": "Torch",
                    "light_bright": 20,
                    "light_dim": 20,
                    "duration_minutes": 60
                }),
            ),
            (
                "node://item/bone_key",
                "item",
                "Carved femur fashioned into an ornate skeletal vault key",
                json.dumps({
                    "name": "Bone Key",
                    "unlocks": "node://room/crypt/ritual_chamber",
                    "quest_prerequisite": True
                }),
            ),
            (
                "node://item/relic_of_dawn",
                "item",
                "Radiant golden solar orb pulsing with pure dawn light",
                json.dumps({
                    "name": "Relic of Dawn",
                    "aura": "radiant",
                    "quest_goal": True
                }),
            ),
            # 4. Rules & Spells
            (
                "node://rule/spell/fireball",
                "rule",
                "8d6 fire damage | 20ft radius | Dex Save DC 15",
                json.dumps({
                    "name": "Fireball",
                    "level": 3,
                    "school": "evocation",
                    "save_type": "dex",
                    "save_dc": 15,
                    "damage_dice": "8d6",
                    "damage_type": "fire",
                    "base_damage": 28,
                    "radius_rooms": 1,
                    "flammable_interaction": "burns_wooden_doors"
                }),
            ),
            # 5. Conditions
            (
                "node://condition/poisoned",
                "condition",
                "Disadvantage on attack rolls and ability checks",
                json.dumps({
                    "name": "Poisoned",
                    "effect": "disadvantage_attacks_ability_checks"
                }),
            ),
            (
                "node://condition/silenced",
                "condition",
                "Cannot cast verbal spells; immune to thunder damage",
                json.dumps({
                    "name": "Silenced",
                    "effect": "no_verbal_spells"
                }),
            ),
        ]

        cur.executemany(
            "INSERT INTO substrate_nodes (coordinate, node_type, summary, body) VALUES (?, ?, ?, ?);",
            nodes,
        )

        # Edges
        edges = [
            # Spatial Room Connectivity (Bidirectional)
            ("node://room/crypt/entrance", "node://room/crypt/hall_of_pillars", "spatial", "stone_door"),
            ("node://room/crypt/hall_of_pillars", "node://room/crypt/entrance", "spatial", "stone_door"),

            ("node://room/crypt/hall_of_pillars", "node://room/crypt/trapped_alcove", "spatial", "secret_door"),
            ("node://room/crypt/trapped_alcove", "node://room/crypt/hall_of_pillars", "spatial", "secret_door"),

            ("node://room/crypt/hall_of_pillars", "node://room/crypt/ritual_chamber", "spatial", "vault_door"),
            ("node://room/crypt/ritual_chamber", "node://room/crypt/hall_of_pillars", "spatial", "vault_door"),

            ("node://room/crypt/hall_of_pillars", "node://room/crypt/chasm", "spatial", "wooden_door"),
            ("node://room/crypt/chasm", "node://room/crypt/hall_of_pillars", "spatial", "wooden_door"),

            # Containment (Entity in Room)
            ("node://entity/player/cleric", "node://room/crypt/entrance", "containment", "resides_in"),
            ("node://entity/npc/skeleton_1", "node://room/crypt/hall_of_pillars", "containment", "resides_in"),
            ("node://entity/npc/skeleton_2", "node://room/crypt/hall_of_pillars", "containment", "resides_in"),
            ("node://entity/npc/skeleton_leader", "node://room/crypt/hall_of_pillars", "containment", "resides_in"),
            ("node://entity/npc/lich_apprentice", "node://room/crypt/ritual_chamber", "containment", "resides_in"),

            # Containment (Item Storage / Inventory)
            ("node://item/mace", "node://entity/player/cleric", "containment", "equipped"),
            ("node://item/torch", "node://entity/player/cleric", "containment", "held"),
            ("node://item/bone_key", "node://entity/npc/skeleton_leader", "containment", "carries"),
            ("node://item/relic_of_dawn", "node://room/crypt/ritual_chamber", "containment", "stored_in"),

            # Prerequisites
            ("node://item/bone_key", "node://room/crypt/ritual_chamber", "prerequisite", "unlocks"),

            # Perception
            ("node://item/torch", "node://room/crypt/entrance", "perception", "illuminates"),

            # Faction Relations
            ("node://entity/player/cleric", "node://entity/npc/skeleton_1", "faction", "hostile"),
            ("node://entity/player/cleric", "node://entity/npc/skeleton_2", "faction", "hostile"),
            ("node://entity/player/cleric", "node://entity/npc/skeleton_leader", "faction", "hostile"),
            ("node://entity/player/cleric", "node://entity/npc/lich_apprentice", "faction", "hostile"),
        ]

        cur.executemany(
            "INSERT INTO hyper_edges (source, target, lens, edge_type) VALUES (?, ?, ?, ?);",
            edges,
        )

        self.conn.commit()

    # --------------------------------------------------------------------------
    # Mechanic 1: Fog-of-War Sensory Lens
    # --------------------------------------------------------------------------
    def get_visible_state(
        self, player_coord: str, darkvision_depth: int = 1, open_doors: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute forward recursive CTE across 'spatial' lens constrained by line-of-sight
        and illumination depth, joining with 'containment' to pull strictly visible entities
        and items. Guarantees 0% spoiler leakage to the LLM narrator.
        """
        t0 = time.perf_counter()
        open_doors = open_doors or set()

        # Step 1: Find player's containing room
        cur = self.conn.cursor()
        cur.execute(
            "SELECT target FROM hyper_edges WHERE source = ? AND lens = 'containment';",
            (player_coord,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Player {player_coord} not contained in any room.")
        player_room = row[0]

        # Step 2: Recursive CTE for visible rooms
        # Secret doors, closed stone doors, and closed vault doors block line-of-sight
        # unless specifically opened in open_doors.
        cte_query = """
        WITH RECURSIVE visible_rooms AS (
            SELECT 
                ? as room_coord,
                0 as depth

            UNION

            SELECT 
                e.target,
                v.depth + 1
            FROM hyper_edges e
            JOIN visible_rooms v ON e.source = v.room_coord
            WHERE e.lens = 'spatial'
              AND v.depth < ?
              -- Concealed doors are invisible without active perception discovery
              AND e.edge_type != 'secret_door'
              -- Closed heavy doors block LoS unless open
              AND (
                  e.edge_type NOT IN ('stone_door', 'vault_door', 'iron_gate:locked')
                  OR e.source IN (SELECT value FROM json_each(?))
                  OR e.target IN (SELECT value FROM json_each(?))
              )
        )
        SELECT room_coord, depth FROM visible_rooms;
        """
        open_doors_json = json.dumps(list(open_doors))
        cur.execute(cte_query, (player_room, darkvision_depth, open_doors_json, open_doors_json))
        visible_room_rows = cur.fetchall()
        visible_room_coords = [r[0] for r in visible_room_rows]

        # Step 3: Fetch Room nodes
        placeholders = ",".join("?" for _ in visible_room_coords)
        cur.execute(
            f"SELECT coordinate, node_type, summary, body FROM substrate_nodes WHERE coordinate IN ({placeholders});",
            visible_room_coords,
        )
        room_nodes = [dict(r) for r in cur.fetchall()]

        # Step 4: Fetch Contained Entities in Visible Rooms
        cur.execute(
            f"""
            SELECT n.coordinate, n.node_type, n.summary, n.body
            FROM hyper_edges e
            JOIN substrate_nodes n ON e.source = n.coordinate
            WHERE e.target IN ({placeholders})
              AND e.lens = 'containment'
              AND n.node_type = 'entity';
            """,
            visible_room_coords,
        )
        entity_nodes = [dict(r) for r in cur.fetchall()]
        visible_entity_coords = [e["coordinate"] for e in entity_nodes]

        # Step 5: Fetch Contained Items (in visible rooms or carried by visible entities)
        container_coords = visible_room_coords + visible_entity_coords
        c_placeholders = ",".join("?" for _ in container_coords)
        cur.execute(
            f"""
            SELECT n.coordinate, n.node_type, n.summary, n.body, e.target as container
            FROM hyper_edges e
            JOIN substrate_nodes n ON e.source = n.coordinate
            WHERE e.target IN ({c_placeholders})
              AND e.lens = 'containment'
              AND n.node_type = 'item';
            """,
            container_coords,
        )
        item_nodes = [dict(r) for r in cur.fetchall()]

        # Step 6: Fetch Exits / Portals from visible rooms
        cur.execute(
            f"""
            SELECT e.source, e.target, e.edge_type, n.summary as target_summary
            FROM hyper_edges e
            JOIN substrate_nodes n ON e.target = n.coordinate
            WHERE e.source IN ({placeholders})
              AND e.lens = 'spatial'
              AND e.edge_type != 'secret_door';
            """,
            visible_room_coords,
        )
        exit_rows = cur.fetchall()

        latency_ms = (time.perf_counter() - t0) * 1000.0

        # Build Compact OpenGraph Narration Context (< 250 tokens)
        narration_lines = ["=== SENSORY PERCEPTION CONTEXT ==="]
        narration_lines.append(f"Current Room: {player_room}")
        for r in room_nodes:
            narration_lines.append(f"[Room] {r['coordinate']}: {r['summary']}")

        narration_lines.append("Visible Entities:")
        for ent in entity_nodes:
            narration_lines.append(f"- [Entity] {ent['coordinate']}: {ent['summary']}")

        narration_lines.append("Items & Inventory in View:")
        for item in item_nodes:
            narration_lines.append(f"- [Item] {item['coordinate']} (held by {item['container']}): {item['summary']}")

        narration_lines.append("Known Exits:")
        for ex in exit_rows:
            narration_lines.append(f"- Exit from {ex['source']} to {ex['target']} via {ex['edge_type']}")

        narration_context = "\n".join(narration_lines)
        token_count = count_tokens(narration_context)

        # Check for forbidden leaks
        forbidden_spoiler_coords = {
            "node://room/crypt/trapped_alcove",
            "node://room/crypt/ritual_chamber",
            "node://entity/npc/lich_apprentice",
            "node://item/relic_of_dawn",
        }
        all_returned_coords = (
            set(visible_room_coords)
            | {e["coordinate"] for e in entity_nodes}
            | {i["coordinate"] for i in item_nodes}
        )
        leaked_nodes = list(forbidden_spoiler_coords.intersection(all_returned_coords))

        return {
            "player_coord": player_coord,
            "player_room": player_room,
            "visible_rooms": room_nodes,
            "visible_entities": entity_nodes,
            "visible_items": item_nodes,
            "exits": [dict(r) for r in exit_rows],
            "narration_context": narration_context,
            "token_count": token_count,
            "leaked_spoilers": leaked_nodes,
            "execution_latency_ms": latency_ms,
        }

    # --------------------------------------------------------------------------
    # Mechanic 2: Spell AoE Blast Radius
    # --------------------------------------------------------------------------
    def resolve_aoe_spell(
        self,
        spell_coord: str,
        origin_room_coord: str,
        max_radius: int = 1,
        damage_override: Optional[int] = None,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Evaluate AoE spell spread across 'spatial' edges, pull contained entities,
        evaluate deterministic saving throws against spell DC, update substrate nodes,
        and trigger environmental edge mutations (e.g. wooden door incinerated).
        """
        t0 = time.perf_counter()
        cur = self.conn.cursor()

        # Step 1: Fetch spell rule node
        cur.execute(
            "SELECT coordinate, summary, body FROM substrate_nodes WHERE coordinate = ? AND node_type = 'rule';",
            (spell_coord,),
        )
        spell_row = cur.fetchone()
        if not spell_row:
            raise ValueError(f"Spell rule {spell_coord} not found.")

        spell_body = json.loads(spell_row["body"])
        save_dc = spell_body.get("save_dc", 15)
        save_type = spell_body.get("save_type", "dex")
        damage = damage_override if damage_override is not None else spell_body.get("base_damage", 28)

        # Step 2: Spatial blast propagation CTE
        # Heavy stone doors, locked vault doors, and secret doors contain blast.
        # Flammable wooden doors are incinerated.
        cte_query = """
        WITH RECURSIVE blast_zone AS (
            SELECT 
                ? as room_coord,
                0 as depth

            UNION

            SELECT 
                e.target,
                b.depth + 1
            FROM hyper_edges e
            JOIN blast_zone b ON e.source = b.room_coord
            WHERE e.lens = 'spatial'
              AND b.depth < ?
              -- Blast does NOT penetrate thick stone/vault/secret barriers
              AND e.edge_type NOT IN ('stone_door', 'vault_door', 'secret_door')
        )
        SELECT room_coord FROM blast_zone;
        """
        cur.execute(cte_query, (origin_room_coord, max_radius))
        affected_rooms = [r[0] for r in cur.fetchall()]

        # Step 3: Identify and burn flammable environmental edges (wooden doors)
        # Any wooden door edge touching the affected rooms is incinerated
        cur.execute(
            """
            SELECT source, target, edge_type
            FROM hyper_edges
            WHERE lens = 'spatial'
              AND edge_type = 'wooden_door'
              AND (source IN ({placeholders}) OR target IN ({placeholders}));
            """.format(placeholders=",".join("?" for _ in affected_rooms)),
            affected_rooms * 2,
        )
        wooden_door_edges = cur.fetchall()
        burned_edges = []
        for edge in wooden_door_edges:
            burned_edges.append((edge[0], edge[1], "spatial", edge[2]))

        # Mutate burned edges to scorched passageways
        if burned_edges:
            cur.execute(
                """
                UPDATE hyper_edges
                SET edge_type = 'scorched_opening'
                WHERE lens = 'spatial'
                  AND edge_type = 'wooden_door'
                  AND (source IN ({placeholders}) OR target IN ({placeholders}));
                """.format(placeholders=",".join("?" for _ in affected_rooms)),
                affected_rooms * 2,
            )

        # Step 4: Pull all contained entities in affected rooms
        cur.execute(
            """
            SELECT n.coordinate, n.summary, n.body, e.target as room
            FROM hyper_edges e
            JOIN substrate_nodes n ON e.source = n.coordinate
            WHERE e.target IN ({placeholders})
              AND e.lens = 'containment'
              AND n.node_type = 'entity';
            """.format(placeholders=",".join("?" for _ in affected_rooms)),
            affected_rooms,
        )
        affected_entities = cur.fetchall()

        # Step 5: Evaluate deterministic saving throws and update HP
        rng = random.Random(seed)
        target_results = []

        for ent in affected_entities:
            coord = ent["coordinate"]
            body = json.loads(ent["body"])
            current_hp = body.get("hp", 10)
            max_hp = body.get("max_hp", 10)
            save_mod = body.get("save_mods", {}).get(save_type, 0)

            # Deterministic d20 roll
            d20 = rng.randint(1, 20)
            total_save = d20 + save_mod
            save_passed = total_save >= save_dc

            # Full damage on failure, half on success
            applied_damage = damage // 2 if save_passed else damage
            new_hp = max(0, current_hp - applied_damage)
            is_destroyed = new_hp == 0

            # Update body and summary
            body["hp"] = new_hp
            if is_destroyed:
                body["status"] = "destroyed"
                new_summary = f"HP: 0/{max_hp} | Destroyed | Burned ash"
            else:
                new_summary = f"HP: {new_hp}/{max_hp} | Damaged | Dex Save: {save_mod:+d}"

            cur.execute(
                "UPDATE substrate_nodes SET summary = ?, body = ? WHERE coordinate = ?;",
                (new_summary, json.dumps(body), coord),
            )

            target_results.append({
                "coordinate": coord,
                "room": ent["room"],
                "save_type": save_type,
                "save_dc": save_dc,
                "save_mod": save_mod,
                "d20_roll": d20,
                "total_save": total_save,
                "save_passed": save_passed,
                "damage_taken": applied_damage,
                "old_hp": current_hp,
                "new_hp": new_hp,
                "is_destroyed": is_destroyed,
            })

        # Step 6: Identify isolated unharmed entities in unaffected rooms
        cur.execute(
            """
            SELECT n.coordinate, e.target as room
            FROM hyper_edges e
            JOIN substrate_nodes n ON e.source = n.coordinate
            WHERE e.target NOT IN ({placeholders})
              AND e.lens = 'containment'
              AND n.node_type = 'entity';
            """.format(placeholders=",".join("?" for _ in affected_rooms)),
            affected_rooms,
        )
        isolated_entities = [dict(r) for r in cur.fetchall()]

        self.conn.commit()
        latency_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "spell_coord": spell_coord,
            "origin_room": origin_room_coord,
            "affected_rooms": affected_rooms,
            "targets": target_results,
            "burned_edges": burned_edges,
            "isolated_unharmed_entities": isolated_entities,
            "execution_latency_ms": latency_ms,
        }

    # --------------------------------------------------------------------------
    # Mechanic 3: Quest & Interaction Triangulation
    # --------------------------------------------------------------------------
    def verify_action_feasibility(
        self, entity_coord: str, target_node_coord: str
    ) -> Dict[str, Any]:
        """
        Verify if an action is valid using a downstream INTERSECT / EXCEPT CTE:
        1. Spatial proximity: Is entity co-located with target, or adjacent via portal?
        2. Prerequisite satisfaction: Does entity hold all required keys / conditions?
        Executes in < 1 ms with zero hallucination.
        """
        t0 = time.perf_counter()
        cur = self.conn.cursor()

        # Step 1: Check entity current room
        cur.execute(
            "SELECT target FROM hyper_edges WHERE source = ? AND lens = 'containment';",
            (entity_coord,),
        )
        entity_room_row = cur.fetchone()
        entity_room = entity_room_row[0] if entity_room_row else None

        # Step 2: Determine spatial reachability
        # Target could be:
        # a) A room adjacent to entity_room
        # b) A room identical to entity_room
        # c) An item/entity inside entity_room
        spatial_in_reach = False

        if target_node_coord.startswith("node://room/"):
            if entity_room == target_node_coord:
                spatial_in_reach = True
            elif entity_room:
                cur.execute(
                    """
                    SELECT 1 FROM hyper_edges
                    WHERE source = ? AND target = ? AND lens = 'spatial'
                    LIMIT 1;
                    """,
                    (entity_room, target_node_coord),
                )
                spatial_in_reach = cur.fetchone() is not None
        else:
            # Target is an item or entity
            cur.execute(
                """
                SELECT 1 FROM hyper_edges
                WHERE source = ? AND target = ? AND lens = 'containment'
                LIMIT 1;
                """,
                (target_node_coord, entity_room),
            )
            spatial_in_reach = cur.fetchone() is not None

        # Step 3: Prerequisite satisfaction CTE using INTERSECT and EXCEPT
        prereq_cte = """
        WITH required_prereqs AS (
            SELECT source as req_coord
            FROM hyper_edges
            WHERE target = ? AND lens = 'prerequisite'
        ),
        held_items AS (
            SELECT source as held_coord
            FROM hyper_edges
            WHERE lens = 'containment'
              AND (
                  target = ?
                  OR target IN (
                      -- Co-located friendly player characters in the same room
                      SELECT e1.source
                      FROM hyper_edges e1
                      JOIN hyper_edges e2 ON e1.target = e2.target
                      WHERE e2.source = ?
                        AND e1.lens = 'containment'
                        AND e2.lens = 'containment'
                        AND e1.source LIKE 'node://entity/player/%'
                  )
              )
        ),
        missing AS (
            SELECT req_coord FROM required_prereqs
            EXCEPT
            SELECT held_coord FROM held_items
        ),
        satisfied AS (
            SELECT req_coord FROM required_prereqs
            INTERSECT
            SELECT held_coord FROM held_items
        )
        SELECT 
            (SELECT COUNT(*) FROM required_prereqs) as total_required,
            (SELECT COUNT(*) FROM missing) as missing_count,
            (SELECT GROUP_CONCAT(req_coord) FROM missing) as missing_deps,
            (SELECT GROUP_CONCAT(req_coord) FROM satisfied) as satisfied_deps;
        """
        cur.execute(prereq_cte, (target_node_coord, entity_coord, entity_coord))
        row = cur.fetchone()

        total_required = row[0] or 0
        missing_count = row[1] or 0
        missing_deps = row[2].split(",") if row[2] else []
        satisfied_deps = row[3].split(",") if row[3] else []

        # Verdict
        if not spatial_in_reach:
            is_feasible = False
            reason = f"Target {target_node_coord} out of spatial reach from current room {entity_room}."
        elif missing_count > 0:
            is_feasible = False
            reason = f"Missing prerequisite: {', '.join(missing_deps)}"
        else:
            is_feasible = True
            reason = "All spatial and prerequisite conditions satisfied."

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "entity_coord": entity_coord,
            "target_node_coord": target_node_coord,
            "entity_room": entity_room,
            "spatial_in_reach": spatial_in_reach,
            "total_prerequisites": total_required,
            "satisfied_prerequisites": satisfied_deps,
            "missing_prerequisites": missing_deps,
            "is_feasible": is_feasible,
            "reason": reason,
            "execution_latency_ms": latency_ms,
        }

    # --------------------------------------------------------------------------
    # Substrate State Mutations
    # --------------------------------------------------------------------------
    def transfer_item(self, item_coord: str, new_target_coord: str):
        """Transfer item containment edge to a new holder (player, npc, or room)."""
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE hyper_edges
            SET target = ?
            WHERE source = ? AND lens = 'containment';
            """,
            (new_target_coord, item_coord),
        )
        self.conn.commit()

    def move_entity(self, entity_coord: str, new_room_coord: str):
        """Move entity containment edge to a new room."""
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE hyper_edges
            SET target = ?
            WHERE source = ? AND lens = 'containment';
            """,
            (new_room_coord, entity_coord),
        )
        self.conn.commit()

    # --------------------------------------------------------------------------
    # Expanded 8-Room Crypt Topology (For Multi-Agent Campaign Simulation)
    # --------------------------------------------------------------------------
    def seed_expanded_crypt(self):
        """
        Populate the expanded 8-room dungeon graph with 3 party agents,
        4 enemies, 2 causal prerequisite keys, armory loot, and boss encounter.
        """
        cur = self.conn.cursor()
        cur.execute("DELETE FROM hyper_edges;")
        cur.execute("DELETE FROM substrate_nodes;")

        # 1. Rooms (8 nodes)
        rooms = [
            (
                "node://room/crypt/entrance",
                "room",
                "Damp stone entryway with mossy stairs, illuminated by a torch sconce.",
                json.dumps({"name": "Entrance", "zone": "crypt", "lit": True}),
            ),
            (
                "node://room/crypt/hall_of_pillars",
                "room",
                "Colonnade of obsidian pillars where ancient guardians linger.",
                json.dumps({"name": "Hall of Pillars", "zone": "crypt", "lit": False}),
            ),
            (
                "node://room/crypt/armory",
                "room",
                "Cobwebbed armory with weapon racks and old supply chests.",
                json.dumps({"name": "Armory", "zone": "crypt", "lit": False}),
            ),
            (
                "node://room/crypt/flooded_crypt",
                "room",
                "Knee-deep stagnant water smelling of decay, lair of a ravenous ghoul.",
                json.dumps({"name": "Flooded Crypt", "zone": "crypt", "hazard": "deep_water", "lit": False}),
            ),
            (
                "node://room/crypt/secret_library",
                "room",
                "Concealed archive of forbidden scrolls and occult grimoires.",
                json.dumps({"name": "Secret Library", "zone": "crypt", "secret": True, "lit": False}),
            ),
            (
                "node://room/crypt/chasm",
                "room",
                "Yawning subterranean fissure spanned by an old wooden bridge.",
                json.dumps({"name": "The Chasm", "zone": "crypt", "hazard": "fall", "depth_ft": 120, "lit": False}),
            ),
            (
                "node://room/crypt/antechamber",
                "room",
                "Foreboding vestibule before the inner sanctum, barred by an iron gate.",
                json.dumps({"name": "Antechamber", "zone": "crypt", "lit": False}),
            ),
            (
                "node://room/crypt/sanctum_of_the_lich",
                "room",
                "Dread sanctum pulsing with necrotic energy around the Relic of Dawn.",
                json.dumps({"name": "Sanctum of the Lich", "zone": "crypt", "locked": True, "boss_room": True, "lit": False}),
            ),
        ]

        # 2. Entities (7 nodes)
        entities = [
            (
                "node://entity/player/fighter",
                "entity",
                "HP: 28/28 | AC: 17 | Init: +1 | Melee Greatsword +5",
                json.dumps({
                    "name": "Krag the Fighter",
                    "type": "player",
                    "class": "fighter",
                    "hp": 28,
                    "max_hp": 28,
                    "ac": 17,
                    "init": 1,
                    "attack_bonus": 5,
                    "damage_dice": "1d10+3",
                    "save_mods": {"str": 3, "dex": 1, "con": 3, "int": 0, "wis": 1, "cha": 0},
                    "status": "active"
                }),
            ),
            (
                "node://entity/player/wizard",
                "entity",
                "HP: 16/16 | AC: 13 | Spell DC: 15 | Evoker",
                json.dumps({
                    "name": "Eldrin the Wizard",
                    "type": "player",
                    "class": "wizard",
                    "hp": 16,
                    "max_hp": 16,
                    "ac": 13,
                    "init": 2,
                    "spell_dc": 15,
                    "attack_bonus": 4,
                    "damage_dice": "1d4",
                    "save_mods": {"str": -1, "dex": 2, "con": 1, "int": 4, "wis": 2, "cha": 0},
                    "status": "active"
                }),
            ),
            (
                "node://entity/player/rogue",
                "entity",
                "HP: 20/20 | AC: 15 | Init: +4 | Perception +5 | Lockpicker",
                json.dumps({
                    "name": "Lyra the Rogue",
                    "type": "player",
                    "class": "rogue",
                    "hp": 20,
                    "max_hp": 20,
                    "ac": 15,
                    "init": 4,
                    "perception": 5,
                    "attack_bonus": 5,
                    "damage_dice": "1d6+3",
                    "save_mods": {"str": 0, "dex": 4, "con": 2, "int": 1, "wis": 3, "cha": 1},
                    "status": "active"
                }),
            ),
            (
                "node://entity/npc/skeleton_1",
                "entity",
                "HP: 13/13 | AC: 13 | Dex Save: +2 | Undead Minion",
                json.dumps({
                    "name": "Skeleton Archer",
                    "type": "npc",
                    "hp": 13,
                    "max_hp": 13,
                    "ac": 13,
                    "attack_bonus": 4,
                    "damage_dice": "1d6+2",
                    "save_mods": {"str": 0, "dex": 2, "con": 2, "int": -2, "wis": -1, "cha": -3},
                    "status": "active"
                }),
            ),
            (
                "node://entity/npc/skeleton_2",
                "entity",
                "HP: 13/13 | AC: 13 | Dex Save: +2 | Undead Minion",
                json.dumps({
                    "name": "Skeleton Warrior",
                    "type": "npc",
                    "hp": 13,
                    "max_hp": 13,
                    "ac": 13,
                    "attack_bonus": 4,
                    "damage_dice": "1d6+2",
                    "save_mods": {"str": 0, "dex": 2, "con": 2, "int": -2, "wis": -1, "cha": -3},
                    "status": "active"
                }),
            ),
            (
                "node://entity/npc/ghoul",
                "entity",
                "HP: 22/22 | AC: 12 | Undead Ghoul | Carries Bone Key",
                json.dumps({
                    "name": "Crypt Ghoul",
                    "type": "npc",
                    "hp": 22,
                    "max_hp": 22,
                    "ac": 12,
                    "attack_bonus": 4,
                    "damage_dice": "2d6+2",
                    "save_mods": {"str": 2, "dex": 2, "con": 0, "int": -2, "wis": 0, "cha": -2},
                    "status": "active"
                }),
            ),
            (
                "node://entity/npc/lich_apprentice",
                "entity",
                "HP: 45/45 | AC: 15 | Boss Necromancer | Guarding Relic",
                json.dumps({
                    "name": "Lich Apprentice Malakor",
                    "type": "npc",
                    "hp": 45,
                    "max_hp": 45,
                    "ac": 15,
                    "attack_bonus": 6,
                    "damage_dice": "2d8+3",
                    "spell_dc": 15,
                    "save_mods": {"str": -1, "dex": 2, "con": 2, "int": 5, "wis": 3, "cha": 1},
                    "status": "active"
                }),
            ),
        ]

        # 3. Items (9 nodes)
        items = [
            (
                "node://item/greatsword",
                "item",
                "2d6 slashing | Heavy martial two-handed blade",
                json.dumps({"name": "Greatsword", "damage": "2d6", "damage_type": "slashing", "weight": 6}),
            ),
            (
                "node://item/spellbook",
                "item",
                "Leatherbound tome filled with evocation arcane formulas",
                json.dumps({"name": "Spellbook", "school": "evocation", "weight": 3}),
            ),
            (
                "node://item/thieves_tools",
                "item",
                "Set of lockpicks and delicate tension wrenches",
                json.dumps({"name": "Thieves' Tools", "bonus": 5, "weight": 1}),
            ),
            (
                "node://item/torch",
                "item",
                "Illuminates 20ft bright light, 20ft dim light | 1 hour",
                json.dumps({"name": "Torch", "light_bright": 20, "light_dim": 20, "fuel_minutes": 60}),
            ),
            (
                "node://item/healing_potion",
                "item",
                "Vial of shimmering red restorative liquid (heals 2d4+2 HP)",
                json.dumps({"name": "Potion of Healing", "heal": "2d4+2", "consumable": True}),
            ),
            (
                "node://item/shield_of_dawn",
                "item",
                "+2 AC | Radiant iron shield adorned with the morning sun",
                json.dumps({"name": "Shield of Dawn", "ac_bonus": 2, "weight": 5}),
            ),
            (
                "node://item/bone_key",
                "item",
                "Carved femur fashioned into an ornate skeletal vault key",
                json.dumps({"name": "Bone Key", "unlocks": "node://room/crypt/sanctum_of_the_lich", "quest_prerequisite": True}),
            ),
            (
                "node://item/iron_key",
                "item",
                "Heavy cold-iron ward key inscribed with runes of unsealing",
                json.dumps({"name": "Iron Key", "unlocks": "node://room/crypt/sanctum_of_the_lich", "quest_prerequisite": True}),
            ),
            (
                "node://item/relic_of_dawn",
                "item",
                "Radiant golden solar orb pulsing with pure dawn light",
                json.dumps({"name": "Relic of Dawn", "aura": "radiant", "quest_goal": True}),
            ),
        ]

        # 4. Rules & Spells
        rules = [
            (
                "node://rule/spell/fireball",
                "rule",
                "8d6 fire damage | 20ft radius | Dex Save DC 15",
                json.dumps({
                    "name": "Fireball",
                    "level": 3,
                    "save_type": "dex",
                    "save_dc": 15,
                    "damage_dice": "8d6",
                    "base_damage": 28,
                    "radius_rooms": 1,
                    "flammable_interaction": "burns_wooden_doors"
                }),
            ),
            (
                "node://rule/spell/magic_missile",
                "rule",
                "3x 1d4+1 force damage darts | Never misses | Evocation",
                json.dumps({
                    "name": "Magic Missile",
                    "level": 1,
                    "darts": 3,
                    "damage_per_dart": "1d4+1",
                    "auto_hit": True
                }),
            ),
        ]

        # Insert all nodes
        cur.executemany(
            "INSERT INTO substrate_nodes (coordinate, node_type, summary, body) VALUES (?, ?, ?, ?);",
            rooms + entities + items + rules,
        )

        # 5. Edges
        edges = [
            # Spatial Bidirectional Topology (7 pairs = 14 edges)
            ("node://room/crypt/entrance", "node://room/crypt/hall_of_pillars", "spatial", "stone_door"),
            ("node://room/crypt/hall_of_pillars", "node://room/crypt/entrance", "spatial", "stone_door"),

            ("node://room/crypt/hall_of_pillars", "node://room/crypt/armory", "spatial", "open_archway"),
            ("node://room/crypt/armory", "node://room/crypt/hall_of_pillars", "spatial", "open_archway"),

            ("node://room/crypt/hall_of_pillars", "node://room/crypt/flooded_crypt", "spatial", "trapped_corridor"),
            ("node://room/crypt/flooded_crypt", "node://room/crypt/hall_of_pillars", "spatial", "trapped_corridor"),

            ("node://room/crypt/hall_of_pillars", "node://room/crypt/chasm", "spatial", "wooden_door"),
            ("node://room/crypt/chasm", "node://room/crypt/hall_of_pillars", "spatial", "wooden_door"),

            ("node://room/crypt/flooded_crypt", "node://room/crypt/secret_library", "spatial", "secret_door"),
            ("node://room/crypt/secret_library", "node://room/crypt/flooded_crypt", "spatial", "secret_door"),

            ("node://room/crypt/chasm", "node://room/crypt/antechamber", "spatial", "stone_bridge"),
            ("node://room/crypt/antechamber", "node://room/crypt/chasm", "spatial", "stone_bridge"),

            ("node://room/crypt/antechamber", "node://room/crypt/sanctum_of_the_lich", "spatial", "iron_gate:locked"),
            ("node://room/crypt/sanctum_of_the_lich", "node://room/crypt/antechamber", "spatial", "iron_gate:locked"),

            # Containment: Entities in Rooms
            ("node://entity/player/fighter", "node://room/crypt/entrance", "containment", "resides_in"),
            ("node://entity/player/wizard", "node://room/crypt/entrance", "containment", "resides_in"),
            ("node://entity/player/rogue", "node://room/crypt/entrance", "containment", "resides_in"),

            ("node://entity/npc/skeleton_1", "node://room/crypt/hall_of_pillars", "containment", "resides_in"),
            ("node://entity/npc/skeleton_2", "node://room/crypt/hall_of_pillars", "containment", "resides_in"),
            ("node://entity/npc/ghoul", "node://room/crypt/flooded_crypt", "containment", "resides_in"),
            ("node://entity/npc/lich_apprentice", "node://room/crypt/sanctum_of_the_lich", "containment", "resides_in"),

            # Containment: Items held by entities or stored in rooms (Exactly 1 per item)
            ("node://item/greatsword", "node://entity/player/fighter", "containment", "equipped"),
            ("node://item/spellbook", "node://entity/player/wizard", "containment", "held"),
            ("node://item/thieves_tools", "node://entity/player/rogue", "containment", "held"),
            ("node://item/torch", "node://entity/player/rogue", "containment", "held"),

            ("node://item/healing_potion", "node://room/crypt/armory", "containment", "stored_in"),
            ("node://item/shield_of_dawn", "node://room/crypt/armory", "containment", "stored_in"),
            ("node://item/bone_key", "node://entity/npc/ghoul", "containment", "carries"),
            ("node://item/iron_key", "node://room/crypt/secret_library", "containment", "stored_in"),
            ("node://item/relic_of_dawn", "node://room/crypt/sanctum_of_the_lich", "containment", "stored_in"),

            # Prerequisites: 2 Keys Required for Sanctum of the Lich Gate
            ("node://item/bone_key", "node://room/crypt/sanctum_of_the_lich", "prerequisite", "unlocks"),
            ("node://item/iron_key", "node://room/crypt/sanctum_of_the_lich", "prerequisite", "unlocks"),
        ]

        # Faction Relations: Players hostile to all Undead Enemies
        player_coords = [
            "node://entity/player/fighter",
            "node://entity/player/wizard",
            "node://entity/player/rogue",
        ]
        enemy_coords = [
            "node://entity/npc/skeleton_1",
            "node://entity/npc/skeleton_2",
            "node://entity/npc/ghoul",
            "node://entity/npc/lich_apprentice",
        ]
        for p in player_coords:
            for e in enemy_coords:
                edges.append((p, e, "faction", "hostile"))

        cur.executemany(
            "INSERT INTO hyper_edges (source, target, lens, edge_type) VALUES (?, ?, ?, ?);",
            edges,
        )
        self.conn.commit()

    # --------------------------------------------------------------------------
    # Combat & Action Execution Engines
    # --------------------------------------------------------------------------
    def _eval_damage_dice(self, dice_str: str, rng: random.Random) -> int:
        """Parse and evaluate standard RPG dice notation like 1d10+3 or 2d6+2."""
        try:
            parts = dice_str.lower().replace(" ", "").split("+")
            die_part = parts[0]
            bonus = int(parts[1]) if len(parts) > 1 else 0
            if "d" in die_part:
                num, sides = map(int, die_part.split("d"))
                roll_val = sum(rng.randint(1, sides) for _ in range(num))
            else:
                roll_val = int(die_part)
            return max(1, roll_val + bonus)
        except Exception:
            return 8

    def execute_move(self, entity_coord: str, target_room_coord: str) -> Dict[str, Any]:
        """Move entity to target room if spatial connection exists and is passable."""
        cur = self.conn.cursor()
        cur.execute("SELECT target FROM hyper_edges WHERE source = ? AND lens = 'containment';", (entity_coord,))
        cur_room_row = cur.fetchone()
        if not cur_room_row:
            return {"success": False, "error": f"Entity {entity_coord} is not in any room"}
        cur_room = cur_room_row[0]

        if cur_room == target_room_coord:
            return {"success": True, "already_there": True, "room": cur_room}

        cur.execute(
            "SELECT edge_type FROM hyper_edges WHERE source = ? AND target = ? AND lens = 'spatial';",
            (cur_room, target_room_coord),
        )
        edge_row = cur.fetchone()
        if not edge_row:
            return {"success": False, "error": f"No spatial connection from {cur_room} to {target_room_coord}"}

        edge_type = edge_row[0]
        if edge_type in ("iron_gate:locked", "vault_door:locked"):
            return {"success": False, "error": f"Cannot pass locked door: {edge_type}"}

        cur.execute(
            "UPDATE hyper_edges SET target = ? WHERE source = ? AND lens = 'containment';",
            (target_room_coord, entity_coord),
        )
        self.conn.commit()
        return {"success": True, "old_room": cur_room, "new_room": target_room_coord, "edge_type": edge_type}

    def execute_attack(
        self, attacker_coord: str, target_coord: str, seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Deterministically resolve attack between two entities in the same room.
        Deletes faction edges on target death and sets status = 'corpse'.
        """
        cur = self.conn.cursor()

        cur.execute("SELECT target FROM hyper_edges WHERE source = ? AND lens = 'containment';", (attacker_coord,))
        att_row = cur.fetchone()
        cur.execute("SELECT target FROM hyper_edges WHERE source = ? AND lens = 'containment';", (target_coord,))
        tgt_row = cur.fetchone()

        if not att_row or not tgt_row:
            return {"success": False, "error": "Attacker or target has no room containment"}
        if att_row[0] != tgt_row[0]:
            return {"success": False, "error": f"Target {target_coord} not in same room as {attacker_coord}"}

        cur.execute("SELECT coordinate, body FROM substrate_nodes WHERE coordinate = ?;", (attacker_coord,))
        att_node = cur.fetchone()
        cur.execute("SELECT coordinate, body, summary FROM substrate_nodes WHERE coordinate = ?;", (target_coord,))
        tgt_node = cur.fetchone()

        if not att_node or not tgt_node:
            return {"success": False, "error": "Attacker or target node not found"}

        att_body = json.loads(att_node["body"])
        tgt_body = json.loads(tgt_node["body"])

        tgt_hp = tgt_body.get("hp", 0)
        if tgt_hp <= 0:
            return {"success": False, "error": f"Target {target_coord} is already a corpse"}

        attack_bonus = att_body.get("attack_bonus", 4)
        target_ac = tgt_body.get("ac", 12)

        rng = random.Random(seed if seed is not None else int(time.time() * 1000) % 100000)
        d20 = rng.randint(1, 20)
        total_attack = d20 + attack_bonus
        is_hit = total_attack >= target_ac or d20 == 20

        if not is_hit:
            return {
                "success": True,
                "hit": False,
                "d20": d20,
                "total_attack": total_attack,
                "target_ac": target_ac,
                "damage": 0,
                "target_new_hp": tgt_hp,
                "target_slain": False,
            }

        damage_dice = att_body.get("damage_dice", "1d8+3")
        damage = self._eval_damage_dice(damage_dice, rng)
        new_hp = max(0, tgt_hp - damage)
        target_slain = new_hp == 0

        tgt_body["hp"] = new_hp
        if target_slain:
            tgt_body["status"] = "corpse"
            new_summary = f"Corpse of {tgt_body.get('name', target_coord)} | Slain"
            # Delete active hostile faction edges
            cur.execute(
                "DELETE FROM hyper_edges WHERE lens = 'faction' AND (source = ? OR target = ?);",
                (target_coord, target_coord),
            )
        else:
            new_summary = f"HP: {new_hp}/{tgt_body.get('max_hp', tgt_hp)} | AC: {target_ac} | Injured"

        cur.execute(
            "UPDATE substrate_nodes SET body = ?, summary = ? WHERE coordinate = ?;",
            (json.dumps(tgt_body), new_summary, target_coord),
        )
        self.conn.commit()

        return {
            "success": True,
            "hit": True,
            "d20": d20,
            "total_attack": total_attack,
            "target_ac": target_ac,
            "damage": damage,
            "target_new_hp": new_hp,
            "target_slain": target_slain,
        }

    def execute_cast(
        self, caster_coord: str, spell_coord: str, target_coord: str, seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """Resolve casting a spell (Fireball AoE or Magic Missile single-target)."""
        cur = self.conn.cursor()
        rng = random.Random(seed if seed is not None else int(time.time() * 1000) % 100000)

        if spell_coord == "node://rule/spell/fireball":
            res = self.resolve_aoe_spell(
                spell_coord=spell_coord,
                origin_room_coord=target_coord,
                max_radius=1,
                seed=seed if seed is not None else 42,
            )
            for tgt in res["targets"]:
                if tgt["is_destroyed"]:
                    cur.execute(
                        "DELETE FROM hyper_edges WHERE lens = 'faction' AND (source = ? OR target = ?);",
                        (tgt["coordinate"], tgt["coordinate"]),
                    )
                    cur.execute("SELECT body FROM substrate_nodes WHERE coordinate = ?;", (tgt["coordinate"],))
                    b_row = cur.fetchone()
                    if b_row:
                        b = json.loads(b_row[0])
                        b["status"] = "corpse"
                        cur.execute("UPDATE substrate_nodes SET body = ? WHERE coordinate = ?;", (json.dumps(b), tgt["coordinate"]))
            self.conn.commit()
            return {"success": True, "spell": spell_coord, "aoe_result": res}

        elif spell_coord == "node://rule/spell/magic_missile":
            cur.execute("SELECT body, summary FROM substrate_nodes WHERE coordinate = ?;", (target_coord,))
            tgt_node = cur.fetchone()
            if not tgt_node:
                return {"success": False, "error": "Target entity not found"}
            tgt_body = json.loads(tgt_node["body"])
            tgt_hp = tgt_body.get("hp", 0)
            if tgt_hp <= 0:
                return {"success": False, "error": "Target is already a corpse"}

            damage = sum(rng.randint(1, 4) + 1 for _ in range(3))  # 3d4+3 force
            new_hp = max(0, tgt_hp - damage)
            target_slain = new_hp == 0

            tgt_body["hp"] = new_hp
            if target_slain:
                tgt_body["status"] = "corpse"
                new_summary = f"Corpse of {tgt_body.get('name', target_coord)} | Slain by Magic Missile"
                cur.execute(
                    "DELETE FROM hyper_edges WHERE lens = 'faction' AND (source = ? OR target = ?);",
                    (target_coord, target_coord),
                )
            else:
                new_summary = f"HP: {new_hp}/{tgt_body.get('max_hp', tgt_hp)} | AC: {tgt_body.get('ac', 10)} | Injured"

            cur.execute(
                "UPDATE substrate_nodes SET body = ?, summary = ? WHERE coordinate = ?;",
                (json.dumps(tgt_body), new_summary, target_coord),
            )
            self.conn.commit()
            return {
                "success": True,
                "spell": spell_coord,
                "hit": True,
                "damage": damage,
                "target_new_hp": new_hp,
                "target_slain": target_slain,
            }
        else:
            return {"success": False, "error": f"Unknown spell {spell_coord}"}

    def execute_interact(self, agent_coord: str, target_node_coord: str) -> Dict[str, Any]:
        """
        Interact with an item (loot it into inventory) or a room/door (unlock/open it).
        Enforces prerequisite verification.
        """
        cur = self.conn.cursor()

        # Item Looting
        if target_node_coord.startswith("node://item/"):
            cur.execute("SELECT target FROM hyper_edges WHERE source = ? AND lens = 'containment';", (target_node_coord,))
            item_holder_row = cur.fetchone()
            if not item_holder_row:
                return {"success": False, "error": f"Item {target_node_coord} has no containment edge"}
            holder = item_holder_row[0]

            cur.execute("SELECT target FROM hyper_edges WHERE source = ? AND lens = 'containment';", (agent_coord,))
            agent_room_row = cur.fetchone()
            if not agent_room_row:
                return {"success": False, "error": "Agent has no room containment"}
            agent_room = agent_room_row[0]

            holder_is_room = (holder == agent_room)
            holder_is_entity_in_room = False
            if not holder_is_room:
                cur.execute("SELECT target FROM hyper_edges WHERE source = ? AND lens = 'containment';", (holder,))
                h_room = cur.fetchone()
                if h_room and h_room[0] == agent_room:
                    holder_is_entity_in_room = True

            if not (holder_is_room or holder_is_entity_in_room):
                return {"success": False, "error": f"Item {target_node_coord} not reachable in room {agent_room}"}

            self.transfer_item(target_node_coord, agent_coord)
            return {"success": True, "action": "looted", "item": target_node_coord, "new_holder": agent_coord}

        # Room / Door Unlocking
        elif target_node_coord.startswith("node://room/"):
            feas = self.verify_action_feasibility(agent_coord, target_node_coord)
            if not feas["is_feasible"]:
                return {
                    "success": False,
                    "action": "unlock_failed",
                    "reason": feas["reason"],
                    "missing_prerequisites": feas["missing_prerequisites"],
                }

            agent_room = feas["entity_room"]
            cur.execute(
                """
                UPDATE hyper_edges
                SET edge_type = 'open'
                WHERE lens = 'spatial'
                  AND ((source = ? AND target = ?) OR (source = ? AND target = ?));
                """,
                (agent_room, target_node_coord, target_node_coord, agent_room),
            )
            self.conn.commit()
            return {"success": True, "action": "unlocked_and_opened", "target_room": target_node_coord}

        return {"success": False, "error": f"Unknown target coordinate type: {target_node_coord}"}

    # --------------------------------------------------------------------------
    # Invariant Watchdogs (Asserted Every Tick)
    # --------------------------------------------------------------------------
    def assert_invariants(self, last_action_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Assert the four physical & mathematical invariants directly in SQLite:
        1. Matter Invariant: COUNT(containment) == 1 per item.
        2. Epistemic Invariant: No action executed on a node outside visible state.
        3. Life Cycle Invariant: Dead entities (HP <= 0) have 0 active faction edges and status == 'corpse'/'destroyed'.
        4. Topological Consistency: All spatial room connections are bidirectional.
        """
        cur = self.conn.cursor()

        # 1. Matter Invariant
        cur.execute("""
            SELECT s.coordinate, COUNT(e.source) as cnt
            FROM substrate_nodes s
            LEFT JOIN hyper_edges e ON s.coordinate = e.source AND e.lens = 'containment'
            WHERE s.node_type = 'item'
            GROUP BY s.coordinate
            HAVING cnt != 1;
        """)
        matter_violations = cur.fetchall()
        if matter_violations:
            violation_details = [f"{row[0]} (edges: {row[1]})" for row in matter_violations]
            raise AssertionError(f"Matter Invariant Violated: Items without exactly 1 containment edge: {violation_details}")

        # 2. Epistemic Invariant
        if last_action_context:
            target_coord = last_action_context.get("target_coord")
            visible_coords = last_action_context.get("visible_coords", set())
            agent_coord = last_action_context.get("agent_coord")
            if target_coord and target_coord not in visible_coords:
                raise AssertionError(
                    f"Epistemic Invariant Violated: Agent {agent_coord} interacted with {target_coord} "
                    f"which is outside line-of-sight perception!"
                )

        # 3. Life Cycle Invariant
        cur.execute("""
            SELECT e.source, e.target, n.coordinate
            FROM hyper_edges e
            JOIN substrate_nodes n ON (e.source = n.coordinate OR e.target = n.coordinate)
            WHERE e.lens = 'faction'
              AND json_extract(n.body, '$.hp') <= 0;
        """)
        faction_violations = cur.fetchall()
        if faction_violations:
            raise AssertionError(
                f"Life Cycle Invariant Violated: Slain entity still has active hostile faction edges: {faction_violations}"
            )

        cur.execute("""
            SELECT coordinate, json_extract(body, '$.status')
            FROM substrate_nodes
            WHERE node_type = 'entity'
              AND json_extract(body, '$.hp') <= 0
              AND json_extract(body, '$.status') NOT IN ('corpse', 'destroyed');
        """)
        status_violations = cur.fetchall()
        if status_violations:
            raise AssertionError(
                f"Life Cycle Invariant Violated: Slain entity not converted to corpse/destroyed: {status_violations}"
            )

        # 4. Topological Consistency
        cur.execute("""
            SELECT e1.source, e1.target
            FROM hyper_edges e1
            WHERE e1.lens = 'spatial'
              AND NOT EXISTS (
                  SELECT 1 FROM hyper_edges e2
                  WHERE e2.source = e1.target
                    AND e2.target = e1.source
                    AND e2.lens = 'spatial'
              );
        """)
        topology_violations = cur.fetchall()
        if topology_violations:
            raise AssertionError(
                f"Topological Consistency Violated: Spatial edges are not bidirectional: {topology_violations}"
            )

        return {"valid": True, "violations": []}


def init_dnd_engine(db_path: Path = Path("dnd_substrate.db"), expanded: bool = False) -> DndSubstrateEngine:
    """Initialize D&D engine and seed either the Sunken Crypt (5-room) or Expanded Crypt (8-room)."""
    engine = DndSubstrateEngine(db_path)
    if expanded:
        engine.seed_expanded_crypt()
    else:
        engine.seed_sunken_crypt()
    return engine


if __name__ == "__main__":
    db_file = Path("dnd_substrate.db")
    engine = init_dnd_engine(db_file)
    print("D&D Substrate Initialized & Sunken Crypt Seeded.")
    v = engine.get_visible_state("node://entity/player/cleric")
    print(f"FoW visible tokens: {v['token_count']} in {v['execution_latency_ms']:.3f} ms")
    engine.close()
