"""
id: evasive_tension_chase
name: High-Tension Evasive Ecosystem
description: Adrenaline dash, raycast occlusion, stamina recovery
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

    # 1. Update Foragers (Active Escape & Dash)
    for forager in foragers:
        fx = forager["x"]
        fy = forager["y"]
        energy = forager["attributes"].get("energy", 100.0)
        
        # Proximity to nearest stalker
        closest_stalker = None
        min_stalker_dist = float("inf")
        for s in stalkers:
            dist = ((fx - s["x"])**2 + (fy - s["y"])**2)**0.5
            if dist < min_stalker_dist:
                min_stalker_dist = dist
                closest_stalker = s
                
        # ADRENALINE DASH: Evade up to 2 tiles away if stalker within 2.0 tiles
        dashed = False
        if min_stalker_dist <= 2.0 and energy >= 12.0 and closest_stalker:
            dash_candidates = [
                (fx + 2, fy), (fx - 2, fy), (fx, fy + 2), (fx, fy - 2),
                (fx + 1, fy + 1), (fx - 1, fy - 1), (fx + 1, fy - 1), (fx - 1, fy + 1)
            ]
            valid_dashes = []
            for dx, dy in dash_candidates:
                if 0 <= dx < state["width"] and 0 <= dy < state["height"]:
                    cell = grid.get((dx, dy), {})
                    if cell.get("attributes", {}).get("traversable", True):
                        d_new = ((dx - closest_stalker["x"])**2 + (dy - closest_stalker["y"])**2)**0.5
                        if d_new > min_stalker_dist:
                            valid_dashes.append((dx, dy, d_new))
            
            if valid_dashes:
                best_dash = max(valid_dashes, key=lambda d: d[2])
                forager["x"] = best_dash[0]
                forager["y"] = best_dash[1]
                forager["attributes"]["energy"] = max(0.0, energy - 12.0)
                events.append({"step": state["step"] + 1, "action": "adrenaline_dash", "entity": forager["id"], "to": [best_dash[0], best_dash[1]]})
                dashed = True

        if not dashed:
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
                d_food = float("inf")
                if resources:
                    for rx, ry in resources:
                        dist = ((cx - rx)**2 + (cy - ry)**2)**0.5
                        if dist < d_food:
                            d_food = dist
                else:
                    d_food = 0.0
                
                d_stalker = float("inf")
                if stalkers:
                    for s in stalkers:
                        dist = ((cx - s["x"])**2 + (cy - s["y"])**2)**0.5
                        if dist < d_stalker:
                            d_stalker = dist
                else:
                    d_stalker = 10.0
                    
                hazard_cost = grid.get((cx, cy), {}).get("attributes", {}).get("hazard", 0.0)
                score = (d_food * 1.0) - (min(d_stalker, 6.0) * 5.0) + (hazard_cost * 0.4)
                
                if score < best_score:
                    best_score = score
                    best_move = (cx, cy)
                    
            forager["x"] = best_move[0]
            forager["y"] = best_move[1]
            forager["attributes"]["energy"] = max(0.0, energy - 0.5)

        # Harvest food
        cur_cell = grid.get((forager["x"], forager["y"]), {})
        cur_res = cur_cell.get("attributes", {}).get("resource", 0.0)
        if cur_res > 0.0:
            intake = min(cur_res, 25.0)
            cur_cell["attributes"]["resource"] -= intake
            forager["attributes"]["energy"] = min(150.0, forager["attributes"].get("energy", 0.0) + intake)
            events.append({"step": state["step"] + 1, "action": "forager_feed", "entity": forager["id"], "amount": intake})

    # 2. Update Stalkers with Line of Sight and Fatigue
    for stalker in stalkers:
        sx = stalker["x"]
        sy = stalker["y"]
        stamina = stalker["attributes"].get("stamina", 100.0)
        cooldown = stalker["attributes"].get("cooldown", 0)
        
        if cooldown > 0:
            stalker["attributes"]["cooldown"] = cooldown - 1
            stalker["attributes"]["stamina"] = min(120.0, stamina + 25.0)
            events.append({"step": state["step"] + 1, "action": "stalker_recharging", "entity": stalker["id"]})
            continue

        if stamina <= 15.0:
            stalker["attributes"]["cooldown"] = 2
            events.append({"step": state["step"] + 1, "action": "stalker_exhausted", "entity": stalker["id"]})
            continue

        visible_targets = []
        for f in foragers:
            dist = ((f["x"] - sx)**2 + (f["y"] - sy)**2)**0.5
            if dist <= 6.0:
                occluded = False
                if (sx < 3 and f["x"] > 3) or (sx > 3 and f["x"] < 3):
                    t = (3.0 - sx) / (f["x"] - sx)
                    y_cross = sy + t * (f["y"] - sy)
                    if 1.5 <= y_cross <= 4.5:
                        occluded = True
                if not occluded:
                    visible_targets.append((f, dist))
        
        candidates = [(sx + 1, sy), (sx - 1, sy), (sx, sy + 1), (sx, sy - 1)]
        valid_moves = []
        for cx, cy in candidates:
            if 0 <= cx < state["width"] and 0 <= cy < state["height"]:
                cell = grid.get((cx, cy), {})
                if cell.get("attributes", {}).get("traversable", True):
                    valid_moves.append((cx, cy))
        
        if valid_moves:
            if visible_targets:
                target = min(visible_targets, key=lambda item: item[1])[0]
                tx = target["x"]
                ty = target["y"]
                best_move = valid_moves[0]
                min_step_dist = float("inf")
                for mx, my in valid_moves:
                    dist = ((mx - tx)**2 + (my - ty)**2)**0.5
                    if dist < min_step_dist:
                        min_step_dist = dist
                        best_move = (mx, my)
                stalker["x"] = best_move[0]
                stalker["y"] = best_move[1]
                stalker["attributes"]["stamina"] = max(0.0, stamina - 4.0)
            else:
                stalker["x"] = valid_moves[0][0]
                stalker["y"] = valid_moves[0][1]
                stalker["attributes"]["stamina"] = max(0.0, stamina - 1.0)

        for f in foragers:
            if stalker["x"] == f["x"] and stalker["y"] == f["y"]:
                f["attributes"]["alive"] = False
                events.append({"step": state["step"] + 1, "action": "stalker_strike", "hunter": stalker["id"], "prey": f["id"]})

    # 3. Hazard checks
    for ent in entities:
        if ent.get("attributes", {}).get("alive", True) and ent["x"] == 4 and ent["y"] == 5:
            if ent.get("attributes", {}).get("role") == "stalker":
                ent["attributes"]["stamina"] = max(0.0, ent["attributes"].get("stamina", 0.0) - 25.0)
            else:
                ent["attributes"]["energy"] = max(0.0, ent["attributes"].get("energy", 0.0) - 8.0)
            events.append({"step": state["step"] + 1, "action": "hazard_burn", "entity": ent["id"]})

    emit_step(new_entities=entities, new_cells=cells, new_events=events)
