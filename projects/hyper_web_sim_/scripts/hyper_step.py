"""
id: hyper_step
name: Hypergraph Step Traversal
description: Inspects outbound links from the active node through a chosen lens and steps forward
default_params: {}
"""

def step(state, params, emit_step):
    entities = [dict(e) for e in state["entities"]]
    events = []
    for e in entities:
        events.append({
            "step": state["step"] + 1,
            "action": "traverse_edge",
            "entity": e["id"]
        })
    emit_step(new_entities=entities, new_cells=state["cells"], new_events=events)
