from coach_store import add_program_version
from test_coach_profile_storage import _client, _create


def _log(client, profile_id, token, *, program_version_id=None, adaptation_response=None, day="2026-11-08"):
    payload = {
        "session_date": day,
        "duration_minutes": 45,
        "difficulty": "moderate",
        "completed": True,
        "exercises": [],
    }
    if program_version_id is not None:
        payload["program_version_id"] = program_version_id
    if adaptation_response is not None:
        payload["adaptation_response"] = adaptation_response
    return client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json=payload,
    )


def _save_version(profile_id, token, version_id, adaptation_id):
    add_program_version(
        profile_id, token, version_id,
        {"goal": "hypertrophy", "sessions": [{"title": "A"}]},
        {"adaptive_decision": {
            "decision": "restructure_session",
            "scope": "session_structure",
            "adaptation_id": adaptation_id,
            "feedback_contract": {
                "field": "adaptation_response",
                "outcomes": ["helped", "no_change", "worse", "not_tried"],
            },
        }},
    )


def test_adaptation_feedback_contract_comes_from_exact_performed_programme(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id, token = created["profile"]["profile_id"], created["profile_access_token"]
    version_id, adaptation_id = "program-v1", "adaptation-12345678"
    _save_version(profile_id, token, version_id, adaptation_id)

    performed = _log(client, profile_id, token, program_version_id=version_id)
    assert performed.status_code == 201

    response = client.get(
        f"/coach/profile/{profile_id}/adaptation",
        headers={"X-Profile-Token": token},
    )
    assert response.status_code == 200
    decision = response.get_json()["adaptive_decision"]
    assert decision["adaptation_id"] == adaptation_id
    assert decision["feedback_contract"]["program_version_id"] == version_id


def test_feedback_must_match_saved_decision_and_can_refer_to_prior_programme(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id, token = created["profile"]["profile_id"], created["profile_access_token"]
    old_version, new_version = "program-v1", "program-v2"
    adaptation_id = "adaptation-12345678"
    _save_version(profile_id, token, old_version, adaptation_id)
    _save_version(profile_id, token, new_version, "adaptation-87654321")

    _log(client, profile_id, token, program_version_id=old_version, day="2026-11-07")
    response = _log(
        client, profile_id, token, program_version_id=new_version,
        adaptation_response={
            "adaptation_id": adaptation_id,
            "outcome": "helped",
            "program_version_id": old_version,
        },
    )
    assert response.status_code == 201
    saved = response.get_json()["session"]
    assert saved["program_version_id"] == new_version
    assert saved["session"]["adaptation_response"]["program_version_id"] == old_version


def test_feedback_cannot_be_submitted_before_target_programme_is_performed(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id, token = created["profile"]["profile_id"], created["profile_access_token"]
    version_id, adaptation_id = "program-v1", "adaptation-12345678"
    _save_version(profile_id, token, version_id, adaptation_id)

    response = _log(
        client, profile_id, token,
        adaptation_response={
            "adaptation_id": adaptation_id,
            "outcome": "helped",
            "program_version_id": version_id,
        },
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "adaptation_program_not_performed"


def test_feedback_rejects_forged_or_mismatched_programme_decision(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id, token = created["profile"]["profile_id"], created["profile_access_token"]
    version_id = "program-v1"
    _save_version(profile_id, token, version_id, "adaptation-12345678")
    _log(client, profile_id, token, program_version_id=version_id)

    forged = _log(
        client, profile_id, token, program_version_id=version_id,
        adaptation_response={
            "adaptation_id": "forged-adaptation-id",
            "outcome": "worse",
            "program_version_id": version_id,
        },
        day="2026-11-09",
    )
    assert forged.status_code == 409
    assert forged.get_json()["code"] == "adaptation_version_mismatch"


def test_feedback_rejects_programme_version_from_another_profile(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    first, second = _create(client), _create(client)
    version_id, adaptation_id = "private-program-v1", "adaptation-12345678"
    _save_version(first["profile"]["profile_id"], first["profile_access_token"], version_id, adaptation_id)

    response = _log(
        client, second["profile"]["profile_id"], second["profile_access_token"],
        adaptation_response={
            "adaptation_id": adaptation_id,
            "outcome": "helped",
            "program_version_id": version_id,
        },
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "adaptation_version_mismatch"
