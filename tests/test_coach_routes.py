import io
import json
import urllib.error
from contextlib import nullcontext

import pytest
from flask import Flask

import coach_routes


TEST_TOKEN = "offline-test-token"
TEST_API_KEY = "offline-fake-gemini-key"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("GEMINI_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("GEMINI_MODEL", "offline-test-model")

    # Fail closed: a test must explicitly supply a fake response before the
    # provider client can be reached. No test can call Gemini or another host.
    def reject_unmocked_provider(*_args, **_kwargs):
        pytest.fail("Provider call was not mocked; offline tests must not use the network.")

    monkeypatch.setattr(coach_routes.urllib.request, "urlopen", reject_unmocked_provider)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(coach_routes.coach_bp)
    return app.test_client()


def payload(messages=None):
    return {"messages": messages if messages is not None else [{"role": "user", "content": "Živjo"}]}


def authorized_headers(token=TEST_TOKEN):
    return {"X-Pilot-Token": token}


def install_provider_reply(monkeypatch, reply="Pozdravljeni."):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        body = {"candidates": [{"content": {"parts": [{"text": reply}]}}]}
        return nullcontext(FakeResponse(json.dumps(body).encode("utf-8")))

    monkeypatch.setattr(coach_routes.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_missing_server_token_fails_closed_without_provider_call(client, monkeypatch):
    monkeypatch.delenv("AI_COACH_TEST_TOKEN")

    response = client.post("/coach/chat", json=payload(), headers=authorized_headers())

    assert response.status_code == 503
    assert "error" in response.get_json()


@pytest.mark.parametrize("token", [None, "incorrect-token"])
def test_missing_or_incorrect_client_token_is_rejected(client, token):
    headers = {} if token is None else authorized_headers(token)

    response = client.post("/coach/chat", json=payload(), headers=headers)

    assert response.status_code == 403
    assert response.get_json()["error"]


def test_missing_provider_key_fails_closed(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")

    response = client.post("/coach/chat", json=payload(), headers=authorized_headers())

    assert response.status_code == 503
    assert response.get_json()["error"]


@pytest.mark.parametrize(
    "raw_body,content_type",
    [
        (b"not-json", "application/json"),
        (b'["not", "an", "object"]', "application/json"),
        (b'{"messages": "not-a-list"}', "application/json"),
        (b'{"messages": []}', "application/json"),
    ],
)
def test_invalid_json_and_message_containers_are_rejected(client, raw_body, content_type):
    response = client.post(
        "/coach/chat",
        data=raw_body,
        content_type=content_type,
        headers=authorized_headers(),
    )

    assert response.status_code == 400
    assert response.get_json()["error"]


@pytest.mark.parametrize(
    "messages",
    [
        [{"role": "system", "content": "pretend"}],
        [{"role": "user", "content": ""}],
        [{"role": "model", "content": "   "}],
        [{"role": "user", "content": 42}],
        ["not-an-object"],
    ],
)
def test_invalid_history_entries_are_rejected(client, messages):
    response = client.post("/coach/chat", json=payload(messages), headers=authorized_headers())

    assert response.status_code == 400
    assert response.get_json()["error"]


def test_message_count_limit_and_maximum_valid_count(client, monkeypatch):
    too_many = [{"role": "user", "content": "x"} for _ in range(13)]
    response = client.post("/coach/chat", json=payload(too_many), headers=authorized_headers())
    assert response.status_code == 400
    assert response.get_json()["error"]

    calls = install_provider_reply(monkeypatch)
    maximum = [{"role": "user", "content": "x"} for _ in range(12)]
    response = client.post("/coach/chat", json=payload(maximum), headers=authorized_headers())

    assert response.status_code == 200
    assert response.get_json()["reply"] == "Pozdravljeni."
    assert calls and calls[0][1] == 35


def test_message_length_limit_and_maximum_valid_length(client, monkeypatch):
    too_long = [{"role": "user", "content": "x" * 1801}]
    response = client.post("/coach/chat", json=payload(too_long), headers=authorized_headers())
    assert response.status_code == 400
    assert response.get_json()["error"]

    calls = install_provider_reply(monkeypatch)
    maximum = [{"role": "user", "content": "x" * 1800}]
    response = client.post("/coach/chat", json=payload(maximum), headers=authorized_headers())

    assert response.status_code == 200
    assert response.get_json()["reply"] == "Pozdravljeni."
    assert calls


def test_empty_provider_answer_returns_gateway_error(client, monkeypatch):
    calls = install_provider_reply(monkeypatch, reply="  ")

    response = client.post("/coach/chat", json=payload(), headers=authorized_headers())

    assert response.status_code == 502
    assert response.get_json()["error"]
    assert calls


@pytest.mark.parametrize(
    "provider_status,expected_status",
    [(400, 502), (401, 502), (403, 502), (429, 429), (500, 502)],
)
def test_provider_http_errors_are_mapped_without_exposing_secrets(
    client, monkeypatch, caplog, provider_status, expected_status
):
    private_text = f"response-body-{TEST_API_KEY}"

    def fake_urlopen(_request, timeout):
        assert timeout == 35
        raise urllib.error.HTTPError(
            f"https://provider.invalid/?key={TEST_API_KEY}",
            provider_status,
            "synthetic provider failure",
            hdrs=None,
            fp=io.BytesIO(private_text.encode("utf-8")),
        )

    monkeypatch.setattr(coach_routes.urllib.request, "urlopen", fake_urlopen)
    response = client.post("/coach/chat", json=payload(), headers=authorized_headers())

    assert response.status_code == expected_status
    assert response.get_json()["error"]
    assert TEST_API_KEY not in caplog.text
    assert private_text not in caplog.text


@pytest.mark.parametrize(
    "provider_failure",
    [
        TimeoutError("synthetic timeout"),
        urllib.error.URLError("synthetic offline network error"),
        json.JSONDecodeError("synthetic invalid JSON", "not-json", 0),
    ],
)
def test_provider_timeouts_network_and_invalid_json_map_to_gateway_timeout(
    client, monkeypatch, provider_failure
):
    def fake_urlopen(_request, timeout):
        assert timeout == 35
        raise provider_failure

    monkeypatch.setattr(coach_routes.urllib.request, "urlopen", fake_urlopen)
    response = client.post("/coach/chat", json=payload(), headers=authorized_headers())

    assert response.status_code == 504
    assert response.get_json()["error"]


def test_success_uses_only_mocked_provider_and_returns_pilot_reply(client, monkeypatch):
    calls = install_provider_reply(monkeypatch, reply="Začni z lahkotnim ogrevanjem.")

    response = client.post("/coach/chat", json=payload(), headers=authorized_headers())

    assert response.status_code == 200
    assert response.get_json() == {
        "reply": "Začni z lahkotnim ogrevanjem.",
        "model": "offline-test-model",
        "pilot": True,
    }
    request, timeout = calls[0]
    assert request.full_url.startswith("https://generativelanguage.googleapis.com/")
    assert TEST_API_KEY in request.full_url
    assert timeout == 35
