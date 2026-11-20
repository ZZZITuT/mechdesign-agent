import copy

import pytest

from mechdesign import mechanics as M
from mechdesign.language import service
from mechdesign.language.schema import Interpretation, ProposedUpdate


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setenv("MECHDESIGN_DISABLE_LLM", "1")


@pytest.fixture
def cfg():
    return copy.deepcopy(M.EXAMPLE_CONFIG)


@pytest.fixture
def current(cfg):
    p = M.parse_config(cfg)
    return M.evaluation_to_display(M.evaluate(p.design, p.requirements))


def fields(res):
    return {d["field"]: d for d in res["diffs"]}


def test_lighter_uses_form_requirements_explicitly(cfg, current):
    r = service.interpret_request("I want this mount to be lighter.", cfg, current)
    assert r["mode"] == "rule-based" and "not a language model" in r["mode_label"]
    assert r["intent"] == "reduce_mass"
    assert r["ready"]
    used = {u["field"] for u in r["used_from_form"]}
    assert {"load_N", "allowable_deflection_mm"} <= used


def test_stiffer_without_wider_needs_target(cfg, current):
    r = service.interpret_request("Make it stiffer without increasing its width.", cfg, current)
    assert r["intent"] == "increase_stiffness"
    f = fields(r)
    assert f["search.b_max_mm"]["new"] == cfg["width_mm"]
    assert f["search.b_max_mm"]["source"] == "derived_from_current"
    assert not r["ready"]
    assert [m["field"] for m in r["missing"]] == ["allowable_deflection_mm"]


def test_compare_with_deflection_limit(cfg, current):
    r = service.interpret_request("Compare designs that deflect less than 0.3 mm.", cfg, current)
    assert r["intent"] == "compare_designs"
    f = fields(r)
    assert f["allowable_deflection_mm"]["new"] == pytest.approx(0.3)
    assert f["allowable_deflection_mm"]["source"] == "user_stated"
    assert r["ready"]


def test_vague_request_requires_load_and_deformation(cfg, current):
    r = service.interpret_request("Make it more stable", cfg, current)
    assert not r["ready"]
    assert {m["field"] for m in r["missing"]} == {"load_N", "allowable_deflection_mm"}
    assert any("ambiguous" in c for c in r["clarifications"])
    assert r["diffs"] == []  # nothing invented


def test_units_and_relative_stiffness(cfg, current):
    r = service.interpret_request(
        "Make it 30% stiffer, keep the height, use aluminium. The sensor weighs 200 g.", cfg, current
    )
    f = fields(r)
    assert f["load_N"]["new"] == pytest.approx(0.2 * 9.80665)
    assert f["load_N"]["source"] == "user_stated"
    assert f["search.h_min_mm"]["new"] == f["search.h_max_mm"]["new"] == cfg["height_mm"]
    k_cur = cfg["load_N"] / current["deflection_mm"]
    assert f["allowable_deflection_mm"]["new"] == pytest.approx(f["load_N"]["new"] / (1.3 * k_cur), rel=1e-6)
    assert f["allowable_deflection_mm"]["source"] == "derived_from_current"
    assert f["material.E_GPa"]["source"] == "assistant_suggestion"
    assert r["guard_notes"] == []


def test_unit_conversion_cm_and_kn(cfg, current):
    r = service.interpret_request("length 12 cm, load 0.01 kN, deflection under 0.2 mm", cfg, current)
    f = fields(r)
    assert f["length_mm"]["new"] == pytest.approx(120)
    assert f["load_N"]["new"] == pytest.approx(10)
    assert f["allowable_deflection_mm"]["new"] == pytest.approx(0.2)


def test_unrecognised_request_does_not_guess(cfg, current):
    r = service.interpret_request("hello there", cfg, current)
    assert r["intent"] == "unclear"
    assert r["diffs"] == []
    assert r["clarifications"]


def test_guard_downgrades_invented_numbers(cfg, current):
    fake = Interpretation(
        intent="increase_stiffness",
        summary="x",
        updates=[
            ProposedUpdate(field="load_N", value=12.0, source="user_stated"),
            ProposedUpdate(field="allowable_deflection_mm", value=0.25, source="derived_from_current"),
            ProposedUpdate(field="search.b_max_mm", value=20.0, source="derived_from_current"),
        ],
    )
    out, notes = service.guard_updates(fake, "make it stiffer, the load is 10 N", cfg, current)
    src = {u.field: u.source for u in out.updates}
    assert src["load_N"] == "assistant_suggestion"
    assert src["allowable_deflection_mm"] == "assistant_suggestion"
    assert src["search.b_max_mm"] == "derived_from_current"
    assert len(notes) == 2


def test_explanation_numbers_come_from_engine(cfg):
    run = M.run_problem(cfg)
    e = service.explain_results(run, "lighter")
    assert e["mode"] == "template"
    assert e["unverified_numbers"] == [] and e["unknown_placeholders"] == []
    assert e["facts"]["top1_mass_g"] in e["text"]
    assert "not a guaranteed global optimum" in e["text"]


def test_explanation_flags_untraceable_numbers(cfg):
    run = M.run_problem(cfg)
    facts = service.build_facts(run)
    raw = "The best design weighs {{top1_mass_g}} g, about 42.5 g lighter, see {{bogus}}."
    text, unknown = service.fill_placeholders(raw, facts)
    assert unknown == ["bogus"]
    assert "42.5" in service.verify_numbers(raw, facts)
    assert facts["top1_mass_g"] in text


def test_no_feasible_explanation(cfg):
    cfg["allowable_deflection_mm"] = 0.001
    e = service.explain_results(M.run_problem(cfg))
    assert "No sampled design satisfies" in e["text"]
    assert e["unverified_numbers"] == []
