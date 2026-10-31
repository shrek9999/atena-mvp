import pytest
from flask import Flask

from coach_history_routes import coach_history_bp

PILOT_TOKEN = "pilot-secret-for-tests"
PROFILE = {
    "goal": "hypertrophy",
    "experience": "intermediate",
    "equipment": ["dumbbell", "bench", "resistance_band"],
    "sessions_per_week": 2,
    "session_minutes": 60,
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", PILOT_TOKEN)
    monkeypatch.setenv("ATENA_DATABASE_PATH", str(tmp_path / "atena.sqlite3"))
    app = Flask(__name__)
    app.register_blueprint(coach_history_bp)
    return app.test_client()


def create_profile(client, profile=None):
    response = client.post(
        "/coach/profile",
        headers={"X-Pilot-Token": PILOT_TOKEN},
        json={"profile": profile or PROFILE},
    )
    assert response.status_code == 201
    return response.get_json()


def profile_headers(created):
    return {"X-Profile-Token": created["profile_token"]}


def feedback(**overrides):
    value = {
        "difficulty": "right",
        "completed": True,
        "discomfort": "no",
        "movement_control": "none",
        "recovery": "normal",
    }
    value.update(overrides)
    return value


def test_profile_creation_requires_pilot_token(client):
    response = client.post("/coach/profile", json={"profile": PROFILE})
    assert response.status_code == 403


def test_profile_token_reads_and_updates_only_its_profile(client):
    created = create_profile(client)
    headers = profile_headers(created)

    read = client.get("/coach/profile", headers=headers)
    assert read.status_code == 200
    assert read.get_json()["profile"]["goal"] == "hypertrophy"

    changed = dict(PROFILE, session_minutes=75)
    update = client.put("/coach/profile", headers=headers, json={"profile": changed})
    assert update.status_code == 200
    assert update.get_json()["profile"]["session_minutes"] == 75

    assert client.get("/coach/profile", headers={"X-Profile-Token": "x" * 40}).status_code == 403


def test_profiles_are_isolated(client):
    first = create_profile(client)
    second = create_profile(client)
    assert first["profile_id"] != second["profile_id"]

    response = client.get("/coach/programs", headers=profile_headers(first))
    assert response.status_code == 200
    assert response.get_json()["programs"] == []


def test_program_is_saved_and_workout_history_is_retrievable(client):
    created = create_profile(client)
    headers = profile_headers(created)

    generated = client.post("/coach/programs", headers=headers, json={})
    assert generated.status_code == 201
    program = generated.get_json()
    assert program["program_id"]
    assert len(program["program"]["sessions"]) == 2

    session = program["program"]["sessions"][0]
    exercise = session["exercises"][0]
    logged = client.post(
        "/coach/workouts",
        headers=headers,
        json={
            "program_id": program["program_id"],
            "session": session["session"],
            "duration_minutes": 54,
            "exercises": [{
                "exercise_id": exercise["exercise_id"],
                "sets": [{"reps": 8, "load_kg": 20, "rir": 2}, {"reps": 8, "load_kg": 20, "rir": 2}],
            }],
            "feedback": feedback(difficulty="hard", completed=False, recovery="poor"),
        },
    )
    assert logged.status_code == 201
    assert logged.get_json()["adaptation_status"] == "feedback_saved"

    history = client.get("/coach/workouts", headers=headers)
    assert history.status_code == 200
    item = history.get_json()["workouts"][0]
    assert item["program_id"] == program["program_id"]
    assert item["exercises"][0]["sets"][0]["load_kg"] == 20.0

    next_program = client.post("/coach/programs", headers=headers, json={})
    assert next_program.status_code == 201
    assert next_program.get_json()["program"]["methodology"]["last_session_adjustment"] == "reduce_sets_increase_reserve"


def test_discomfort_blocks_next_program_until_new_check_in(client):
    created = create_profile(client)
    headers = profile_headers(created)
    generated = client.post("/coach/programs", headers=headers, json={}).get_json()
    session = generated["program"]["sessions"][0]
    exercise = session["exercises"][0]

    logged = client.post(
        "/coach/workouts",
        headers=headers,
        json={
            "program_id": generated["program_id"],
            "session": session["session"],
            "exercises": [{"exercise_id": exercise["exercise_id"], "sets": [{"reps": 8}]}],
            "feedback": feedback(difficulty="hard", completed=False, discomfort="yes"),
        },
    )
    assert logged.status_code == 201
    assert logged.get_json()["adaptation_status"] == "blocked_pending_review"

    blocked = client.post("/coach/programs", headers=headers, json={})
    assert blocked.status_code == 409
    assert blocked.get_json()["adaptation_blocked"] is True

    check_in = client.post(
        "/coach/check-ins",
        headers=headers,
        json={"feedback": {"discomfort": "no", "recovery": "normal"}},
    )
    assert check_in.status_code == 201
    resumed = client.post("/coach/programs", headers=headers, json={})
    assert resumed.status_code == 201


def test_workout_log_rejects_exercises_not_in_the_selected_session(client):
    created = create_profile(client)
    headers = profile_headers(created)
    generated = client.post("/coach/programs", headers=headers, json={}).get_json()
    session = generated["program"]["sessions"][0]

    response = client.post(
        "/coach/workouts",
        headers=headers,
        json={
            "program_id": generated["program_id"],
            "session": session["session"],
            "exercises": [{"exercise_id": "not_in_this_program", "sets": [{"reps": 8}]}],
            "feedback": feedback(),
        },
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    ("field", "value"),
    [("discomfort", {}), ("movement_control", []), ("recovery", {})],
)
def test_invalid_feedback_types_return_client_error_not_server_error(client, field, value):
    created = create_profile(client)
    response = client.post(
        "/coach/check-ins",
        headers=profile_headers(created),
        json={"feedback": {"discomfort": "no", field: value}},
    )
    assert response.status_code == 400


def test_profile_rejects_unhashable_goal_value(client):
    response = client.post(
        "/coach/profile",
        headers={"X-Pilot-Token": PILOT_TOKEN},
        json={"profile": dict(PROFILE, goal=[])},
    )
    assert response.status_code == 400


def test_full_app_registers_history_routes_and_profile_cors():
    import app as atena_app

    response = atena_app.app.test_client().options(
        "/coach/profile",
        headers={"Origin": "https://gregajenko.si"},
    )
    assert response.status_code == 204
    assert "X-Profile-Token" in response.headers["Access-Control-Allow-Headers"]
    assert "PUT" in response.headers["Access-Control-Allow-Methods"]
