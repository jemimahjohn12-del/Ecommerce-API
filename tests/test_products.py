from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def body(category, **overrides):
    data = {"name": "Mouse", "price": "10.00", "stock": 5, "sku": "M-1", "category_id": category["id"]}
    data.update(overrides)
    return data


def test_admin_creates_product(make_product):
    product = make_product(name="Mouse", price="15.99", stock=10)
    assert Decimal(product["price"]) == Decimal("15.99")
    assert product["is_active"] is True


def test_customers_cannot_create_products(client, customer_headers, category):
    assert client.post("/products", json=body(category), headers=customer_headers).status_code == 403
    assert client.post("/products", json=body(category)).status_code == 401


def test_duplicate_sku_is_rejected(client, admin_headers, category):
    assert client.post("/products", json=body(category), headers=admin_headers).status_code == 201
    assert client.post("/products", json=body(category), headers=admin_headers).status_code == 409


def test_invalid_product_data_is_rejected(client, admin_headers, category):
    assert client.post("/products", json=body(category, price="-5"), headers=admin_headers).status_code == 422
    assert client.post("/products", json=body(category, stock=-1, sku="X"), headers=admin_headers).status_code == 422
    bad_category = body(category, sku="Y", category_id=9999)
    assert client.post("/products", json=bad_category, headers=admin_headers).status_code == 404


def test_search_filter_sort_and_pagination(client, admin_headers, make_product):
    make_product(name="Wireless Mouse", price="15.00")
    make_product(name="Mechanical Keyboard", price="80.00")
    make_product(name="USB Cable", price="5.00")
    make_product(name="Laptop Stand", price="25.00")
    make_product(name="Wireless Charger", price="30.00")

    assert client.get("/products", params={"search": "wireless"}).json()["total"] == 2
    assert client.get("/products", params={"min_price": "10", "max_price": "30"}).json()["total"] == 3

    ascending = client.get("/products", params={"sort_by": "price", "sort_order": "asc"}).json()
    prices = [Decimal(p["price"]) for p in ascending["items"]]
    assert prices == sorted(prices)
    assert prices[0] == Decimal("5.00")

    page = client.get("/products", params={"page": 3, "page_size": 2}).json()
    assert len(page["items"]) == 1
    assert page["total"] == 5
    assert page["total_pages"] == 3


def test_filter_by_category(client, admin_headers, make_product):
    make_product(name="Mouse")
    books = client.post("/categories", json={"name": "Books"}, headers=admin_headers).json()
    r = client.post(
        "/products",
        json={"name": "Python Book", "price": "20.00", "stock": 3, "sku": "BOOK-1", "category_id": books["id"]},
        headers=admin_headers,
    )
    assert r.status_code == 201
    result = client.get("/products", params={"category_id": books["id"]}).json()
    assert result["total"] == 1
    assert result["items"][0]["name"] == "Python Book"


def test_bad_query_values_are_rejected(client):
    assert client.get("/products", params={"min_price": "50", "max_price": "10"}).status_code == 400
    assert client.get("/products", params={"sort_by": "color"}).status_code == 422


def test_deactivated_products_are_hidden_from_customers(client, admin_headers, make_product):
    product = make_product()
    assert client.delete(f"/products/{product['id']}", headers=admin_headers).status_code == 204
    assert client.get(f"/products/{product['id']}").status_code == 404
    assert client.get("/products").json()["total"] == 0
    assert client.get("/products/admin/all", headers=admin_headers).json()["total"] == 1


def test_admin_updates_product_and_stock(client, admin_headers, make_product):
    product = make_product(price="10.00", stock=5)
    r = client.patch(f"/products/{product['id']}", json={"price": "12.50"}, headers=admin_headers)
    assert r.status_code == 200
    assert Decimal(r.json()["price"]) == Decimal("12.50")

    r = client.patch(f"/products/{product['id']}/stock", json={"stock": 42}, headers=admin_headers)
    assert r.json()["stock"] == 42
    r = client.patch(f"/products/{product['id']}/stock", json={"stock": -1}, headers=admin_headers)
    assert r.status_code == 422


def test_category_with_products_cannot_be_deleted(client, admin_headers, category, make_product):
    make_product()
    assert client.delete(f"/categories/{category['id']}", headers=admin_headers).status_code == 409


def test_database_itself_refuses_negative_stock(make_product, db):
    product = make_product(stock=1)
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE products SET stock = -1 WHERE id = :i"), {"i": product["id"]})
        db.commit()
    db.rollback()