#!/usr/bin/env python3
"""Validate grounded conference contact extraction; never infer natural language.

stdin: schema_version1, source {message_id,kind,text}, event {id,name,evidence},
people [{name,conversation,quote,email}]. kind is text or voice_transcript.
Event evidence and each person's quote must be exact substrings of source text.
Name, conversation and any email must occur verbatim in that person's quote.
Use a preceding owner message as additional source text only with its identity
retained in the calling skill; this operation supplies neither identity nor consent.
stdout: the validated input plus stable source_id, and each person's contact_key
when an explicit email is present. Missing emails remain unresolved.
Exit2: invalid input, empty stdout, bounded diagnostic. No state/network writes.
"""

from __future__ import annotations

import hashlib
import json
import sys
from email.headerregistry import Address


def text(value: object, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(c) == 0 or 0xD800 <= ord(c) <= 0xDFFF for c in value)
    ):
        raise ValueError("Provide complete bounded source text without invalid characters.")
    return value


def mailbox(value: object) -> str:
    value = text(value, 254)
    if (
        not value.isascii()
        or value != value.strip()
        or any(ord(c) < 33 or ord(c) == 127 for c in value)
    ):
        raise ValueError("Confirm one plain recipient email address.")
    address = Address(addr_spec=value)
    if not address.username or not address.domain or address.addr_spec != value:
        raise ValueError("Confirm one complete plain recipient email address.")
    return value


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def prepare(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"schema_version", "source", "event", "people"}:
        raise ValueError("Provide one schema-1 source, event and extracted people array.")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("Update the intake reader for the supported schema version 1.")
    source, event, people = value["source"], value["event"], value["people"]
    if not isinstance(source, dict) or set(source) != {"message_id", "kind", "text"}:
        raise ValueError("Retain the actual source message identity and complete transcript.")
    source_id = text(source["message_id"], 200)
    original = text(source["text"], 32000)
    if source["kind"] not in ("text", "voice_transcript"):
        raise ValueError("Supply owner text or its voice transcript, never inferred audio content.")
    if not isinstance(event, dict) or set(event) != {"id", "name", "evidence"}:
        raise ValueError("Resolve the exact conference occurrence before drafting.")
    event_id, name, evidence = (text(event[k], 500) for k in ("id", "name", "evidence"))
    if evidence not in original or name not in evidence:
        raise ValueError("Quote the owner's actual conference evidence; clarify a missing event.")
    if not isinstance(people, list) or not 1 <= len(people) <= 40:
        raise ValueError("Extract between one and forty explicitly mentioned people.")
    prepared = []
    seen = set()
    for person in people:
        if not isinstance(person, dict) or set(person) != {
            "name",
            "conversation",
            "quote",
            "email",
        }:
            raise ValueError(
                "Retain each person's name, conversation, exact quote and optional email."
            )
        person_name = text(person["name"], 120)
        conversation = text(person["conversation"], 2000)
        quote = text(person["quote"], 4000)
        if quote not in original or person_name not in quote or conversation not in quote:
            raise ValueError(
                "Ground every extracted person and conversation in an exact source quote."
            )
        email = None if person["email"] is None else mailbox(person["email"])
        if email and email not in quote:
            raise ValueError(
                "Clarify the spoken address or resolve it separately from source evidence."
            )
        identity = (person_name.casefold(), email.casefold() if email else None)
        if identity in seen:
            raise ValueError("Resolve duplicate person mentions before preparing the batch.")
        seen.add(identity)
        prepared.append(
            {**person, "contact_key": digest([event_id, email.casefold()]) if email else None}
        )
    return {**value, "people": prepared, "source_id": digest([source_id, original])}


def main() -> int:
    try:
        value = json.loads(sys.stdin.read(128001))
        result = prepare(value)
    except (ValueError, TypeError, KeyError):
        print(
            "conference intake: restore schema-1 input and exact source quotes before drafting.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
