"""Tests for the /api/v1/health endpoint."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_response_envelope():
    response = client.get("/api/v1/health")
    body = response.json()

    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert "message" in body
    assert "request_id" in body and body["request_id"]
    assert "timestamp" in body


def test_health_response_includes_request_id_header():
    response = client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_health_honors_caller_supplied_request_id():
    response = client.get(
        "/api/v1/health", headers={"X-Request-ID": "test-request-id-123"}
    )
    assert response.headers["X-Request-ID"] == "test-request-id-123"
    assert response.json()["request_id"] == "test-request-id-123"
