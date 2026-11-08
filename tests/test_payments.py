PNG = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"


def upload(client, headers, order_id, content=PNG, filename="receipt.png", content_type="image/png"):
    return client.post(
        f"/orders/{order_id}/payment",
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


def test_new_order_has_no_payment(client, customer_headers, placed_order):
    r = client.get(f"/orders/{placed_order['id']}/payment", headers=customer_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "NOT_SUBMITTED"
    assert r.json()["payments"] == []
    assert r.json()["amount_due"] == "50.00"


def test_upload_receipt_puts_payment_under_review(client, customer_headers, placed_order):
    r = upload(client, customer_headers, placed_order["id"])
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "UNDER_REVIEW"
    assert r.json()["amount"] == "50.00"
    status = client.get(f"/orders/{placed_order['id']}/payment", headers=customer_headers).json()
    assert status["status"] == "UNDER_REVIEW"


def test_only_real_images_are_accepted(client, customer_headers, placed_order):
    oid = placed_order["id"]
    assert upload(client, customer_headers, oid, b"hello", "notes.txt", "text/plain").status_code == 400
    assert upload(client, customer_headers, oid, b"hello", "fake.png", "image/png").status_code == 400
    assert upload(client, customer_headers, oid, b"").status_code == 400
    too_big = PNG + b"0" * (5 * 1024 * 1024)
    assert upload(client, customer_headers, oid, too_big).status_code == 400


def test_cannot_submit_twice_while_under_review(client, customer_headers, placed_order):
    assert upload(client, customer_headers, placed_order["id"]).status_code == 201
    assert upload(client, customer_headers, placed_order["id"]).status_code == 409


def test_other_customers_cannot_see_or_pay_the_order(client, customer2_headers, placed_order):
    assert upload(client, customer2_headers, placed_order["id"]).status_code == 404
    assert client.get(f"/orders/{placed_order['id']}/payment", headers=customer2_headers).status_code == 404


def test_customers_cannot_review_payments(client, customer_headers, placed_order):
    payment = upload(client, customer_headers, placed_order["id"]).json()
    assert client.post(f"/payments/{payment['id']}/approve", headers=customer_headers).status_code == 403
    reject = client.post(
        f"/payments/{payment['id']}/reject", json={"reason": "no"}, headers=customer_headers
    )
    assert reject.status_code == 403


def test_admin_can_list_view_and_download(
    client, admin_headers, customer_headers, customer2_headers, placed_order
):
    payment = upload(client, customer_headers, placed_order["id"]).json()

    assert client.get("/payments", headers=admin_headers).json()["total"] == 1
    listed = client.get("/payments", params={"status": "UNDER_REVIEW"}, headers=admin_headers).json()
    assert listed["total"] == 1

    detail = client.get(f"/payments/{payment['id']}", headers=admin_headers).json()
    assert detail["order"]["id"] == placed_order["id"]
    assert detail["payment"]["amount"] == "50.00"

    receipt = client.get(f"/payments/{payment['id']}/receipt", headers=admin_headers)
    assert receipt.status_code == 200
    assert receipt.headers["content-type"] == "image/png"
    assert receipt.content == PNG
    assert client.get(f"/payments/{payment['id']}/receipt", headers=customer_headers).status_code == 200
    assert client.get(f"/payments/{payment['id']}/receipt", headers=customer2_headers).status_code == 404


def test_approval_confirms_the_order(client, admin_headers, customer_headers, placed_order):
    payment = upload(client, customer_headers, placed_order["id"]).json()
    r = client.post(f"/payments/{payment['id']}/approve", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"

    order = client.get(f"/orders/{placed_order['id']}", headers=customer_headers).json()
    assert order["status"] == "CONFIRMED"
    assert client.post(f"/payments/{payment['id']}/approve", headers=admin_headers).status_code == 409
    assert upload(client, customer_headers, placed_order["id"]).status_code == 409


def test_rejection_needs_a_reason_and_allows_a_new_upload(
    client, admin_headers, customer_headers, placed_order
):
    first = upload(client, customer_headers, placed_order["id"]).json()
    url = f"/payments/{first['id']}/reject"
    assert client.post(url, json={"reason": ""}, headers=admin_headers).status_code == 422

    r = client.post(url, json={"reason": "Amount does not match"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"

    status = client.get(f"/orders/{placed_order['id']}/payment", headers=customer_headers).json()
    assert status["status"] == "REJECTED"
    assert status["payments"][0]["rejection_reason"] == "Amount does not match"

    assert upload(client, customer_headers, placed_order["id"]).status_code == 201
    status = client.get(f"/orders/{placed_order['id']}/payment", headers=customer_headers).json()
    assert status["status"] == "UNDER_REVIEW"
    assert len(status["payments"]) == 2  # the history keeps both submissions


def test_processing_is_allowed_after_payment_is_approved(
    client, admin_headers, customer_headers, placed_order
):
    payment = upload(client, customer_headers, placed_order["id"]).json()
    client.post(f"/payments/{payment['id']}/approve", headers=admin_headers)

    status_url = f"/orders/{placed_order['id']}/status"
    r = client.patch(status_url, json={"status": "PROCESSING"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "PROCESSING"


def test_processing_is_blocked_without_an_approved_payment(
    client, admin_headers, placed_order
):
    status_url = f"/orders/{placed_order['id']}/status"
    client.patch(status_url, json={"status": "CONFIRMED"}, headers=admin_headers)
    r = client.patch(status_url, json={"status": "PROCESSING"}, headers=admin_headers)
    assert r.status_code == 400
    assert "Payment must be approved" in r.json()["detail"]