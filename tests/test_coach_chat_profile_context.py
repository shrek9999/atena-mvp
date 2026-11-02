import json

from flask import Flask

import coach_routes
from training.catalogue import load_catalogue


class FakeGeminiResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({
            "candidates": [{
                "content": {"parts": [{"text": "Preglejva zadnji zabeleženi trening."}]}
            }]
        }).encode("utf-8")


def _client(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-test-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    app = Flask(__name__)
    app.register_blueprint(coach_routes.coach_bp)
    return app.test_client()


def test_chat_includes_authenticated_recent_training_history_without_health_data(monkeypatch):
    client = _client(monkeypatch)
    profile_id = "123e4567-e89b-12d3-a456-426614174000"
    token = "profile-access-token-that-is-long-enough"
    exercise = load_catalogue()[0]
    captured = {}

    def fake_profile(requested_id, supplied_token):
        assert requested_id == profile_id
        assert supplied_token == token
        return {
            "profile_id": profile_id,
            "profile": {
                "goal": "hypertrophy",
                "experience": "intermediate",
                "equipment": ["bodyweight", "dumbbell"],
                "sessions_per_week": 3,
                "session_minutes": 50,
            },
            "health_data_consent": True,
        }

    def fake_sessions(requested_id, supplied_token, limit):
        assert requested_id == profile_id
        assert supplied_token == token
        assert limit == 4
        return [{
            "session_date": "2026-11-01",
            "session": {
                "duration_minutes": 48,
                "difficulty": "moderate",
                "recovery": "good",
                "completed": True,
                "discomfort_reported": True,
                "private_symptom_note": "This must never enter the chat context",
                "exercises": [{
                    "exercise_id": exercise["id"],
                    "sets_completed": 3,
                    "reps_completed": 10,
                    "load_kg": 22.5,
                    "rir": 2,
                }],
            },
        }]

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeGeminiResponse()

    monkeypatch.setattr(coach_routes, "store_get_profile", fake_profile)
    monkeypatch.setattr(coach_routes, "store_list_sessions", fake_sessions)
    monkeypatch.setattr(coach_routes.urllib.request, "urlopen", fake_urlopen)

    response = client.post(
        "/coach/chat",
        headers={
            "X-Pilot-Token": "pilot-test-secret",
            "X-Profile-Token": token,
        },
        json={
            "profile_id": profile_id,
            "messages": [{
                "role": "user",
                "content": (
                    'Profil: {"goal":"hypertrophy","experience":"intermediate",'
                    '"equipment":["bodyweight","dumbbell"]}. '
                    "Varnostna potrditev: nimam večjih zdravstvenih omejitev, "
                    "svežih poškodb ali zdravniških prepovedi za vadbo. "
                    "Kako naj razumem svoj zadnji trening?"
                ),
            }],
        },
    )

    assert response.status_code == 200
    prompt = captured["body"]["systemInstruction"]["parts"][0]["text"]
    assert "AUTHENTICATED SAVED ATENA PROFILE AND TRAINING HISTORY" in prompt
    assert "2026-11-01" in prompt
    assert exercise["name"] in prompt
    assert "3 series" in prompt
    assert "10 reps per set" in prompt
    assert "22.5 kg" in prompt
    assert "RIR 2" in prompt
    assert "This must never enter the chat context" not in prompt
    assert "discomfort_reported" not in prompt
    assert captured["timeout"] == 65


def test_chat_profile_context_requires_a_valid_profile_id_and_access_token(monkeypatch):
    client = _client(monkeypatch)
    calls = {"profile": 0}

    def fake_profile(*_args):
        calls["profile"] += 1
        raise coach_routes.ProfileNotFound()

    monkeypatch.setattr(coach_routes, "store_get_profile", fake_profile)

    invalid_id = client.post(
        "/coach/chat",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={"profile_id": "not-a-uuid", "messages": [{"role": "user", "content": "Živjo."}]},
    )
    assert invalid_id.status_code == 400
    assert calls["profile"] == 0

    missing_token = client.post(
        "/coach/chat",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={
            "profile_id": "123e4567-e89b-12d3-a456-426614174000",
            "messages": [{"role": "user", "content": "Živjo."}],
        },
    )
    assert missing_token.status_code == 404
    assert calls["profile"] == 0

    wrong_token = client.post(
        "/coach/chat",
        headers={
            "X-Pilot-Token": "pilot-test-secret",
            "X-Profile-Token": "wrong-profile-token",
        },
        json={
            "profile_id": "123e4567-e89b-12d3-a456-426614174000",
            "messages": [{"role": "user", "content": "Živjo."}],
        },
    )
    assert wrong_token.status_code == 404
    assert calls["profile"] == 1


def test_chat_rejects_unexpected_payload_fields(monkeypatch):
    client = _client(monkeypatch)
    response = client.post(
        "/coach/chat",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={
            "messages": [{"role": "user", "content": "Živjo."}],
            "unapproved_context": "do not accept",
        },
    )
    assert response.status_code == 400
