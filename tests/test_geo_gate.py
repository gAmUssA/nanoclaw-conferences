"""Tests for skills/check-cfps/scripts/geo-gate.py (jbaruch/nanoclaw-conferences#91).

Locks the operator's travel policy as data: a recognized country outside
`allowed_countries` is excluded, an alias resolves to its allowed name, a
per-slug exception wins, and anything the gate cannot read as a country
goes on to the topic filter instead of being geo-dismissed.
"""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_REL = "skills/check-cfps/scripts/geo-gate.py"

POLICY = {
    "allowed_countries": [
        "United States",
        "Czechia",
        "Netherlands",
        "Sweden",
        "Switzerland",
        "Hong Kong",
    ],
    "aliases": {"USA": "United States", "The Netherlands": "Netherlands", "UK": "United Kingdom"},
    "exceptions": {"kept-conf": "Baruch, 2026-10-16"},
}


@pytest.fixture
def gate():
    spec = importlib.util.spec_from_file_location("geo_gate_under_test", REPO_ROOT / SCRIPT_REL)
    if spec is None or spec.loader is None:
        raise ImportError(
            f"cannot load {SCRIPT_REL}: confirm the script still lives there "
            "(update SCRIPT_REL if it moved) and rerun pytest"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def policy_path(tmp_path: Path) -> Path:
    path = tmp_path / "cfp-geo-policy.json"
    path.write_text(json.dumps(POLICY), encoding="utf-8")
    return path


def _run(gate, policy_path, records, monkeypatch, capsys) -> tuple[int, str, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(records)))
    code = gate.main(["--policy", str(policy_path)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _verdicts(gate, policy_path, records, monkeypatch, capsys) -> list[dict]:
    code, out, err = _run(gate, policy_path, records, monkeypatch, capsys)
    assert code == 0, err
    return json.loads(out)


@pytest.mark.parametrize(
    ("record", "country"),
    [
        ({"country": "United States"}, "United States"),
        ({"country": "The Netherlands"}, "Netherlands"),
        ({"city": "Prague (Czechia)"}, "Czechia"),
        ({"city": "Salt Lake City, UT (USA)"}, "United States"),
        ({"city": "Stockholm, Sweden"}, "Sweden"),
        ({"location": "Zürich, Switzerland", "city": "Zurich"}, "Switzerland"),
        ({"city": "Hong Kong"}, "Hong Kong"),
    ],
)
def test_an_allowed_country_passes(gate, policy_path, monkeypatch, capsys, record, country):
    out = _verdicts(gate, policy_path, [{"slug": "c", **record}], monkeypatch, capsys)
    assert out == [
        {"slug": "c", "verdict": "allowed", "country": country, "reason": f"Geo: {country}"}
    ]


@pytest.mark.parametrize(
    ("record", "country"),
    [
        ({"city": "Lima, Peru"}, "Peru"),
        ({"country": "India", "city": "Bengaluru"}, "India"),
        ({"city": "Istanbul (Turkey)"}, "Turkey"),
        ({"location": "Kuala Lumpur, Malaysia"}, "Malaysia"),
        ({"country": "UK"}, "United Kingdom"),
    ],
)
def test_a_recognized_country_outside_the_policy_is_excluded(
    gate, policy_path, monkeypatch, capsys, record, country
):
    out = _verdicts(gate, policy_path, [{"slug": "c", **record}], monkeypatch, capsys)
    assert out[0]["verdict"] == "excluded"
    assert out[0]["country"] == country
    assert out[0]["reason"] == (
        f"Auto-dismissed: Geo: {country} is outside the travel policy (cfp-geo-policy.json)"
    )


@pytest.mark.parametrize(
    "record",
    [
        {"city": "Lima"},
        {"city": "?"},
        {"city": "San Francisco, CA"},
        {},
        {"country": "Atlantis", "city": "Poseidonia"},
    ],
)
def test_a_country_the_gate_cannot_read_goes_to_the_topic_filter(
    gate, policy_path, monkeypatch, capsys, record
):
    out = _verdicts(gate, policy_path, [{"slug": "c", **record}], monkeypatch, capsys)
    assert out[0]["verdict"] == "unresolved"
    assert out[0]["country"] is None


def test_the_country_field_wins_over_the_city(gate, policy_path, monkeypatch, capsys):
    record = {"slug": "c", "country": "Sweden", "city": "Lima, Peru"}
    out = _verdicts(gate, policy_path, [record], monkeypatch, capsys)
    assert out[0]["country"] == "Sweden"


def test_an_exception_keeps_a_conference_the_policy_would_exclude(
    gate, policy_path, monkeypatch, capsys
):
    record = {"slug": "kept-conf", "city": "Lima, Peru"}
    out = _verdicts(gate, policy_path, [record], monkeypatch, capsys)
    assert out[0]["verdict"] == "allowed"


def test_an_online_event_is_left_to_the_topic_filter(gate, policy_path, monkeypatch, capsys):
    record = {"slug": "c", "is_online": True, "country": "India"}
    out = _verdicts(gate, policy_path, [record], monkeypatch, capsys)
    assert out[0]["verdict"] == "unresolved"


def test_output_stays_parallel_to_input(gate, policy_path, monkeypatch, capsys):
    records = [{"slug": "a", "city": "Lima, Peru"}, {"slug": "b", "country": "USA"}, {"slug": "c"}]
    out = _verdicts(gate, policy_path, records, monkeypatch, capsys)
    assert [(o["slug"], o["verdict"]) for o in out] == [
        ("a", "excluded"),
        ("b", "allowed"),
        ("c", "unresolved"),
    ]


def test_a_missing_policy_exits_1_and_gates_nothing(gate, tmp_path, monkeypatch, capsys):
    code, out, err = _run(gate, tmp_path / "absent.json", [{"slug": "c"}], monkeypatch, capsys)
    assert (code, out) == (1, "")
    assert "No candidate was geo-gated" in err


@pytest.mark.parametrize(
    "policy",
    [
        [],
        {"allowed_countries": "US"},
        {"allowed_countries": ["US"], "aliases": {"x": 1}},
        {"allowed_countries": [], "exceptions": []},
    ],
)
def test_a_malformed_policy_exits_1(gate, tmp_path, monkeypatch, capsys, policy):
    path = tmp_path / "cfp-geo-policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    code, out, _ = _run(gate, path, [{"slug": "c"}], monkeypatch, capsys)
    assert (code, out) == (1, "")


@pytest.mark.parametrize("records", [{}, [1], [{"city": "Oslo"}], [{"slug": "c", "city": 7}]])
def test_bad_input_exits_2(gate, policy_path, monkeypatch, capsys, records):
    code, out, _ = _run(gate, policy_path, records, monkeypatch, capsys)
    assert (code, out) == (2, "")


def test_deeply_nested_input_exits_2_not_a_traceback(gate, policy_path, monkeypatch, capsys):
    deep = "[" * 100_000 + "]" * 100_000
    monkeypatch.setattr("sys.stdin", io.StringIO(deep))
    code = gate.main(["--policy", str(policy_path)])
    captured = capsys.readouterr()
    assert (code, captured.out) == (2, "")
    assert "bad candidate input" in captured.err


def test_a_deeply_nested_policy_exits_1_not_a_traceback(gate, tmp_path, monkeypatch, capsys):
    path = tmp_path / "cfp-geo-policy.json"
    path.write_text("[" * 100_000 + "]" * 100_000, encoding="utf-8")
    code, out, err = _run(gate, path, [{"slug": "c"}], monkeypatch, capsys)
    assert (code, out) == (1, "")
    assert "No candidate was geo-gated" in err
