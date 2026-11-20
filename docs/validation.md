# Validation and traceability

## What is checked

The closed-form model (δ = FL³/3EI, σ = 6FL/bh²) is compared with three numerical solvers that do
**not** evaluate those formulas:

| Solver | Source | Physics | What agreement means |
|---|---|---|---|
| In-house Euler–Bernoulli FE | `src/mechdesign/fem.py::beam_fe_euler_bernoulli` | 20 two-node Hermite-cubic beam elements, standard 4×4 element stiffness (e.g. Cook et al., *Concepts and Applications of FEA*, 4th ed., §2.4). The global matrix is assembled and solved. Root stress = FE root moment × (h/2)/I. | Units, load placement and boundary conditions are implemented consistently. For a tip point load this element is nodally exact, so differences should be at round-off level. |
| **anaStruct 1.7.1** (open source, <https://github.com/ritchie46/anaStruct>) | `src/mechdesign/fem.py::beam_fe_anastruct` | 2D Euler–Bernoulli frame FE, a separate code base. 10 elements, fixed support at node 1, point load at the tip. Root stress = reported root reaction moment × (h/2)/I. | Agreement with a third-party implementation of the same physics. |
| In-house 2D plane-stress continuum FE | `src/mechdesign/fem.py::plane_stress_q8` | 8-node serendipity quads, 3×3 Gauss, 4 elements through the depth, square elements. All root nodes are clamped. Uniform shear traction F/(bh) on the free edge, with consistent nodal loads. ν = 0.3. | Not beam theory. It includes shear deformation and Poisson effects. It is compared with the Timoshenko estimate δ_T = FL³/3EI + FL/(κGA), κ = 5/6. The gap between it and Euler–Bernoulli is **model-form error**, not solver error. |

## Cases and tolerances

Six cases (`src/mechdesign/validation.py`, run with `mechdesign validate --out validation`): the example PLA mount (L/h 13.3), the example's lightest
feasible candidate (L/h 7.3), a slender PETG strip (L/h 37.5), a steel textbook bar (L/h 10, with a
hand-checkable δ = 0.2 mm and σ = 60 MPa), a stubby aluminium block (L/h 3) and a wide thin section (b/h 25).

| Check | Tolerance (relative) | Rationale |
|---|---|---|
| In-house EB FE vs closed form (δ, σ) | 1e-9 | Nodally exact element; only round-off remains (observed ≤ 2e-11). |
| anaStruct vs closed form (δ, σ) | 1e-5 | anaStruct shows a systematic ~1e-7 difference (internal rounding). The tolerance leaves margin but would still catch any unit or load-placement error. |
| Q8 continuum δ vs Timoshenko estimate | 2 % | Clamp over-constraint (all root nodes fixed) and load-introduction effects, which the 1D estimate ignores. Observed 0.05–0.9 %. |
| Q8 σ_xx (top fibre, mid-span) vs beam theory at the same x | 1 % | Away from the clamp and the load, beam theory holds well. Observed ≤ 0.04 %. |

## Results (latest run)

**36 of 36 checks passed.** The full tables are in [`validation/results.md`](../validation/results.md), and machine-readable
results with the environment versions are in [`validation/results.json`](../validation/results.json). CI re-runs the
suite on every push, on Linux, Windows and macOS. Highlights:

| Case | L/h | Closed-form δ [mm] | anaStruct δ [mm] | Q8 continuum δ [mm] | Q8 vs Euler–Bernoulli |
|---|---|---|---|---|---|
| C1 example | 13.3 | 0.677249 | 0.677249 | 0.679061 | +0.27 % |
| C2 lightest example candidate | 7.3 | 0.439626 | 0.439626 | 0.444629 | +1.14 % |
| C4 steel bar | 10 | 0.2 | 0.2 | 0.201091 | +0.55 % |
| C5 stubby block | 3 | 0.00391872 | 0.00391872 | 0.0042194 | +7.67 % |

The last column shows why the app warns when L/h < 10: Euler–Bernoulli theory underestimates deflection
as the beam gets shorter and deeper. The test `test_shear_effect_grows_for_stubby_beams` asserts this trend.

The same comparison runs live for any selected design (**Cross-check (FE)** button) and is included in
every exported report.

## Notes on specific cases

- C3 (slender PETG) has δ/L ≈ 0.13. All three solvers are linear, so they agree, but small-deflection
  theory is itself questionable there. The app shows a δ/L warning for such designs.
- C6 (b/h = 25) is plate-like. A plane-stress model of the side view does not capture the plate
  (anticlastic) stiffening, which can reach about 1/(1−ν²) ≈ 10 % for very wide sections.

## Unit and formula tests

[`tests/test_mechanics.py`](../tests/test_mechanics.py) includes hand-calculated reference values. For example, for the steel bar:
I = 833.33 mm⁴, δ = 0.2 mm, σ = 60 MPa and m = 78.5 g. It also tests unit round-trips,
the L³, 1/h³, 1/b, 1/E and F scalings of δ, the σ scalings, the m scalings, zero load, invalid inputs,
constraint filtering against a scalar brute force, ranking and the no-feasible-design case.

## What this is not

Numerical agreement between models is **not physical validation**. No physical tests, prototypes or
measurements were made for this project, and no material-saving, performance or user-feedback claims
are made. Before relying on a design, test a prototype that includes the real joint, the real material
or printing process, and the real loading (including any dynamic loads).
