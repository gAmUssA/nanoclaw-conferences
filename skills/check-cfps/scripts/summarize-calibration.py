#!/usr/bin/env python3
"""Summarize recorded CFP relevance calibration without network or state writes.

Input: stdin JSON object with labels and scores arrays, joined by unique slug.
Labels carry label (yes/no/other/null) and optional boolean geo_excluded.
Scores carry verdict (open/dismiss/model/preserve) and optional metadata_warning.
Only non-geographic yes/no labels are evaluated; every evaluated slug needs a
score. Scores for excluded labels or other candidates do not affect the result.
Extra object fields are ignored. No classifier thresholds are applied here.

Output: one schema_version=1 JSON summary with labelled/excluded counts,
automatic decisions/errors, model fallbacks, preserved rows, metadata warnings
and error_slugs. Exit 0: summary; exit 2: invalid input, diagnostic on stderr and
no stdout. This report is a run artifact, never a CFP-state schema extension.
"""

from __future__ import annotations

import json
import sys


def index(rows) -> dict[str, dict]:
    if not isinstance(rows, list):
        raise ValueError("labels and scores must be arrays")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("slug"), str):
            raise ValueError("each record needs a string slug")
        slug = row["slug"]
        if not slug.strip() or slug in result:
            raise ValueError("slugs must be nonempty and unique within each array")
        result[slug] = row
    return result


def summarize(data) -> dict:
    if not isinstance(data, dict):
        raise ValueError("input must be an object")
    labels, scores = index(data.get("labels")), index(data.get("scores"))
    eligible = {}
    for slug, row in labels.items():
        if row.get("label") is not None and not isinstance(row["label"], str):
            raise ValueError("label must be a string or null")
        if type(row.get("geo_excluded", False)) is not bool:
            raise ValueError("geo_excluded must be boolean")
        if row.get("label") in ("yes", "no") and not row.get("geo_excluded", False):
            eligible[slug] = row
    report = {
        "schema_version": 1,
        "labelled": len(eligible),
        "excluded": len(labels) - len(eligible),
        "automatic": 0,
        "automatic_errors": 0,
        "model_fallback": 0,
        "preserved": 0,
        "metadata_unavailable": 0,
        "error_slugs": [],
    }
    for slug, label in eligible.items():
        if slug not in scores:
            raise ValueError("every evaluated label needs a recorded score")
        score = scores[slug]
        verdict = score.get("verdict")
        if verdict not in ("open", "dismiss", "model", "preserve"):
            raise ValueError("evaluated scores need a recognized verdict")
        warning = score.get("metadata_warning", "")
        if not isinstance(warning, str):
            raise ValueError("metadata_warning must be a string")
        report["metadata_unavailable"] += bool(warning)
        if verdict == "model":
            report["model_fallback"] += 1
        elif verdict == "preserve":
            report["preserved"] += 1
        else:
            report["automatic"] += 1
            if (verdict == "open") != (label["label"] == "yes"):
                report["automatic_errors"] += 1
                report["error_slugs"].append(slug)
    return report


def main() -> int:
    try:
        result = summarize(json.load(sys.stdin))
    except (ValueError, RecursionError) as exc:
        diagnostic = (
            str(exc) if not isinstance(exc, RecursionError) else "JSON is too deeply nested"
        )
        print(f"summarize-calibration: {diagnostic}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
