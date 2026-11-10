"""
id: multi_agent_chase
name: Multi-Forager vs Dual-Stalker Ecosystem
description: Flattened loop safe for sandboxed exec without comprehension scoping leaks.
default_params: {}
"""

for _ in range(steps_to_run):
    cells = state["cells"]
    entities = state["entities"]
    events = []
    
    grid = {}
    for c in cells:
        grid[(c["x"], c["y"])] = c

    resources = []
    for c in cells:
        if c.get("attributes", {}).get("resource", 0.0) > 0.0:
            resources.append((c["x"], c["y"]))

    foragers = []
    stalkers = []
    for e in entities:
        attrs = e.get("attributes", {})
        if attrs.get("alive", True):
            if attrs.get("role") == "forager":
                foragers.append(e)
            elif attrs.get("role") == "stalker":
                stalkers.append(e)

    # 1. Update Foragers
    for forager in foragers:
        fx = forager["x"]
        fy = forager["y"]
        
        candidates = [(fx, fy), (fx + 1, fy), (fx - 1, fy), (fx, fy + 1), (fx, fy - 1)]
        valid_moves = []
        for cx, cy in candidates:
            if 0 <= cx < state["width"] and 0 <= cy < state["height"]:
                cell = grid.get((cx, cy), {})
                if cell.get("attributes", {}).get("traversable", True):
                    valid_moves.append((cx, cy))
        
        best_move = (fx, fy)
        best_score = float("inf")
        
        for cx, cy in valid_moves:
            # Explicit min distance to food
            d_food = float("inf")
            if resources:
                for rx, ry in resources:
                    dist = ((cx - rx)**2 + (cy - ry)**2)**0.5
                    if dist < d_food:
                        d_food = dist
            else:
                d_food = 0.0
            
            # Explicit min distance to stalker
            d_stalker = float("inf")
            if stalkers:
                for s in stalkers:
                    dist = ((cx - s["x"])**2 + (cy - s["y"])**2)**0.5
                    if dist < d_stalker:
                        d_stalker = dist
            else:
                d_stalker = 10.0
                
            hazard_cost = grid.get((cx, cy), {}).get("attributes", {}).get("hazard", 0.0)
            score = (d_food * 1.5) - (min(d_stalker, 4.0) * 3.5) + (hazard_cost * 0.5)
            
            if score < best_score:
                best_score = score
                best_move = (cx, cy)
                
        forager["x"] = best_move[0]
        forager["y"] = best_move[1]
        forager["attributes"]["energy"] = max(0.0, forager["attributes"].get("energy", 100.0) - 1.0)
        
        # Feed if standing on resource
        cur_cell = grid.get(best_move, {})
        cur_res = cur_cell.get("attributes", {}).get("resource", 0.0)
        if cur_res > 0.0:
            intake = min(cur_res, 20.0)
            cur_cell["attributes"]["resource"] -= intake
            forager["attributes"]["energy"] = min(150.0, forager["attributes"].get("energy", 0.0) + intake)
            events.append({"step": state["step"] + 1, "action": "forager_feed", "entity": forager["id"], "amount": intake})

    # 2. Update Stalkers
    for stalker in stalkers:
        sx = stalker["x"]
        sy = stalker["y"]
        
        if foragers:
            # Find nearest living forager target
            target = None
            min_target_dist = float("inf")
            for f in foragers:
                dist = ((f["x"] - sx)**2 + (f["y"] - sy)**2)**0.5
                if dist < min_target_dist:
                    min_target_dist = dist
                    target = f
            
            tx = target["x"]
            ty = target["y"]
            
            candidates = [(sx + 1, sy), (sx - 1, sy), (sx, sy + 1), (sx, sy - 1)]
            valid_moves = []
            for cx, cy in candidates:
                if 0 <= cx < state["width"] and 0 <= cy < state["height"]:
                    cell = grid.get((cx, cy), {})
                    if cell.get("attributes", {}).get("traversable", True):
                        valid_moves.append((cx, cy))
            
            if valid_moves:
                best_move = valid_moves[0]
                min_step_dist = float("inf")
                for mx, my in valid_moves:
                    dist = ((mx - tx)**2 + (my - ty)**2)**0.5
                    if dist < min_step_dist:
                        min_step_dist = dist
                        best_move = (mx, my)
                        
                stalker["x"] = best_move[0]
                stalker["y"] = best_move[1]
                stalker["attributes"]["stamina"] = max(0.0, stalker["attributes"].get("stamina", 120.0) - 1.2)
                
            # Intercept
            if stalker["x"] == target["x"] and stalker["y"] == target["y"]:
                target["attributes"]["alive"] = False
                events.append({"step": state["step"] + 1, "action": "stalker_strike", "hunter": stalker["id"], "prey": target["id"]})

    # 3. Hazard checks
    for ent in entities:
        if ent.get("attributes", {}).get("alive", True) and ent["x"] == 4 and ent["y"] == 5:
            stat = "energy" if "energy" in ent.get("attributes", {}) else "stamina"
            ent["attributes"][stat] = max(0.0, ent["attributes"].get(stat, 0.0) - 15.0)
            events.append({"step": state["step"] + 1, "action": "hazard_burn", "entity": ent["id"]})

    emit_step(new_entities=entities, new_cells=cells, new_events=events)
