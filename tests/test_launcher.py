"""Tests for the one-step launcher ``start.py`` (repository checkouts only)."""

import importlib.util
import sys
from pathlib import Path

import pytest

LAUNCHER = Path(__file__).resolve().parents[1] / "start.py"
pytestmark = pytest.mark.skipif(not LAUNCHER.exists(), reason="start.py is not part of the source distribution")


@pytest.fixture
def start():
    spec = importlib.util.spec_from_file_location("mechdesign_start", LAUNCHER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _windows(start, monkeypatch, root, long_paths=False):
    monkeypatch.setattr(start, "WINDOWS", True)
    monkeypatch.setattr(start, "ROOT", Path(root))
    monkeypatch.setattr(start, "windows_long_paths_enabled", lambda: long_paths)


def test_short_windows_path_installs_all_extras(start, monkeypatch):
    _windows(start, monkeypatch, "C:/code/mechdesign-agent")
    assert start.choose_extras() == "llm,validation"


def test_deep_windows_path_skips_llm_extra_and_says_why(start, monkeypatch, capsys):
    _windows(start, monkeypatch, "C:/" + "x" * 120)
    assert start.choose_extras() == "validation"
    out = capsys.readouterr().out
    assert "rule-based parser" in out and "start it again" in out
    assert start.choose_extras(explain=False) == "validation"
    assert capsys.readouterr().out == ""


def test_deep_windows_path_is_fine_with_long_paths_enabled(start, monkeypatch):
    _windows(start, monkeypatch, "C:/" + "x" * 120, long_paths=True)
    assert start.choose_extras() == "llm,validation"


def test_path_length_is_irrelevant_off_windows(start, monkeypatch):
    monkeypatch.setattr(start, "WINDOWS", False)
    monkeypatch.setattr(start, "ROOT", Path("/" + "x" * 200))
    assert start.choose_extras() == "llm,validation"


def test_install_runs_pip_only_when_needed(start, monkeypatch, tmp_path):
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    monkeypatch.setattr(start, "ROOT", tmp_path / "a")
    monkeypatch.setattr(start, "STAMP", tmp_path / "stamp")
    extras = ["validation"]
    monkeypatch.setattr(start, "choose_extras", lambda explain=True: extras[0])
    calls = []
    monkeypatch.setattr(start.subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    start.install()
    start.install()
    assert len(calls) == 1 and calls[0][-1] == ".[validation]"
    extras[0] = "llm,validation"  # different extras -> install again
    start.install()
    assert len(calls) == 2
    monkeypatch.setattr(start, "ROOT", tmp_path / "b")  # folder moved -> install again
    start.install()
    assert len(calls) == 3


def test_broken_venv_is_reported_not_used(start, monkeypatch, tmp_path, capsys):
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    monkeypatch.setattr(start, "VENV", venv_dir)
    monkeypatch.setattr(start, "VENV_PYTHON", venv_dir / "no-python-here")
    monkeypatch.setattr(sys, "argv", ["start.py", "--no-browser"])
    assert start.main() == 1
    assert "--reinstall" in capsys.readouterr().out
