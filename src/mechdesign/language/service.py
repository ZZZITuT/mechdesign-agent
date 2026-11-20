"""Orchestrates the language layer around the deterministic engine.

* interpret_request(): LLM (if configured) or rule-based parser -> proposal,
  then deterministic guards that downgrade any unsupported "user_stated"
  numbers and decide whether required inputs are still missing.
* explain_results(): builds a FACTS table from engine output, gets prose
  from the LLM (placeholders only) or a deterministic template, and verifies
  that every number in the final text came from FACTS.
"""

from __future__ import annotations

import contextlib
import copy
import re
from typing import Any

from .. import units as U
from . import llm, rule_parser
from .schema import EDITABLE_FIELDS, Interpretation, ProposedUpdate

FALLBACK_LABEL = "Rule-based parser (no LLM configured) - limited pattern matching, not a language model"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"(?<![A-Za-z_])-?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?")


def numbers_in(text: str) -> list[float]:
    out = []
    for m in _NUM_RE.finditer(text):
        with contextlib.suppress(ValueError):
            out.append(float(m.group(0).replace(",", ".")))
    return out


def _close(a: float, b: float, rel: float = 2e-3) -> bool:
    return abs(a - b) <= rel * max(abs(a), abs(b), 1e-12)


def _get(cfg: dict, path: str) -> Any:
    cur: Any = cfg
    for p in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _set(cfg: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = cfg
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


# Conversions a user number may legitimately undergo before becoming a field value.
_CONVERSIONS = [1.0, 10.0, 1000.0, 0.001, 0.1, U.STANDARD_GRAVITY, U.STANDARD_GRAVITY / 1000.0, 1e-3 * 1e3]


def guard_updates(
    interp: Interpretation, message: str, config: dict, current: dict | None
) -> tuple[Interpretation, list[str]]:
    """Deterministically verify the provenance claimed for each proposed value."""
    notes: list[str] = []
    user_nums = numbers_in(message)
    cur_vals = [v for v in _flatten_numbers(config)] + [v for v in _flatten_numbers(current or {})]
    fixed: list[ProposedUpdate] = []
    for u in interp.updates:
        if u.source == "user_stated":
            ok = any(_close(u.value, n * c) for n in user_nums for c in _CONVERSIONS)
            if not ok:
                notes.append(
                    f"{u.field} = {u.value:g} was labelled as stated by you, but that number does not appear in your message; it is shown as a suggestion that needs confirmation."
                )
                u = u.model_copy(update={"source": "assistant_suggestion"})
        elif u.source == "derived_from_current":
            loads = [config.get("load_N")] + [x.value for x in interp.updates if x.field == "load_N"]
            ok = any(_close(u.value, v) for v in cur_vals) or _derived_ratio_ok(
                u.value, message, config, current, loads
            )
            if not ok:
                notes.append(
                    f"{u.field} = {u.value:g} was labelled as derived from the current design, but it could not be traced to a current value; shown as a suggestion that needs confirmation."
                )
                u = u.model_copy(update={"source": "assistant_suggestion"})
        fixed.append(u)
    return interp.model_copy(update={"updates": fixed}), notes


def _derived_ratio_ok(value: float, message: str, config: dict, current: dict | None, loads: list) -> bool:
    """Accept a deflection limit derived from a stated relative stiffness change:
    allowable = F / (factor * k_current), k_current = F_current / delta_current."""
    cur_d = (current or {}).get("deflection_mm")
    cur_F = config.get("load_N")
    if not cur_d or not cur_F:
        return False
    k = cur_F / cur_d
    for n in numbers_in(message):
        factors = [1 + n / 100, n]
        if n < 100:
            factors.append(1 / (1 - n / 100))
        for fct in factors:
            for F in loads:
                if fct and F and _close(value, F / (fct * k)):
                    return True
    return False


def _flatten_numbers(d: Any):
    if isinstance(d, dict):
        for v in d.values():
            yield from _flatten_numbers(v)
    elif isinstance(d, list):
        for v in d:
            yield from _flatten_numbers(v)
    elif isinstance(d, (int, float)) and not isinstance(d, bool):
        yield float(d)


# ---------------------------------------------------------------------------
# interpret
# ---------------------------------------------------------------------------


def interpret_request(message: str, config: dict, current: dict | None) -> dict[str, Any]:
    if not message or not message.strip():
        return {"error": "Please type a request."}
    mode, model, llm_error = "rule-based", None, None
    interp: Interpretation | None = None
    if llm.llm_enabled():
        try:
            interp, model = llm.interpret(message, config, current)
            mode = "llm"
        except Exception as e:
            llm_error = f"LLM call failed ({e}); used the rule-based parser instead."
    if interp is None:
        interp = rule_parser.parse(message, config, current)

    interp, guard_notes = guard_updates(interp, message, config, current)

    proposed = copy.deepcopy(config)
    diffs = []
    for u in interp.updates:
        old = _get(config, u.field)
        _set(proposed, u.field, u.value)
        label, unit = EDITABLE_FIELDS[u.field]
        diffs.append(
            {
                "field": u.field,
                "label": label,
                "unit": unit,
                "old": old,
                "new": u.value,
                "source": u.source,
                "note": u.note,
            }
        )
    if interp.material_name:
        _set(proposed, "material.name", interp.material_name)

    missing = []
    for mr in interp.missing_requirements:
        if any(d["field"] == mr.field for d in diffs):
            continue
        label, unit = EDITABLE_FIELDS[mr.field]
        missing.append(
            {
                "field": mr.field,
                "label": label,
                "unit": unit,
                "question": mr.question,
                "current_form_value": _get(config, mr.field),
            }
        )

    # Requirements that will be used as-is from the form (made explicit, never silent).
    used_from_form = []
    for f in ("load_N", "allowable_deflection_mm", "allowable_stress_MPa"):
        if not any(d["field"] == f for d in diffs) and not any(m["field"] == f for m in missing):
            label, unit = EDITABLE_FIELDS[f]
            used_from_form.append({"field": f, "label": label, "unit": unit, "value": _get(config, f)})

    return {
        "mode": mode,
        "mode_label": f"LLM ({model})" if mode == "llm" else FALLBACK_LABEL,
        "llm_error": llm_error,
        "intent": interp.intent,
        "summary": interp.summary,
        "diffs": diffs,
        "missing": missing,
        "used_from_form": used_from_form,
        "clarifications": interp.clarifications,
        "guard_notes": guard_notes,
        "material_name": interp.material_name,
        "proposed_config": proposed,
        "ready": len(missing) == 0,
    }


# ---------------------------------------------------------------------------
# explain
# ---------------------------------------------------------------------------


def _fmt(v: float, sig: int = 3) -> str:
    if v == 0:
        return "0"
    s = f"{v:.{sig}g}"
    if "e" in s:
        s = f"{v:.{sig}e}"
    return s


def build_facts(run: dict[str, Any], selected: dict | None = None) -> dict[str, str]:
    cfg = run["config"]
    cur = run["current"]
    s = run["search"]
    f: dict[str, str] = {
        "load_N": _fmt(cfg["load_N"]),
        "length_mm": _fmt(cfg["length_mm"]),
        "allowable_deflection_mm": _fmt(cfg["allowable_deflection_mm"]),
        "current_b_mm": _fmt(cur["b_mm"]),
        "current_h_mm": _fmt(cur["h_mm"]),
        "current_mass_g": _fmt(cur["mass_g"]),
        "current_deflection_mm": _fmt(cur["deflection_mm"]),
        "current_stress_MPa": _fmt(cur["stress_MPa"]),
        "current_status": "feasible" if cur["feasible"] else "not feasible",
        "n_candidates": str(s["n_candidates"]),
        "n_feasible": str(s["n_feasible"]),
        "n_fail_deflection": str(s["n_fail_deflection"]),
        "n_fail_stress": str(s["n_fail_stress"]),
        "n_fail_aspect": str(s["n_fail_aspect"]),
        "material": run.get("material_name", ""),
    }
    if cfg.get("allowable_stress_MPa") is not None:
        f["allowable_stress_MPa"] = _fmt(cfg["allowable_stress_MPa"])
    for k, c in enumerate(run["top"][:3], start=1):
        f[f"top{k}_b_mm"] = _fmt(c["b_mm"])
        f[f"top{k}_h_mm"] = _fmt(c["h_mm"])
        f[f"top{k}_mass_g"] = _fmt(c["mass_g"])
        f[f"top{k}_deflection_mm"] = _fmt(c["deflection_mm"])
        f[f"top{k}_stress_MPa"] = _fmt(c["stress_MPa"])
        f[f"top{k}_mass_change_pct"] = _fmt(c["mass_change_vs_current_pct"], 2)
        f[f"top{k}_deflection_utilisation_pct"] = _fmt(100 * c["checks"][0]["utilisation"], 3)
    for k, c in enumerate(run.get("nearest_infeasible", [])[:2], start=1):
        f[f"nearest{k}_b_mm"] = _fmt(c["b_mm"])
        f[f"nearest{k}_h_mm"] = _fmt(c["h_mm"])
        f[f"nearest{k}_deflection_mm"] = _fmt(c["deflection_mm"])
        f[f"nearest{k}_stress_MPa"] = _fmt(c["stress_MPa"])
        f[f"nearest{k}_max_utilisation_pct"] = _fmt(100 * c["max_utilisation"], 3)
    if selected:
        f["selected_b_mm"] = _fmt(selected["b_mm"])
        f["selected_h_mm"] = _fmt(selected["h_mm"])
        f["selected_mass_g"] = _fmt(selected["mass_g"])
        f["selected_deflection_mm"] = _fmt(selected["deflection_mm"])
        f["selected_stress_MPa"] = _fmt(selected["stress_MPa"])
    return f


_PH = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def fill_placeholders(text: str, facts: dict[str, str]) -> tuple[str, list[str]]:
    unknown: list[str] = []

    def rep(m):
        k = m.group(1)
        if k in facts:
            return facts[k]
        unknown.append(k)
        return f"[unknown value '{k}']"

    return _PH.sub(rep, text), unknown


def verify_numbers(raw_text: str, facts: dict[str, str]) -> list[str]:
    """Numbers written directly by the model (outside placeholders) that do not
    match any FACTS value. These are flagged to the user."""
    stripped = _PH.sub(" ", raw_text)
    allowed = []
    for v in facts.values():
        allowed += numbers_in(v)
    bad = []
    for n in numbers_in(stripped):
        if not any(_close(n, a, 5e-3) for a in allowed):
            bad.append(_fmt(n, 6))
    return bad


def template_explanation(run: dict[str, Any], facts: dict[str, str]) -> str:
    """Deterministic explanation (used without an LLM). Placeholders only."""
    parts = []
    stress_txt = " and allowable bending stress {{allowable_stress_MPa}} MPa" if "allowable_stress_MPa" in facts else ""
    parts.append(
        "With L = {{length_mm}} mm, tip load {{load_N}} N and material {{material}}, the current design "
        "(b = {{current_b_mm}} mm, h = {{current_h_mm}} mm) has mass {{current_mass_g}} g, tip deflection "
        "{{current_deflection_mm}} mm and max bending stress {{current_stress_MPa}} MPa; it is {{current_status}} "
        "against the allowable deflection {{allowable_deflection_mm}} mm" + stress_txt + "."
    )
    parts.append(
        "Of {{n_candidates}} sampled (b, h) combinations, {{n_feasible}} satisfy all constraints "
        "({{n_fail_deflection}} exceed the deflection limit, {{n_fail_stress}} exceed the stress limit, "
        "{{n_fail_aspect}} exceed the aspect-ratio limit; a candidate can fail more than one)."
    )
    if run["top"]:
        parts.append(
            "The lightest feasible sampled candidate is b = {{top1_b_mm}} mm, h = {{top1_h_mm}} mm: mass "
            "{{top1_mass_g}} g ({{top1_mass_change_pct}}% vs current), deflection {{top1_deflection_mm}} mm "
            "({{top1_deflection_utilisation_pct}}% of the limit), stress {{top1_stress_MPa}} MPa."
        )
        if "top2_b_mm" in facts:
            parts.append(
                "Next: b = {{top2_b_mm}} mm, h = {{top2_h_mm}} mm ({{top2_mass_g}} g, {{top2_deflection_mm}} mm)."
            )
        parts.append(
            "Because deflection is inversely proportional to b·h³ while mass is proportional to b·h, taller, narrower sections "
            "are lighter for the same stiffness; check that such sections are acceptable for buckling, "
            "fastening and printing, which this model does not cover."
        )
        parts.append("This ranking covers only the sampled grid; it is not a guaranteed global optimum.")
    else:
        parts.append("No sampled design satisfies the constraints, and the constraints have not been relaxed.")
        if "nearest1_b_mm" in facts:
            parts.append(
                "The closest sampled design is b = {{nearest1_b_mm}} mm, h = {{nearest1_h_mm}} mm with deflection "
                "{{nearest1_deflection_mm}} mm and stress {{nearest1_stress_MPa}} MPa (worst constraint at "
                "{{nearest1_max_utilisation_pct}}% of its limit)."
            )
        parts.append(
            "Options: widen the b/h search ranges, change material or length, or revisit the requirements deliberately."
        )
    return " ".join(parts)


def explain_results(run: dict[str, Any], user_request: str = "", selected: dict | None = None) -> dict[str, Any]:
    facts = build_facts(run, selected)
    mode, model, llm_error = "template", None, None
    raw = None
    if llm.llm_enabled():
        try:
            raw, model = llm.explain(facts, user_request)
            mode = "llm"
        except Exception as e:
            llm_error = f"LLM call failed ({e}); used the deterministic template instead."
    if raw is None:
        raw = template_explanation(run, facts)
    text, unknown = fill_placeholders(raw, facts)
    unverified = verify_numbers(raw, facts)
    return {
        "mode": mode,
        "mode_label": f"LLM ({model}); numbers inserted from engine results"
        if mode == "llm"
        else "Deterministic template (no LLM); numbers inserted from engine results",
        "llm_error": llm_error,
        "text": text,
        "facts": facts,
        "unknown_placeholders": unknown,
        "unverified_numbers": unverified,
    }
