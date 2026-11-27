from app import app

PILOT_ORIGIN = "https://pilot-atena-profile-history.atena-ai-trener.pages.dev"
PROFILE_HEADERS = "content-type, x-pilot-token, x-profile-id, x-profile-token"


def test_cloudflare_origin_can_preflight_authenticated_coach_chat():
    response = app.test_client().options(
        "/coach/chat",
        headers={
            "Origin": PILOT_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": PROFILE_HEADERS,
        },
    )

    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == PILOT_ORIGIN
    allowed = response.headers["Access-Control-Allow-Headers"].lower()
    assert all(name in allowed for name in PROFILE_HEADERS.split(", "))


def test_cloudflare_origin_can_preflight_top_level_app_routes():
    response = app.test_client().options(
        "/health",
        headers={
            "Origin": PILOT_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type, x-pilot-token",
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == PILOT_ORIGIN
    allowed = response.headers["Access-Control-Allow-Headers"].lower()
    assert "content-type" in allowed
    assert "x-pilot-token" in allowed
