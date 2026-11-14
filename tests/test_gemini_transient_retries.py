import urllib.error
from unittest.mock import MagicMock, patch

import pytest

import coach_routes


def _success_response():
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = b'{"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}'
    return response


def _http_error(status):
    return urllib.error.HTTPError(
        "https://generativelanguage.googleapis.com/test",
        status,
        "provider error",
        hdrs=None,
        fp=None,
    )


def test_gemini_retries_transient_503_then_returns_primary_model():
    with patch.object(
        coach_routes.urllib.request,
        "urlopen",
        side_effect=[_http_error(503), _success_response()],
    ) as mocked, patch.object(coach_routes.time, "sleep"):
        data, used_model = coach_routes._request_gemini_content(
            "test-key", "gemini-primary", "gemini-fallback", {"contents": []}
        )

    assert used_model == "gemini-primary"
    assert data["candidates"][0]["content"]["parts"][0]["text"] == "OK"
    assert mocked.call_count == 2


def test_gemini_uses_configured_fallback_after_primary_transient_failures():
    with patch.object(
        coach_routes.urllib.request,
        "urlopen",
        side_effect=[
            _http_error(503),
            _http_error(503),
            _success_response(),
        ],
    ) as mocked, patch.object(coach_routes.time, "sleep"):
        data, used_model = coach_routes._request_gemini_content(
            "test-key", "gemini-primary", "gemini-fallback", {"contents": []}
        )

    assert used_model == "gemini-fallback"
    assert data["candidates"][0]["content"]["parts"][0]["text"] == "OK"
    assert mocked.call_count == 3
    fallback_request = mocked.call_args_list[-1].args[0]
    assert "gemini-fallback:generateContent" in fallback_request.full_url


def test_gemini_retries_rate_limit_once_per_model_then_returns_error():
    with patch.object(
        coach_routes.urllib.request, "urlopen", side_effect=_http_error(429)
    ) as mocked, patch.object(coach_routes.time, "sleep") as sleeper:
        with pytest.raises(urllib.error.HTTPError) as error:
            coach_routes._request_gemini_content(
                "test-key", "gemini-primary", "gemini-fallback", {"contents": []}
            )

    assert error.value.code == 429
    assert mocked.call_count == 4
    assert sleeper.call_count == 2
    assert all(call.args == (5.0,) for call in sleeper.call_args_list)


def _invalid_json_response():
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = b"not valid JSON"
    return response


def test_gemini_uses_fallback_after_primary_network_errors():
    with patch.object(
        coach_routes.urllib.request,
        "urlopen",
        side_effect=[
            TimeoutError("provider timed out"),
            OSError("connection reset"),
            _success_response(),
        ],
    ) as mocked, patch.object(coach_routes.time, "sleep") as sleeper:
        data, used_model = coach_routes._request_gemini_content(
            "test-key", "gemini-primary", "gemini-fallback", {"contents": []}
        )

    assert used_model == "gemini-fallback"
    assert data["candidates"][0]["content"]["parts"][0]["text"] == "OK"
    assert mocked.call_count == 3
    assert sleeper.call_count == 1
    fallback_request = mocked.call_args_list[-1].args[0]
    assert "gemini-fallback:generateContent" in fallback_request.full_url


def test_gemini_uses_fallback_after_primary_returns_invalid_json_twice():
    with patch.object(
        coach_routes.urllib.request,
        "urlopen",
        side_effect=[
            _invalid_json_response(),
            _invalid_json_response(),
            _success_response(),
        ],
    ) as mocked, patch.object(coach_routes.time, "sleep") as sleeper:
        data, used_model = coach_routes._request_gemini_content(
            "test-key", "gemini-primary", "gemini-fallback", {"contents": []}
        )

    assert used_model == "gemini-fallback"
    assert data["candidates"][0]["content"]["parts"][0]["text"] == "OK"
    assert mocked.call_count == 3
    assert sleeper.call_count == 1
