#!/usr/bin/env python3
"""Mark unambiguous, dated CFP records from submission confirmation mail.

Read inbox confirmations through OneCLI and merge submission fields under the
tracker lock. Gmail access is read-only: confirmations remain in the inbox.
Unknown, undated or ambiguous editions stay unmatched for discovery or owner
review; never invent a conference date or choose the newest edition.

No arguments. Exit 0 prints {"marked": [slugs], "archived": 0, "unmatched": [senders]}.
Exit 1 reports Gmail or state failures on stderr.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
STATE = Path("/workspace/group/cfp-state.json")
INSTALLED_COMMIT = Path("/home/node/.claude/skills/tessl__check-cfps/scripts/commit-state.py")
SOURCE_COMMIT = Path(__file__).resolve().parents[2] / "check-cfps" / "scripts" / "commit-state.py"
QUERIES = (
    'from:events.sessionize.com "successfully submitted"',
    'from:socallinuxexpo.org subject:"session proposal has been received"',
    'from:oxfordabstracts.com subject:"thank you for submitting your proposal"',
)
SESSIONIZE = re.compile(r"([a-z0-9-]+)@events\.sessionize\.com", re.IGNORECASE)
RECEIVED_PREFIX = "your session proposal has been received:"


def gmail(method: str, path: str, *, params: dict | None = None, body: dict | None = None) -> dict:
    if method != "GET" or body is not None:
        raise ValueError("Submission confirmation reads cannot mutate Gmail")
    query = f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""
    request = urllib.request.Request(
        f"{GMAIL}{path}{query}",
        data=None if body is None else json.dumps(body).encode(),
        headers={"content-type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def confirmations(api: Callable[..., dict]) -> list[dict]:
    found = {}
    for query in QUERIES:
        params = {"q": f"{query} in:inbox newer_than:30d", "maxResults": 100}
        seen_tokens = set()
        while True:
            listed = api("GET", "/messages", params=params)
            for row in listed.get("messages", []):
                if row["id"] in found:
                    continue
                raw = api(
                    "GET",
                    f"/messages/{row['id']}",
                    params={"format": "metadata", "metadataHeaders": ["From", "Subject"]},
                )
                headers = {h["name"].lower(): h["value"] for h in raw["payload"]["headers"]}
                received = datetime.fromtimestamp(int(raw["internalDate"]) / 1000, UTC)
                found[row["id"]] = {
                    "id": row["id"],
                    "from": headers.get("from", ""),
                    "subject": headers.get("subject", ""),
                    "received_at": received.isoformat(),
                }
            token = listed.get("nextPageToken")
            if not token:
                break
            if token in seen_tokens:
                raise ValueError("Gmail repeated a confirmation page token")
            seen_tokens.add(token)
            params = {**params, "pageToken": token}
    return list(found.values())


def _sessionize_slug(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname not in {"sessionize.com", "www.sessionize.com"}:
        return None
    return parsed.path.strip("/").split("/")[0].lower()


def _unique(
    records: dict, matches: Callable[[str, dict], bool], year: str | None = None
) -> str | None:
    hits = [
        slug
        for slug, record in records.items()
        if matches(slug, record)
        and (year is None or str(record.get("conf_date") or "").startswith(year + "-"))
    ]
    return hits[0] if len(hits) == 1 else None


def resolve(mail: dict, records: dict) -> tuple[str | None, str | None, dict | None]:
    """The (slug, talk title, record to create) a confirmation belongs to."""
    sender, subject = mail["from"], mail["subject"]
    sessionize = SESSIONIZE.search(sender)
    if sessionize:
        slug = sessionize.group(1).lower()
        known = _unique(
            records,
            lambda key, record: (
                key == slug or _sessionize_slug(str(record.get("cfp_url") or "")) == slug
            ),
        )
        return known, subject, None
    if "socallinuxexpo.org" in sender:
        title = subject[len(RECEIVED_PREFIX) :].strip() if ":" in subject else None
        known = _unique(
            records, lambda _, record: "socallinuxexpo.org" in str(record.get("cfp_url") or "")
        )
        return known, title, None
    if "oxfordabstracts.com" in sender and "ocx" in subject.lower():
        edition = re.search(r"\bocx[ -]?(?:20)?([0-9]{2})\b", subject, re.IGNORECASE)
        known = _unique(
            records,
            lambda key, record: "ocx" in key.lower() or "ocx" in str(record.get("name")).lower(),
            "20" + edition.group(1) if edition else None,
        )
        return known, None, None
    return None, None, None


def plan(mails: list[dict], records: dict, today: str) -> tuple[dict, list[dict], list[str]]:
    """Tracker updates, matched mail and senders needing owner review."""
    updates: dict = {}
    archive: list[dict] = []
    unmatched: list[str] = []
    for mail in mails:
        slug, title, created = resolve(mail, records)
        if slug is None or (
            not records[slug].get("conf_date") and records[slug].get("status") != "sent"
        ):
            unmatched.append(mail["from"])
            continue
        archive.append(mail)
        record = updates.get(slug) or created or records[slug]
        talks = set(record.get("submitted_talks", []))
        if record.get("status") == "sent" and (not title or title in talks):
            continue
        if title:
            talks.add(title)
        updates[slug] = {
            **record,
            "status": "sent",
            "user_actioned": True,
            "updated": today,
            "submitted_talks": sorted(talks),
            "_submission_evidence": [
                *record.get("_submission_evidence", []),
                {
                    "id": mail["id"],
                    "received_at": mail["received_at"],
                    "talk": title,
                },
            ],
        }
    return updates, archive, sorted(set(unmatched))


def commit(updates: dict) -> list[str]:
    script = INSTALLED_COMMIT if INSTALLED_COMMIT.exists() else SOURCE_COMMIT
    done = subprocess.run(
        [sys.executable, str(script), "--state", str(STATE), "--submission-confirmed"],
        input=json.dumps(updates),
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"commit-state failed: {done.stderr.strip()}")
    return json.loads(done.stdout)["written_slugs"]


def run(api: Callable[..., dict] = gmail, today: str | None = None) -> dict:
    day = today or datetime.now(UTC).date().isoformat()
    records = {
        slug: record
        for slug, record in json.loads(STATE.read_text()).items()
        if not slug.startswith("_") and isinstance(record, dict)
    }
    updates, _matched, unmatched = plan(confirmations(api), records, day)
    marked = commit(updates) if updates else []
    return {"marked": sorted(marked), "archived": 0, "unmatched": unmatched}


def main() -> int:
    try:
        print(json.dumps(run()))
    except (OSError, RuntimeError, ValueError, KeyError, urllib.error.URLError) as error:
        print(f"mark-submitted: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
