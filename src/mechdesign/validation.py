"""Documented numerical cross-check suite.

Run with ``mechdesign validate --out validation/``. The suite compares the
closed-form model against independent numerical solvers (see ``fem.py``) for a
fixed set of representative cases and checks each comparison against a
documented tolerance (see ``docs/validation.md``).
"""

from __future__ import annotations

import datetime as dt
import functools
import json
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from . import fem
from . import mechanics as M
from .crosscheck import TOL_ANASTRUCT, TOL_INHOUSE_FE, TOL_Q8_STRESS_MIDSPAN, TOL_Q8_VS_TIMOSHENKO

NU = 0.3

# id, description, L, b, h [mm], E [GPa], F [N]
CASES: list[tuple[str, str, float, float, float, float, float]] = [
    ("C1", "Example PLA mount (L/h = 13.3)", 80, 20, 6, 3.5, 5),
    ("C2", "Lightest feasible example candidate (L/h = 7.3)", 80, 5, 11, 3.5, 5),
    ("C3", "Slender PETG strip (L/h = 37.5)", 150, 10, 4, 2.1, 2),
    ("C4", "Steel bar, textbook check (L/h = 10)", 100, 10, 10, 200, 100),
    ("C5", "Stubby aluminium block (L/h = 3)", 30, 20, 10, 68.9, 50),
    ("C6", "Wide thin plate-like section (L/h = 40, b/h = 25)", 80, 50, 2, 3.5, 0.5),
]


def _rel(a: float, b: float) -> float:
    return (a - b) / b


def _version(pkg: str) -> str | None:
    try:
        return version(pkg)
    except PackageNotFoundError:
        return None


def run_suite() -> dict[str, Any]:
    """Run every case through every available solver. Pure computation, no I/O."""
    rows: list[dict[str, Any]] = []
    checks: list[tuple[str, str, float, float]] = []
    have_anastruct = fem.anastruct_available()
    for cid, desc, L, b, h, E, F in CASES:
        Ls, bs, hs, Es = L / 1000, b / 1000, h / 1000, E * 1e9
        cf = M.compute(M.BeamDesign(Ls, bs, hs, Es, 1000.0, F))
        eb = fem.beam_fe_euler_bernoulli(Ls, bs, hs, Es, F)
        q8 = fem.plane_stress_q8(Ls, bs, hs, Es, F, nu=NU)
        dT = fem.timoshenko_tip_deflection(Ls, bs, hs, Es, F, nu=NU)
        assert eb.max_stress is not None
        xs = q8.extra["x_sample"]
        sig_beam_x = 6 * F * (Ls - xs) / (bs * hs * hs)

        r: dict[str, Any] = {
            "id": cid,
            "description": desc,
            "inputs": {"L_mm": L, "b_mm": b, "h_mm": h, "E_GPa": E, "F_N": F, "nu_for_continuum": NU},
            "closed_form": {"delta_mm": cf.delta * 1e3, "sigma_MPa": cf.sigma / 1e6},
            "inhouse_eb_fe": {
                "delta_mm": eb.tip_deflection * 1e3,
                "sigma_MPa": eb.max_stress / 1e6,
                "rel_delta": _rel(eb.tip_deflection, cf.delta),
                "rel_sigma": _rel(eb.max_stress, cf.sigma),
            },
            "q8_continuum": {
                "delta_mm": q8.tip_deflection * 1e3,
                "timoshenko_delta_mm": dT * 1e3,
                "rel_vs_timoshenko": _rel(q8.tip_deflection, dT),
                "rel_vs_euler_bernoulli": _rel(q8.tip_deflection, cf.delta),
                "midspan_sigma_MPa": q8.extra["sigma_xx_top_at_x"] / 1e6,
                "beam_sigma_at_x_MPa": sig_beam_x / 1e6,
                "rel_midspan_sigma": _rel(q8.extra["sigma_xx_top_at_x"], sig_beam_x),
                "mesh": f"{q8.extra['nx']}x{q8.extra['ny']} Q8",
            },
        }
        checks += [
            (cid, "In-house EB FE: tip deflection", r["inhouse_eb_fe"]["rel_delta"], TOL_INHOUSE_FE),
            (cid, "In-house EB FE: root stress", r["inhouse_eb_fe"]["rel_sigma"], TOL_INHOUSE_FE),
        ]
        if have_anastruct:
            an = fem.beam_fe_anastruct(Ls, bs, hs, Es, F)
            assert an.max_stress is not None
            r["anastruct"] = {
                "delta_mm": an.tip_deflection * 1e3,
                "sigma_MPa": an.max_stress / 1e6,
                "rel_delta": _rel(an.tip_deflection, cf.delta),
                "rel_sigma": _rel(an.max_stress, cf.sigma),
            }
            checks += [
                (cid, "anaStruct: tip deflection", r["anastruct"]["rel_delta"], TOL_ANASTRUCT),
                (cid, "anaStruct: root stress", r["anastruct"]["rel_sigma"], TOL_ANASTRUCT),
            ]
        checks += [
            (
                cid,
                "Q8 continuum vs Timoshenko: tip deflection",
                r["q8_continuum"]["rel_vs_timoshenko"],
                TOL_Q8_VS_TIMOSHENKO,
            ),
            (
                cid,
                "Q8 continuum vs beam theory: mid-span bending stress",
                r["q8_continuum"]["rel_midspan_sigma"],
                TOL_Q8_STRESS_MIDSPAN,
            ),
        ]
        rows.append(r)

    check_rows = [{"case": c, "check": n, "rel_diff": d, "tolerance": t, "pass": abs(d) <= t} for c, n, d, t in checks]
    n_pass = sum(1 for c in check_rows if c["pass"])
    return {
        "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "environment": {
            "python": platform.python_version(),
            "mechdesign": _version("mechdesign-agent"),
            "numpy": _version("numpy"),
            "scipy": _version("scipy"),
            "anastruct": _version("anastruct") if have_anastruct else None,
            "platform": platform.platform(),
        },
        "cases": rows,
        "checks": check_rows,
        "summary": {
            "n_checks": len(check_rows),
            "n_pass": n_pass,
            "anastruct_included": have_anastruct,
        },
    }


@functools.lru_cache(maxsize=1)
def cached_suite() -> dict[str, Any]:
    """The suite is deterministic; run it once per process (used by reports)."""
    return run_suite()


def to_markdown(o: dict[str, Any]) -> str:
    env = ", ".join(f"{k} {v}" for k, v in o["environment"].items() if v)
    lines = [
        f"# Validation results (generated {o['generated']})",
        "",
        "Generated by `mechdesign validate --out validation`. See `docs/validation.md` for the method and tolerance rationale.",
        "",
        f"Environment: {env}",
        "",
        f"**{o['summary']['n_pass']} of {o['summary']['n_checks']} checks passed.**",
        "",
        "## Tip deflection [mm]",
        "",
        "| Case | Description | Closed form (EB) | In-house EB FE | anaStruct | Q8 continuum | Timoshenko est. | Q8 vs EB |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in o["cases"]:
        an = r.get("anastruct", {}).get("delta_mm")
        an_s = f"{an:.6g}" if an is not None else "n/a"
        q = r["q8_continuum"]
        lines.append(
            f"| {r['id']} | {r['description']} | {r['closed_form']['delta_mm']:.6g} | {r['inhouse_eb_fe']['delta_mm']:.6g} | "
            f"{an_s} | {q['delta_mm']:.6g} | {q['timoshenko_delta_mm']:.6g} | {100 * q['rel_vs_euler_bernoulli']:+.2f} % |"
        )
    lines += [
        "",
        "## Max bending stress [MPa]",
        "",
        "| Case | Closed form | In-house EB FE (from root moment) | anaStruct (from root moment) | Q8 sigma_xx at mid-span | Beam theory at same x |",
        "|---|---|---|---|---|---|",
    ]
    for r in o["cases"]:
        an = r.get("anastruct", {}).get("sigma_MPa")
        an_s = f"{an:.6g}" if an is not None else "n/a"
        q = r["q8_continuum"]
        lines.append(
            f"| {r['id']} | {r['closed_form']['sigma_MPa']:.6g} | {r['inhouse_eb_fe']['sigma_MPa']:.6g} | {an_s} | "
            f"{q['midspan_sigma_MPa']:.6g} | {q['beam_sigma_at_x_MPa']:.6g} |"
        )
    lines += [
        "",
        "## Checks",
        "",
        "| Case | Check | Relative difference | Tolerance | Result |",
        "|---|---|---|---|---|",
    ]
    for c in o["checks"]:
        lines.append(
            f"| {c['case']} | {c['check']} | {c['rel_diff']:+.3e} | {c['tolerance']:g} | {'PASS' if c['pass'] else 'FAIL'} |"
        )
    lines += [
        "",
        "Numerical agreement between models is not physical validation. No physical tests were performed.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(result: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    j = out_dir / "results.json"
    m = out_dir / "results.md"
    j.write_text(json.dumps(result, indent=1), encoding="utf-8")
    m.write_text(to_markdown(result), encoding="utf-8")
    return j, m
