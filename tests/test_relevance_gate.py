"""Observable relevance routes and bounded metadata retrieval, without a network."""

import importlib.util
import io
import json
import socket
import subprocess
from email.message import Message
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/check-cfps/scripts"


@pytest.fixture
def gate(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "cfp_relevance_test", SCRIPTS / "relevance-gate.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def distribution(kind="core", chance=0.99):
    values = {key: 0.0 for key in ("core", "adjacent", "off_topic", "not_dev", "unknown")}
    values[kind] = chance
    values["adjacent" if kind == "core" else "core"] = 1 - chance
    return values


def answer(fit, kind="core", chance=0.99):
    return {
        "fit": {"type": "noul", "noul": fit},
        "kind": {
            "type": "choice",
            "choice": kind,
            "confidence": 0.0,
            "probabilities": distribution(kind, chance),
        },
    }


@pytest.mark.parametrize(
    "fit,kind,chance,verdict",
    [
        (0.95, "core", 0.99, "open"),
        (0.90, "adjacent", 0.8, "open"),
        (0.20, "core", 0.99, "dismiss"),
        (0.90, "off_topic", 0.99, "dismiss"),
        (0.90, "not_dev", 0.99, "dismiss"),
        (0.60, "core", 0.99, "model"),
        (0.90, "unknown", 0.99, "model"),
        (0.90, "off_topic", 0.50, "model"),
        (0.83, "core", 0.46, "model"),
    ],
)
def test_routes_use_fit_kind_and_uncertainty(gate, fit, kind, chance, verdict):
    assert gate.route(fit, distribution(kind, chance)) == verdict


def test_state_has_live_profile_and_evidence_without_prior_verdict_or_expenses(gate):
    asked = []

    def ask(state):
        asked.append(state)
        return answer(0.95)

    result = gate.score(
        {
            "slug": "conf",
            "name": "Conference",
            "description": "Java tracks",
            "tags": ["JVM"],
            "organizer": {"name": "Community"},
            "is_user_group": False,
            "expenses_covered": {"travel": False},
            "bot_notes": "Previously relevant",
        },
        "Current speaker topics",
        "Local criteria",
        ask=ask,
        fetch=lambda url: {"description": "Professional developer conference", "warning": ""},
    )
    state = asked[0]
    assert len(asked) == 1
    assert state["speaker_profile"] == "Current speaker topics"
    assert state["candidate"]["website_description"] == "Professional developer conference"
    assert state["candidate"]["description"] == "Java tracks"
    assert "expenses_covered" not in state["candidate"]
    assert "bot_notes" not in state["candidate"]
    assert result["verdict"] == "open"


@pytest.mark.parametrize(
    "record",
    [
        {"slug": "mine", "user_actioned": True},
        {"slug": "geo", "status": "dismissed", "bot_notes": "Auto-dismissed: Geo: Peru"},
    ],
)
def test_preserved_rows_never_fetch_or_classify(gate, record):
    def forbidden(*args, **kwargs):
        pytest.fail("preserved row reached the network")

    assert (
        gate.score(record, "profile", "criteria", ask=forbidden, fetch=forbidden)["verdict"]
        == "preserve"
    )


def test_one_rejected_candidate_does_not_stop_other_asks(gate):
    asked = []

    def ask(state, *args, **kwargs):
        asked.append(state["candidate"]["name"])
        if len(asked) == 2:
            raise gate.JevUnavailable("TypeSafe HTTP 400")
        return answer(0.95)

    results = [
        gate.score(
            {"slug": str(i), "name": str(i)},
            "profile",
            "criteria",
            ask=ask,
            fetch=lambda url: {"description": "", "warning": "no website"},
        )
        for i in range(4)
    ]
    assert asked == ["0", "1", "2", "3"]
    assert [row["verdict"] for row in results] == ["open", "model", "open", "open"]


def test_missing_profile_is_a_reported_failure(gate, tmp_path, capsys):
    assert gate.main(["--profile", str(tmp_path / "missing")]) == 1
    out = capsys.readouterr()
    assert out.out == "" and "use Sonnet" in out.err


def test_cli_processes_the_whole_cohort_in_order(gate, tmp_path, monkeypatch, capsys):
    profile = tmp_path / "profile.md"
    profile.write_text("Current profile")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps([{"slug": str(i)} for i in range(51)])))
    monkeypatch.setattr(gate, "score", lambda row, *args: {"slug": row["slug"], "verdict": "model"})
    assert gate.main(["--profile", str(profile), "--criteria", str(profile)]) == 0
    assert [row["slug"] for row in json.loads(capsys.readouterr().out)] == [
        str(i) for i in range(51)
    ]


def test_metadata_child_has_an_absolute_deadline(gate, monkeypatch):
    calls = []

    def timeout(*args, **kwargs):
        calls.append(kwargs)
        raise subprocess.TimeoutExpired("metadata child", kwargs["timeout"])

    monkeypatch.setattr(gate.subprocess, "run", timeout)
    assert gate.metadata("https://conference.example")["warning"] == "website metadata unavailable"
    assert calls[0]["timeout"] == 15


def test_meta_parser_uses_description_then_open_graph_and_decodes_entities(gate):
    parser = gate.website_meta.DescriptionParser()
    parser.feed(
        '<script>irrelevant</script><meta property="og:description" content="Fallback">'
        '<META NAME="DESCRIPTION" content="Java &amp; AI   conference">'
    )
    assert parser.description() == "Java & AI conference"
    fallback = gate.website_meta.DescriptionParser()
    fallback.feed('<meta property="og:description" content="Only description">')
    assert fallback.description() == "Only description"


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "https://a:b@example.org", "http://example.org:10256"]
)
def test_meta_rejects_credentials_schemes_and_internal_ports_before_dns(gate, monkeypatch, url):
    monkeypatch.setattr(
        gate.website_meta.socket, "getaddrinfo", lambda *a, **k: pytest.fail("DNS called")
    )
    with pytest.raises(ValueError):
        gate.website_meta.public_target(url)


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "192.168.1.2", "169.254.169.254", "::1", "fc00::1"]
)
def test_meta_rejects_nonpublic_dns_results(gate, monkeypatch, address):
    monkeypatch.setattr(
        gate.website_meta.socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))],
    )
    with pytest.raises(ValueError, match="nonpublic"):
        gate.website_meta.public_target("https://conference.example")


def fake_website(gate, monkeypatch, replies):
    connections, pins = [], []
    monkeypatch.setattr(
        gate.website_meta.socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 80))],
    )
    monkeypatch.setattr(
        gate.website_meta.socket, "create_connection", lambda target, **kwargs: pins.append(target)
    )

    class Response:
        def __init__(self, status, body, location=None):
            self.status, self.body, self.location = status, body, location
            self.headers = Message()
            self.headers["Content-Type"] = "text/html; charset=utf-8"

        def getheader(self, name):
            return self.location

        def read(self, count):
            assert count == gate.website_meta.MAX_BYTES + 1
            return self.body[:count]

    class Connection:
        def __init__(self, host, port, **kwargs):
            connections.append(self)
            self.closed = False

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response(*replies.pop(0))

        def close(self):
            self.closed = True

    monkeypatch.setattr(gate.website_meta.http.client, "HTTPConnection", Connection)
    return connections, pins


def test_website_uses_pinned_public_address_and_reads_a_bounded_preview(gate, monkeypatch):
    body = b'<meta name="description" content="Java conference">' + b" " * 300_000
    connections, pins = fake_website(gate, monkeypatch, [(200, body)])
    result = gate.website_meta.fetch_description("http://conference.example")
    assert result["description"] == "Java conference"
    assert result["warning"] == "website preview limited to 256 KiB"
    assert pins == [("93.184.215.14", 80)]
    assert all(conn.closed for conn in connections)


def test_redirects_are_revalidated_and_stop_before_private_connections(gate, monkeypatch):
    connections, pins = fake_website(gate, monkeypatch, [(302, b"", "http://127.0.0.1")])
    original = gate.website_meta.public_target

    def target(url):
        if "127.0.0.1" in url:
            raise ValueError("nonpublic destination")
        return original(url)

    monkeypatch.setattr(gate.website_meta, "public_target", target)
    assert gate.website_meta.fetch_description("http://conference.example")["description"] == ""
    assert len(pins) == 1 and connections[0].closed


def fake_jev(gate, monkeypatch, body):
    calls = []
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    class Response(io.BytesIO):
        pass

    class Opener:
        def open(self, request, timeout):
            calls.append((request, timeout))
            return Response(body)

    monkeypatch.setattr(gate.urllib.request, "build_opener", lambda *args: Opener())
    return calls


def test_one_http_request_asks_both_questions_and_reads_the_environment(gate, monkeypatch):
    raw = json.dumps({"model": gate.MODEL, "answers": answer(0.95)}).encode()
    calls = fake_jev(gate, monkeypatch, raw)
    assert gate.ask_jev({"candidate": {"name": "Conference"}})["fit"]["noul"] == 0.95
    assert len(calls) == 1
    request, timeout = calls[0]
    assert request.get_header("Authorization") == "Bearer test-key"
    assert set(json.loads(request.data)["questions"]) == {"fit", "kind"}
    assert b"test-key" not in request.data
    assert timeout == 30


@pytest.mark.parametrize("body", [b"not JSON", b"[" * 2000, b'{"model":"other"}'])
def test_malformed_or_deep_json_becomes_a_safe_fallback(gate, monkeypatch, body):
    fake_jev(gate, monkeypatch, body)
    with pytest.raises(gate.JevUnavailable) as exc:
        gate.ask_jev({})
    assert "test-key" not in str(exc.value)


def test_missing_environment_key_never_starts_a_request(gate, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(gate.urllib.request, "build_opener", lambda *a: pytest.fail("network"))
    with pytest.raises(gate.JevUnavailable, match="set TYPESAFE_API_KEY"):
        gate.ask_jev({})


def test_truncated_network_response_becomes_a_model_fallback(gate, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    class Opener:
        def open(self, *args, **kwargs):
            raise gate.http.client.IncompleteRead(b"private truncated response")

    monkeypatch.setattr(gate.urllib.request, "build_opener", lambda *args: Opener())
    with pytest.raises(gate.JevUnavailable, match="cannot reach TypeSafe"):
        gate.ask_jev({})


@pytest.mark.parametrize("status", [302, 400, 401, 413, 422, 429, 500])
def test_http_errors_never_read_or_echo_the_body_or_retry(gate, monkeypatch, status):
    calls = []
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    class PrivateBody(io.BytesIO):
        def read(self, *args):
            pytest.fail("read provider error body")

    class Opener:
        def open(self, *args, **kwargs):
            calls.append(1)
            raise gate.urllib.error.HTTPError(
                gate.ENDPOINT, status, "private text", {}, PrivateBody()
            )

    monkeypatch.setattr(gate.urllib.request, "build_opener", lambda *args: Opener())
    with pytest.raises(gate.JevUnavailable) as error:
        gate.ask_jev({})
    assert str(error.value) == f"TypeSafe HTTP {status}" and len(calls) == 1


def test_provider_label_and_confidence_do_not_decide_the_route(gate):
    response = answer(0.95)
    response["kind"].update(choice="not_dev", confidence=1.0)
    result = gate.score(
        {"slug": "conf"},
        "profile",
        "criteria",
        ask=lambda state: response,
        fetch=lambda url: {"description": "", "warning": ""},
    )
    assert result["verdict"] == "open" and result["kind"] == "core"
    assert result["probabilities"] == distribution()


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"core": 1},
        {"core": 0.4, "adjacent": 0.1, "off_topic": 0.1, "not_dev": 0.1, "unknown": 0.1},
    ],
)
def test_incomplete_or_indeterminate_distributions_go_to_the_model(gate, values):
    response = answer(0.95)
    response["kind"]["probabilities"] = values
    result = gate.score(
        {"slug": "conf"},
        "profile",
        "criteria",
        ask=lambda state: response,
        fetch=lambda url: {"description": "", "warning": ""},
    )
    assert result["verdict"] == "model"


def test_documented_rounded_distribution_is_usable(gate):
    values = {"core": 0.9, "adjacent": 0.06, "off_topic": 0.03, "not_dev": 0.01, "unknown": 0.01}
    assert gate.route(0.95, values) == "open"
