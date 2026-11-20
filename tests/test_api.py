import copy

import pytest
from fastapi.testclient import TestClient

from mechdesign import mechanics as M
from mechdesign.server import app


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setenv("MECHDESIGN_DISABLE_LLM", "1")


client = TestClient(app)


def test_status_and_example():
    s = client.get("/api/status").json()
    assert s["llm_enabled"] is False
    ex = client.get("/api/example").json()
    assert "EXAMPLE" in ex["config"]["_label"]
    assert len(ex["materials"]) >= 3


def test_run_example():
    r = client.post("/api/run", json={"config": M.EXAMPLE_CONFIG})
    assert r.status_code == 200
    d = r.json()
    assert d["search"]["n_candidates"] == 26 * 19
    assert d["top"][0]["rank"] == 1
    assert len(d["deflection_shape"]["xi"]) == len(d["deflection_shape"]["v"])


def test_run_invalid_returns_422_with_fields():
    cfg = copy.deepcopy(M.EXAMPLE_CONFIG)
    cfg["width_mm"] = 0
    r = client.post("/api/run", json={"config": cfg})
    assert r.status_code == 422
    assert r.json()["errors"][0]["field"] == "width_mm"


def test_interpret_and_apply_cycle():
    r = client.post(
        "/api/interpret", json={"message": "Compare designs that deflect less than 0.4 mm.", "config": M.EXAMPLE_CONFIG}
    ).json()
    assert r["ready"]
    run = client.post("/api/run", json={"config": r["proposed_config"]}).json()
    assert all(c["deflection_mm"] <= 0.4 for c in run["top"])


def test_explain_and_crosscheck():
    e = client.post("/api/explain", json={"config": M.EXAMPLE_CONFIG}).json()
    assert e["unverified_numbers"] == []
    x = client.post("/api/crosscheck", json={"config": M.EXAMPLE_CONFIG, "b_mm": 6, "h_mm": 10}).json()
    assert x["closed_form"]["tip_deflection_mm"] == pytest.approx(5 * 80**3 / (3 * 3500 * 6 * 1000 / 12), rel=1e-9)
    assert all(row["pass"] in (True, None) for row in x["rows"])


@pytest.mark.parametrize("fmt,needle", [("md", "# MechDesign Agent - Calculation Report"), ("html", "<table>")])
def test_report(fmt, needle):
    r = client.post("/api/report", json={"config": M.EXAMPLE_CONFIG, "selected_id": "b6_h10", "format": fmt})
    assert r.status_code == 200
    t = r.text
    assert needle in t
    for section in ("Inputs", "assumptions", "Current design", "Selected candidate", "Validation", "Limitations"):
        assert section in t
    assert "No physical testing has been performed" in t


def test_frontend_served():
    assert "MechDesign Agent" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_crosscheck_rejects_bad_poisson_and_dimensions():
    r = client.post("/api/crosscheck", json={"config": M.EXAMPLE_CONFIG, "poisson": 0.6})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "poisson"
    r = client.post("/api/crosscheck", json={"config": M.EXAMPLE_CONFIG, "b_mm": -1, "h_mm": 5})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "b"


def test_report_unknown_candidate_is_422():
    r = client.post("/api/report", json={"config": M.EXAMPLE_CONFIG, "selected_id": "b999_h1"})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "selected_id"


def test_report_rejects_unknown_format():
    r = client.post("/api/report", json={"config": M.EXAMPLE_CONFIG, "format": "pdf"})
    assert r.status_code == 422


def test_explain_invalid_config_is_422():
    cfg = copy.deepcopy(M.EXAMPLE_CONFIG)
    cfg["load_N"] = -3
    assert client.post("/api/explain", json={"config": cfg}).status_code == 422


def test_interpret_with_invalid_form_still_answers():
    cfg = copy.deepcopy(M.EXAMPLE_CONFIG)
    cfg["length_mm"] = 0
    r = client.post("/api/interpret", json={"message": "length 90 mm", "config": cfg}).json()
    assert {d["field"]: d["new"] for d in r["diffs"]}["length_mm"] == 90


def test_load_dotenv(tmp_path, monkeypatch):
    from mechdesign.server import load_dotenv

    (tmp_path / ".env").write_text(
        "# comment\nMECHDESIGN_TEST_A='x'\nMECHDESIGN_TEST_B=\nMECHDESIGN_TEST_C=keep\n", encoding="utf-8"
    )
    monkeypatch.delenv("MECHDESIGN_TEST_A", raising=False)
    monkeypatch.delenv("MECHDESIGN_TEST_B", raising=False)
    monkeypatch.setenv("MECHDESIGN_TEST_C", "env-wins")
    load_dotenv(tmp_path / ".env")
    import os

    assert os.environ["MECHDESIGN_TEST_A"] == "x"
    assert "MECHDESIGN_TEST_B" not in os.environ  # empty values are ignored
    assert os.environ["MECHDESIGN_TEST_C"] == "env-wins"
