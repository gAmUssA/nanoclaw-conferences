"""Synthetic contacts only: no mail, calendar, owner decision or account access."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(script):
    path = ROOT / "skills/conference-followups/scripts" / script
    spec = importlib.util.spec_from_file_location(script.replace("-", "_"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def intake():
    return {
        "schema_version": 1,
        "source": {
            "message_id": "owner-intake-12",
            "kind": "text",
            "text": "Synthetic Summit 2024. Alex alex@example.test: discussed JVM tooling.",
        },
        "event": {
            "id": "synthetic-summit-2024",
            "name": "Synthetic Summit 2024",
            "evidence": "Synthetic Summit 2024",
        },
        "people": [
            {
                "name": "Alex",
                "conversation": "discussed JVM tooling",
                "quote": "Alex alex@example.test: discussed JVM tooling.",
                "email": "alex@example.test",
            }
        ],
    }


@pytest.fixture
def drafts():
    return {
        "schema_version": 1,
        "event_id": "synthetic-summit-2024",
        "event_name": "Synthetic Summit 2024",
        "source_message_id": "owner-intake-12",
        "items": [
            {
                "name": "Alex",
                "to": "alex@example.test",
                "subject": "JVM tooling at Synthetic Summit",
                "body": "Hi Alex,\n\nGood meeting you at Synthetic Summit 2024. "
                "I enjoyed our JVM tooling conversation.",
            }
        ],
    }


def test_intake_preserves_exact_owner_text_and_optional_unresolved_contact(intake):
    module = load("prepare-intake.py")
    before = copy.deepcopy(intake)
    parsed = module.prepare(intake)
    assert parsed["source"] == before["source"]
    assert parsed["people"][0]["conversation"] == "discussed JVM tooling"
    assert parsed["people"][0]["contact_key"]
    assert intake == before
    intake["people"][0]["email"] = None
    assert module.prepare(intake)["people"][0]["contact_key"] is None


def test_voice_transcript_is_not_treated_as_raw_audio_or_permission(intake):
    module = load("prepare-intake.py")
    intake["source"]["kind"] = "voice_transcript"
    assert module.prepare(intake)["source"]["kind"] == "voice_transcript"
    intake["source"]["kind"] = "audio"
    with pytest.raises(ValueError):
        module.prepare(intake)


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "Invented person"),
        ("conversation", "agreed to a meeting"),
        ("email", "guessed@example.test"),
        ("quote", "invented quote"),
    ],
)
def test_intake_refuses_ungrounded_contact_claims(intake, field, value):
    intake["people"][0][field] = value
    with pytest.raises(ValueError):
        load("prepare-intake.py").prepare(intake)


def test_intake_requires_exact_event_and_unambiguous_people(intake):
    module = load("prepare-intake.py")
    intake["event"]["evidence"] = "Another Summit"
    with pytest.raises(ValueError):
        module.prepare(intake)
    intake["event"]["evidence"] = "Synthetic Summit 2024"
    intake["people"].append(copy.deepcopy(intake["people"][0]))
    with pytest.raises(ValueError):
        module.prepare(intake)


@pytest.mark.parametrize(
    "address", ["bob.alex@example.test", "alex@example.test.org", "éalex@example.test"]
)
def test_intake_refuses_email_substrings_inside_another_address(intake, address):
    intake["source"]["text"] = intake["source"]["text"].replace("alex@example.test", address)
    intake["people"][0]["quote"] = intake["people"][0]["quote"].replace(
        "alex@example.test", address
    )
    with pytest.raises(ValueError):
        load("prepare-intake.py").prepare(intake)


@pytest.mark.parametrize("field", ["id", "name"])
def test_intake_uses_the_builder_event_limits(intake, field):
    intake["event"][field] = "x" * 201
    with pytest.raises(ValueError):
        load("prepare-intake.py").prepare(intake)


def test_complete_card_carries_exact_visible_effect_and_stable_reference(drafts):
    module = load("build-card.py")
    result = module.build(drafts)
    card = result["cards"][0]
    assert drafts["items"][0]["body"] in card["text"]
    assert "To: alex@example.test" in card["text"]
    assert "Subject: JVM tooling at Synthetic Summit" in card["text"]
    assert "apply only to this card" in card["text"]
    assert [[b["label"] for b in row] for row in card["buttons"]] == [
        ["Send 1", "Cancel 1"],
        ["Send all", "Cancel all"],
        ["Edit 1", "Edit all"],
    ]
    assert card == module.build(copy.deepcopy(drafts))["cards"][0]
    assert card["buttons"][-1][0] == {
        "label": "Edit 1",
        "action": "owner.answer.v1",
        "payload": {"label": "Edit 1"},
    }
    assert card["buttons"][-1][-1] == {
        "label": "Edit all",
        "action": "owner.answer.v1",
        "payload": {"label": "Edit all"},
    }
    original = card["batch_id"]
    drafts["items"][0]["body"] += " Thanks."
    assert module.build(drafts)["cards"][0]["batch_id"] != original
    assert card["buttons"][0][0]["payload"]["item"]["body"] != drafts["items"][0]["body"]


def test_six_people_paginate_without_truncation_or_implied_unseen_approval(drafts):
    module = load("build-card.py")
    drafts["items"] = [
        {**drafts["items"][0], "name": f"Synthetic {n}", "to": f"person{n}@example.test"}
        for n in range(6)
    ]
    cards = module.build(drafts)["cards"]
    assert len(cards) == 2
    assert [len(card["buttons"]) - 2 for card in cards] == [3, 3]
    actual = [row[0]["payload"]["item"] for card in cards for row in card["buttons"][:-2]]
    assert actual == drafts["items"]
    assert all(module.fits(card) for card in cards)


def test_unicode_drafts_split_at_real_utf16_and_utf8_host_limits(drafts):
    module = load("build-card.py")
    drafts["items"] = [
        {**drafts["items"][0], "to": f"person{n}@example.test", "body": "😀" * 500}
        for n in range(3)
    ]
    cards = module.build(drafts)["cards"]
    assert len(cards) > 1
    assert all(module.fits(card) for card in cards)
    assert all(
        row[0]["payload"]["item"]["body"] == "😀" * 500
        for card in cards
        for row in card["buttons"][:-2]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("to", "Alex <alex@example.test>"),
        ("to", "alex@example.test\nBcc: other@example.test"),
        ("subject", "Header\r\nInjection"),
        ("body", "body\x00hidden"),
        ("name", "Alex\nSecond person"),
    ],
)
def test_card_refuses_ambiguous_or_injected_effect_fields(drafts, field, value):
    drafts["items"][0][field] = value
    with pytest.raises(ValueError):
        load("build-card.py").build(drafts)


def test_no_proposal_approval_flag_or_duplicate_recipient_bypass(drafts):
    module = load("build-card.py")
    drafts["approved"] = True
    with pytest.raises(ValueError):
        module.build(drafts)
    del drafts["approved"]
    drafts["items"].append({**drafts["items"][0], "to": "ALEX@example.test"})
    with pytest.raises(ValueError):
        module.build(drafts)


@pytest.mark.parametrize("script", ["prepare-intake.py", "build-card.py"])
def test_bad_cli_input_is_bounded_and_never_echoes_private_text(script, monkeypatch, capsys):
    module = load(script)
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"private":"synthetic-sensitive-note"}'))
    assert module.main() == 2
    result = capsys.readouterr()
    assert not result.out
    assert "synthetic-sensitive-note" not in result.err


@pytest.mark.parametrize("script", ["prepare-intake.py", "build-card.py"])
def test_malformed_mailbox_cli_is_bounded(script, intake, drafts, monkeypatch, capsys):
    value = intake if script == "prepare-intake.py" else drafts
    if script == "prepare-intake.py":
        value["people"][0]["email"] = "@private-example.test"
    else:
        value["items"][0]["to"] = "@private-example.test"
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(value)))
    assert load(script).main() == 2
    result = capsys.readouterr()
    assert not result.out
    assert "private-example.test" not in result.err


def test_published_rule_retains_required_read_and_complete_provider_reference():
    manifest = json.loads((ROOT / ".tessl-plugin/plugin.json").read_text())
    assert "rules/conference-followup-callbacks.md" in manifest["rules"]
    assert "skills/conference-followups" in manifest["skills"]
    rule = (ROOT / "rules/conference-followup-callbacks.md").read_text()
    reference = ROOT / "skills/conference-followups/references/callback-contract.md"
    assert "read `skills/conference-followups/references/callback-contract.md` in full" in rule
    assert "owning installed" in rule and "missing or unreadable" in rule
    assert "Never load it through an `@` import" in rule
    assert reference.is_file()
    for boundary in (
        "Private hold and decisions",
        "Host execution and gateway",
        "sending",
        "uncertain",
        "Cancel",
        "Edit",
        "Sent",
        "configured owner",
        "OneCLI",
    ):
        assert boundary in reference.read_text()


@pytest.fixture
def adapter(tmp_path, monkeypatch):
    root = tmp_path / "host"
    (root / "dist").mkdir(parents=True)
    target = root / "dist/conference-followup-callback-cli.js"
    target.write_text("synthetic host entrypoint", encoding="utf-8")
    monkeypatch.setenv("NANOCLAW_CALLBACK_HOST_ROOT", str(root))
    monkeypatch.setenv("NANOCLAW_CALLBACK_NODE", "/host-owned/node")
    return load("conference-followup-callback-v1.py"), root, target


def test_adapter_invokes_one_fixed_host_target_and_retains_handled_failure(adapter, monkeypatch):
    module, root, target = adapter
    calls = []

    def invoke(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args, 0, json.dumps({"status": "failed", "text": "Inspect the held item."}), ""
        )

    monkeypatch.setattr(module.subprocess, "run", invoke)
    assert module.run(["A" * 22])["status"] == "failed"
    assert len(calls) == 1
    assert calls[0][0] == ["/host-owned/node", str(target), "A" * 22]
    assert calls[0][1]["cwd"] == root
    assert calls[0][1]["stdin"] == subprocess.DEVNULL


@pytest.mark.parametrize("args", [[], ["bad"], ["A" * 22, "extra"]])
def test_adapter_rejects_unbound_commands_before_execution(adapter, monkeypatch, args):
    module, _, _ = adapter

    def refuse(*_args, **_kwargs):
        pytest.fail("invalid claim must not start a process")

    monkeypatch.setattr(module.subprocess, "run", refuse)
    with pytest.raises(ValueError):
        module.run(args)


def test_adapter_refuses_module_symlink_escape(adapter, tmp_path):
    module, _, target = adapter
    target.unlink()
    outside = tmp_path / "outside.js"
    outside.write_text("outside", encoding="utf-8")
    target.symlink_to(outside)
    with pytest.raises(ValueError):
        module.run(["A" * 22])


@pytest.mark.parametrize(
    "output",
    [
        "not-json",
        '{"status":"applied","text":"ok","extra":true}',
        '{"status":"sent","text":"ok"}',
        json.dumps({"status": "applied", "text": "x" * 201}),
    ],
)
def test_adapter_refuses_malformed_results_without_leaking_drafts(
    adapter, monkeypatch, capsys, output
):
    module, _, _ = adapter
    monkeypatch.setattr(sys, "argv", ["adapter", "A" * 22])
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(
            args, 0, output, "synthetic-private-draft"
        ),
    )
    assert module.main() == 1
    result = capsys.readouterr()
    assert not result.out
    assert "synthetic-private-draft" not in result.err
