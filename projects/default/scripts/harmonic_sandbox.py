"""
id: harmonic_sandbox
name: Prime Harmonic Wave Reservoir
description: Flattened execution loop with no lambdas or scoped comprehensions
default_params: {}
"""

c_sq = 0.22      # Wave propagation speed
damping = 0.965  # Slight acoustic dispersion
dt = 1.0

for _ in range(steps_to_run):
    step_num = state["step"] + 1
    cells = state["cells"]
    entities = state["entities"]
    events = []
    w, h = state["width"], state["height"]

    u_grid = {}
    v_grid = {}
    for c in cells:
        pos = (c["x"], c["y"])
        attrs = c.get("attributes", {})
        u_grid[pos] = attrs.get("u", 0.0)
        v_grid[pos] = attrs.get("v", 0.0)

    # 1. Emitters pulse on their prime cycles (cadence = 2, 3, 5)
    for ent in entities:
        attrs = ent.get("attributes", {})
        if attrs.get("role") == "emitter":
            cadence = attrs.get("prime_cadence", 2)
            if step_num % cadence == 0:
                pos = (ent["x"], ent["y"])
                pulse_amp = attrs.get("amplitude", 0.8)
                u_grid[pos] = u_grid.get(pos, 0.0) + pulse_amp
                events.append({
                    "step": step_num,
                    "event": "prime_pluck",
                    "emitter": ent["id"],
                    "cadence": cadence
                })

    # 2. Integrate 2D Discrete Wave Field
    new_u = {}
    new_v = {}
    total_energy = 0.0

    for y in range(h):
        for x in range(w):
            u_c = u_grid[(x, y)]
            v_c = v_grid[(x, y)]

            # Neumann reflective boundaries
            u_l = u_grid[(x - 1, y)] if x > 0 else u_c
            u_r = u_grid[(x + 1, y)] if x < w - 1 else u_c
            u_u = u_grid[(x, y - 1)] if y > 0 else u_c
            u_d = u_grid[(x, y + 1)] if y < h - 1 else u_c

            laplacian = (u_l + u_r + u_u + u_d) - (4.0 * u_c)
            v_next = (v_c + laplacian * c_sq * dt) * damping
            u_next = u_c + v_next * dt

            if -0.0008 < u_next < 0.0008:
                u_next = 0.0
            if -0.0008 < v_next < 0.0008:
                v_next = 0.0

            new_u[(x, y)] = u_next
            new_v[(x, y)] = v_next
            total_energy += abs(u_next)

    # 3. Update Cells with field heights
    for c in cells:
        pos = (c["x"], c["y"])
        val = new_u[pos]
        vel = new_v[pos]
        c["attributes"]["u"] = round(val, 4)
        c["attributes"]["v"] = round(vel, 4)
        c["attributes"]["intensity"] = min(1.0, round(abs(val), 3))

    # 4. Listener (Hydrophone) navigation without lambdas
    for ent in entities:
        if ent.get("attributes", {}).get("role") == "listener":
            lx, ly = ent["x"], ent["y"]
            
            candidates = [(lx, ly), (lx + 1, ly), (lx - 1, ly), (lx, ly + 1), (lx, ly - 1)]
            valid_moves = []
            for cx, cy in candidates:
                if 0 <= cx < w and 0 <= cy < h:
                    valid_moves.append((cx, cy))
            
            best_pos = (lx, ly)
            highest_amp = -1.0
            for mx, my in valid_moves:
                amp = abs(new_u.get((mx, my), 0.0))
                if amp > highest_amp:
                    highest_amp = amp
                    best_pos = (mx, my)
            
            ent["x"] = best_pos[0]
            ent["y"] = best_pos[1]
            
            heard = round(new_u.get(best_pos, 0.0), 3)
            ent["attributes"]["heard_amplitude"] = heard
            
            if abs(heard) > 0.45:
                sensation = "surging_harmonic"
            elif abs(heard) > 0.18:
                sensation = "resonant_hum"
            elif abs(heard) < 0.03:
                sensation = "quiet_node"
            else:
                sensation = "steady_drift"
                
            ent["attributes"]["sensation"] = sensation
            
            events.append({
                "step": step_num,
                "event": "listening",
                "pos": [best_pos[0], best_pos[1]],
                "amplitude": heard,
                "sensation": sensation
            })

    emit_step(new_entities=entities, new_cells=cells, new_events=events)
