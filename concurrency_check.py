import threading
import uuid

import httpx

BASE = "http://127.0.0.1:8000"
PRODUCT_ID = 1  # change this to a product whose stock is exactly 1
USERS = ["b@test.com", "c@test.com"]  # two customers, password "password123"


def login(email):
    r = httpx.post(f"{BASE}/auth/login", data={"username": email, "password": "password123"})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


headers = [login(email) for email in USERS]

for h in headers:
    httpx.delete(f"{BASE}/cart", headers=h)
    r = httpx.post(f"{BASE}/cart/items", json={"product_id": PRODUCT_ID, "quantity": 1}, headers=h)
    print("add to cart:", r.status_code)

barrier = threading.Barrier(len(USERS))
results = {}


def buy(i):
    h = {**headers[i], "Idempotency-Key": str(uuid.uuid4())}
    barrier.wait()  # both threads start at the same moment
    r = httpx.post(f"{BASE}/orders/checkout", json={}, headers=h, timeout=60)
    results[USERS[i]] = (r.status_code, r.json().get("detail", "order created"))


threads = [threading.Thread(target=buy, args=(i,)) for i in range(len(USERS))]
for t in threads:
    t.start()
for t in threads:
    t.join()

for user, result in results.items():
    print(user, result)