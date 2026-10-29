"""Calibration reports join labels, exclude geography and expose real mistakes."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/check-cfps/scripts/summarize-calibration.py"


def run(data):
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=json.dumps(data), text=True, capture_output=True
    )


def test_report_joins_slugs_and_counts_errors_without_scoring_again():
    result = run(
        {
            "labels": [
                {"slug": "keep", "label": "yes"},
                {"slug": "reject", "label": "no"},
                {"slug": "mistake", "label": "yes"},
                {"slug": "uncertain", "label": "no"},
                {"slug": "acted", "label": "yes"},
                {"slug": "geo", "label": "yes", "geo_excluded": True},
                {"slug": "unknown", "label": "unknown_to_baruch"},
                {"slug": "unlabelled", "label": None},
            ],
            "scores": [
                {"slug": "unknown", "verdict": "open"},
                {"slug": "geo", "verdict": "dismiss"},
                {"slug": "acted", "verdict": "preserve"},
                {"slug": "uncertain", "verdict": "model", "metadata_warning": "no website"},
                {"slug": "mistake", "verdict": "dismiss"},
                {"slug": "reject", "verdict": "dismiss"},
                {"slug": "keep", "verdict": "open"},
            ],
        }
    )
    assert result.returncode == 0 and not result.stderr
    assert json.loads(result.stdout) == {
        "schema_version": 1,
        "labelled": 5,
        "excluded": 3,
        "automatic": 3,
        "automatic_errors": 1,
        "model_fallback": 1,
        "preserved": 1,
        "metadata_unavailable": 1,
        "error_slugs": ["mistake"],
    }


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"labels": [], "scores": None},
        {"labels": [{"slug": "a", "label": "yes"}], "scores": []},
        {"labels": [{"slug": ""}], "scores": []},
        {"labels": [{"slug": "a"}, {"slug": "a"}], "scores": []},
        {"labels": [{"slug": "a", "geo_excluded": "false"}], "scores": []},
        {"labels": [{"slug": "a", "label": True}], "scores": []},
        {
            "labels": [{"slug": "a", "label": "yes"}],
            "scores": [{"slug": "a", "verdict": "automatic"}],
        },
        {
            "labels": [{"slug": "a", "label": "yes"}],
            "scores": [{"slug": "a", "verdict": "model", "metadata_warning": None}],
        },
        {"labels": [], "scores": [{"slug": "a"}, {"slug": "a"}]},
        {"labels": [None], "scores": []},
    ],
)
def test_invalid_input_is_an_error_without_a_partial_summary(data):
    result = run(data)
    assert result.returncode == 2
    assert not result.stdout
    assert "summarize-calibration:" in result.stderr


@pytest.mark.parametrize("raw", ["{", "[" * 2000 + "]" * 2000])
def test_malformed_and_deep_json_are_reported(raw):
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input=raw, text=True, capture_output=True
    )
    assert result.returncode == 2 and not result.stdout
    assert "Traceback" not in result.stderr


def test_empty_evaluation_is_explicit():
    result = run({"labels": [], "scores": []})
    assert result.returncode == 0
    assert json.loads(result.stdout)["labelled"] == 0
