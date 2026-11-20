"""Optional Claude-backed language layer.

Credentials are read server-side from the ANTHROPIC_API_KEY environment
variable (or any other credential source the Anthropic SDK resolves). They are
never sent to the browser. If no credentials are configured, or the call
fails, the application falls back to the rule-based parser and says so.

The LLM is used for two things only:
  * interpret(): turn a free-text request into a *proposed* configuration
    change (structured output validated with Pydantic);
  * explain(): write prose about results, referencing numbers only through
    placeholders that are filled in from the deterministic engine's output.
"""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, Field

from .schema import EDITABLE_FIELDS, Interpretation

DEFAULT_MODEL = "claude-opus-5-5"


def model_name() -> str:
    """Model id, read at call time so a ``.env`` loaded at startup is honoured."""
    return os.environ.get("MECHDESIGN_LLM_MODEL", "").strip() or DEFAULT_MODEL


def llm_enabled() -> bool:
    if os.environ.get("MECHDESIGN_DISABLE_LLM", "").strip() in ("1", "true", "yes"):
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


class LLMError(RuntimeError):
    pass


def _call_parse(system: str, user: str, output_format: Any) -> tuple[Any, str]:
    try:
        import anthropic
    except ImportError as e:
        raise LLMError("the 'anthropic' package is not installed (pip install 'mechdesign-agent[llm]')") from e

    client = anthropic.Anthropic()
    try:
        resp = client.beta.messages.parse(
            model=model_name(),
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=output_format,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIConnectionError as e:
        raise LLMError(f"could not reach the API ({e.__class__.__name__})") from e
    except anthropic.RateLimitError as e:
        raise LLMError("rate limited by the API") from e
    except anthropic.AuthenticationError as e:
        raise LLMError("API credentials were rejected") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"API error {e.status_code}") from e
    if resp.stop_reason == "refusal":
        raise LLMError("the model declined the request")
    if resp.stop_reason == "max_tokens" or resp.parsed_output is None:
        raise LLMError("the model response was incomplete")
    return resp.parsed_output, getattr(resp, "model", model_name())


INTERPRET_SYSTEM = """You interpret engineering requests for a sensor-mount design tool.
The mount is modelled as a rectangular cantilever: length L, width b, height h (bending direction),
Young's modulus E, density rho, a transverse tip load F, an allowable tip deflection, an optional
allowable bending stress and an optional max aspect ratio h/b. A separate deterministic engine does
ALL calculations; you never compute mechanics results.

Your job: propose configuration changes and list missing requirements. Rules:
- Use only these fields (display units): {fields}.
- source = "user_stated" ONLY if the number (or a plain unit conversion of a number) appears in the user's message.
  Say the conversion in `note` (e.g. "1 kg sensor -> 9.81 N static weight").
- source = "derived_from_current" when the value is copied from, or a simple stated ratio of, the current
  configuration/results given below (e.g. "without increasing width" -> search.b_max_mm = current width_mm;
  "keep height" -> search.h_min_mm = search.h_max_mm = current height_mm). Explain the derivation in `note`.
- source = "assistant_suggestion" for anything else. Do not invent loads, deflection limits or stress limits.
- If the goal depends on a load or acceptable deformation the user has not stated and that cannot be
  derived (e.g. "more stable", "stiffer" without a target), add it to missing_requirements with a clear
  question. Vague words like stable/sturdy/robust/better must be flagged in clarifications.
- Mention out-of-scope aspects (vibration, fatigue, buckling, joints, printing anisotropy) in clarifications if the user raises them.
- Do not recommend dimensions. Do not state any calculated results.
"""


def interpret(message: str, config: dict, current: dict | None) -> tuple[Interpretation, str]:
    fields = ", ".join(f"{k} [{u}]" for k, (_, u) in EDITABLE_FIELDS.items())
    system = INTERPRET_SYSTEM.format(fields=fields)
    cur = {k: v for k, v in (current or {}).items() if k in ("deflection_mm", "stress_MPa", "mass_g")}
    user = (
        "Current configuration (display units):\n"
        + json.dumps(config, indent=1)
        + "\n\nCurrent design results from the deterministic engine:\n"
        + json.dumps(cur)
        + "\n\nUser request:\n"
        + message
    )
    out, model = _call_parse(system, user, Interpretation)
    return out, model


class Explanation(BaseModel):
    text: str = Field(description="Explanation prose. Every number must be written as a {{fact_key}} placeholder.")


EXPLAIN_SYSTEM = """You explain results from a deterministic cantilever-beam calculation to an engineer.
You are given FACTS: a JSON object of pre-formatted values keyed by name. Rules:
- Every numerical value you mention MUST be written as a placeholder {{key}} using a key from FACTS.
  Do not write any digits yourself (write "the top-ranked candidate", not "candidate 1").
- Explain which candidates are feasible and why others are rejected, the main trade-off (mass vs deflection),
  and which constraint is governing.
- Say the ranking covers only the sampled grid, not a guaranteed global optimum.
- If there are no feasible candidates, say so plainly; do not suggest that limits were relaxed.
- Mention relevant model limitations briefly. 4-8 sentences, plain text, no markdown headings.
"""


def explain(facts: dict[str, str], user_request: str) -> tuple[str, str]:
    user = "FACTS:\n" + json.dumps(facts, indent=1) + "\n\nUser request (context):\n" + (user_request or "(none)")
    out, model = _call_parse(EXPLAIN_SYSTEM, user, Explanation)
    return out.text, model
