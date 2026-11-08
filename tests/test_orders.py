from decimal import Decimal

import pytest
from sqlalchemy import text

from app.infrastructure.repositories.order_repository import SqlAlchemyOrderUnitOfWork


def stock_of(client, product_id):
    return client.get(f"/products/{product_id}").json()["stock"]


def test_checkout_creates_order_and_updates_stock(
    client, customer_headers, make_product, add_to_cart, checkout
):
    mouse = make_product(name="Mouse", price="10.00", stock=10)
    keyboard = make_product(name="Keyboard", price="50.00", stock=5)
    add_to_cart(customer_headers, mouse["id"], 2)
    add_to_cart(customer_headers, keyboard["id"], 1)

    r = checkout(customer_headers)
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["status"] == "PENDING"
    assert Decimal(order["total"]) == Decimal("70.00")
    assert {item["product_name"] for item in order["items"]} == {"Mouse", "Keyboard"}

    assert stock_of(client, mouse["id"]) == 8
    assert stock_of(client, keyboard["id"]) == 4
    assert client.get("/cart", headers=customer_headers).json()["items"] == []


def test_checkout_with_empty_cart_fails(client, customer_headers, checkout):
    r = checkout(customer_headers)
    assert r.status_code == 400
    assert "empty" in r.json()["detail"]


def test_checkout_requires_idempotency_key(client, customer_headers):
    assert client.post("/orders/checkout", headers=customer_headers).status_code == 422


def test_same_idempotency_key_returns_the_same_order(
    client, customer_headers, make_product, add_to_cart, checkout
):
    product = make_product(stock=10)
    add_to_cart(customer_headers, product["id"], 2)
    first = checkout(customer_headers, key="same-key-0001")
    add_to_cart(customer_headers, product["id"], 1)
    second = checkout(customer_headers, key="same-key-0001")

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert stock_of(client, product["id"]) == 8  # deducted only once
    assert client.get("/orders", headers=customer_headers).json()["total"] == 1


def test_checkout_fails_when_stock_dropped_below_cart_quantity(
    client, admin_headers, customer_headers, make_product, add_to_cart, checkout
):
    product = make_product(stock=5)
    add_to_cart(customer_headers, product["id"], 3)
    client.patch(f"/products/{product['id']}/stock", json={"stock": 1}, headers=admin_headers)

    assert checkout(customer_headers).status_code == 409
    assert stock_of(client, product["id"]) == 1
    assert len(client.get("/cart", headers=customer_headers).json()["items"]) == 1
    assert client.get("/orders", headers=customer_headers).json()["total"] == 0


def test_checkout_fails_for_deactivated_product(
    client, admin_headers, customer_headers, make_product, add_to_cart, checkout
):
    product = make_product()
    add_to_cart(customer_headers, product["id"], 1)
    client.delete(f"/products/{product['id']}", headers=admin_headers)
    assert checkout(customer_headers).status_code == 400


def test_failure_during_checkout_rolls_everything_back(
    client, customer_headers, make_product, add_to_cart, checkout, monkeypatch
):
    product = make_product(stock=10)
    add_to_cart(customer_headers, product["id"], 2)

    def crash(*args, **kwargs):
        raise RuntimeError("simulated crash while saving the order")

    monkeypatch.setattr(SqlAlchemyOrderUnitOfWork, "create_order", crash)
    with pytest.raises(RuntimeError):
        checkout(customer_headers)
    monkeypatch.undo()

    assert stock_of(client, product["id"]) == 10  # the stock deduction was undone
    assert len(client.get("/cart", headers=customer_headers).json()["items"]) == 1
    assert client.get("/orders", headers=customer_headers).json()["total"] == 0


def test_invalid_coupon_changes_nothing(
    client, customer_headers, make_product, make_coupon, add_to_cart, checkout
):
    product = make_product(stock=10)
    make_coupon(code="OLD10", expires_at="2020-01-01T00:00:00Z")
    add_to_cart(customer_headers, product["id"], 2)

    assert checkout(customer_headers, coupon="OLD10").status_code == 400
    assert stock_of(client, product["id"]) == 10
    assert len(client.get("/cart", headers=customer_headers).json()["items"]) == 1


def test_checkout_with_coupon_applies_discount_and_counts_usage(
    client, admin_headers, customer_headers, make_product, make_coupon, add_to_cart, checkout
):
    product = make_product(price="100.00", stock=10)
    coupon = make_coupon(code="SAVE10", value="10")
    add_to_cart(customer_headers, product["id"], 2)

    order = checkout(customer_headers, coupon="SAVE10").json()
    assert Decimal(order["subtotal"]) == Decimal("200.00")
    assert Decimal(order["discount"]) == Decimal("20.00")
    assert Decimal(order["total"]) == Decimal("180.00")
    assert client.get(f"/coupons/{coupon['id']}", headers=admin_headers).json()["times_used"] == 1


def test_order_keeps_the_price_from_purchase_time(
    client, admin_headers, customer_headers, placed_order
):
    product_id = placed_order["items"][0]["product_id"]
    client.patch(f"/products/{product_id}", json={"price": "99.00"}, headers=admin_headers)
    order = client.get(f"/orders/{placed_order['id']}", headers=customer_headers).json()
    assert Decimal(order["items"][0]["unit_price"]) == Decimal("25.00")
    assert Decimal(order["total"]) == Decimal("50.00")


def test_customers_only_see_their_own_orders(
    client, admin_headers, customer_headers, customer2_headers, placed_order
):
    url = f"/orders/{placed_order['id']}"
    assert client.get(url, headers=customer_headers).status_code == 200
    assert client.get(url, headers=customer2_headers).status_code == 404
    assert client.get(url, headers=admin_headers).status_code == 200
    assert client.get("/orders", headers=customer2_headers).json()["total"] == 0
    assert client.post(f"{url}/cancel", headers=customer2_headers).status_code == 404


def test_cancel_restores_stock_and_cannot_be_repeated(client, customer_headers, placed_order):
    product_id = placed_order["items"][0]["product_id"]
    assert stock_of(client, product_id) == 8

    r = client.post(f"/orders/{placed_order['id']}/cancel", headers=customer_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"
    assert stock_of(client, product_id) == 10

    again = client.post(f"/orders/{placed_order['id']}/cancel", headers=customer_headers)
    assert again.status_code == 409
    assert stock_of(client, product_id) == 10  # not restored twice


def test_delivered_order_cannot_be_cancelled(client, admin_headers, customer_headers, placed_order, db):
    db.execute(text("UPDATE orders SET status = 'DELIVERED' WHERE id = :i"), {"i": placed_order["id"]})
    db.commit()
    assert client.post(f"/orders/{placed_order['id']}/cancel", headers=customer_headers).status_code == 409
    url = f"/orders/{placed_order['id']}/status"
    assert client.patch(url, json={"status": "CANCELLED"}, headers=admin_headers).status_code == 409


def test_admin_status_rules(client, admin_headers, customer_headers, placed_order):
    url = f"/orders/{placed_order['id']}/status"
    assert client.patch(url, json={"status": "CONFIRMED"}, headers=admin_headers).status_code == 200
    assert client.patch(url, json={"status": "DELIVERED"}, headers=admin_headers).status_code == 409
    # PROCESSING needs an approved payment first
    assert client.patch(url, json={"status": "PROCESSING"}, headers=admin_headers).status_code == 400
    assert client.patch(url, json={"status": "CONFIRMED"}, headers=customer_headers).status_code == 403


def test_admin_sees_all_orders(client, admin_headers, customer_headers, placed_order):
    result = client.get("/orders/admin/all", headers=admin_headers).json()
    assert result["total"] == 1
    assert client.get("/orders/admin/all", params={"status": "SHIPPED"}, headers=admin_headers).json()["total"] == 0


def test_atomic_stock_deduction_never_goes_below_zero(make_product, db):
    product = make_product(stock=1)
    uow = SqlAlchemyOrderUnitOfWork(db)
    assert uow.deduct_stock(product["id"], 1) is True
    assert uow.deduct_stock(product["id"], 1) is False  # the conditional update matched nothing
    uow.commit()
    stock = db.execute(text("SELECT stock FROM products WHERE id = :i"), {"i": product["id"]}).scalar()
    assert stock == 0