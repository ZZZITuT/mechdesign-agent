"""Every shipped example configuration must be valid and behave as its label says."""

import json
from pathlib import Path

import pytest

from mechdesign import mechanics as M

EXAMPLES = sorted((Path(__file__).resolve().parent.parent / "examples").glob("*.json"))


def test_examples_exist():
    assert len(EXAMPLES) >= 3


@pytest.mark.parametrize("path", EXAMPLES, ids=[p.stem for p in EXAMPLES])
def test_example_runs(path):
    cfg = json.loads(path.read_text(encoding="utf-8"))
    out = M.run_problem(cfg)
    assert out["search"]["n_candidates"] > 0
    if "no_feasible" in path.stem:
        assert out["search"]["n_feasible"] == 0
    else:
        assert out["search"]["n_feasible"] > 0


def test_example_config_matches_builtin():
    p = Path(__file__).resolve().parent.parent / "examples" / "example_config.json"
    assert json.loads(p.read_text(encoding="utf-8")) == M.EXAMPLE_CONFIG


def test_steel_textbook_values():
    p = Path(__file__).resolve().parent.parent / "examples" / "steel_textbook.json"
    cur = M.run_problem(json.loads(p.read_text(encoding="utf-8")))["current"]
    assert cur["deflection_mm"] == pytest.approx(0.2, rel=1e-12)
    assert cur["stress_MPa"] == pytest.approx(60.0, rel=1e-12)
