from decimal import Decimal


def test_adding_same_product_updates_quantity(customer_headers, make_product, add_to_cart):
    product = make_product(stock=10)
    add_to_cart(customer_headers, product["id"], 2)
    r = add_to_cart(customer_headers, product["id"], 3)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["quantity"] == 5


def test_cart_total_is_calculated_by_the_backend(customer_headers, make_product, add_to_cart):
    a = make_product(name="A", price="10.00")
    b = make_product(name="B", price="5.50")
    add_to_cart(customer_headers, a["id"], 2)
    r = add_to_cart(customer_headers, b["id"], 1)
    assert Decimal(r.json()["total"]) == Decimal("25.50")
    assert r.json()["item_count"] == 3


def test_cannot_add_more_than_stock(customer_headers, make_product, add_to_cart):
    product = make_product(stock=10)
    assert add_to_cart(customer_headers, product["id"], 11).status_code == 409
    assert add_to_cart(customer_headers, product["id"], 6).status_code == 200
    assert add_to_cart(customer_headers, product["id"], 5).status_code == 409  # 6 + 5 > 10


def test_invalid_cart_requests(client, admin_headers, customer_headers, make_product, add_to_cart):
    product = make_product()
    assert add_to_cart(customer_headers, 9999).status_code == 404
    assert add_to_cart(customer_headers, product["id"], 0).status_code == 422
    client.delete(f"/products/{product['id']}", headers=admin_headers)
    assert add_to_cart(customer_headers, product["id"]).status_code == 404  # inactive product
    assert client.get("/cart").status_code == 401


def test_update_and_remove_items(client, customer_headers, make_product, add_to_cart):
    product = make_product(stock=10)
    add_to_cart(customer_headers, product["id"], 2)
    url = f"/cart/items/{product['id']}"

    r = client.put(url, json={"quantity": 4}, headers=customer_headers)
    assert r.json()["items"][0]["quantity"] == 4
    assert client.put(url, json={"quantity": 11}, headers=customer_headers).status_code == 409
    assert client.put("/cart/items/999", json={"quantity": 1}, headers=customer_headers).status_code == 404

    assert client.delete(url, headers=customer_headers).json()["items"] == []
    assert client.delete(url, headers=customer_headers).status_code == 404


def test_clear_cart(client, customer_headers, make_product, add_to_cart):
    add_to_cart(customer_headers, make_product()["id"], 2)
    assert client.delete("/cart", headers=customer_headers).status_code == 204
    assert client.get("/cart", headers=customer_headers).json()["items"] == []


def test_carts_are_private(client, customer_headers, customer2_headers, make_product, add_to_cart):
    add_to_cart(customer_headers, make_product()["id"], 2)
    assert len(client.get("/cart", headers=customer_headers).json()["items"]) == 1
    assert client.get("/cart", headers=customer2_headers).json()["items"] == []