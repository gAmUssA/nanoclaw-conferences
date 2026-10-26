#!/usr/bin/env python3
"""Build complete content-bound conference.followup.v1 hold cards, never send.

stdin: {schema_version:1,event_id,event_name,source_message_id,
        items:[{name,to,subject,body}]} with already-humanized approved-for-review
drafts. Each item has a unique canonical mailbox. Event occurrence and actual
source message identity remain stable across retries. See callback-contract.md.
stdout: {schema_version:1,cards:[{text,buttons,batch_id}]}; each card holds at
most three items and fits host text/button limits. All means this card only.
Exit2: invalid input or an item too large, empty stdout and bounded stderr.
No network, state writes, owner identity or approval is supplied by this builder.
"""

from __future__ import annotations

import hashlib
import json
import sys
from email.headerregistry import Address

ACTION = "conference.followup.v1"
LABELS = {"send": "Send", "cancel": "Cancel", "edit": "Edit"}


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
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def card(event_id: str, event_name: str, source: str, items: list[dict]) -> dict:
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
                {
                    "label": f"{LABELS[decision]} {index}",
                    "action": ACTION,
                    "payload": {
                        **base,
                        "kind": "item",
                        "decision": decision,
                        "index": index,
                        "item": item,
                    },
                }
                for decision in LABELS
            ]
        )
    rows.append(
        [
            {
                "label": LABELS[decision] + " all",
                "action": ACTION,
                "payload": {**base, "kind": "batch", "decision": decision},
            }
            for decision in LABELS
        ]
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
        address = Address(addr_spec=to)
        if (
            not to.isascii()
            or not address.username
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
        result = build(json.loads(sys.stdin.read(128001)))
    except (ValueError, TypeError, KeyError):
        print(
            "follow-up card: validate complete draft fields and host card limits before retrying.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
