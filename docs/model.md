# Model and assumptions

## Geometry and sign convention

```
   fixed end (x = 0)                        free end (x = L)
   ▓▓│                                          │  F  (transverse, in the h direction)
   ▓▓│══════════════════════════════════════════│  ↓
   ▓▓│                                          │
         ← L →                    cross-section:  ┌──b──┐
                                                  │     │ h   (h is in the bending direction)
                                                  └─────┘
```

- x runs along the beam axis from the clamp (x = 0) to the free end (x = L).
- The load F acts at x = L, perpendicular to the axis and parallel to h. The input is a **magnitude** (F ≥ 0),
  and deflection is reported as a positive number in the direction of the load.
- b is the width out of the bending plane. h is the height in the bending plane.

## Equations

Small-deflection Euler–Bernoulli theory for a prismatic beam with an ideal clamp and a tip point load:

| Quantity | Expression | Where it is computed |
|---|---|---|
| Second moment of area | I = b h³ / 12 | `mechanics.second_moment_rect` |
| Mass | m = ρ b h L | `mechanics.mass_rect` |
| Deflection curve | v(x) = F x² (3L − x) / (6 E I) | `mechanics.deflection_curve` |
| Tip deflection | δ = v(L) = F L³ / (3 E I) | `mechanics.tip_deflection` |
| Bending moment | M(x) = F (L − x), maximum F L at the clamp | (used by the FE cross-checks) |
| Max bending stress | σ = M c / I = 6 F L / (b h²), at x = 0 and y = ±h/2 | `mechanics.max_bending_stress` |

All calculations are done in SI units (m, N, Pa, kg). Conversion to and from the display units (mm, N, GPa, MPa,
kg/m³, g) happens only in `units.py` and `mechanics.parse_config` / `evaluation_to_display`.

## Assumptions

- Straight, prismatic beam with a solid rectangular section.
- Ideal clamp: zero displacement and zero rotation at x = 0.
- A single static point load at the free end. Self-weight is ignored.
- Homogeneous, isotropic, linearly elastic material.
- Plane sections remain plane and normal to the axis (no shear deformation).
- Small deflections and rotations.

## Validity warnings

The engine attaches warnings to a design; they never change feasibility.

| Condition | Why it matters |
|---|---|
| L/h < 10 | Shear deformation is no longer negligible. Euler–Bernoulli underestimates deflection, by about 1 % at L/h ≈ 7 and about 8 % at L/h = 3 (see [validation](validation.md)). |
| h/b > 4 | Deep, thin sections can buckle sideways (lateral-torsional buckling), which is not checked. |
| δ/L > 0.05 | Small-deflection theory becomes inaccurate. |
| F = 0 | Every design trivially satisfies the limits. |

## Design search

For fixed L, E, ρ and F, the engine evaluates every grid point

    b ∈ {b_min, b_min + Δb, …} ≤ b_max,   h ∈ {h_min, h_min + Δh, …} ≤ h_max

and marks a candidate feasible if δ ≤ δ_allow, σ ≤ σ_allow (if set) and h/b ≤ (h/b)_max (if set).
Feasible candidates are sorted by mass, with ties broken by smaller deflection.

Because δ ∝ 1/(b h³) while m ∝ b h, the lightest section with a given stiffness is as deep and narrow as the ranges
allow. This is why the h/b warning and the optional aspect-ratio constraint exist.

The ranking is only the best within the sampled grid. Designs between grid points or outside the ranges are not
evaluated, and no claim of a global optimum is made.

## Not modelled

These effects are listed in every report:

- real joint or fastener flexibility;
- 3D-printing effects (anisotropy, infill, layer adhesion, creep, moisture, temperature);
- large deformation;
- dynamic loading (vibration, resonance, impact, fatigue);
- buckling;
- stress concentrations;
- material failure beyond the optional stress limit.

## References

- S. P. Timoshenko and J. M. Gere, *Mechanics of Materials* — cantilever deflection and bending stress formulas.
- R. D. Cook, D. S. Malkus, M. E. Plesha and R. J. Witt, *Concepts and Applications of Finite Element Analysis*,
  4th ed. — Hermite beam element and 8-node serendipity element used in the cross-checks.
