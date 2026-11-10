"""
id: patrol_and_recover
name: Patrol and Recover Routine
description: Scavenger retreats to heal, drone conducts perimeter sweep, agent rests.
default_params: {}
"""

for _ in range(steps_to_run):
    entities = state["entities"]
    events = []
    
    for ent in entities:
        if ent["id"] == "scavenger_beta":
            # Retreat toward 0,0 to repair
            if ent["x"] > 0: ent["x"] -= 1
            if ent["y"] > 0: ent["y"] -= 1
            ent["attributes"]["stamina"] = min(100.0, ent["attributes"].get("stamina", 0) + 10.0)
            ent["attributes"]["status"] = "retreating_to_reboot"
            events.append({"step": state["step"] + 1, "action": "retreat", "entity": "scavenger_beta"})
            
        elif ent["id"] == "agent_1":
            # Siphon energy and de-stress at cache
            ent["attributes"]["energy"] = min(200.0, ent["attributes"].get("energy", 0) + 5.0)
            ent["attributes"]["stress_level"] = max(0.0, ent["attributes"].get("stress_level", 0) - 1.0)
            events.append({"step": state["step"] + 1, "action": "rest_and_recharge", "entity": "agent_1"})
            
        elif ent["id"] == "drone_alpha":
            # Reposition to overwatch
            ent["x"] = 1
            ent["y"] = 2
            ent["attributes"]["battery"] = max(0.0, ent["attributes"].get("battery", 0) - 2.0)
            events.append({"step": state["step"] + 1, "action": "high_overwatch", "entity": "drone_alpha"})

    emit_step(new_entities=entities, new_events=events)
