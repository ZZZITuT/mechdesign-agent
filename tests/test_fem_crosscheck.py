"""Cross-checks against independent numerical solvers (not the closed form)."""

import pytest

from mechdesign import fem
from mechdesign import mechanics as M
from mechdesign.crosscheck import TOL_ANASTRUCT, TOL_INHOUSE_FE, TOL_Q8_VS_TIMOSHENKO, cross_check

CASES = [
    # (L, b, h, E, F)  - slender to stubby, polymer and metal
    (0.08, 0.02, 0.006, 3.5e9, 5.0),
    (0.15, 0.01, 0.004, 2.1e9, 2.0),
    (0.10, 0.01, 0.01, 200e9, 100.0),
    (0.03, 0.02, 0.01, 68.9e9, 50.0),
]


def closed(L, b, h, E, F):
    r = M.compute(M.BeamDesign(L, b, h, E, 1000.0, F))
    return r.delta, r.sigma


@pytest.mark.parametrize("L,b,h,E,F", CASES)
def test_inhouse_hermite_fe_matches(L, b, h, E, F):
    d, s = closed(L, b, h, E, F)
    r = fem.beam_fe_euler_bernoulli(L, b, h, E, F)
    assert r.tip_deflection == pytest.approx(d, rel=TOL_INHOUSE_FE)
    assert r.max_stress == pytest.approx(s, rel=TOL_INHOUSE_FE)
    assert r.root_moment == pytest.approx(F * L, rel=TOL_INHOUSE_FE)


@pytest.mark.skipif(not fem.anastruct_available(), reason="anaStruct not installed")
@pytest.mark.parametrize("L,b,h,E,F", CASES)
def test_anastruct_matches(L, b, h, E, F):
    d, s = closed(L, b, h, E, F)
    r = fem.beam_fe_anastruct(L, b, h, E, F)
    assert r.tip_deflection == pytest.approx(d, rel=TOL_ANASTRUCT)
    assert r.max_stress == pytest.approx(s, rel=TOL_ANASTRUCT)


@pytest.mark.parametrize("L,b,h,E,F", CASES)
def test_plane_stress_continuum_vs_timoshenko(L, b, h, E, F):
    r = fem.plane_stress_q8(L, b, h, E, F, nu=0.3)
    dT = fem.timoshenko_tip_deflection(L, b, h, E, F, nu=0.3)
    assert r.tip_deflection == pytest.approx(dT, rel=TOL_Q8_VS_TIMOSHENKO)
    # the continuum model is never stiffer than Euler-Bernoulli by more than the clamp effect
    d, _ = closed(L, b, h, E, F)
    assert r.tip_deflection > 0.99 * d


def test_shear_effect_grows_for_stubby_beams():
    """Model-form check: EB underestimates deflection more as L/h decreases."""
    E, F, b = 3.5e9, 5.0, 0.02
    gaps = []
    for L_over_h in (20, 8, 3):
        h = 0.006
        L = L_over_h * h
        d, _ = closed(L, b, h, E, F)
        q = fem.plane_stress_q8(L, b, h, E, F)
        gaps.append(q.tip_deflection / d - 1)
    assert gaps[0] < gaps[1] < gaps[2]
    assert gaps[2] > 0.05


def test_midspan_stress_from_continuum():
    L, b, h, E, F = 0.08, 0.02, 0.006, 3.5e9, 5.0
    q = fem.plane_stress_q8(L, b, h, E, F)
    x = q.extra["x_sample"]
    assert q.extra["sigma_xx_top_at_x"] == pytest.approx(6 * F * (L - x) / (b * h * h), rel=0.01)


def test_crosscheck_report_structure():
    out = cross_check(M.BeamDesign(0.08, 0.02, 0.006, 3.5e9, 1240, 5.0))
    assert out["closed_form"]["tip_deflection_mm"] == pytest.approx(0.6772486, rel=1e-6)
    assert all(r["pass"] in (True, None) for r in out["rows"])
    assert "not physical reality" in out["disclaimer"]


def test_crosscheck_zero_load():
    out = cross_check(M.BeamDesign(0.08, 0.02, 0.006, 3.5e9, 1240, 0.0))
    assert all(r["pass"] in (True, None) for r in out["rows"])
