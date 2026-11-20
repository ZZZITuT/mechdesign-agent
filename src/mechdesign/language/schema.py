"""Shared schema for the language layer (LLM and rule-based parser).

The language layer only *proposes* configuration changes. It never computes
mechanics results; the UI shows every proposed value to the user, who must
review/edit it before the deterministic engine is run.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EDITABLE_FIELDS = {
    "length_mm": ("Length L", "mm"),
    "width_mm": ("Width b (current design)", "mm"),
    "height_mm": ("Height h (current design)", "mm"),
    "material.E_GPa": ("Young's modulus E", "GPa"),
    "material.density_kg_m3": ("Density rho", "kg/m^3"),
    "load_N": ("Tip load F", "N"),
    "allowable_deflection_mm": ("Allowable tip deflection", "mm"),
    "allowable_stress_MPa": ("Allowable bending stress", "MPa"),
    "max_aspect_ratio": ("Max aspect ratio h/b", "-"),
    "search.b_min_mm": ("Search b min", "mm"),
    "search.b_max_mm": ("Search b max", "mm"),
    "search.b_step_mm": ("Search b step", "mm"),
    "search.h_min_mm": ("Search h min", "mm"),
    "search.h_max_mm": ("Search h max", "mm"),
    "search.h_step_mm": ("Search h step", "mm"),
}

FieldName = Literal[
    "length_mm",
    "width_mm",
    "height_mm",
    "material.E_GPa",
    "material.density_kg_m3",
    "load_N",
    "allowable_deflection_mm",
    "allowable_stress_MPa",
    "max_aspect_ratio",
    "search.b_min_mm",
    "search.b_max_mm",
    "search.b_step_mm",
    "search.h_min_mm",
    "search.h_max_mm",
    "search.h_step_mm",
]

Source = Literal["user_stated", "derived_from_current", "assistant_suggestion"]

Intent = Literal[
    "reduce_mass",
    "increase_stiffness",
    "compare_designs",
    "reduce_stress",
    "evaluate_current",
    "change_parameters",
    "unclear",
]


class ProposedUpdate(BaseModel):
    field: FieldName
    value: float = Field(description="Value in the field's display unit (mm, N, GPa, MPa, kg/m^3).")
    source: Source = Field(
        description="user_stated: the number (or a unit conversion of it) appears in the user's message. "
        "derived_from_current: copied or computed from the current configuration values. "
        "assistant_suggestion: anything else; the user must confirm it."
    )
    note: str = Field(default="", description="Short justification, including any unit conversion performed.")


class MissingRequirement(BaseModel):
    field: FieldName
    question: str = Field(description="Question to ask the user so they can supply this value.")


class Interpretation(BaseModel):
    intent: Intent
    summary: str = Field(description="One or two sentences restating what the user asked for, in engineering terms.")
    updates: list[ProposedUpdate] = Field(default_factory=list)
    missing_requirements: list[MissingRequirement] = Field(default_factory=list)
    material_name: str | None = Field(default=None, description="Material name if the user named one, else null.")
    clarifications: list[str] = Field(
        default_factory=list, description="Ambiguities or out-of-scope aspects to tell the user about."
    )
