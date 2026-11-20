"""LLM code path with the network call mocked (no API key needed).

These tests check orchestration, provenance guards, placeholder filling and
fallback behaviour. They do not exercise the live Anthropic API.
"""

import copy

import pytest

from mechdesign import mechanics as M
from mechdesign.language import llm, service
from mechdesign.language.schema import Interpretation, MissingRequirement, ProposedUpdate


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.delenv("MECHDESIGN_DISABLE_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")


def test_llm_interpretation_is_guarded(enabled, monkeypatch):
    def fake_interpret(message, config, current):
        return Interpretation(
            intent="increase_stiffness",
            summary="Stiffer, width capped.",
            updates=[
                ProposedUpdate(field="search.b_max_mm", value=20.0, source="derived_from_current"),
                ProposedUpdate(field="load_N", value=8.0, source="user_stated"),
            ],  # 8 not in message
            missing_requirements=[
                MissingRequirement(field="allowable_deflection_mm", question="How much deflection is OK?")
            ],
        ), "claude-opus-5-5"

    monkeypatch.setattr(llm, "interpret", fake_interpret)
    r = service.interpret_request("make it stiffer without increasing width", copy.deepcopy(M.EXAMPLE_CONFIG), None)
    assert r["mode"] == "llm" and "claude-opus-5-5" in r["mode_label"]
    src = {d["field"]: d["source"] for d in r["diffs"]}
    assert src["load_N"] == "assistant_suggestion"  # downgraded by the guard
    assert r["guard_notes"]
    assert not r["ready"]


def test_llm_failure_falls_back_transparently(enabled, monkeypatch):
    def boom(*a, **k):
        raise llm.LLMError("could not reach the API")

    monkeypatch.setattr(llm, "interpret", boom)
    r = service.interpret_request("I want this mount to be lighter.", copy.deepcopy(M.EXAMPLE_CONFIG), None)
    assert r["mode"] == "rule-based"
    assert "LLM call failed" in r["llm_error"]


def test_llm_explanation_placeholders_and_number_check(enabled, monkeypatch):
    def fake_explain(facts, req):
        return (
            "The lightest feasible design ({{top1_b_mm}} x {{top1_h_mm}} mm) weighs {{top1_mass_g}} g. "
            "That is roughly 3 times lighter."
        ), "claude-opus-5-5"

    monkeypatch.setattr(llm, "explain", fake_explain)
    run = M.run_problem(copy.deepcopy(M.EXAMPLE_CONFIG))
    e = service.explain_results(run, "lighter")
    assert e["mode"] == "llm"
    assert run["top"][0]["b_mm"] == float(e["facts"]["top1_b_mm"])
    assert e["unverified_numbers"] == ["3"]  # number the model wrote itself is flagged


def test_no_key_means_disabled(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert llm.llm_enabled() is False
