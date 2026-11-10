"""
id: epistemic_chase
name: Epistemic Forager vs Stalker Labyrinth Loop
description: Forager minimizes expected free energy to forage and evade; stalker hunts.
default_params: {}
"""

for _ in range(steps_to_run):
    cells = state["cells"]
    entities = state["entities"]
    events = []
    
    # Fast cell attribute lookup: (x, y) -> cell dict
    grid = {}
    for c in cells:
        grid[(c["x"], c["y"])] = c
    
    # Locate entities
    forager = None
    stalker = None
    for e in entities:
        if e["id"] == "forager_alpha":
            forager = e
        elif e["id"] == "stalker_beta":
            stalker = e
            
    # Known active resources
    resources = []
    for c in cells:
        if c.get("attributes", {}).get("resource", 0.0) > 0.0:
            resources.append((c["x"], c["y"]))
            
    # 1. Update Forager
    if forager and forager.get("attributes", {}).get("alive", True):
        fx = forager["x"]
        fy = forager["y"]
        
        candidates = [(fx, fy), (fx + 1, fy), (fx - 1, fy), (fx, fy + 1), (fx, fy - 1)]
        valid_moves = []
        for cand_x, cand_y in candidates:
            if 0 <= cand_x < state["width"] and 0 <= cand_y < state["height"]:
                cell = grid.get((cand_x, cand_y), {})
                if cell.get("attributes", {}).get("traversable", True):
                    valid_moves.append((cand_x, cand_y))
        
        best_move = (fx, fy)
        best_score = float("inf")
        
        for cand_x, cand_y in valid_moves:
            # Explicit min distance to food
            if resources:
                d_food = float("inf")
                for rx, ry in resources:
                    dist = ((cand_x - rx)**2 + (cand_y - ry)**2)**0.5
                    if dist < d_food:
                        d_food = dist
            else:
                d_food = 0.0
                
            # Distance from stalker
            if stalker:
                d_stalker = ((cand_x - stalker["x"])**2 + (cand_y - stalker["y"])**2)**0.5
            else:
                d_stalker = 10.0
                
            hazard_cost = grid.get((cand_x, cand_y), {}).get("attributes", {}).get("hazard", 0.0)
            
            score = (d_food * 1.5) - (min(d_stalker, 4.0) * 3.0) + (hazard_cost * 0.5)
            if score < best_score:
                best_score = score
                best_move = (cand_x, cand_y)
                
        forager["x"] = best_move[0]
        forager["y"] = best_move[1]
        forager["attributes"]["energy"] = max(0.0, forager["attributes"].get("energy", 100.0) - 1.0)
        
        # Check resource harvest
        cur_cell = grid.get(best_move, {})
        cur_res = cur_cell.get("attributes", {}).get("resource", 0.0)
        if cur_res > 0.0:
            intake = min(cur_res, 30.0)
            cur_cell["attributes"]["resource"] -= intake
            forager["attributes"]["energy"] = min(150.0, forager["attributes"].get("energy", 0.0) + intake)
            events.append({"step": state["step"] + 1, "action": "forager_feed", "amount": intake, "at": list(best_move)})

    # 2. Update Stalker
    if stalker and stalker.get("attributes", {}).get("alive", True):
        sx = stalker["x"]
        sy = stalker["y"]
        tx = forager["x"]
        ty = forager["y"]
        
        candidates = [(sx + 1, sy), (sx - 1, sy), (sx, sy + 1), (sx, sy - 1)]
        valid_stalker_moves = []
        for cand_x, cand_y in candidates:
            if 0 <= cand_x < state["width"] and 0 <= cand_y < state["height"]:
                cell = grid.get((cand_x, cand_y), {})
                if cell.get("attributes", {}).get("traversable", True):
                    valid_stalker_moves.append((cand_x, cand_y))
                    
        if valid_stalker_moves:
            best_stalker_move = valid_stalker_moves[0]
            min_dist = float("inf")
            for mx, my in valid_stalker_moves:
                dist = ((mx - tx)**2 + (my - ty)**2)**0.5
                if dist < min_dist:
                    min_dist = dist
                    best_stalker_move = (mx, my)
                    
            stalker["x"] = best_stalker_move[0]
            stalker["y"] = best_stalker_move[1]
            stalker["attributes"]["stamina"] = max(0.0, stalker["attributes"].get("stamina", 90.0) - 1.5)
            
        if stalker["x"] == forager["x"] and stalker["y"] == forager["y"]:
            forager["attributes"]["alive"] = False
            forager["attributes"]["stress_level"] = 100.0
            events.append({"step": state["step"] + 1, "action": "stalker_strike", "target": "forager_alpha"})

    # Check thermal hazard
    for ent in [forager, stalker]:
        if ent and ent["x"] == 4 and ent["y"] == 5:
            stat_key = "energy" if "energy" in ent.get("attributes", {}) else "stamina"
            ent["attributes"][stat_key] = max(0.0, ent["attributes"].get(stat_key, 0.0) - 15.0)
            events.append({"step": state["step"] + 1, "action": "hazard_burn", "entity": ent["id"]})

    emit_step(new_entities=entities, new_cells=cells, new_events=events)
