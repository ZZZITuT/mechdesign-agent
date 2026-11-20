"""Exportable calculation report (Markdown or standalone HTML)."""

from __future__ import annotations

import datetime as _dt
import html
from typing import Any

from . import __version__
from . import mechanics as M
from .crosscheck import cross_check
from .mechanics import MODEL_ASSUMPTIONS, MODEL_LIMITATIONS


def _g(v, nd=4):
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        return f"{v:.{nd}g}"
    return str(v)


def build_sections(
    run: dict[str, Any],
    selected: dict | None,
    crosscheck: dict | None,
    explanation: dict | None,
    validation_summary: dict | None = None,
    top_n: int = 15,
) -> list[tuple]:
    cfg = run["config"]
    s = run["search"]["fixed"]
    sec: list[tuple] = []
    now = _dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M (UTC%z)")
    sec.append(("h1", "MechDesign Agent - Calculation Report"))
    sec.append(
        (
            "p",
            f"Generated {now} by MechDesign Agent v{__version__}. Model: rectangular cantilever, Euler-Bernoulli beam theory. "
            "All numbers below were computed by the deterministic mechanics engine.",
        )
    )
    if cfg.get("_label"):
        sec.append(("p", f"Note: {cfg['_label']}."))

    sec.append(("h2", "1. Inputs"))
    sp = cfg["search"]
    sec.append(
        (
            "table",
            ["Quantity", "Symbol", "Value", "Unit"],
            [
                ["Beam length", "L", _g(cfg["length_mm"]), "mm"],
                ["Current width (out of bending plane)", "b", _g(cfg["width_mm"]), "mm"],
                ["Current height (bending direction)", "h", _g(cfg["height_mm"]), "mm"],
                ["Material", "-", run.get("material_name", ""), "-"],
                ["Young's modulus", "E", _g(cfg["material"]["E_GPa"]), "GPa"],
                ["Density", "rho", _g(cfg["material"]["density_kg_m3"]), "kg/m^3"],
                ["Tip load (transverse, h direction)", "F", _g(cfg["load_N"]), "N"],
                ["Allowable tip deflection", "delta_allow", _g(cfg["allowable_deflection_mm"]), "mm"],
                [
                    "Allowable bending stress",
                    "sigma_allow",
                    _g(cfg.get("allowable_stress_MPa"))
                    if cfg.get("allowable_stress_MPa") is not None
                    else "not checked",
                    "MPa",
                ],
                [
                    "Max aspect ratio h/b",
                    "-",
                    _g(cfg.get("max_aspect_ratio")) if cfg.get("max_aspect_ratio") is not None else "not checked",
                    "-",
                ],
                [
                    "Search range b",
                    "-",
                    f"{_g(sp['b_min_mm'])} to {_g(sp['b_max_mm'])} step {_g(sp['b_step_mm'])}",
                    "mm",
                ],
                [
                    "Search range h",
                    "-",
                    f"{_g(sp['h_min_mm'])} to {_g(sp['h_max_mm'])} step {_g(sp['h_step_mm'])}",
                    "mm",
                ],
            ],
        )
    )
    sec.append(("p", "Internal calculations use SI units (m, N, Pa, kg); values are converted for display."))

    sec.append(("h2", "2. Model and assumptions"))
    sec.append(
        (
            "ul",
            [
                "I = b h^3 / 12;  m = rho b h L;  delta = F L^3 / (3 E I);  sigma_max = 6 F L / (b h^2) (at the fixed end, extreme fibres).",
                *MODEL_ASSUMPTIONS,
            ],
        )
    )
    sec.append(("h3", "Limitations (not represented by this model)"))
    sec.append(("ul", MODEL_LIMITATIONS))

    sec.append(("h2", "3. Current design"))
    cur = run["current"]
    sec.append(
        (
            "table",
            ["b [mm]", "h [mm]", "I [mm^4]", "Mass [g]", "Tip deflection [mm]", "Max stress [MPa]", "Status"],
            [
                [
                    _g(cur["b_mm"]),
                    _g(cur["h_mm"]),
                    _g(cur["I_mm4"]),
                    _g(cur["mass_g"]),
                    _g(cur["deflection_mm"]),
                    _g(cur["stress_MPa"]),
                    "FEASIBLE" if cur["feasible"] else "NOT FEASIBLE",
                ]
            ],
        )
    )
    sec.append(("ul", [c["text"] for c in cur["checks"]] + [f"Warning: {w}" for w in cur["warnings"]]))

    sec.append(("h2", "4. Design-space search"))
    se = run["search"]
    sec.append(
        (
            "p",
            f"Fixed during the search: L = {_g(s['L_mm'])} mm, E = {_g(s['E_GPa'])} GPa, rho = {_g(s['density_kg_m3'])} kg/m^3, F = {_g(s['load_N'])} N. "
            f"Grid: {se['n_b']} b values x {se['n_h']} h values = {se['n_candidates']} candidates. "
            f"Feasible: {se['n_feasible']}. Failing deflection: {se['n_fail_deflection']}; failing stress: {se['n_fail_stress']}; "
            f"failing aspect ratio: {se['n_fail_aspect']} (a candidate may fail several).",
        )
    )
    sec.append(("p", run["statement"]))
    if run["top"]:
        rows = []
        for c in run["top"][:top_n]:
            rows.append(
                [
                    str(c["rank"]),
                    _g(c["b_mm"]),
                    _g(c["h_mm"]),
                    _g(c["mass_g"]),
                    _g(c["mass_change_vs_current_pct"], 3) + " %",
                    _g(c["deflection_mm"]),
                    _g(c["stress_MPa"]),
                    _g(c["h_mm"] / c["b_mm"], 3),
                    c["reason"],
                ]
            )
        sec.append(("h3", f"Feasible candidates ranked by mass (top {min(top_n, len(run['top']))})"))
        sec.append(
            (
                "table",
                [
                    "Rank",
                    "b [mm]",
                    "h [mm]",
                    "Mass [g]",
                    "Mass vs current",
                    "Deflection [mm]",
                    "Stress [MPa]",
                    "h/b",
                    "Reason",
                ],
                rows,
            )
        )
    if run.get("nearest_infeasible"):
        sec.append(("h3", "Closest infeasible candidates (constraints NOT relaxed)"))
        sec.append(
            (
                "table",
                ["b [mm]", "h [mm]", "Mass [g]", "Deflection [mm]", "Stress [MPa]", "Worst utilisation", "Reason"],
                [
                    [
                        _g(c["b_mm"]),
                        _g(c["h_mm"]),
                        _g(c["mass_g"]),
                        _g(c["deflection_mm"]),
                        _g(c["stress_MPa"]),
                        _g(100 * c["max_utilisation"], 3) + " %",
                        c["reason"],
                    ]
                    for c in run["nearest_infeasible"]
                ],
            )
        )

    if selected:
        sec.append(("h2", "5. Selected candidate"))
        sec.append(
            (
                "table",
                ["b [mm]", "h [mm]", "I [mm^4]", "Mass [g]", "Tip deflection [mm]", "Max stress [MPa]", "Status"],
                [
                    [
                        _g(selected["b_mm"]),
                        _g(selected["h_mm"]),
                        _g(selected["I_mm4"]),
                        _g(selected["mass_g"]),
                        _g(selected["deflection_mm"]),
                        _g(selected["stress_MPa"]),
                        "FEASIBLE" if selected["feasible"] else "NOT FEASIBLE",
                    ]
                ],
            )
        )
        sec.append(("ul", [c["text"] for c in selected["checks"]] + [f"Warning: {w}" for w in selected["warnings"]]))

    sec.append(("h2", "6. Validation information"))
    if crosscheck:
        sec.append(
            (
                "p",
                f"Numerical cross-check of the {'selected' if selected else 'current'} design. Closed form: tip deflection "
                f"{_g(crosscheck['closed_form']['tip_deflection_mm'], 6)} mm, max stress {_g(crosscheck['closed_form']['max_stress_MPa'], 6)} MPa.",
            )
        )
        rows = []
        for r in crosscheck["rows"]:
            if r.get("pass") is None:
                rows.append([r["solver"], "-", "-", "-", "skipped", r["notes"]])
                continue
            if "timoshenko_deflection_mm" in r:
                cmp = f"{r['rel_diff_vs_timoshenko']:+.2e} vs Timoshenko ({_g(r['timoshenko_deflection_mm'], 6)} mm); {r['rel_diff_deflection']:+.2e} vs Euler-Bernoulli"
            else:
                cmp = f"{r['rel_diff_deflection']:+.2e} (deflection), {r['rel_diff_stress']:+.2e} (stress)"
            rows.append(
                [
                    r["solver"],
                    r["physics"],
                    _g(r["tip_deflection_mm"], 6),
                    cmp,
                    f"{r['tolerance']:g}",
                    ("PASS" if r["pass"] else "FAIL") + " - " + r["notes"],
                ]
            )
        sec.append(
            (
                "table",
                ["Solver", "Physics", "Tip deflection [mm]", "Relative difference", "Tolerance", "Result / notes"],
                rows,
            )
        )
        sec.append(("p", crosscheck["disclaimer"]))
    if validation_summary:
        vs = validation_summary["summary"]
        sec.append(
            (
                "p",
                f"Documented validation suite (6 representative cases, run {validation_summary['generated']}): "
                f"{vs['n_pass']} of {vs['n_checks']} comparison checks passed"
                + ("" if vs.get("anastruct_included") else " (anaStruct not installed, its checks were skipped)")
                + ". See docs/validation.md for cases and tolerances.",
            )
        )
    sec.append(
        (
            "p",
            "No physical testing has been performed. Numerical agreement is not physical validation; "
            "prototype testing of the real mount (including its joint and printing process) is required before relying on these numbers.",
        )
    )

    if explanation:
        sec.append(("h2", "7. Narrative explanation"))
        sec.append(("p", f"Source: {explanation['mode_label']}."))
        sec.append(("p", explanation["text"]))
        if explanation.get("unverified_numbers"):
            sec.append(
                (
                    "p",
                    "Warning: numbers not traceable to engine results: " + ", ".join(explanation["unverified_numbers"]),
                )
            )
    return sec


def to_markdown(sections: list[tuple]) -> str:
    out = []
    for s in sections:
        kind = s[0]
        if kind == "h1":
            out.append(f"# {s[1]}\n")
        elif kind == "h2":
            out.append(f"\n## {s[1]}\n")
        elif kind == "h3":
            out.append(f"\n### {s[1]}\n")
        elif kind == "p":
            out.append(s[1] + "\n")
        elif kind == "ul":
            out.extend(f"- {x}" for x in s[1])
            out.append("")
        elif kind == "table":
            head, rows = s[1], s[2]
            out.append("| " + " | ".join(head) + " |")
            out.append("|" + "|".join("---" for _ in head) + "|")
            for r in rows:
                out.append("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |")
            out.append("")
    return "\n".join(out) + "\n"


def to_html(sections: list[tuple]) -> str:
    e = html.escape
    body = []
    for s in sections:
        kind = s[0]
        if kind in ("h1", "h2", "h3"):
            body.append(f"<{kind}>{e(s[1])}</{kind}>")
        elif kind == "p":
            body.append(f"<p>{e(s[1])}</p>")
        elif kind == "ul":
            body.append("<ul>" + "".join(f"<li>{e(x)}</li>" for x in s[1]) + "</ul>")
        elif kind == "table":
            head = "".join(f"<th>{e(h)}</th>" for h in s[1])
            rows = "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in r) + "</tr>" for r in s[2])
            body.append(f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")
    css = (
        "body{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1d2330;line-height:1.45}"
        "table{border-collapse:collapse;margin:8px 0 16px;font-size:13px}td,th{border:1px solid #c9ced8;padding:4px 8px;text-align:left;vertical-align:top}"
        "th{background:#eef1f6}h1{font-size:24px}h2{font-size:19px;border-bottom:1px solid #d5d9e2;padding-bottom:4px;margin-top:28px}h3{font-size:15px}"
    )
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>MechDesign Agent report</title>"
        f"<style>{css}</style></head><body>{''.join(body)}</body></html>"
    )


def find_candidate(run: dict[str, Any], candidate_id: str | None) -> dict | None:
    if not candidate_id:
        return None
    return next((c for c in run["candidates"] if c["id"] == candidate_id), None)


def generate_report(
    config: dict[str, Any],
    selected_id: str | None = None,
    fmt: str = "html",
    message: str = "",
    include_explanation: bool = True,
    include_validation_suite: bool = True,
) -> str:
    """Run the full workflow for ``config`` and render a report.

    Raises :class:`mechdesign.mechanics.InputError` for invalid configurations and
    ``KeyError`` if ``selected_id`` is not a candidate of the search grid.
    """
    from .language import service  # local import keeps report usable without the language layer
    from .validation import cached_suite

    if fmt not in ("html", "md"):
        raise ValueError("format must be 'html' or 'md'")
    run = M.run_problem(config)
    sel = find_candidate(run, selected_id)
    if selected_id and sel is None:
        raise KeyError(f"candidate '{selected_id}' is not in the search grid")
    p = M.parse_config(config)
    d = (
        p.design
        if sel is None
        else M.BeamDesign(p.design.L, sel["b_mm"] / 1000, sel["h_mm"] / 1000, p.design.E, p.design.rho, p.design.F)
    )
    xc = cross_check(d)
    expl = service.explain_results(run, message, sel) if include_explanation else None
    vs = cached_suite() if include_validation_suite else None
    sections = build_sections(run, sel, xc, expl, vs)
    return to_markdown(sections) if fmt == "md" else to_html(sections)
