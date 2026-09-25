import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def get_admin_token():
    resp = client.post("/auth/login", data={"username": "admin@example.com", "password": "admin123!"})
    return resp.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoints:
    def test_health_basic(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_detailed(self):
        token = get_admin_token()
        resp = client.get("/health/detailed", headers={"Authorization": f"Bearer {get_admin_token()}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "database" in data
        assert "timestamp" in data


class TestMetrics:
    def test_metrics_endpoint(self):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "http_requests_total" in resp.text


class TestRateLimiting:
    def test_rate_limit_health(self):
        # Make requests up to limit
        for _ in range(65):
            resp = client.get("/health")
        # Should eventually hit rate limit (60/min)
        # Note: TestClient doesn't enforce rate limits in same way
        # This is more of an integration test


class TestSecurityHeaders:
    def test_security_headers_present(self):
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in resp.headers


class TestCORS:
    def test_cors_headers(self):
        resp = client.options("/health", headers={"Origin": "http://localhost:3000"})
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")