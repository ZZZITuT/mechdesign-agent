import copy

import pytest

from mechdesign import mechanics as M
from mechdesign import units as U


def design(**kw):
    base = dict(L=0.08, b=0.02, h=0.006, E=3.5e9, rho=1240.0, F=5.0)
    base.update(kw)
    return M.BeamDesign(**base)


# --------------------------------------------------------------- units


def test_unit_conversions_roundtrip():
    assert U.mm_to_m(80) == pytest.approx(0.08)
    assert U.m_to_mm(0.0006772) == pytest.approx(0.6772)
    assert U.gpa_to_pa(3.5) == pytest.approx(3.5e9)
    assert U.pa_to_gpa(200e9) == pytest.approx(200)
    assert U.mpa_to_pa(20) == pytest.approx(20e6)
    assert U.pa_to_mpa(3.333e6) == pytest.approx(3.333)
    assert U.kg_to_g(0.011904) == pytest.approx(11.904)
    assert U.g_per_cm3_to_kg_per_m3(1.24) == pytest.approx(1240)
    assert U.m4_to_mm4(3.6e-10) == pytest.approx(360)
    assert U.kg_mass_to_newton(1.0) == pytest.approx(9.80665)


# --------------------------------------------------------------- formulas (hand-calculated reference)


def test_reference_case_hand_calculation():
    # L=80 mm, b=20 mm, h=6 mm, E=3.5 GPa, rho=1240 kg/m^3, F=5 N
    # I = 20*6^3/12 = 360 mm^4 = 3.6e-10 m^4
    # m = 1240 * 0.02*0.006*0.08 = 0.011904 kg
    # delta = 5*0.08^3/(3*3.5e9*3.6e-10) = 0.00256/3.78 = 6.7724868e-4 m
    # sigma = 6*5*0.08/(0.02*0.006^2) = 2.4/7.2e-7 = 3.3333e6 Pa
    r = M.compute(design())
    assert pytest.approx(3.6e-10, rel=1e-12) == r.I
    assert r.mass == pytest.approx(0.011904, rel=1e-12)
    assert r.delta == pytest.approx(6.772486772e-4, rel=1e-9)
    assert r.sigma == pytest.approx(3.333333333e6, rel=1e-9)


def test_steel_reference_case():
    # L=100 mm, b=10 mm, h=10 mm, E=200 GPa, F=100 N
    # I = 833.333 mm^4; delta = 100*1e6/(3*200000*833.333) mm = 0.2 mm; sigma = 6*100*100/(10*100) = 60 MPa
    d = M.BeamDesign(L=0.1, b=0.01, h=0.01, E=200e9, rho=7850, F=100)
    r = M.compute(d)
    assert U.m_to_mm(r.delta) == pytest.approx(0.2, rel=1e-12)
    assert U.pa_to_mpa(r.sigma) == pytest.approx(60.0, rel=1e-12)
    assert U.kg_to_g(r.mass) == pytest.approx(78.5, rel=1e-12)


def test_deflection_curve_matches_tip_and_root():
    d = design()
    r = M.compute(d)
    v = M.deflection_curve(d.F, d.L, d.E, r.I, [0.0, d.L])
    assert v[0] == 0.0
    assert v[1] == pytest.approx(r.delta, rel=1e-12)


# --------------------------------------------------------------- scaling relationships


@pytest.mark.parametrize("factor", [0.5, 2.0, 3.0])
def test_deflection_scales_with_L_cubed(factor):
    d0 = M.compute(design()).delta
    d1 = M.compute(design(L=0.08 * factor)).delta
    assert d1 / d0 == pytest.approx(factor**3, rel=1e-12)


@pytest.mark.parametrize("factor", [0.5, 2.0, 1.7])
def test_deflection_scales_with_inverse_h_cubed(factor):
    d0 = M.compute(design()).delta
    d1 = M.compute(design(h=0.006 * factor)).delta
    assert d1 / d0 == pytest.approx(factor**-3, rel=1e-12)


def test_other_scalings():
    base = M.compute(design())
    assert M.compute(design(b=0.04)).delta / base.delta == pytest.approx(0.5)
    assert M.compute(design(E=7e9)).delta / base.delta == pytest.approx(0.5)
    assert M.compute(design(F=10)).delta / base.delta == pytest.approx(2.0)
    assert M.compute(design(h=0.012)).sigma / base.sigma == pytest.approx(0.25)
    assert M.compute(design(L=0.16)).sigma / base.sigma == pytest.approx(2.0)
    assert M.compute(design(b=0.04)).mass / base.mass == pytest.approx(2.0)
    assert M.compute(design(rho=2480)).mass / base.mass == pytest.approx(2.0)
    # mass independent of load and modulus
    assert M.compute(design(F=50, E=1e9)).mass == pytest.approx(base.mass)


# --------------------------------------------------------------- zero load & invalid inputs


def test_zero_load_gives_zero_response_and_warning():
    ev = M.evaluate(design(F=0.0), M.Requirements(delta_allow=0.0005, sigma_allow=20e6))
    assert ev.result.delta == 0.0
    assert ev.result.sigma == 0.0
    assert ev.result.mass > 0
    assert ev.feasible
    assert any("Load is zero" in w for w in ev.warnings)


@pytest.mark.parametrize(
    "field,value",
    [
        ("L", 0.0),
        ("L", -1.0),
        ("b", 0.0),
        ("h", -0.001),
        ("E", 0.0),
        ("rho", -5.0),
        ("F", -1.0),
        ("L", float("nan")),
        ("E", float("inf")),
    ],
)
def test_invalid_design_rejected(field, value):
    with pytest.raises(M.InputError) as ei:
        M.compute(design(**{field: value}))
    assert ei.value.errors[0].field == field


def test_invalid_config_lists_every_problem():
    cfg = copy.deepcopy(M.EXAMPLE_CONFIG)
    cfg["length_mm"] = -10
    cfg["material"]["E_GPa"] = None
    cfg["allowable_deflection_mm"] = 0
    cfg["search"]["h_step_mm"] = 0
    cfg["search"]["b_max_mm"] = 1  # < b_min
    cfg["load_N"] = "five"
    with pytest.raises(M.InputError) as ei:
        M.parse_config(cfg)
    fields = {e.field for e in ei.value.errors}
    assert {
        "length_mm",
        "material.E_GPa",
        "allowable_deflection_mm",
        "search.h_step_mm",
        "search.b_max_mm",
        "load_N",
    } <= fields


def test_missing_key_reported():
    cfg = copy.deepcopy(M.EXAMPLE_CONFIG)
    del cfg["allowable_deflection_mm"]
    with pytest.raises(M.InputError) as ei:
        M.parse_config(cfg)
    assert ei.value.errors[0].field == "allowable_deflection_mm"


def test_unit_plausibility_checks():
    cfg = copy.deepcopy(M.EXAMPLE_CONFIG)
    cfg["material"]["E_GPa"] = 3.5e9  # entered in Pa by mistake
    cfg["material"]["density_kg_m3"] = 1.24  # entered in g/cm^3 by mistake
    with pytest.raises(M.InputError) as ei:
        M.parse_config(cfg)
    assert {e.field for e in ei.value.errors} == {"material.E_GPa", "material.density_kg_m3"}


def test_grid_too_large_rejected():
    cfg = copy.deepcopy(M.EXAMPLE_CONFIG)
    cfg["search"]["b_step_mm"] = 0.001
    with pytest.raises(M.InputError):
        M.parse_config(cfg)


def test_optional_stress_limit_can_be_disabled():
    cfg = copy.deepcopy(M.EXAMPLE_CONFIG)
    cfg["allowable_stress_MPa"] = None
    p = M.parse_config(cfg)
    assert p.requirements.sigma_allow is None
    ev = M.evaluate(p.design, p.requirements)
    assert [c["name"] for c in ev.checks] == ["tip_deflection"]


def test_parse_config_converts_to_si():
    p = M.parse_config(M.EXAMPLE_CONFIG)
    assert pytest.approx(0.08) == p.design.L
    assert pytest.approx(3.5e9) == p.design.E
    assert p.requirements.delta_allow == pytest.approx(0.0005)
    assert p.requirements.sigma_allow == pytest.approx(20e6)
    assert p.space.h_step == pytest.approx(0.0005)


# --------------------------------------------------------------- grid & constraint filtering


def test_grid_values_inclusive_and_float_safe():
    v = M.grid_values(0.1, 0.3, 0.1)
    assert list(v) == [0.1, 0.2, 0.3]
    assert len(M.grid_values(3.0, 12.0, 0.5)) == 19
    assert len(M.grid_values(5.0, 5.0, 1.0)) == 1


def test_constraint_filtering_matches_bruteforce():
    p = M.parse_config(M.EXAMPLE_CONFIG)
    s = M.search(p.design, p.requirements, p.space)
    for i in range(len(s["b"])):
        d = M.BeamDesign(p.design.L, s["b"][i], s["h"][i], p.design.E, p.design.rho, p.design.F)
        ev = M.evaluate(d, p.requirements)
        assert ev.feasible == bool(s["feasible"][i])
        assert ev.result.delta == pytest.approx(s["delta"][i], rel=1e-12)


def test_ranking_by_mass_and_all_feasible_satisfy_limits():
    out = M.run_problem(M.EXAMPLE_CONFIG)
    top = out["top"]
    assert top, "example should have feasible designs"
    masses = [c["mass_g"] for c in top]
    assert masses == sorted(masses)
    for c in top:
        assert c["deflection_mm"] <= M.EXAMPLE_CONFIG["allowable_deflection_mm"] + 1e-12
        assert c["stress_MPa"] <= M.EXAMPLE_CONFIG["allowable_stress_MPa"] + 1e-12
        assert c["reason"].startswith("Feasible")
    # every lighter candidate than the best feasible one must be infeasible
    best = top[0]["mass_g"]
    for c in out["candidates"]:
        if c["mass_g"] < best - 1e-12:
            assert not c["feasible"] and c["reason"].startswith("Rejected")


def test_stress_constraint_filters():
    cfg = copy.deepcopy(M.EXAMPLE_CONFIG)
    cfg["allowable_stress_MPa"] = 3.0
    out = M.run_problem(cfg)
    assert all(c["stress_MPa"] <= 3.0 for c in out["candidates"] if c["feasible"])
    assert any((not c["feasible"]) and c["deflection_mm"] <= 0.5 for c in out["candidates"])  # rejected by stress only


def test_aspect_ratio_constraint_filters():
    cfg = copy.deepcopy(M.EXAMPLE_CONFIG)
    cfg["max_aspect_ratio"] = 1.0
    out = M.run_problem(cfg)
    assert out["search"]["n_feasible"] > 0
    assert all(c["h_mm"] / c["b_mm"] <= 1.0 + 1e-12 for c in out["candidates"] if c["feasible"])


def test_no_feasible_design_reported_without_relaxing():
    cfg = copy.deepcopy(M.EXAMPLE_CONFIG)
    cfg["allowable_deflection_mm"] = 0.001
    out = M.run_problem(cfg)
    assert out["search"]["n_feasible"] == 0
    assert out["top"] == []
    assert "No design" in out["statement"] and "not been relaxed" in out["statement"]
    assert out["config"]["allowable_deflection_mm"] == 0.001
    assert len(out["nearest_infeasible"]) == 5
    assert all(c["max_utilisation"] > 1 for c in out["nearest_infeasible"])


def test_current_design_status_example():
    out = M.run_problem(M.EXAMPLE_CONFIG)
    cur = out["current"]
    assert cur["deflection_mm"] == pytest.approx(0.677248677, rel=1e-8)
    assert not cur["feasible"]
    assert out["statement"].count("not guaranteed global optima") == 1


def test_validity_warnings():
    ev = M.evaluate(design(L=0.03, h=0.01), M.Requirements(1.0, None))
    assert any("L/h" in w for w in ev.warnings)
    ev = M.evaluate(design(b=0.002, h=0.012), M.Requirements(1.0, None))
    assert any("h/b" in w for w in ev.warnings)
    ev = M.evaluate(design(L=0.3, h=0.002, F=20), M.Requirements(1.0, None))
    assert any("small-deflection" in w for w in ev.warnings)
