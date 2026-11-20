# MechDesign Agent - Calculation Report

Generated 2026-11-20 02:18 (UTC+0800) by MechDesign Agent v0.1.0. Model: rectangular cantilever, Euler-Bernoulli beam theory. All numbers below were computed by the deterministic mechanics engine.

Note: EXAMPLE configuration (illustrative values, not a real product specification).


## 1. Inputs

| Quantity | Symbol | Value | Unit |
|---|---|---|---|
| Beam length | L | 80 | mm |
| Current width (out of bending plane) | b | 20 | mm |
| Current height (bending direction) | h | 6 | mm |
| Material | - | PLA (nominal bulk values) | - |
| Young's modulus | E | 3.5 | GPa |
| Density | rho | 1240 | kg/m^3 |
| Tip load (transverse, h direction) | F | 5 | N |
| Allowable tip deflection | delta_allow | 0.5 | mm |
| Allowable bending stress | sigma_allow | 20 | MPa |
| Max aspect ratio h/b | - | not checked | - |
| Search range b | - | 5 to 30 step 1 | mm |
| Search range h | - | 3 to 12 step 0.5 | mm |

Internal calculations use SI units (m, N, Pa, kg); values are converted for display.


## 2. Model and assumptions

- I = b h^3 / 12;  m = rho b h L;  delta = F L^3 / (3 E I);  sigma_max = 6 F L / (b h^2) (at the fixed end, extreme fibres).
- Straight, prismatic beam with a solid rectangular cross-section (width b, height h in the bending direction).
- One end ideally fixed (perfectly rigid clamp: zero displacement and zero rotation).
- A single static transverse point load F at the free end, acting perpendicular to the beam axis in the h direction.
- Homogeneous, isotropic, linearly elastic material (Young's modulus E, density rho).
- Euler-Bernoulli beam theory: plane sections remain plane and normal to the axis; shear deformation neglected.
- Small deflections and rotations (linear geometry).
- Self-weight of the beam is not included in the load.


### Limitations (not represented by this model)

- Does not represent actual joint or fastener flexibility at the fixed end (a real clamp/bolted joint is less stiff, so real deflection will be larger).
- Does not represent 3D-printing effects: anisotropy between layers, infill, porosity, layer adhesion, creep, moisture or temperature dependence.
- Does not represent large deformation / geometric nonlinearity.
- Does not represent dynamic loading: vibration, resonance, impact, or fatigue.
- Does not check lateral-torsional buckling, local buckling, stress concentrations at the root fillet/holes, or yield/fracture of the material beyond the optional stress limit.
- Shear deformation is neglected; for short, deep beams (L/h below about 10) the true deflection is noticeably larger than predicted.


## 3. Current design

| b [mm] | h [mm] | I [mm^4] | Mass [g] | Tip deflection [mm] | Max stress [MPa] | Status |
|---|---|---|---|---|---|---|
| 20 | 6 | 360 | 11.9 | 0.6772 | 3.333 | NOT FEASIBLE |

- Tip deflection 0.677 mm exceeds limit 0.5 mm
- Max bending stress 3.33 MPa <= limit 20 MPa


## 4. Design-space search

Fixed during the search: L = 80 mm, E = 3.5 GPa, rho = 1240 kg/m^3, F = 5 N. Grid: 26 b values x 19 h values = 494 candidates. Feasible: 256. Failing deflection: 238; failing stress: 18; failing aspect ratio: 0 (a candidate may fail several).

256 of 494 sampled (b, h) combinations satisfy all constraints. Candidates are ranked by mass within this sampled grid only; they are not guaranteed global optima, and designs between grid points or outside the ranges were not evaluated.


### Feasible candidates ranked by mass (top 15)

| Rank | b [mm] | h [mm] | Mass [g] | Mass vs current | Deflection [mm] | Stress [MPa] | h/b | Reason |
|---|---|---|---|---|---|---|---|---|
| 1 | 5 | 11 | 5.456 | -54.2 % | 0.4396 | 3.967 | 2.2 | Feasible: Tip deflection 0.44 mm <= limit 0.5 mm; Max bending stress 3.97 MPa <= limit 20 MPa. |
| 2 | 5 | 11.5 | 5.704 | -52.1 % | 0.3847 | 3.629 | 2.3 | Feasible: Tip deflection 0.385 mm <= limit 0.5 mm; Max bending stress 3.63 MPa <= limit 20 MPa. |
| 3 | 5 | 12 | 5.952 | -50 % | 0.3386 | 3.333 | 2.4 | Feasible: Tip deflection 0.339 mm <= limit 0.5 mm; Max bending stress 3.33 MPa <= limit 20 MPa. |
| 4 | 6 | 10 | 5.952 | -50 % | 0.4876 | 4 | 1.67 | Feasible: Tip deflection 0.488 mm <= limit 0.5 mm; Max bending stress 4 MPa <= limit 20 MPa. |
| 5 | 6 | 10.5 | 6.25 | -47.5 % | 0.4212 | 3.628 | 1.75 | Feasible: Tip deflection 0.421 mm <= limit 0.5 mm; Max bending stress 3.63 MPa <= limit 20 MPa. |
| 6 | 6 | 11 | 6.547 | -45 % | 0.3664 | 3.306 | 1.83 | Feasible: Tip deflection 0.366 mm <= limit 0.5 mm; Max bending stress 3.31 MPa <= limit 20 MPa. |
| 7 | 7 | 9.5 | 6.597 | -44.6 % | 0.4875 | 3.799 | 1.36 | Feasible: Tip deflection 0.487 mm <= limit 0.5 mm; Max bending stress 3.8 MPa <= limit 20 MPa. |
| 8 | 6 | 11.5 | 6.845 | -42.5 % | 0.3206 | 3.025 | 1.92 | Feasible: Tip deflection 0.321 mm <= limit 0.5 mm; Max bending stress 3.02 MPa <= limit 20 MPa. |
| 9 | 7 | 10 | 6.944 | -41.7 % | 0.418 | 3.429 | 1.43 | Feasible: Tip deflection 0.418 mm <= limit 0.5 mm; Max bending stress 3.43 MPa <= limit 20 MPa. |
| 10 | 6 | 12 | 7.142 | -40 % | 0.2822 | 2.778 | 2 | Feasible: Tip deflection 0.282 mm <= limit 0.5 mm; Max bending stress 2.78 MPa <= limit 20 MPa. |
| 11 | 7 | 10.5 | 7.291 | -38.8 % | 0.361 | 3.11 | 1.5 | Feasible: Tip deflection 0.361 mm <= limit 0.5 mm; Max bending stress 3.11 MPa <= limit 20 MPa. |
| 12 | 8 | 9.5 | 7.539 | -36.7 % | 0.4266 | 3.324 | 1.19 | Feasible: Tip deflection 0.427 mm <= limit 0.5 mm; Max bending stress 3.32 MPa <= limit 20 MPa. |
| 13 | 7 | 11 | 7.638 | -35.8 % | 0.314 | 2.834 | 1.57 | Feasible: Tip deflection 0.314 mm <= limit 0.5 mm; Max bending stress 2.83 MPa <= limit 20 MPa. |
| 14 | 8 | 10 | 7.936 | -33.3 % | 0.3657 | 3 | 1.25 | Feasible: Tip deflection 0.366 mm <= limit 0.5 mm; Max bending stress 3 MPa <= limit 20 MPa. |
| 15 | 7 | 11.5 | 7.986 | -32.9 % | 0.2748 | 2.592 | 1.64 | Feasible: Tip deflection 0.275 mm <= limit 0.5 mm; Max bending stress 2.59 MPa <= limit 20 MPa. |


## 5. Selected candidate

| b [mm] | h [mm] | I [mm^4] | Mass [g] | Tip deflection [mm] | Max stress [MPa] | Status |
|---|---|---|---|---|---|---|
| 6 | 10 | 500 | 5.952 | 0.4876 | 4 | FEASIBLE |

- Tip deflection 0.488 mm <= limit 0.5 mm
- Max bending stress 4 MPa <= limit 20 MPa
- Warning: L/h = 8 < 10: shear deformation (neglected by Euler-Bernoulli theory) may noticeably increase the real deflection.


## 6. Validation information

Numerical cross-check of the selected design. Closed form: tip deflection 0.487619 mm, max stress 4 MPa.

| Solver | Physics | Tip deflection [mm] | Relative difference | Tolerance | Result / notes |
|---|---|---|---|---|---|
| In-house Euler-Bernoulli FE (20 Hermite elements) | Euler-Bernoulli beam (same physics, independent numerical method) | 0.487619 | +8.59e-12 (deflection), +3.96e-11 (stress) | 1e-09 | PASS - Root stress = FE root moment x (h/2) / I. |
| anaStruct 1.7.1 2D frame FE (10 elements) | Euler-Bernoulli frame (open-source, separate code base) | 0.487619 | -6.71e-08 (deflection), -2.24e-08 (stress) | 1e-05 | PASS - Root stress = anaStruct root reaction moment x (h/2) / I. |
| In-house 2D plane-stress FE (Q8, 32x4 elements, nu=0.3) | 2D plane-stress continuum (includes shear deformation; not beam theory) | 0.492092 | -2.98e-03 vs Timoshenko (0.493562 mm); +9.17e-03 vs Euler-Bernoulli | 0.02 | PASS - Compared against Timoshenko estimate (nu = 0.3, kappa = 5/6). The difference from Euler-Bernoulli is model-form error (mainly shear deformation), not a solver error. |

Agreement between numerical models checks the implementation, not physical reality. No physical tests have been performed.

Documented validation suite (6 representative cases, run 2026-11-20T02:18:28+08:00): 36 of 36 comparison checks passed. See docs/validation.md for cases and tolerances.

No physical testing has been performed. Numerical agreement is not physical validation; prototype testing of the real mount (including its joint and printing process) is required before relying on these numbers.


## 7. Narrative explanation

Source: Deterministic template (no LLM); numbers inserted from engine results.

With L = 80 mm, tip load 5 N and material PLA (nominal bulk values), the current design (b = 20 mm, h = 6 mm) has mass 11.9 g, tip deflection 0.677 mm and max bending stress 3.33 MPa; it is not feasible against the allowable deflection 0.5 mm and allowable bending stress 20 MPa. Of 494 sampled (b, h) combinations, 256 satisfy all constraints (238 exceed the deflection limit, 18 exceed the stress limit, 0 exceed the aspect-ratio limit; a candidate can fail more than one). The lightest feasible sampled candidate is b = 5 mm, h = 11 mm: mass 5.46 g (-54% vs current), deflection 0.44 mm (87.9% of the limit), stress 3.97 MPa. Next: b = 5 mm, h = 11.5 mm (5.7 g, 0.385 mm). Because deflection is inversely proportional to b·h³ while mass is proportional to b·h, taller, narrower sections are lighter for the same stiffness; check that such sections are acceptable for buckling, fastening and printing, which this model does not cover. This ranking covers only the sampled grid; it is not a guaranteed global optimum.

