"""Cross-check a single design against the independent numerical solvers."""

from __future__ import annotations

from typing import Any

from . import fem
from . import units as U
from .mechanics import BeamDesign, compute

# Documented tolerances (relative). See VALIDATION.md for rationale.
TOL_INHOUSE_FE = 1e-9  # nodally exact element; differences are round-off
TOL_ANASTRUCT = 1e-5  # anaStruct shows ~1e-7 differences (internal rounding)
TOL_Q8_VS_TIMOSHENKO = 0.02  # continuum vs Timoshenko estimate (clamp & load-introduction effects)
TOL_Q8_STRESS_MIDSPAN = 0.01


def cross_check(design: BeamDesign, nu: float = 0.3) -> dict[str, Any]:
    cf = compute(design)
    L, b, h, E, F = design.L, design.b, design.h, design.E, design.F
    rows = []

    def rel(a, ref):
        return 0.0 if ref == 0 and a == 0 else (a - ref) / ref if ref != 0 else float("inf")

    r = fem.beam_fe_euler_bernoulli(L, b, h, E, F)
    assert r.max_stress is not None
    rows.append(
        {
            "solver": r.solver,
            "physics": "Euler-Bernoulli beam (same physics, independent numerical method)",
            "tip_deflection_mm": U.m_to_mm(r.tip_deflection),
            "rel_diff_deflection": rel(r.tip_deflection, cf.delta),
            "max_stress_MPa": U.pa_to_mpa(r.max_stress),
            "rel_diff_stress": rel(r.max_stress, cf.sigma),
            "tolerance": TOL_INHOUSE_FE,
            "pass": abs(rel(r.tip_deflection, cf.delta)) <= TOL_INHOUSE_FE
            and abs(rel(r.max_stress, cf.sigma)) <= TOL_INHOUSE_FE,
            "notes": r.notes,
        }
    )

    if F == 0:
        rows.append(
            {
                "solver": "anaStruct",
                "physics": "",
                "pass": None,
                "notes": "Skipped: anaStruct refuses to solve a structure with zero load.",
            }
        )
    elif fem.anastruct_available():
        r = fem.beam_fe_anastruct(L, b, h, E, F)
        assert r.max_stress is not None
        rows.append(
            {
                "solver": r.solver,
                "physics": "Euler-Bernoulli frame (open-source, separate code base)",
                "tip_deflection_mm": U.m_to_mm(r.tip_deflection),
                "rel_diff_deflection": rel(r.tip_deflection, cf.delta),
                "max_stress_MPa": U.pa_to_mpa(r.max_stress),
                "rel_diff_stress": rel(r.max_stress, cf.sigma),
                "tolerance": TOL_ANASTRUCT,
                "pass": abs(rel(r.tip_deflection, cf.delta)) <= TOL_ANASTRUCT
                and abs(rel(r.max_stress, cf.sigma)) <= TOL_ANASTRUCT,
                "notes": r.notes,
            }
        )
    else:
        rows.append(
            {
                "solver": "anaStruct",
                "physics": "",
                "pass": None,
                "notes": "anaStruct is not installed; open-source cross-check skipped.",
            }
        )

    q8 = fem.plane_stress_q8(L, b, h, E, F, nu=nu)
    dT = fem.timoshenko_tip_deflection(L, b, h, E, F, nu=nu)
    xs = q8.extra["x_sample"]
    sig_beam = 6 * F * (L - xs) / (b * h * h)
    rows.append(
        {
            "solver": q8.solver,
            "physics": "2D plane-stress continuum (includes shear deformation; not beam theory)",
            "tip_deflection_mm": U.m_to_mm(q8.tip_deflection),
            "rel_diff_deflection": rel(q8.tip_deflection, cf.delta),
            "timoshenko_deflection_mm": U.m_to_mm(dT),
            "rel_diff_vs_timoshenko": rel(q8.tip_deflection, dT),
            "midspan_stress_MPa": U.pa_to_mpa(q8.extra["sigma_xx_top_at_x"]),
            "midspan_x_mm": U.m_to_mm(xs),
            "rel_diff_midspan_stress": rel(q8.extra["sigma_xx_top_at_x"], sig_beam) if F else 0.0,
            "tolerance": TOL_Q8_VS_TIMOSHENKO,
            "pass": (abs(rel(q8.tip_deflection, dT)) <= TOL_Q8_VS_TIMOSHENKO if F else True),
            "notes": (
                f"Compared against Timoshenko estimate (nu = {nu:g}, kappa = 5/6). The difference from "
                "Euler-Bernoulli is model-form error (mainly shear deformation), not a solver error."
            ),
        }
    )

    return {
        "closed_form": {"tip_deflection_mm": U.m_to_mm(cf.delta), "max_stress_MPa": U.pa_to_mpa(cf.sigma)},
        "rows": rows,
        "disclaimer": (
            "Agreement between numerical models checks the implementation, not physical reality. "
            "No physical tests have been performed."
        ),
    }
