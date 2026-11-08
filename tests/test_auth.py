from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import text

from app.core.config import settings


def register(client, email="a@test.com", password="password123", **extra):
    return client.post(
        "/auth/register",
        json={"email": email, "full_name": "Ada", "password": password, **extra},
    )


def test_register_success_never_returns_password(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "a@test.com"
    assert body["role"] == "CUSTOMER"
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_duplicate_email_is_rejected(client):
    register(client)
    assert register(client).status_code == 409
    assert register(client, email="A@TEST.com").status_code == 409


def test_public_registration_cannot_choose_admin_role(client):
    r = register(client, role="ADMIN")
    assert r.status_code == 201
    assert r.json()["role"] == "CUSTOMER"


def test_register_validation(client):
    assert register(client, email="not-an-email").status_code == 422
    assert register(client, password="123").status_code == 422


def test_password_is_stored_hashed(client, db):
    register(client)
    stored = db.execute(text("SELECT hashed_password FROM users")).scalar()
    assert stored != "password123"
    assert stored.startswith("$2")


def test_login_success(client):
    register(client)
    r = client.post("/auth/login", data={"username": "a@test.com", "password": "password123"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_with_wrong_credentials(client):
    register(client)
    wrong_password = client.post("/auth/login", data={"username": "a@test.com", "password": "nope12345"})
    unknown_email = client.post("/auth/login", data={"username": "x@test.com", "password": "password123"})
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    # Same message, so attackers can't tell which emails exist
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_me_endpoint_needs_a_valid_token(client, customer_headers):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer abc123"}).status_code == 401
    r = client.get("/auth/me", headers=customer_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "ben@test.com"


def test_expired_token_is_rejected(client):
    token = jwt.encode(
        {"sub": "1", "role": "CUSTOMER", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert "expired" in r.json()["detail"].lower()


def test_customer_cannot_use_admin_endpoints(client, customer_headers):
    assert client.post("/categories", json={"name": "X"}, headers=customer_headers).status_code == 403
    assert client.get("/coupons", headers=customer_headers).status_code == 403
    assert client.get("/orders/admin/all", headers=customer_headers).status_code == 403
    assert client.get("/payments", headers=customer_headers).status_code == 403


def test_admin_can_use_admin_endpoints(client, admin_headers):
    assert client.post("/categories", json={"name": "X"}, headers=admin_headers).status_code == 201