import pytest

from training.athlete_state import (
    ATHLETE_STATE_SCHEMA_VERSION,
    AthleteStateError,
    MOVEMENT_TASKS,
    create_athlete_state,
    validate_athlete_state,
)


def make_state(**overrides):
    args = {
        "profile_id": "pilot-123",
        "goal": "strength_muscle",
        "experience": "beginner",
        "equipment": ["bodyweight", "dumbbell"],
        "sessions_per_week": 2,
    }
    args.update(overrides)
    return create_athlete_state(**args)


def test_state_is_versioned_and_preserves_explicit_equipment():
    state = make_state()
    assert state["schema_version"] == ATHLETE_STATE_SCHEMA_VERSION == 1
    assert state["equipment"] == ["bodyweight", "dumbbell"]
    assert state["availability"]["sessions_per_week"] == 2
    assert state["goal"]["canonical_goal"] == "strength_muscle"


def test_missing_movement_tasks_remain_not_assessed():
    state = make_state()
    tasks = state["movement_assessment"]["tasks"]
    assert set(tasks) == MOVEMENT_TASKS
    assert all(item["status"] == "not_assessed" for item in tasks.values())
    assert all(item["source"] is None for item in tasks.values())


def test_missing_symptom_information_is_not_asked_not_denied():
    state = make_state()
    assert state["symptoms"] == {"status": "not_asked", "items": []}


def test_user_denial_is_explicit_and_distinct_from_missing_answer():
    state = make_state(symptoms={"status": "denied"})
    assert state["symptoms"]["status"] == "denied"
    assert make_state()["symptoms"]["status"] == "not_asked"


def test_reported_symptom_requires_context_and_does_not_clear_other_training():
    state = make_state(symptoms={
        "status": "present_stable",
        "items": [{"location": "koleno", "side": "levo", "provoking_task": "izpadni korak"}],
    })
    assert state["symptoms"]["items"][0]["location"] == "koleno"
    assert state["constraints"]["excluded_patterns"] == []


def test_new_or_worsening_symptom_is_preserved_as_distinct_state():
    state = make_state(symptoms={
        "status": "new_or_worsening",
        "items": [{"location": "ramo", "trend": "worsening"}],
    })
    assert state["symptoms"]["status"] == "new_or_worsening"


@pytest.mark.parametrize("bad_status", ["", "no_issue", "unknown"])
def test_invalid_symptom_state_fails_closed(bad_status):
    with pytest.raises(AthleteStateError):
        make_state(symptoms={"status": bad_status})


def test_unassessed_task_cannot_claim_evidence_source():
    with pytest.raises(AthleteStateError):
        make_state(movement_tasks={"squat": {"status": "not_assessed", "source": "observed"}})


def test_observed_movement_task_records_provenance_separately():
    state = make_state(movement_tasks={
        "squat": {"status": "needs_support", "source": "observed", "note": "kontrola trupa"},
    })
    assert state["movement_assessment"]["tasks"]["squat"]["source"] == "observed"


def test_unknown_movement_task_fails_closed():
    with pytest.raises(AthleteStateError):
        make_state(movement_tasks={"pull": "comfortable"})


def test_empty_equipment_is_not_replaced_with_assumed_gym_equipment():
    assert make_state(equipment=[])["equipment"] == []


def test_state_round_trips_through_validator():
    state = make_state()
    validated = validate_athlete_state(state)
    assert validated == state


def test_unsupported_schema_version_is_rejected():
    state = make_state()
    state["schema_version"] = 99
    with pytest.raises(AthleteStateError):
        validate_athlete_state(state)


def test_invalid_provenance_is_rejected():
    with pytest.raises(AthleteStateError):
        make_state(provenance={"goal": {"source": "guessed"}})


def test_symptom_denial_cannot_contain_symptom_entries():
    with pytest.raises(AthleteStateError):
        make_state(symptoms={
            "status": "denied",
            "items": [{"location": "koleno"}],
        })


def test_advanced_strength_emphasis_survives_state_validation_round_trip():
    state = create_athlete_state(
        profile_id="advanced-1",
        goal="strength_muscle",
        experience="advanced",
        training_emphasis="strength",
        equipment=["barbell"],
        sessions_per_week=3,
    )
    assert state["goal"]["strength_emphasis"] == "strength"
    assert validate_athlete_state(state)["goal"]["strength_emphasis"] == "strength"


def test_functional_focus_survives_state_validation_round_trip():
    state = create_athlete_state(
        profile_id="functional-1",
        goal="functional_fitness",
        experience="intermediate",
        functional_focus="power",
        equipment=["bodyweight"],
        sessions_per_week=2,
    )
    assert validate_athlete_state(state)["goal"]["functional_focus"] == "power"



def test_available_training_days_are_part_of_canonical_availability():
    state = create_athlete_state(
        profile_id="days-1",
        goal="strength_muscle",
        experience="intermediate",
        equipment=["bodyweight"],
        sessions_per_week=2,
        available_days=["monday", "thursday"],
    )
    assert state["availability"]["available_days"] == ["monday", "thursday"]
    assert validate_athlete_state(state)["availability"]["available_days"] == [
        "monday", "thursday"
    ]


def test_invalid_available_training_day_is_rejected():
    with pytest.raises(AthleteStateError):
        create_athlete_state(
            profile_id="days-2",
            goal="strength_muscle",
            experience="intermediate",
            equipment=["bodyweight"],
            sessions_per_week=2,
            available_days=["holiday"],
        )


def test_self_reported_capabilities_are_separate_from_observed_assessment():
    state = create_athlete_state(
        profile_id="capability-1",
        goal="strength_muscle",
        experience="intermediate",
        equipment=["bodyweight"],
        sessions_per_week=2,
        self_reported_capabilities={"pistol_squat": True},
    )
    assert state["capabilities"]["self_reported"]["pistol_squat"] is True
    assert state["movement_assessment"]["tasks"]["squat"]["status"] == "not_assessed"
    assert validate_athlete_state(state)["capabilities"]["self_reported"]["pistol_squat"] is True


def test_unknown_self_reported_capability_is_rejected():
    with pytest.raises(AthleteStateError):
        create_athlete_state(
            profile_id="capability-2",
            goal="strength_muscle",
            experience="intermediate",
            equipment=["bodyweight"],
            sessions_per_week=2,
            self_reported_capabilities={"observed_squat_quality": True},
        )
