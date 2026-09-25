import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import engine
from app.models import User

client = TestClient(app)


def get_admin_token():
    resp = client.post("/auth/login", data={"username": "admin@example.com", "password": "admin123!"})
    return resp.json()["access_token"]


def get_refresh_token():
    resp = client.post("/auth/login", data={"username": "admin@example.com", "password": "admin123!"})
    return resp.json().get("refresh_token")


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestUserManagement:
    def test_create_user_admin(self):
        token = get_admin_token()
        resp = client.post("/auth/users/",
            json={"email": "newuser@test.com", "password": "Pass1234", "role": "operator"},
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201
        assert resp.json()["email"] == "newuser@test.com"
        assert resp.json()["role"] == "operator"

    def test_create_user_operator_forbidden(self):
        op_token = get_operator_token()
        resp = client.post("/auth/users/",
            json={"email": "test@test.com", "password": "Pass1234"},
            headers={"Authorization": f"Bearer {op_token}"})
        assert resp.status_code == 403

    def test_create_user_duplicate_email(self):
        token = get_admin_token()
        client.post("/auth/users/", json={"email": "dup@test.com", "password": "Pass1234"}, headers={"Authorization": f"Bearer {get_admin_token()}"})
        resp = client.post("/auth/users/", json={"email": "dup@test.com", "password": "Pass1234"}, headers={"Authorization": f"Bearer {get_admin_token()}"})
        assert resp.status_code == 400

    def test_list_users(self):
        token = get_admin_token()
        resp = client.get("/auth/users/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_user(self):
        token = get_admin_token()
        create = client.post("/auth/users/", json={"email": "getme@test.com", "password": "Pass1234"}, headers={"Authorization": f"Bearer {get_admin_token()}"})
        uid = create.json()["id"]
        resp = client.get(f"/auth/users/{uid}", headers={"Authorization": f"Bearer {get_admin_token()}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "getme@test.com"

    def test_update_user(self):
        token = get_admin_token()
        create = client.post("/auth/users/", json={"email": "updateme@test.com", "password": "Pass1234"}, headers={"Authorization": f"Bearer {get_admin_token()}"})
        uid = create.json()["id"]
        resp = client.patch(f"/auth/users/{uid}", json={"role": "admin", "is_active": False}, headers={"Authorization": f"Bearer {get_admin_token()}"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"
        assert resp.json()["is_active"] is False

    def test_delete_user(self):
        token = get_admin_token()
        create = client.post("/auth/users/", json={"email": "deleteme@test.com", "password": "Pass1234"}, headers={"Authorization": f"Bearer {get_admin_token()}"})
        uid = create.json()["id"]
        resp = client.delete(f"/auth/users/{uid}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 204
        assert client.get(f"/auth/users/{uid}", headers={"Authorization": f"Bearer {token}"}).status_code == 404


class TestRefreshToken:
    def test_refresh_token_flow(self):
        resp = client.post("/auth/login", data={"username": "admin@example.com", "password": "admin123!"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

        refresh_token = data["refresh_token"]

        resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        new_data = resp.json()
        assert "access_token" in new_data
        assert "refresh_token" in new_data
        assert new_data["refresh_token"] != refresh_token

        resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401

    def test_logout_revokes_refresh(self):
        resp = client.post("/auth/login", data={"username": "admin@example.com", "password": "admin123!"})
        refresh_token = resp.json()["refresh_token"]

        resp = client.post("/auth/logout", json={"refresh_token": refresh_token})
        assert resp.status_code == 200

        resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401