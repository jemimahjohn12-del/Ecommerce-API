from decimal import Decimal

import pytest
from sqlalchemy import text


@pytest.fixture
def cart_with_200(customer_headers, make_product, add_to_cart):
    product = make_product(price="100.00", stock=10)
    add_to_cart(customer_headers, product["id"], 2)  # subtotal 200.00
    return product


def apply(client, headers, code):
    return client.post("/coupons/apply", json={"code": code}, headers=headers)


def test_admin_creates_coupon_and_rules_are_enforced(client, admin_headers, customer_headers, make_coupon):
    make_coupon(code="SAVE10")
    payload = {
        "code": "SAVE10", "discount_type": "PERCENTAGE", "discount_value": "10",
        "expires_at": "2099-12-31T23:59:59Z", "max_uses": 5,
    }
    assert client.post("/coupons", json=payload, headers=admin_headers).status_code == 409
    assert client.post("/coupons", json=payload, headers=customer_headers).status_code == 403

    too_high = {**payload, "code": "BAD150", "discount_value": "150"}
    assert client.post("/coupons", json=too_high, headers=admin_headers).status_code == 400
    negative = {**payload, "code": "NEG", "discount_value": "-5"}
    assert client.post("/coupons", json=negative, headers=admin_headers).status_code == 422


def test_percentage_coupon_calculation(client, customer_headers, make_coupon, cart_with_200):
    make_coupon(code="SAVE10", value="10")
    r = apply(client, customer_headers, "SAVE10")
    assert r.status_code == 200
    body = r.json()
    assert Decimal(body["subtotal"]) == Decimal("200.00")
    assert Decimal(body["discount"]) == Decimal("20.00")
    assert Decimal(body["final_total"]) == Decimal("180.00")


def test_code_is_case_insensitive(client, customer_headers, make_coupon, cart_with_200):
    make_coupon(code="SAVE10")
    assert apply(client, customer_headers, "save10").status_code == 200


def test_fixed_coupon_calculation(client, customer_headers, make_coupon, cart_with_200):
    make_coupon(code="FIXED5", discount_type="FIXED", value="5")
    body = apply(client, customer_headers, "FIXED5").json()
    assert Decimal(body["discount"]) == Decimal("5.00")
    assert Decimal(body["final_total"]) == Decimal("195.00")


def test_final_total_is_never_negative(client, customer_headers, make_coupon, cart_with_200):
    make_coupon(code="HUGE", discount_type="FIXED", value="500")
    body = apply(client, customer_headers, "HUGE").json()
    assert Decimal(body["discount"]) == Decimal("200.00")
    assert Decimal(body["final_total"]) == Decimal("0.00")


def test_expired_coupon_is_rejected(client, customer_headers, make_coupon, cart_with_200):
    make_coupon(code="OLD10", expires_at="2020-01-01T00:00:00Z")
    r = apply(client, customer_headers, "OLD10")
    assert r.status_code == 400
    assert "expired" in r.json()["detail"]


def test_inactive_coupon_is_rejected(client, admin_headers, customer_headers, make_coupon, cart_with_200):
    coupon = make_coupon(code="OFF10")
    client.patch(f"/coupons/{coupon['id']}", json={"is_active": False}, headers=admin_headers)
    r = apply(client, customer_headers, "OFF10")
    assert r.status_code == 400
    assert "inactive" in r.json()["detail"]


def test_usage_limit_is_enforced(client, customer_headers, make_coupon, cart_with_200, db):
    make_coupon(code="LIMIT1", max_uses=1)
    db.execute(text("UPDATE coupons SET times_used = 1 WHERE code = 'LIMIT1'"))
    db.commit()
    r = apply(client, customer_headers, "LIMIT1")
    assert r.status_code == 400
    assert "usage limit" in r.json()["detail"]


def test_minimum_order_amount_is_enforced(client, customer_headers, make_coupon, cart_with_200):
    make_coupon(code="BIG", min_order_amount="1000")
    r = apply(client, customer_headers, "BIG")
    assert r.status_code == 400
    assert "Minimum order amount" in r.json()["detail"]


def test_unknown_coupon_and_empty_cart(client, customer_headers, customer2_headers, make_coupon, cart_with_200):
    make_coupon(code="SAVE10")
    assert apply(client, customer_headers, "NOPE").status_code == 404
    assert apply(client, customer2_headers, "SAVE10").status_code == 400  # customer 2 has an empty cart