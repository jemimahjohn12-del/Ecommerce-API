import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.infrastructure import models  # noqa: F401  (registers every table)
from app.infrastructure.database import Base
from app.main import app
from app.presentation.dependencies import get_db

if not settings.test_database_url:
    raise RuntimeError("Add TEST_DATABASE_URL to your .env (see the README)")
if not (make_url(settings.test_database_url).database or "").endswith("test"):
    # Safety: the tests empty their database, so it must never be your real one
    raise RuntimeError("TEST_DATABASE_URL must point to a database whose name ends with 'test'")

engine = create_engine(settings.test_database_url, pool_pre_ping=True)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

PASSWORD = "password123"


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def clean_database():
    yield
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


def _override_get_db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    """A direct database session, for checking or preparing data."""
    session = TestingSession()
    yield session
    session.close()


def _login_headers(client, email, admin=False):
    r = client.post(
        "/auth/register", json={"email": email, "full_name": "Test User", "password": PASSWORD}
    )
    assert r.status_code == 201, r.text
    if admin:
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET role = 'ADMIN' WHERE email = :e"), {"e": email})
    r = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    return _login_headers(client, "admin@test.com", admin=True)


@pytest.fixture
def customer_headers(client):
    return _login_headers(client, "ben@test.com")


@pytest.fixture
def customer2_headers(client):
    return _login_headers(client, "chidi@test.com")


@pytest.fixture
def category(client, admin_headers):
    r = client.post("/categories", json={"name": "Electronics"}, headers=admin_headers)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def make_product(client, admin_headers, category):
    counter = {"n": 0}

    def _make(name="Mouse", price="10.00", stock=10, **extra):
        counter["n"] += 1
        body = {
            "name": name, "price": price, "stock": stock,
            "sku": f"SKU-{counter['n']}", "category_id": category["id"], **extra,
        }
        r = client.post("/products", json=body, headers=admin_headers)
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture
def make_coupon(client, admin_headers):
    def _make(
        code="SAVE10", discount_type="PERCENTAGE", value="10",
        expires_at="2099-12-31T23:59:59Z", max_uses=100, min_order_amount="0",
    ):
        r = client.post(
            "/coupons",
            json={
                "code": code, "discount_type": discount_type, "discount_value": value,
                "expires_at": expires_at, "max_uses": max_uses,
                "min_order_amount": min_order_amount,
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture
def add_to_cart(client):
    def _add(headers, product_id, quantity=1):
        return client.post(
            "/cart/items", json={"product_id": product_id, "quantity": quantity}, headers=headers
        )

    return _add


@pytest.fixture
def checkout(client):
    def _checkout(headers, key=None, coupon=None):
        kwargs = {"json": {"coupon_code": coupon}} if coupon else {}
        key = key or str(uuid.uuid4())
        return client.post(
            "/orders/checkout", headers={**headers, "Idempotency-Key": key}, **kwargs
        )

    return _checkout


@pytest.fixture
def placed_order(customer_headers, make_product, add_to_cart, checkout):
    """A PENDING order for the customer, total 50.00 (2 x 25.00)."""
    product = make_product(name="Keyboard", price="25.00", stock=10)
    add_to_cart(customer_headers, product["id"], 2)
    r = checkout(customer_headers)
    assert r.status_code == 201, r.text
    return r.json()