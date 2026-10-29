#!/usr/bin/env python3
"""Build complete content-bound conference.followup.v1 hold cards, never send.

stdin: {schema_version:1,event_id,event_name,source_message_id,
        items:[{name,to,subject,body}]} with already-humanized approved-for-review
drafts. Each item has a unique canonical mailbox. Event occurrence and actual
source message identity remain stable across retries. See callback-contract.md.
stdout: {schema_version:1,cards:[{text,buttons,batch_id}]}; each card holds at
most three items and fits host text/button limits. All means this card only.
Input is UTF-8 JSON capped by MAX_INPUT_BYTES (8 MiB), covering compact escaped
representations of the declared field/count bounds. Read cap+1 and reject excess
before parsing; parse the complete admitted input, including trailing bytes.
Exit2: invalid input or an item too large, empty stdout and bounded stderr.
No network, state writes, owner identity or approval is supplied by this builder.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from email.errors import HeaderParseError
from email.headerregistry import Address

MAX_INPUT_BYTES = 8 * 1024 * 1024
ACTION = "conference.followup.v1"
LABELS = {"send": "Send", "cancel": "Cancel", "edit": "Edit"}
MAILBOX = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*"
)


def button(label: str, payload: dict) -> dict:
    if payload["decision"] == "edit":
        return {"label": label, "action": "owner.answer.v1", "payload": {"label": label}}
    return {"label": label, "action": ACTION, "payload": payload}


def text(value: object, maximum: int, *, multiline: bool = False) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or value != value.strip()
        or any(
            (ord(c) < 32 and (not multiline or c != "\n"))
            or ord(c) == 127
            or 0xD800 <= ord(c) <= 0xDFFF
            for c in value
        )
    ):
        raise ValueError("Provide bounded complete draft fields without header/control characters.")
    return value


def digest(value: object) -> str:
    """SHA-256 of UTF-8 JSON: sorted object keys, compact separators, literal Unicode.

    card() hashes [event_id,event_name,source_message_id,items] for batch_id.
    A shortened displayed prefix never substitutes for this complete identity.
    """
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def card(event_id: str, event_name: str, source: str, items: list[dict]) -> dict:
    """Render the complete literal review text and exact effect/answer rows.

    The text begins with event and reference lines plus the card-local All
    boundary, followed by each numbered name, To, Subject and complete body.
    Native host acceptance compares this actual output with its consumer.
    """
    batch_id = digest([event_id, event_name, source, items])
    base = {
        "schema_version": 1,
        "batch_id": batch_id,
        "event_id": event_id,
        "event_name": event_name,
        "source_message_id": source,
    }
    lines = [
        f"Conference follow-ups: {event_name}",
        f"Conference starts: {event_id}",
        f"Reference: {batch_id[:12]}",
        "Send all / Cancel all / Edit all apply only to this card.",
    ]
    rows = []
    for index, item in enumerate(items, 1):
        lines.extend(
            [
                "",
                f"{index}. {item['name']}",
                f"To: {item['to']}",
                f"Subject: {item['subject']}",
                "",
                item["body"],
            ]
        )
        rows.append(
            [
                button(
                    f"{LABELS[decision]} {index}",
                    {
                        **base,
                        "kind": "item",
                        "decision": decision,
                        "index": index,
                        "item": item,
                    },
                )
                for decision in ("send", "cancel")
            ]
        )
    rows.append(
        [
            button(LABELS[decision] + " all", {**base, "kind": "batch", "decision": decision})
            for decision in ("send", "cancel")
        ]
    )
    rows.append(
        [button(f"Edit {index}", {"decision": "edit"}) for index in range(1, len(items) + 1)]
        + [button("Edit all", {"decision": "edit"})]
    )
    return {"text": "\n".join(lines), "buttons": rows, "batch_id": batch_id}


def fits(value: dict) -> bool:
    return (
        len(value["text"].encode("utf-16-le")) // 2 <= 2800
        and len(
            json.dumps(value["buttons"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        <= 16384
        and all(
            len(
                json.dumps(button["payload"], ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                )
            )
            <= 4096
            for row in value["buttons"]
            for button in row
        )
    )


def build(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "event_id",
        "event_name",
        "source_message_id",
        "items",
    }:
        raise ValueError("Provide schema-1 event/source identity and complete humanized drafts.")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("Update the card builder for supported schema version 1.")
    event_id, event_name, source = (
        text(value[k], 200) for k in ("event_id", "event_name", "source_message_id")
    )
    if date.fromisoformat(event_id).isoformat() != event_id:
        raise ValueError("Resolve the actual conference start date as canonical YYYY-MM-DD.")
    if not isinstance(value["items"], list) or not 1 <= len(value["items"]) <= 40:
        raise ValueError("Provide one to forty grounded follow-up drafts.")
    items = []
    recipients = set()
    for raw in value["items"]:
        if not isinstance(raw, dict) or set(raw) != {"name", "to", "subject", "body"}:
            raise ValueError("Provide name, recipient, subject and complete plain-text body.")
        name, to, subject = (
            text(raw[k], limit) for k, limit in (("name", 120), ("to", 254), ("subject", 160))
        )
        body = text(raw["body"], 1600, multiline=True)
        if not MAILBOX.fullmatch(to):
            raise ValueError("Resolve one plain recipient mailbox before showing a send choice.")
        try:
            address = Address(addr_spec=to)
        except (IndexError, HeaderParseError, ValueError):
            raise ValueError("Resolve one complete plain recipient mailbox.") from None
        if (
            not address.username
            or not address.domain
            or address.addr_spec != to
            or any(c.isspace() for c in to)
        ):
            raise ValueError("Resolve one plain recipient mailbox before showing a send choice.")
        if to.casefold() in recipients:
            raise ValueError("Merge duplicate recipients for this event before preparing cards.")
        recipients.add(to.casefold())
        items.append({"name": name, "to": to, "subject": subject, "body": body})
    cards = []
    group = []
    for item in items:
        candidate = card(event_id, event_name, source, [*group, item])
        if group and (len(group) == 3 or not fits(candidate)):
            cards.append(card(event_id, event_name, source, group))
            group = []
        group.append(item)
        if not fits(card(event_id, event_name, source, group)):
            raise ValueError(
                "Shorten this complete draft before showing it; never truncate approved text."
            )
    if group:
        cards.append(card(event_id, event_name, source, group))
    return {"schema_version": 1, "cards": cards}


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError("Reduce draft JSON within the documented input byte cap.")
        result = build(json.loads(raw.decode("utf-8")))
    except (ValueError, TypeError, KeyError, HeaderParseError, RecursionError):
        print(
            "follow-up card: validate complete draft fields and host card limits before retrying.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
