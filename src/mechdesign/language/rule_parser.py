"""Rule-based requirement parser (fallback when no LLM API key is configured).

This is a small, transparent pattern matcher, NOT a language model. It
recognises a limited vocabulary (see README) and reports anything it cannot
interpret as a clarification instead of guessing.
"""

from __future__ import annotations

import re
from typing import Any

from .. import units as U
from ..mechanics import MATERIAL_PRESETS
from .schema import Intent, Interpretation, MissingRequirement, ProposedUpdate

NUM = r"(\d+(?:[.,]\d+)?)"
UNIT_RE = re.compile(NUM + r"\s*(mm|cm|m|kn|n|kg|g|mpa|gpa|kpa|%|x)(?![a-z])", re.I)

DEFLECTION_WORDS = r"deflect|sag|droop|displac|bend|deform|move|movement|tip"
STRESS_WORDS = r"stress|strength|mpa"
LENGTH_WORDS = r"length|long|reach|overhang|span"
WIDTH_WORDS = r"width|wide|breadth"
HEIGHT_WORDS = r"height|thick|tall|deep|depth"
LOAD_WORDS = r"load|force|weigh|sensor|carry|support|hold"

VAGUE_TERMS = {
    "stable": "'Stable' is ambiguous: it could mean stiffness under a static load (modelled here), vibration/resonance (not modelled), or tipping/anchoring (not modelled).",
    "sturdy": "'Sturdy' is ambiguous: it could mean stiffness (deflection) or strength (stress).",
    "robust": "'Robust' is ambiguous: it could mean stiffness, strength, fatigue or impact resistance; only static deflection and stress are modelled.",
    "stronger": "'Stronger' usually means lower stress for a given load; please state the load and an allowable stress.",
    "better": "'Better' does not identify a requirement; please state what should improve (mass, deflection or stress) and the limits.",
    "solid": "'Solid' is ambiguous; please state a load and acceptable deformation.",
}


def _f(s: str) -> float:
    return float(s.replace(",", "."))


_CLAUSE_BREAK = re.compile(r"[,;:!?]|\.(?!\d)|\band\b|\bbut\b|\bwith\b")


def _context(text: str, start: int, span: int = 45) -> str:
    """Words before a number, limited to the same clause."""
    before = text[max(0, start - span) : start].lower()
    parts = _CLAUSE_BREAK.split(before)
    return parts[-1] if parts else before


def _after(text: str, end: int, span: int = 25) -> str:
    """Words after a number, limited to the same clause."""
    after = text[end : end + span].lower()
    return _CLAUSE_BREAK.split(after)[0]


def _get(cfg: dict, path: str) -> Any:
    cur: Any = cfg
    for p in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def parse(message: str, config: dict, current: dict | None = None) -> Interpretation:
    """Interpret a free-text request against the current configuration.

    ``current`` is the deterministic evaluation of the current design (display
    units) and is only used for relative requests such as "20% stiffer".
    """
    text = message.strip()
    low = text.lower()
    updates: list[ProposedUpdate] = []
    missing: list[MissingRequirement] = []
    clar: list[str] = []
    stated: set[str] = set()
    relative_stiffness: tuple[float, str] | None = None

    def add(field, value, source, note=""):
        for u in updates:
            if u.field == field:
                return
        updates.append(ProposedUpdate(field=field, value=round(float(value), 9), source=source, note=note))
        stated.add(field)

    # ---- intent -----------------------------------------------------------
    intent: Intent = "unclear"
    if re.search(r"\bcompar|alternativ|options|candidates|trade-?off", low):
        intent = "compare_designs"
    elif re.search(r"light|less material|reduce (the )?(mass|weight)|save material|less mass|less weight|cheaper", low):
        intent = "reduce_mass"
    elif re.search(r"stiff|rigid|less deflect|deflect less|reduce (the )?deflect|less sag|bend less", low):
        intent = "increase_stiffness"
    elif re.search(r"lower stress|reduce (the )?stress|less stress", low):
        intent = "reduce_stress"
    elif re.search(r"evaluat|check|calculat|analy[sz]e", low):
        intent = "evaluate_current"

    # ---- numbers with units -----------------------------------------------
    for m in UNIT_RE.finditer(text):
        val, unit = _f(m.group(1)), m.group(2).lower()
        ctx = _context(text, m.start())
        after = _after(text, m.end())
        if unit in ("mm", "cm", "m"):
            mm = val * {"mm": 1.0, "cm": 10.0, "m": 1000.0}[unit]
            conv = "" if unit == "mm" else f" (converted from {val:g} {unit})"
            if re.search(DEFLECTION_WORDS, ctx) or re.search(DEFLECTION_WORDS, after):
                add("allowable_deflection_mm", mm, "user_stated", "Allowable tip deflection" + conv)
            elif re.search(WIDTH_WORDS, ctx) or re.search(WIDTH_WORDS, after):
                add("width_mm", mm, "user_stated", "Width" + conv)
            elif re.search(HEIGHT_WORDS, ctx) or re.search(HEIGHT_WORDS, after):
                add("height_mm", mm, "user_stated", "Height" + conv)
            elif re.search(LENGTH_WORDS, ctx) or re.search(LENGTH_WORDS, after):
                add("length_mm", mm, "user_stated", "Length" + conv)
            else:
                clar.append(
                    f"I could not tell what '{m.group(0)}' refers to (deflection limit, length, width or height). Please enter it in the form or rephrase."
                )
        elif unit in ("n", "kn"):
            add(
                "load_N",
                val * (1000.0 if unit == "kn" else 1.0),
                "user_stated",
                "Tip load" + ("" if unit == "n" else f" (converted from {val:g} kN)"),
            )
        elif unit in ("kg", "g"):
            if re.search(r"light|mass|weigh(s|t)? (less|under|below)|under|below|less than", ctx) and not re.search(
                LOAD_WORDS + r"|sensor", ctx
            ):
                clar.append(
                    f"'{m.group(0)}' looks like a mass target. Mass is minimised by ranking rather than constrained; compare it with the candidate masses in the table."
                )
            else:
                kg = val if unit == "kg" else val / 1000.0
                add(
                    "load_N",
                    U.kg_mass_to_newton(kg),
                    "user_stated",
                    f"Static weight of {val:g} {unit} under standard gravity ({U.STANDARD_GRAVITY} m/s^2); no dynamic factor applied",
                )
        elif unit in ("mpa", "kpa"):
            mpa = val / 1000.0 if unit == "kpa" else val
            if re.search(r"modul|young|\be\s*=", ctx):
                clar.append(f"'{m.group(0)}' looks like a modulus; enter Young's modulus in GPa in the form.")
            else:
                add("allowable_stress_MPa", mpa, "user_stated", "Allowable bending stress")
        elif unit == "gpa":
            add("material.E_GPa", val, "user_stated", "Young's modulus")
        elif unit in ("%", "x"):
            factor_text = ctx + " " + after
            if re.search(r"stiff|rigid|deflect|sag", factor_text):
                if unit == "%":
                    if re.search(r"less|reduc|lower|decreas", factor_text):
                        if val < 100:
                            relative_stiffness = (1.0 / (1 - val / 100.0), f"tip deflection reduced by {val:g}%")
                    else:
                        relative_stiffness = (1 + val / 100.0, f"{val:g}% stiffer")
                elif val > 0:
                    relative_stiffness = (val, f"{val:g}x stiffer")
                if relative_stiffness is None:
                    clar.append(f"Could not interpret '{m.group(0)}' as a stiffness change.")
            elif re.search(r"light|mass|weigh|material", factor_text):
                clar.append(
                    f"Mass reduction target '{m.group(0)}': mass is minimised by ranking, not constrained. Compare candidate 'mass change vs current' in the table."
                )
            else:
                clar.append(f"Could not interpret '{m.group(0)}'.")

    # Relative stiffness request -> deflection limit, using the engine's current
    # stiffness k = F_current / delta_current and the (possibly new) load.
    if relative_stiffness is not None:
        factor, what = relative_stiffness
        cur_d = (current or {}).get("deflection_mm")
        cur_F = _get(config, "load_N")
        new_F = next((u.value for u in updates if u.field == "load_N"), cur_F)
        if cur_d and cur_F:
            k_cur = cur_F / cur_d  # N/mm, from the deterministic evaluation
            target = new_F / (factor * k_cur)
            add(
                "allowable_deflection_mm",
                target,
                "derived_from_current",
                f"{what} than the current design: current stiffness {cur_F:g} N / {cur_d:.4g} mm = {k_cur:.4g} N/mm; "
                f"target {factor:.4g} x {k_cur:.4g} N/mm; allowable deflection = {new_F:.4g} N / target stiffness",
            )
        else:
            clar.append(
                "A relative stiffness change needs a valid current design with a non-zero load; please enter an allowable deflection directly."
            )

    # dimensionless aspect-ratio limit, e.g. "h/b <= 3" or "aspect ratio below 3"
    m_ar = re.search(r"(?:h/b|aspect ratio)[^0-9]{0,20}" + NUM, low)
    if m_ar:
        add("max_aspect_ratio", _f(m_ar.group(1)), "user_stated", "Maximum h/b")

    # ---- geometric restrictions -------------------------------------------
    w = _get(config, "width_mm")
    h = _get(config, "height_mm")
    for dim, words, cur, fmin, fmax in (
        ("width", r"width|wider", w, "search.b_min_mm", "search.b_max_mm"),
        ("height", r"height|thickness|thicker|taller|deeper", h, "search.h_min_mm", "search.h_max_mm"),
    ):
        if cur is None:
            continue
        no_increase = (
            re.search(
                r"(without|not|never|no|don't|do not)\s+(increas\w*|making it (wider|thicker|taller|deeper)|grow\w*)[\w\s']{0,15}("
                + words
                + ")",
                low,
            )
            or re.search(
                r"(" + words + r")[\w\s]{0,12}(must not|cannot|can't|should not|shouldn't) (increase|grow|exceed)", low
            )
            or (re.search(r"(no|not) (wider|thicker|taller|deeper)", low) and re.search(words, low))
        )
        keep = re.search(
            r"(keep|same|fixed|fix|without changing|don't change|do not change|unchanged)[\w\s]{0,12}(" + words + ")",
            low,
        ) or re.search(r"(" + words + r")[\w\s]{0,10}(fixed|unchanged|stays|the same)", low)
        if keep:
            add(fmin, cur, "derived_from_current", f"Keep {dim} fixed at the current {cur:g} mm")
            add(fmax, cur, "derived_from_current", f"Keep {dim} fixed at the current {cur:g} mm")
        elif no_increase:
            add(fmax, cur, "derived_from_current", f"Do not exceed the current {dim} {cur:g} mm")
            smin = _get(config, fmin)
            if smin is not None and smin > cur:
                add(fmin, cur, "derived_from_current", f"Lower bound reduced so the range contains the current {dim}")

    # ---- material ---------------------------------------------------------
    material_name: str | None = None
    for preset, pat in (
        (MATERIAL_PRESETS[0], r"\bpla\b"),
        (MATERIAL_PRESETS[1], r"\bpetg\b"),
        (MATERIAL_PRESETS[2], r"\babs\b"),
        (MATERIAL_PRESETS[3], r"alumin"),
        (MATERIAL_PRESETS[4], r"\bsteel\b"),
    ):
        if re.search(pat, low):
            material_name = str(preset["name"])
            if "material.E_GPa" not in stated:
                add(
                    "material.E_GPa",
                    preset["E_GPa"],
                    "assistant_suggestion",
                    f"Preset value for {preset['name']}: {preset['note']}",
                )
            add(
                "material.density_kg_m3",
                preset["density_kg_m3"],
                "assistant_suggestion",
                f"Preset value for {preset['name']}",
            )
            break

    # ---- vague wording & missing requirements ------------------------------
    vague_hits = [t for t in VAGUE_TERMS if re.search(r"\b" + t, low)]
    for t in vague_hits:
        clar.append(VAGUE_TERMS[t])

    if vague_hits:
        if "load_N" not in stated:
            missing.append(
                MissingRequirement(
                    field="load_N",
                    question="What load (N) must the mount carry at its tip? Include the sensor weight and any handling or dynamic allowance you want to cover.",
                )
            )
        if "allowable_deflection_mm" not in stated:
            missing.append(
                MissingRequirement(
                    field="allowable_deflection_mm", question="What tip deflection (mm) is acceptable under that load?"
                )
            )
        if intent == "unclear":
            intent = "increase_stiffness" if any(t in ("stable", "sturdy", "solid") for t in vague_hits) else "unclear"

    if intent == "increase_stiffness" and "allowable_deflection_mm" not in stated:
        cur_d = (current or {}).get("deflection_mm")
        hint = f" The current design deflects {cur_d:.4g} mm under the current load." if cur_d is not None else ""
        if not any(mr.field == "allowable_deflection_mm" for mr in missing):
            missing.append(
                MissingRequirement(
                    field="allowable_deflection_mm",
                    question="How stiff must it be? Enter the allowable tip deflection (mm)." + hint,
                )
            )

    if intent == "reduce_stress" and "allowable_stress_MPa" not in stated:
        missing.append(
            MissingRequirement(
                field="allowable_stress_MPa", question="What allowable bending stress (MPa) should be enforced?"
            )
        )

    if intent == "unclear" and not updates and not missing:
        clar.append(
            "I could not identify a design goal. Try e.g. 'make it lighter', 'make it stiffer without increasing width', "
            "or 'compare designs that deflect less than 0.5 mm'."
        )

    summary = _summary(intent, updates, missing)
    return Interpretation(
        intent=intent,
        summary=summary,
        updates=updates,
        missing_requirements=missing,
        material_name=material_name,
        clarifications=clar,
    )


def _summary(intent, updates, missing) -> str:
    base = {
        "reduce_mass": "Reduce mass while keeping the deflection (and any stress) limits.",
        "increase_stiffness": "Reduce tip deflection (increase bending stiffness), ranking feasible designs by mass.",
        "compare_designs": "Compare candidate cross-sections that satisfy the stated limits.",
        "reduce_stress": "Reduce maximum bending stress below an allowable value.",
        "evaluate_current": "Evaluate the current design against the requirements.",
        "change_parameters": "Update the stated parameters and recalculate.",
        "unclear": "The goal is unclear.",
    }[intent]
    if updates:
        base += f" {len(updates)} parameter change(s) proposed."
    if missing:
        base += f" {len(missing)} requirement(s) missing; please supply them before running."
    return base
