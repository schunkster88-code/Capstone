"""
id: baseline_forage
name: Baseline Random Walk Foraging
description: Active exploratory foraging routine stepping through traversable terrain
default_params: {
  "energy_decay": 1.0,
  "step_rate": 1
}
"""

def step(state, params, emit_step):
    w = state["width"]
    h = state["height"]
    entities = [dict(e) for e in state["entities"]]
    events = []

    for e in entities:
        cx, cy = e["x"], e["y"]
        attrs = dict(e.get("attributes", {}))

        # Check adjacent traversable moves
        moves = [
            (cx + dx, cy + dy)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
            if 0 <= cx + dx < w and 0 <= cy + dy < h
        ]
        valid_moves = []
        for mx, my in moves:
            cell = next((c for c in state["cells"] if c["x"] == mx and c["y"] == my), None)
            if cell and cell.get("attributes", {}).get("traversable", True):
                valid_moves.append((mx, my))

        if valid_moves:
            nx, ny = random.choice(valid_moves)
            e["x"] = nx
            e["y"] = ny
            action_name = f"forage_step_to_{nx}_{ny}"
            attrs["last_action"] = action_name
            attrs["energy"] = round(attrs.get("energy", 100.0) - params.get("energy_decay", 1.0), 2)
            attrs["stress_level"] = round(max(0.0, attrs.get("stress_level", 4.0) + random.uniform(-0.15, 0.15)), 2)
            attrs["cumulative_surprise"] = round(attrs.get("cumulative_surprise", 0.0) + random.uniform(0.1, 0.4), 2)
            e["attributes"] = attrs
            events.append({"step": state["step"] + 1, "entity_id": e["id"], "action": action_name, "surprise": 0.22})

    emit_step(entities=entities, cells=state["cells"], events=events)
