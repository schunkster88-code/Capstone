"""
id: dynamic_walker
name: Dynamic Substrate Traversal
description: Traverses hypergraph path and emits step transitions within runner sandbox
default_params: {}
"""

def step(state, params, emit_step):
    entities = [dict(e) for e in state.get("entities", [])]
    events = []
    current_step = state.get("step", 0) + 1

    # Map of coordinates to next hop under the dependency lens
    adjacency = {
        "node://task/101": {"next": "node://task/102", "weight": 1.0},
        "node://task/102": {"next": "node://task/103", "weight": 2.0}
    }

    # Ensure our walker entity exists in state
    walker = None
    for e in entities:
        if e.get("id") == "traverser_1":
            walker = e
            break

    if not walker:
        walker = {
            "id": "traverser_1",
            "x": 0,
            "y": 0,
            "coordinate": "node://task/101",
            "status": "active"
        }
        entities.append(walker)

    current_coord = walker.get("coordinate", "node://task/101")
    edge = adjacency.get(current_coord)

    if edge:
        target = edge["next"]
        walker["coordinate"] = target
        # Shift coordinate position on the 2D visualizer grid
        walker["x"] = min(state.get("width", 20) - 1, walker.get("x", 0) + 1)

        events.append({
            "step": current_step,
            "action": "traverse_hop",
            "entity": walker["id"],
            "from": current_coord,
            "to": target,
            "lens": "dependency",
            "weight": edge["weight"]
        })
    else:
        events.append({
            "step": current_step,
            "action": "terminal_reached",
            "entity": walker["id"],
            "coordinate": current_coord
        })

    emit_step(new_entities=entities, new_cells=state.get("cells", []), new_events=events)
