"""Deterministic mechanics engine for a rectangular cantilever sensor mount.

Model (Euler-Bernoulli, small deflection, linear elastic, isotropic):
    * Straight, prismatic beam of length L, fixed (ideally clamped) at x = 0.
    * Rectangular section: width b (out of the bending plane), height h (in
      the bending direction).
    * Transverse point load F applied at the free end x = L.

    I     = b h^3 / 12
    m     = rho b h L
    delta = F L^3 / (3 E I)          (tip deflection)
    sigma = 6 F L / (b h^2)          (max bending stress magnitude, at the root,
                                      extreme fibres y = +/- h/2)

This module has no dependency on the UI, the web server or the language layer.
All internal quantities are SI. Public helpers accept a "display" configuration
(mm, N, GPa, MPa, kg/m^3) and convert explicitly via :mod:`mechdesign.units`.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from . import units as U

MODEL_ASSUMPTIONS = [
    "Straight, prismatic beam with a solid rectangular cross-section (width b, height h in the bending direction).",
    "One end ideally fixed (perfectly rigid clamp: zero displacement and zero rotation).",
    "A single static transverse point load F at the free end, acting perpendicular to the beam axis in the h direction.",
    "Homogeneous, isotropic, linearly elastic material (Young's modulus E, density rho).",
    "Euler-Bernoulli beam theory: plane sections remain plane and normal to the axis; shear deformation neglected.",
    "Small deflections and rotations (linear geometry).",
    "Self-weight of the beam is not included in the load.",
]

MODEL_LIMITATIONS = [
    "Does not represent actual joint or fastener flexibility at the fixed end (a real clamp/bolted joint is less stiff, so real deflection will be larger).",
    "Does not represent 3D-printing effects: anisotropy between layers, infill, porosity, layer adhesion, creep, moisture or temperature dependence.",
    "Does not represent large deformation / geometric nonlinearity.",
    "Does not represent dynamic loading: vibration, resonance, impact, or fatigue.",
    "Does not check lateral-torsional buckling, local buckling, stress concentrations at the root fillet/holes, or yield/fracture of the material beyond the optional stress limit.",
    "Shear deformation is neglected; for short, deep beams (L/h below about 10) the true deflection is noticeably larger than predicted.",
]

# Advisory thresholds (warnings only; they never change feasibility).
SLENDERNESS_WARNING = 10.0  # L/h below this: shear deformation may matter
ASPECT_WARNING = 4.0  # h/b above this: lateral-torsional buckling not checked
DEFLECTION_RATIO_WARNING = 0.05  # delta/L above this: small-deflection assumption questionable

MAX_POINTS_PER_AXIS = 400
MAX_CANDIDATES = 40000


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


@dataclass
class FieldError:
    field: str
    message: str


class InputError(ValueError):
    """Raised when the configuration is invalid. Carries per-field messages."""

    def __init__(self, errors: list[FieldError]):
        self.errors = errors
        super().__init__("; ".join(f"{e.field}: {e.message}" for e in errors))

    def as_list(self) -> list[dict[str, str]]:
        return [asdict(e) for e in self.errors]


# ---------------------------------------------------------------------------
# Core SI data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BeamDesign:
    """A fully specified design, SI units."""

    L: float  # m
    b: float  # m
    h: float  # m
    E: float  # Pa
    rho: float  # kg/m^3
    F: float  # N (magnitude, >= 0)


@dataclass(frozen=True)
class Requirements:
    delta_allow: float  # m, > 0
    sigma_allow: float | None  # Pa, > 0 or None (not checked)
    max_aspect_ratio: float | None = None  # h/b upper bound, or None


@dataclass(frozen=True)
class SearchSpace:
    b_min: float
    b_max: float
    b_step: float
    h_min: float
    h_max: float
    h_step: float


@dataclass
class BeamResult:
    I: float  # m^4
    mass: float  # kg
    delta: float  # m
    sigma: float  # Pa


@dataclass
class Evaluation:
    design: BeamDesign
    result: BeamResult
    feasible: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Closed-form formulas (scalar and vectorised)
# ---------------------------------------------------------------------------


def second_moment_rect(b: float, h: float) -> float:
    return b * h**3 / 12.0


def mass_rect(rho: float, b: float, h: float, L: float) -> float:
    return rho * b * h * L


def tip_deflection(F: float, L: float, E: float, I: float) -> float:
    return F * L**3 / (3.0 * E * I)


def max_bending_stress(F: float, L: float, b: float, h: float) -> float:
    return 6.0 * F * L / (b * h**2)


def deflection_curve(F: float, L: float, E: float, I: float, x):
    """Transverse deflection v(x) (positive in the load direction).

    v(x) = F x^2 (3L - x) / (6 E I); v(L) equals the tip deflection.
    """
    x = np.asarray(x, dtype=float)
    return F * x**2 * (3.0 * L - x) / (6.0 * E * I)


def compute(design: BeamDesign) -> BeamResult:
    validate_design(design)
    I = second_moment_rect(design.b, design.h)
    return BeamResult(
        I=I,
        mass=mass_rect(design.rho, design.b, design.h, design.L),
        delta=tip_deflection(design.F, design.L, design.E, I),
        sigma=max_bending_stress(design.F, design.L, design.b, design.h),
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _positive(errors: list[FieldError], name: str, v: Any, label: str) -> None:
    if not _is_number(v):
        errors.append(FieldError(name, f"{label} must be a finite number."))
    elif v <= 0:
        errors.append(FieldError(name, f"{label} must be greater than zero (got {v})."))


def validate_design(d: BeamDesign) -> None:
    errors: list[FieldError] = []
    _positive(errors, "L", d.L, "Length L")
    _positive(errors, "b", d.b, "Width b")
    _positive(errors, "h", d.h, "Height h")
    _positive(errors, "E", d.E, "Young's modulus E")
    _positive(errors, "rho", d.rho, "Density rho")
    if not _is_number(d.F):
        errors.append(FieldError("F", "Load F must be a finite number."))
    elif d.F < 0:
        errors.append(
            FieldError(
                "F", "Enter the load as a magnitude (>= 0). Its direction is fixed: transverse, in the h direction."
            )
        )
    if errors:
        raise InputError(errors)


# ---------------------------------------------------------------------------
# Feasibility checks
# ---------------------------------------------------------------------------


def _fmt(v: float, nd: int = 3) -> str:
    return f"{v:.{nd}g}"


def evaluate(design: BeamDesign, req: Requirements) -> Evaluation:
    """Compute results and check them against the requirements."""
    res = compute(design)
    checks: list[dict[str, Any]] = []

    d_mm = U.m_to_mm(res.delta)
    da_mm = U.m_to_mm(req.delta_allow)
    ok_d = res.delta <= req.delta_allow
    checks.append(
        {
            "name": "tip_deflection",
            "value": d_mm,
            "limit": da_mm,
            "unit": "mm",
            "utilisation": res.delta / req.delta_allow,
            "passed": ok_d,
            "text": (
                f"Tip deflection {_fmt(d_mm)} mm <= limit {_fmt(da_mm)} mm"
                if ok_d
                else f"Tip deflection {_fmt(d_mm)} mm exceeds limit {_fmt(da_mm)} mm"
            ),
        }
    )

    if req.sigma_allow is not None:
        s = U.pa_to_mpa(res.sigma)
        sa = U.pa_to_mpa(req.sigma_allow)
        ok_s = res.sigma <= req.sigma_allow
        checks.append(
            {
                "name": "bending_stress",
                "value": s,
                "limit": sa,
                "unit": "MPa",
                "utilisation": res.sigma / req.sigma_allow,
                "passed": ok_s,
                "text": (
                    f"Max bending stress {_fmt(s)} MPa <= limit {_fmt(sa)} MPa"
                    if ok_s
                    else f"Max bending stress {_fmt(s)} MPa exceeds limit {_fmt(sa)} MPa"
                ),
            }
        )

    if req.max_aspect_ratio is not None:
        ar = design.h / design.b
        ok_a = ar <= req.max_aspect_ratio + 1e-12
        checks.append(
            {
                "name": "aspect_ratio",
                "value": ar,
                "limit": req.max_aspect_ratio,
                "unit": "h/b",
                "utilisation": ar / req.max_aspect_ratio,
                "passed": ok_a,
                "text": (
                    f"Aspect ratio h/b = {_fmt(ar)} <= limit {_fmt(req.max_aspect_ratio)}"
                    if ok_a
                    else f"Aspect ratio h/b = {_fmt(ar)} exceeds limit {_fmt(req.max_aspect_ratio)}"
                ),
            }
        )

    return Evaluation(
        design=design,
        result=res,
        feasible=all(c["passed"] for c in checks),
        checks=checks,
        warnings=design_warnings(design, res),
    )


def design_warnings(design: BeamDesign, res: BeamResult) -> list[str]:
    w: list[str] = []
    if design.F == 0:
        w.append(
            "Load is zero: deflection and stress are zero, so every design trivially satisfies the limits. Check that the load is intended."
        )
    slender = design.L / design.h
    if slender < SLENDERNESS_WARNING:
        w.append(
            f"L/h = {_fmt(slender)} < {SLENDERNESS_WARNING:g}: shear deformation (neglected by Euler-Bernoulli theory) may noticeably increase the real deflection."
        )
    ar = design.h / design.b
    if ar > ASPECT_WARNING:
        w.append(
            f"h/b = {_fmt(ar)} > {ASPECT_WARNING:g}: thin, deep section. Lateral-torsional buckling is not checked by this model."
        )
    if res.delta / design.L > DEFLECTION_RATIO_WARNING:
        w.append(
            f"delta/L = {_fmt(res.delta / design.L)} > {DEFLECTION_RATIO_WARNING:g}: small-deflection theory may be inaccurate."
        )
    return w


# ---------------------------------------------------------------------------
# Design-space search
# ---------------------------------------------------------------------------


def grid_values(vmin: float, vmax: float, step: float) -> np.ndarray:
    """Inclusive grid vmin, vmin+step, ... <= vmax (tolerant to float error)."""
    n = math.floor((vmax - vmin) / step + 1e-9) + 1
    vals = vmin + step * np.arange(n)
    # Remove float noise so that e.g. 0.1 + 2*0.1 is reported as 0.3.
    return np.round(vals, 12)


def validate_search_space(s: SearchSpace) -> None:
    errors: list[FieldError] = []
    for name, label in [
        ("b_min", "b min"),
        ("b_max", "b max"),
        ("b_step", "b step"),
        ("h_min", "h min"),
        ("h_max", "h max"),
        ("h_step", "h step"),
    ]:
        _positive(errors, name, getattr(s, name), label)
    if errors:
        raise InputError(errors)
    if s.b_max < s.b_min:
        errors.append(FieldError("b_max", "b max must be greater than or equal to b min."))
    if s.h_max < s.h_min:
        errors.append(FieldError("h_max", "h max must be greater than or equal to h min."))
    if errors:
        raise InputError(errors)
    nb = len(grid_values(s.b_min, s.b_max, s.b_step))
    nh = len(grid_values(s.h_min, s.h_max, s.h_step))
    if nb > MAX_POINTS_PER_AXIS:
        errors.append(
            FieldError(
                "b_step", f"b range gives {nb} values; increase the step so there are at most {MAX_POINTS_PER_AXIS}."
            )
        )
    if nh > MAX_POINTS_PER_AXIS:
        errors.append(
            FieldError(
                "h_step", f"h range gives {nh} values; increase the step so there are at most {MAX_POINTS_PER_AXIS}."
            )
        )
    if nb * nh > MAX_CANDIDATES:
        errors.append(
            FieldError(
                "search",
                f"{nb * nh} candidates exceed the limit of {MAX_CANDIDATES}; coarsen the steps or narrow the ranges.",
            )
        )
    if errors:
        raise InputError(errors)


def validate_requirements(r: Requirements) -> None:
    errors: list[FieldError] = []
    _positive(errors, "delta_allow", r.delta_allow, "Allowable tip deflection")
    if r.sigma_allow is not None:
        _positive(errors, "sigma_allow", r.sigma_allow, "Allowable bending stress")
    if r.max_aspect_ratio is not None:
        _positive(errors, "max_aspect_ratio", r.max_aspect_ratio, "Maximum aspect ratio h/b")
    if errors:
        raise InputError(errors)


def search(base: BeamDesign, req: Requirements, space: SearchSpace) -> dict[str, Any]:
    """Evaluate every (b, h) on the grid with L, E, rho, F fixed.

    Returns SI arrays plus feasibility masks; ranking is by mass among the
    feasible candidates (ties broken by smaller deflection).
    """
    validate_design(base)
    validate_requirements(req)
    validate_search_space(space)

    bv = grid_values(space.b_min, space.b_max, space.b_step)
    hv = grid_values(space.h_min, space.h_max, space.h_step)
    B, H = np.meshgrid(bv, hv, indexing="ij")
    B = B.ravel()
    H = H.ravel()

    I = B * H**3 / 12.0
    mass = base.rho * B * H * base.L
    delta = base.F * base.L**3 / (3.0 * base.E * I)
    sigma = 6.0 * base.F * base.L / (B * H**2)

    ok_delta = delta <= req.delta_allow
    ok_sigma = np.ones_like(ok_delta) if req.sigma_allow is None else sigma <= req.sigma_allow
    ok_aspect = np.ones_like(ok_delta) if req.max_aspect_ratio is None else req.max_aspect_ratio + 1e-12 >= (H / B)
    feasible = ok_delta & ok_sigma & ok_aspect

    order_feasible = np.lexsort((delta[feasible], mass[feasible]))
    feasible_idx = np.flatnonzero(feasible)[order_feasible]

    return {
        "b": B,
        "h": H,
        "I": I,
        "mass": mass,
        "delta": delta,
        "sigma": sigma,
        "ok_delta": ok_delta,
        "ok_sigma": ok_sigma,
        "ok_aspect": ok_aspect,
        "feasible": feasible,
        "ranked_feasible_idx": feasible_idx,
        "n_b": len(bv),
        "n_h": len(hv),
    }


# ---------------------------------------------------------------------------
# Display-unit configuration (what the UI / API exchange)
# ---------------------------------------------------------------------------

EXAMPLE_CONFIG: dict[str, Any] = {
    "_label": "EXAMPLE configuration (illustrative values, not a real product specification)",
    "length_mm": 80.0,
    "width_mm": 20.0,
    "height_mm": 6.0,
    "material": {"name": "PLA (nominal bulk values)", "E_GPa": 3.5, "density_kg_m3": 1240.0},
    "load_N": 5.0,
    "allowable_deflection_mm": 0.5,
    "allowable_stress_MPa": 20.0,
    "max_aspect_ratio": None,
    "search": {
        "b_min_mm": 5.0,
        "b_max_mm": 30.0,
        "b_step_mm": 1.0,
        "h_min_mm": 3.0,
        "h_max_mm": 12.0,
        "h_step_mm": 0.5,
    },
}

MATERIAL_PRESETS = [
    {
        "name": "PLA (nominal bulk values)",
        "E_GPa": 3.5,
        "density_kg_m3": 1240.0,
        "note": "Typical datasheet bulk value. Printed parts are usually less stiff and anisotropic.",
    },
    {
        "name": "PETG (nominal bulk values)",
        "E_GPa": 2.1,
        "density_kg_m3": 1270.0,
        "note": "Typical datasheet bulk value. Printed parts are usually less stiff and anisotropic.",
    },
    {
        "name": "ABS (nominal bulk values)",
        "E_GPa": 2.2,
        "density_kg_m3": 1050.0,
        "note": "Typical datasheet bulk value. Printed parts are usually less stiff and anisotropic.",
    },
    {"name": "Aluminium 6061-T6", "E_GPa": 68.9, "density_kg_m3": 2700.0, "note": "Typical handbook value."},
    {"name": "Structural steel", "E_GPa": 200.0, "density_kg_m3": 7850.0, "note": "Typical handbook value."},
]


def _get(cfg: dict, path: str, errors: list[FieldError]) -> Any:
    cur: Any = cfg
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            errors.append(FieldError(path, "is required."))
            return None
        cur = cur[part]
    return cur


def _num(cfg: dict, path: str, errors: list[FieldError], optional: bool = False) -> float | None:
    if optional:
        v = _get_optional(cfg, path)
        if v is None:
            return None
    else:
        n_before = len(errors)
        v = _get(cfg, path, errors)
        if v is None:
            if len(errors) == n_before:  # key present but empty/null
                errors.append(FieldError(path, "is required."))
            return None
    if isinstance(v, str):
        if v.strip().lower() in ("", "blank"):
            errors.append(FieldError(path, "is enabled but empty; enter a value or untick the option."))
            return None
        try:
            v = float(v.strip())
        except ValueError:
            errors.append(FieldError(path, f"'{v}' is not a number."))
            return None
    if not _is_number(v):
        errors.append(FieldError(path, "must be a finite number."))
        return None
    return float(v)


def _get_optional(cfg: dict, path: str) -> Any:
    cur: Any = cfg
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    if cur == "":
        return None
    return cur


@dataclass
class Problem:
    design: BeamDesign
    requirements: Requirements
    space: SearchSpace
    material_name: str


def parse_config(cfg: dict) -> Problem:
    """Validate a display-unit configuration and convert it to SI objects.

    Raises InputError listing every problem found (display-unit field names).
    """
    errors: list[FieldError] = []
    L = _num(cfg, "length_mm", errors)
    b = _num(cfg, "width_mm", errors)
    h = _num(cfg, "height_mm", errors)
    E = _num(cfg, "material.E_GPa", errors)
    rho = _num(cfg, "material.density_kg_m3", errors)
    F = _num(cfg, "load_N", errors)
    da = _num(cfg, "allowable_deflection_mm", errors)
    sa = _num(cfg, "allowable_stress_MPa", errors, optional=True)
    ar = _num(cfg, "max_aspect_ratio", errors, optional=True)
    s = {
        k: _num(cfg, f"search.{k}", errors)
        for k in ["b_min_mm", "b_max_mm", "b_step_mm", "h_min_mm", "h_max_mm", "h_step_mm"]
    }

    def pos(name, v, label):
        if v is not None and v <= 0:
            errors.append(FieldError(name, f"{label} must be greater than zero (got {v:g})."))

    pos("length_mm", L, "Length")
    pos("width_mm", b, "Width")
    pos("height_mm", h, "Height")
    pos("material.E_GPa", E, "Young's modulus")
    pos("material.density_kg_m3", rho, "Density")
    if F is not None and F < 0:
        errors.append(
            FieldError(
                "load_N",
                "Enter the load as a magnitude (>= 0). Its direction is fixed: transverse, in the h direction.",
            )
        )
    pos("allowable_deflection_mm", da, "Allowable tip deflection")
    pos("allowable_stress_MPa", sa, "Allowable bending stress")
    pos("max_aspect_ratio", ar, "Maximum aspect ratio h/b")
    for k, v in s.items():
        pos(f"search.{k}", v, k.replace("_mm", "").replace("_", " "))
    if s["b_min_mm"] and s["b_max_mm"] and s["b_max_mm"] < s["b_min_mm"]:
        errors.append(FieldError("search.b_max_mm", "b max must be >= b min."))
    if s["h_min_mm"] and s["h_max_mm"] and s["h_max_mm"] < s["h_min_mm"]:
        errors.append(FieldError("search.h_max_mm", "h max must be >= h min."))
    if E is not None and E > 0 and (E > 2000 or E < 0.001):
        errors.append(
            FieldError(
                "material.E_GPa",
                f"E = {E:g} GPa is outside the plausible range 0.001-2000 GPa; check the unit (GPa expected, e.g. 3.5 for PLA, 200 for steel).",
            )
        )
    if rho is not None and rho > 0 and (rho < 10 or rho > 25000):
        errors.append(
            FieldError(
                "material.density_kg_m3",
                f"Density {rho:g} kg/m^3 is outside the plausible range 10-25000 kg/m^3; check the unit (e.g. 1240 kg/m^3 for PLA, not 1.24 g/cm^3).",
            )
        )
    if errors:
        raise InputError(errors)
    # Every required value is present once no errors were recorded.
    assert L is not None and b is not None and h is not None and E is not None
    assert rho is not None and F is not None and da is not None
    sv = [s[k] for k in ["b_min_mm", "b_max_mm", "b_step_mm", "h_min_mm", "h_max_mm", "h_step_mm"]]
    assert all(v is not None for v in sv)

    design = BeamDesign(L=U.mm_to_m(L), b=U.mm_to_m(b), h=U.mm_to_m(h), E=U.gpa_to_pa(E), rho=rho, F=F)
    req = Requirements(
        delta_allow=U.mm_to_m(da), sigma_allow=None if sa is None else U.mpa_to_pa(sa), max_aspect_ratio=ar
    )
    space = SearchSpace(*(U.mm_to_m(v) for v in sv if v is not None))
    validate_search_space(space)  # grid-size limits
    name = str(_get_optional(cfg, "material.name") or "Custom material")
    return Problem(design, req, space, name)


# ---------------------------------------------------------------------------
# Display-unit result packaging
# ---------------------------------------------------------------------------


def evaluation_to_display(ev: Evaluation) -> dict[str, Any]:
    d, r = ev.design, ev.result
    return {
        "b_mm": U.m_to_mm(d.b),
        "h_mm": U.m_to_mm(d.h),
        "L_mm": U.m_to_mm(d.L),
        "I_mm4": U.m4_to_mm4(r.I),
        "mass_g": U.kg_to_g(r.mass),
        "deflection_mm": U.m_to_mm(r.delta),
        "stress_MPa": U.pa_to_mpa(r.sigma),
        "feasible": ev.feasible,
        "checks": ev.checks,
        "warnings": ev.warnings,
    }


def run_problem(cfg: dict, top_n: int = 15) -> dict[str, Any]:
    """Full workflow: validate config, evaluate the current design, search.

    Every number returned here is produced by the closed-form formulas above.
    """
    p = parse_config(cfg)
    cur = evaluate(p.design, p.requirements)
    cur_disp = evaluation_to_display(cur)

    s = search(p.design, p.requirements, p.space)
    n = len(s["b"])
    cands = []
    for i in range(n):
        ev = Evaluation(
            design=BeamDesign(p.design.L, float(s["b"][i]), float(s["h"][i]), p.design.E, p.design.rho, p.design.F),
            result=BeamResult(float(s["I"][i]), float(s["mass"][i]), float(s["delta"][i]), float(s["sigma"][i])),
            feasible=bool(s["feasible"][i]),
        )
        cands.append(ev)

    ranked = [int(i) for i in s["ranked_feasible_idx"]]
    rank_of = {idx: k + 1 for k, idx in enumerate(ranked)}
    out_cands = []
    for i, ev in enumerate(cands):
        full = evaluate(ev.design, p.requirements)  # attaches checks/warnings text
        dd = evaluation_to_display(full)
        dd["id"] = f"b{dd['b_mm']:g}_h{dd['h_mm']:g}"
        dd["rank"] = rank_of.get(i)
        dd["mass_change_vs_current_pct"] = 100.0 * (full.result.mass - cur.result.mass) / cur.result.mass
        dd["reason"] = _reason(full)
        out_cands.append(dd)

    top = [out_cands[i] for i in ranked[:top_n]]

    nearest = []
    if not ranked:
        # Report how close the sampled space gets, without relaxing anything.
        util = np.maximum.reduce(
            [
                s["delta"] / p.requirements.delta_allow,
                (s["sigma"] / p.requirements.sigma_allow) if p.requirements.sigma_allow else np.zeros(n),
                (s["h"] / s["b"] / p.requirements.max_aspect_ratio) if p.requirements.max_aspect_ratio else np.zeros(n),
            ]
        )
        for i in np.argsort(util)[:5]:
            c = dict(out_cands[int(i)])
            c["max_utilisation"] = float(util[int(i)])
            nearest.append(c)

    # Normalised deflected shape v(x)/v(L) (independent of b, h, E, F) for plotting.
    xi = np.linspace(0.0, 1.0, 41)
    shape = deflection_curve(1.0, 1.0, 1.0, 1.0, xi) / deflection_curve(1.0, 1.0, 1.0, 1.0, 1.0)

    return {
        "config": cfg,
        "deflection_shape": {"xi": xi.tolist(), "v": shape.tolist(), "formula": "v(x)/v(L) = x^2 (3L - x) / (2 L^3)"},
        "material_name": p.material_name,
        "current": cur_disp,
        "search": {
            "n_candidates": n,
            "n_b": s["n_b"],
            "n_h": s["n_h"],
            "n_feasible": len(ranked),
            "n_fail_deflection": int((~s["ok_delta"]).sum()),
            "n_fail_stress": int((~s["ok_sigma"]).sum()),
            "n_fail_aspect": int((~s["ok_aspect"]).sum()),
            "fixed": {
                "L_mm": U.m_to_mm(p.design.L),
                "E_GPa": U.pa_to_gpa(p.design.E),
                "density_kg_m3": p.design.rho,
                "load_N": p.design.F,
            },
        },
        "candidates": out_cands,
        "top": top,
        "nearest_infeasible": nearest,
        "statement": _statement(len(ranked), n)
        + (
            " WARNING: the load is zero, so all deflections and stresses are zero and every candidate passes trivially; "
            "the mass ranking then only reflects the smallest cross-section."
            if p.design.F == 0
            else ""
        ),
    }


def _reason(ev: Evaluation) -> str:
    if ev.feasible:
        return "Feasible: " + "; ".join(c["text"] for c in ev.checks) + "."
    failed = [c["text"] for c in ev.checks if not c["passed"]]
    return "Rejected: " + "; ".join(failed) + "."


def _statement(n_feasible: int, n: int) -> str:
    if n_feasible == 0:
        return (
            f"No design among the {n} sampled (b, h) combinations satisfies all constraints. "
            "The constraints have not been relaxed. Consider changing the search ranges, the "
            "material, the length, or (if justified) the requirements."
        )
    return (
        f"{n_feasible} of {n} sampled (b, h) combinations satisfy all constraints. Candidates are ranked "
        "by mass within this sampled grid only; they are not guaranteed global optima, and designs "
        "between grid points or outside the ranges were not evaluated."
    )
