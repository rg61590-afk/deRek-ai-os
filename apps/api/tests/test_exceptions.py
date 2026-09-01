"""Tests for global exception handling (HTTPException / 404s)."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_unknown_route_returns_standard_error_envelope():
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404

    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert "request_id" in body and body["request_id"]
    assert "timestamp" in body


def test_unknown_route_includes_request_id_header():
    response = client.get("/api/v1/does-not-exist")
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_validation_error_from_custom_validator_is_json_safe():
    """Regression test: a `field_validator` that raises a plain
    `ValueError` (as `packages/tasks/models.py`'s `validate_capability`
    and `validate_task_name` do) causes Pydantic to embed that
    exception instance in the error's `ctx["error"]` field. The global
    `validation_exception_handler` must sanitize this before building
    the response, since raw exception objects are not JSON-serializable
    and previously caused this exact request to fail.
    """
    response = client.post(
        "/api/v1/tasks", json={"name": "regression-check", "capability": "Not Valid!"}
    )
    assert response.status_code == 422

    # The critical assertion: parsing succeeds at all. Before the fix,
    # the response body could not be constructed as valid JSON in the
    # first place because a raw ValueError reached `json.dumps` with
    # no `default=` fallback.
    body = response.json()
    assert body["success"] is False
    assert body["data"] is not None
    assert isinstance(body["data"]["errors"], list)

    for error in body["data"]["errors"]:
        # Every value in every error dict must already be a JSON-native
        # type — nothing that reached this point could have survived
        # `response.json()` above if it weren't, but this makes the
        # invariant explicit rather than implicit.
        _assert_json_safe(error)


def _assert_json_safe(value: object) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, dict):
        for item in value.values():
            _assert_json_safe(item)
        return
    if isinstance(value, list):
        for item in value:
            _assert_json_safe(item)
        return
    raise AssertionError(f"non-JSON-safe value leaked into response: {value!r}")
