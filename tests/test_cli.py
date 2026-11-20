import json

import pytest

from mechdesign import __version__
from mechdesign import mechanics as M
from mechdesign.cli import main


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setenv("MECHDESIGN_DISABLE_LLM", "1")


@pytest.fixture
def example_file(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(M.EXAMPLE_CONFIG), encoding="utf-8")
    return p


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_prints_help(capsys):
    assert main([]) == 0
    assert "usage: mechdesign" in capsys.readouterr().out


def test_example_roundtrip(tmp_path, capsys):
    out = tmp_path / "ex.json"
    assert main(["example", "-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == M.EXAMPLE_CONFIG


def test_run_text(example_file, capsys):
    assert main(["run", str(example_file), "--top", "3"]) == 0
    out = capsys.readouterr().out
    assert "NOT FEASIBLE" in out
    assert "b5_h11" in out  # rank 1 of the example
    assert "not guaranteed global optima" in out


def test_run_json(example_file, capsys):
    assert main(["run", str(example_file), "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["search"]["n_feasible"] == 256
    assert "candidates" not in d


def test_run_invalid_config_exit_code(tmp_path, capsys):
    cfg = dict(M.EXAMPLE_CONFIG, length_mm=-1)
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    assert main(["run", str(p)]) == 2
    assert "length_mm" in capsys.readouterr().err


def test_run_missing_file():
    with pytest.raises(SystemExit) as e:
        main(["run", "does-not-exist.json"])
    assert "not found" in str(e.value.code)


def test_run_not_json(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{ not json", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        main(["run", str(p)])
    assert "not valid JSON" in str(e.value.code)


@pytest.mark.parametrize(
    "name,needle", [("r.md", "# MechDesign Agent - Calculation Report"), ("r.html", "<!doctype html>")]
)
def test_report(example_file, tmp_path, name, needle):
    out = tmp_path / name
    assert main(["report", str(example_file), "-o", str(out), "--select", "b6_h10"]) == 0
    text = out.read_text(encoding="utf-8")
    assert needle in text
    assert "Selected candidate" in text
    assert "comparison checks passed" in text  # validation suite summary


def test_report_unknown_candidate(example_file, capsys):
    assert main(["report", str(example_file), "--select", "b999_h1"]) == 2
    assert "not in the search grid" in capsys.readouterr().err


def test_validate_writes_outputs(tmp_path, capsys):
    assert main(["validate", "--out", str(tmp_path)]) == 0
    res = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert res["summary"]["n_pass"] == res["summary"]["n_checks"]
    assert (tmp_path / "results.md").read_text(encoding="utf-8").startswith("# Validation results")
