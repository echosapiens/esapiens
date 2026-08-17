"""Tests for API endpoints — real TestClient, no mocks.

Tests health, auth enforcement, and job CRUD with real dependencies.
DISABLE_AUTH defaults to true (dev mode); auth enforcement tests
set it to false explicitly to verify JWT blocking.
"""
from fastapi.testclient import TestClient
from app.main import app
from app.security import create_access_token
from app.config import settings

client = TestClient(app)


def _valid_token():
    """Helper: create a valid JWT for testing."""
    return create_access_token({"sub": "test-user"})


class TestHealth:
    """GET /health is public and returns system status."""

    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["runtime"] == "split-architecture"


class TestAuthEnforcement:
    """All /api/v1/ routes require JWT when DISABLE_AUTH=false."""

    def setup_method(self):
        """Toggle auth enforcement for this test class."""
        self._orig = settings.DISABLE_AUTH
        settings.DISABLE_AUTH = False

    def teardown_method(self):
        """Restore original auth setting."""
        settings.DISABLE_AUTH = self._orig

    def test_jobs_list_requires_auth(self):
        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 403

    def test_jobs_list_with_valid_token(self):
        token = _valid_token()
        resp = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_jobs_list_with_invalid_token(self):
        resp = client.get("/api/v1/jobs", headers={"Authorization": "Bearer invalid-token"})
        assert resp.status_code == 403

    def test_pipeline_requires_auth(self):
        resp = client.post("/api/v1/run-pipeline", json={"user_prompt": "test"})
        assert resp.status_code == 403

    def test_cost_requires_auth(self):
        resp = client.post("/api/v1/simulate-cost", json={"user_prompt": "test", "tier": "free"})
        assert resp.status_code == 403

    def test_chat_requires_auth(self):
        resp = client.post("/api/v1/chat/stream", json={"user_prompt": "hello"})
        assert resp.status_code == 403


class TestJobsCRUD:
    """Job CRUD endpoints with valid auth (dev mode)."""

    def test_list_jobs_empty(self):
        token = _valid_token()
        resp = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_nonexistent_job(self):
        token = _valid_token()
        resp = client.get("/api/v1/jobs/nonexistent-id", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_delete_nonexistent_job(self):
        token = _valid_token()
        resp = client.delete("/api/v1/jobs/nonexistent-id", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404


class TestSessions:
    """Session CRUD endpoints with valid auth (dev mode)."""

    def test_list_sessions_empty(self):
        token = _valid_token()
        resp = client.get("/api/v1/sessions", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_session(self):
        token = _valid_token()
        resp = client.post("/api/v1/sessions", headers={"Authorization": f"Bearer {token}"}, json={"title": "Test Session"})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["title"] == "Test Session"

    def test_get_nonexistent_session(self):
        token = _valid_token()
        resp = client.get("/api/v1/sessions/nonexistent-id", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_delete_nonexistent_session(self):
        token = _valid_token()
        resp = client.delete("/api/v1/sessions/nonexistent-id", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_create_and_get_session(self):
        token = _valid_token()
        # Create
        create_resp = client.post("/api/v1/sessions", headers={"Authorization": f"Bearer {token}"}, json={"title": "My Session"})
        assert create_resp.status_code == 200
        session_id = create_resp.json()["id"]

        # Get
        get_resp = client.get(f"/api/v1/sessions/{session_id}", headers={"Authorization": f"Bearer {token}"})
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "My Session"

        # Delete
        del_resp = client.delete(f"/api/v1/sessions/{session_id}", headers={"Authorization": f"Bearer {token}"})
        assert del_resp.status_code == 200

        # Verify deleted
        get_resp2 = client.get(f"/api/v1/sessions/{session_id}", headers={"Authorization": f"Bearer {token}"})
        assert get_resp2.status_code == 404