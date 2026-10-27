"""Checkpoint tests that run without a real Supabase project.

A small fake stands in for the Supabase client: it keeps users in a dict and hands out random tokens,
and it raises the same AuthApiError the real SDK raises. The routes cannot tell the difference.
Run with:  pytest -q
"""
import os
import secrets
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from supabase_auth.errors import AuthApiError, AuthRetryableError

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-anon-key")

from app import auth as auth_module  # noqa: E402
from app import main as main_module  # noqa: E402


class FakeAuth:
    def __init__(self):
        self.users = {}       # email -> user record
        self.sessions = {}    # access token -> email
        self.admin = SimpleNamespace(sign_out=self._sign_out)
        self.down = False     # simulate Supabase being unreachable

    def _user(self, email):
        u = self.users[email]
        return SimpleNamespace(id=u["id"], email=email, created_at="2026-10-27T10:00:00Z")

    def sign_up(self, creds):
        if len(creds["password"]) < 6:
            raise AuthApiError("Password should be at least 6 characters.", 422, "weak_password")
        self.users.setdefault(creds["email"], {"id": str(uuid.uuid4()), "password": creds["password"]})
        return SimpleNamespace(user=self._user(creds["email"]), session=SimpleNamespace())

    def sign_in_with_password(self, creds):
        u = self.users.get(creds["email"])
        if not u or u["password"] != creds["password"]:
            raise AuthApiError("Invalid login credentials", 400, "invalid_credentials")
        token = "eyJ" + secrets.token_urlsafe(24)
        self.sessions[token] = creds["email"]
        return SimpleNamespace(session=SimpleNamespace(access_token=token, refresh_token="r-" + token[-6:],
                                                       expires_in=3600), user=self._user(creds["email"]))

    def get_user(self, token):
        if self.down:
            raise AuthRetryableError("connection refused", 0)
        if token not in self.sessions:
            raise AuthApiError("invalid JWT: unable to parse or verify signature", 403, "bad_jwt")
        return SimpleNamespace(user=self._user(self.sessions[token]))

    def _sign_out(self, token, scope="global"):
        self.sessions.pop(token, None)


@pytest.fixture
def fake(monkeypatch):
    fake_auth = FakeAuth()
    factory = lambda: SimpleNamespace(auth=fake_auth)  # noqa: E731
    monkeypatch.setattr(main_module, "new_client", factory)
    monkeypatch.setattr(auth_module, "new_client", factory)
    return fake_auth


@pytest.fixture
def client(fake):
    return TestClient(main_module.app)


def login(client, email="test@example.com", password="password123"):
    client.post("/auth/signup", json={"email": email, "password": password})
    return client.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]


def test_public_info_is_open(client):
    r = client.get("/public/info")
    assert r.status_code == 200
    assert r.json() == {"message": "Welcome stranger! This info is public."}


def test_signup_201_and_missing_fields_400(client):
    r = client.post("/auth/signup", json={"email": "test@example.com", "password": "password123"})
    assert r.status_code == 201 and r.json()["email"] == "test@example.com"
    r = client.post("/auth/signup", json={"email": "test@example.com"})
    assert r.status_code == 400 and "password" in r.json()["error"]
    assert client.post("/auth/signup", json={}).status_code == 400


def test_signup_weak_password_is_400(client):
    r = client.post("/auth/signup", json={"email": "a@b.co", "password": "123"})
    assert r.status_code == 400 and "6 characters" in r.json()["error"]


def test_login_200_returns_tokens(client):
    client.post("/auth/signup", json={"email": "test@example.com", "password": "password123"})
    r = client.post("/auth/login", json={"email": "test@example.com", "password": "password123"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"] and body["token_type"] == "bearer"


def test_login_wrong_password_401_and_empty_400(client):
    client.post("/auth/signup", json={"email": "test@example.com", "password": "password123"})
    r = client.post("/auth/login", json={"email": "test@example.com", "password": "nope-nope"})
    assert r.status_code == 401 and r.json() == {"error": "Invalid login credentials"}
    assert client.post("/auth/login", json={"email": "", "password": ""}).status_code == 400


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer "},
                                     {"Authorization": "token-without-scheme"}])
def test_profile_without_proper_bearer_is_401(client, headers):
    r = client.get("/protected/profile", headers=headers)
    assert r.status_code == 401 and r.json() == {"error": "Access token required"}


def test_profile_with_valid_token_200(client):
    token = login(client)
    r = client.get("/protected/profile", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "test@example.com" and r.json()["id"] and r.json()["created_at"]


def test_tampered_token_401(client):
    token = login(client)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    r = client.get("/protected/profile", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401 and r.json() == {"error": "Invalid or expired token"}


def test_second_protected_route_uses_same_guard(client):
    assert client.get("/protected/dashboard").status_code == 401
    assert client.get("/protected/dashboard", headers={"Authorization": "Bearer junk"}).status_code == 401
    token = login(client)
    r = client.get("/protected/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and "test@example.com" in r.json()["message"]


def test_logout_204_then_token_is_dead(client):
    token = login(client)
    h = {"Authorization": f"Bearer {token}"}
    assert client.post("/auth/logout").status_code == 401
    r = client.post("/auth/logout", headers=h)
    assert r.status_code == 204 and r.content == b""
    assert client.get("/protected/profile", headers=h).status_code == 401


def test_provider_down_is_503_not_401(client, fake):
    token = login(client)
    fake.down = True
    r = client.get("/protected/profile", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 503


def test_swagger_has_bearer_padlock(client):
    spec = client.get("/openapi.json").json()
    assert spec["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http", "scheme": "bearer", "description": "Paste the access_token from POST /auth/login"}
    assert spec["paths"]["/protected/profile"]["get"]["security"] == [{"HTTPBearer": []}]
    assert "security" not in spec["paths"]["/public/info"]["get"]
