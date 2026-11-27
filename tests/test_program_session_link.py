from coach_store import add_program_version
from test_coach_profile_storage import _client, _create


def _log_session(client, profile_id, token, program_version_id=None):
    payload = {"session_date": "2026-11-08", "duration_minutes": 45, "difficulty": "moderate", "completed": True, "exercises": []}
    if program_version_id is not None: payload["program_version_id"] = program_version_id
    return client.post(f"/coach/profile/{profile_id}/sessions", headers={"X-Profile-Token": token}, json=payload)


def test_training_session_is_linked_to_exact_owned_programme_version(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path); created = _create(client)
    profile_id, token = created["profile"]["profile_id"], created["profile_access_token"]
    version_id = "program-version-test-001"
    add_program_version(profile_id, token, version_id, {"goal": "hypertrophy", "sessions": [{"name": "A"}]}, {"decision": "maintain_and_monitor"})
    saved = _log_session(client, profile_id, token, version_id)
    assert saved.status_code == 201 and saved.get_json()["session"]["program_version_id"] == version_id
    history = client.get(f"/coach/profile/{profile_id}/sessions", headers={"X-Profile-Token": token})
    assert history.status_code == 200 and history.get_json()["sessions"][0]["program_version_id"] == version_id


def test_training_session_rejects_programme_version_owned_by_another_profile(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path); first, second = _create(client), _create(client)
    version_id = "belongs-to-first-profile"
    add_program_version(first["profile"]["profile_id"], first["profile_access_token"], version_id, {"sessions": []}, {"decision": "baseline"})
    response = _log_session(client, second["profile"]["profile_id"], second["profile_access_token"], version_id)
    assert response.status_code == 400 and response.get_json()["code"] == "invalid_program_version"


def test_legacy_training_session_without_programme_version_remains_supported(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path); created = _create(client)
    response = _log_session(client, created["profile"]["profile_id"], created["profile_access_token"])
    assert response.status_code == 201 and response.get_json()["session"]["program_version_id"] is None
