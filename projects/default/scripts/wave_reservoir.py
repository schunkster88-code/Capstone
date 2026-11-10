"""
id: wave_reservoir
name: 2D Wave Equation Reservoir
description: Discretized scalar wave equation with reflective boundaries
default_params: {}
"""

c_speed_sq = 0.25   # Propagation wave speed squared (Courant stable <= 0.5)
damping = 0.97      # Viscous medium decay
dt = 1.0

for _ in range(steps_to_run):
    cells = state["cells"]
    entities = state["entities"]
    events = []
    w = state["width"]
    h = state["height"]
    
    # Fast 2D lookup of current field u and velocity v
    u_grid = {}
    v_grid = {}
    for c in cells:
        pos = (c["x"], c["y"])
        attrs = c.get("attributes", {})
        u_grid[pos] = attrs.get("u", 0.0)
        v_grid[pos] = attrs.get("v", 0.0)

    # 1. Update probes / wave sources (inject periodic perturbations into the field)
    for probe in entities:
        attrs = probe.get("attributes", {})
        phase = attrs.get("phase", 0.0)
        freq = attrs.get("freq", 0.3)
        
        # Periodic pulse without external math library: simple 3-term polynomial sine proxy
        # normalized cycle p in [-1, 1]
        p = (phase % 6.28318) - 3.14159
        # sine approximation: x - x^3/6
        pulse = p - (p**3) / 6.0
        
        px, py = probe["x"], probe["y"]
        u_grid[(px, py)] = u_grid.get((px, py), 0.0) + (pulse * 0.4)
        attrs["phase"] = phase + freq

    # 2. Compute 2D discrete Laplacian & integrate wave field
    new_u = {}
    new_v = {}
    for y in range(h):
        for x in range(w):
            u_center = u_grid[(x, y)]
            v_center = v_grid[(x, y)]
            
            # Neumann boundary conditions (reflective walls at grid bounds)
            u_left  = u_grid[(x - 1, y)] if x > 0 else u_center
            u_right = u_grid[(x + 1, y)] if x < w - 1 else u_center
            u_up    = u_grid[(x, y - 1)] if y > 0 else u_center
            u_down  = u_grid[(x, y + 1)] if y < h - 1 else u_center
            
            # Discrete Laplacian
            laplacian = (u_left + u_right + u_up + u_down) - (4.0 * u_center)
            
            # Euler leapfrog integration
            v_next = (v_center + laplacian * c_speed_sq * dt) * damping
            u_next = u_center + v_next * dt
            
            # Clamp minimal residual noise to keep JSON tiny
            if -0.001 < u_next < 0.001:
                u_next = 0.0
            if -0.001 < v_next < 0.001:
                v_next = 0.0

            new_u[(x, y)] = u_next
            new_v[(x, y)] = v_next

    # 3. Commit wave states back to cells and compute total field energy
    total_energy = 0.0
    for c in cells:
        pos = (c["x"], c["y"])
        val = new_u[pos]
        vel = new_v[pos]
        
        c["attributes"]["u"] = round(val, 4)
        c["attributes"]["v"] = round(vel, 4)
        # Intensity mapped for UI rendering (absolute amplitude)
        c["attributes"]["intensity"] = min(1.0, round(abs(val), 3))
        
        total_energy += (val**2 + vel**2)

    events.append({
        "step": state["step"] + 1,
        "phase": "wave_interference",
        "reservoir_energy": round(total_energy, 4)
    })

    emit_step(new_entities=entities, new_cells=cells, new_events=events)
