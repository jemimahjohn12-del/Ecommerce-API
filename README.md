# E-Commerce & Order Management API

A RESTful backend for an online shop, built with **FastAPI**, **PostgreSQL (Neon)** and **Clean Architecture**. Customers browse products, fill a cart, check out, and upload payment receipts. Administrators manage products, coupons, orders and payment verification.

**Live API:** https://ecommerce-api-zmd5.onrender.com  
**Interactive documentation:**https://ecommerce-api-zmd5.onrender.com/docs

> The API runs on a free hosting plan that sleeps after 15 minutes without traffic. The first request after a pause can take up to a minute. Open the `/docs` page first and wait for it to load.

![Live API documentation](docs/live-docs.png)

## Main features

- Registration and login with JWT, password hashing (bcrypt), roles `CUSTOMER` and `ADMIN`
- Categories and products: admin create, update, deactivate; search by name, filter by category and price, sort by price or date, pagination
- Per-customer shopping cart with stock validation
- Coupons: percentage or fixed, expiry date, usage limit, minimum order amount
- Checkout in one database transaction, with atomic stock deduction and idempotency
- Orders with a status workflow, cancellation (stock is restored) and admin management
- Payment verification: receipt image upload, admin approve or reject with a reason, full history

## Technologies

Python 3.13, FastAPI, SQLAlchemy 2, PostgreSQL (Neon), Psycopg 3, Alembic, PyJWT, bcrypt, Pydantic, pytest, Postman, Git and GitHub. Deployed on Render.

## Project architecture

```
app/
├── domain/          business entities, rules and repository interfaces (no framework code)
├── application/     use cases (Checkout, AddToCart, ReviewPayment, ...) and service interfaces
├── infrastructure/  PostgreSQL models, repository implementations, JWT and password hashing
├── presentation/    FastAPI routes, request and response schemas, dependencies
└── core/            configuration
alembic/             database migrations
tests/               automated tests
docs/                ERD and screenshots
postman/             exported Postman collections
```

**Dependency rule:** `domain` imports nothing from the other layers, `application` imports only `domain`, and `infrastructure` and `presentation` depend inward. Business rules such as coupon calculation, status transitions and product validation live in the domain, so they can be tested without a database or a web server.

## Database design

ERD image: [docs/erd.png](docs/erd.png)

![ERD](docs/erd.png)

```mermaid
erDiagram
    USERS ||--o| CARTS : has
    CARTS ||--o{ CART_ITEMS : contains
    PRODUCTS ||--o{ CART_ITEMS : "added as"
    CATEGORIES ||--o{ PRODUCTS : groups
    USERS ||--o{ ORDERS : places
    ORDERS ||--|{ ORDER_ITEMS : contains
    PRODUCTS ||--o{ ORDER_ITEMS : "bought as"
    ORDERS ||--o{ PAYMENTS : "paid by"
    PAYMENTS ||--|| PAYMENT_RECEIPTS : "has image"
    COUPONS ||--o{ COUPON_USAGES : "used in"
    ORDERS ||--o| COUPON_USAGES : applies
    USERS ||--o{ COUPON_USAGES : uses
    ORDERS ||--|| IDEMPOTENCY_KEYS : "created by"
```

Notes: emails and product SKUs are unique. `order_items` stores the product name and price at purchase time. `CHECK` constraints keep stock, prices and quantities valid. A partial unique index allows only one `UNDER_REVIEW` or `APPROVED` payment per order. Every schema change is an Alembic migration.

## Installation and setup

```bash
git clone https://https://github.com/jemimahjohn12-del/Ecommerce-API.git
cd YOUR-REPO
python -m venv venv
venv\Scripts\activate          
pip install -r requirements.txt
copy .env.example .env         
```

Fill in `.env`, then create the tables:
```bash
alembic upgrade head
```

### Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string, for example `postgresql+psycopg://user:password@host/dbname?sslmode=require` |
| `SECRET_KEY` | Long random string used to sign JWTs |
| `ALGORITHM` | Optional, default `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional, default `30` |
| `TEST_DATABASE_URL` | Only for tests: a separate database whose name ends with `test` |

Real secrets are never committed. `.env` is ignored by Git, and `.env.example` lists the names only.

## Running the application

```bash
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs for the interactive documentation.

**First admin:** public registration always creates a customer. Register a user, then promote it once in the database:
```sql
UPDATE users SET role = 'ADMIN' WHERE email = 'you@example.com';
```

## Running the automated tests

Create an empty test database (for example `ecommerce_test`), set `TEST_DATABASE_URL` in `.env`, then:
```bash
pytest -v
```

![All tests passing](docs/tests-passed.png)

The 100 tests cover authentication and authorization, products, cart, coupon calculations, checkout, stock validation, rollback, idempotency, order status rules and payment review, including failure cases. The tests empty their database, so it must be separate from your real one.

The overselling scenario (two customers buying the last item at the same moment) is checked by `concurrency_check.py` while the server runs: exactly one checkout succeeds and the other gets `409`.

## API documentation and Postman

- Swagger UI: `/docs` (locally and on the live site)
- [postman/ecommerce-api.postman_collection.json](postman/ecommerce-api.postman_collection.json): every endpoint, organised in folders
- [postman/ecommerce-api-scenarios.postman_collection.json](postman/ecommerce-api-scenarios.postman_collection.json): success and failure test scenarios

To use them: import the file in Postman, set the base URL variable to `http://127.0.0.1:8000` or the live URL, log in as a user, and save the returned token as the `token` variable. Checkout requests need an `Idempotency-Key` header.

## Deployment

The API runs on **Render** (free web service) with a **Neon** PostgreSQL database.

- Build command: `pip install -r requirements.txt`
- Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment variables set in Render: `DATABASE_URL`, `SECRET_KEY`

Migrations run automatically each time the service starts.

## Important business rules and design decisions

- **Prices are calculated by the backend** from the database. The client never sends a price.
- **No overselling:** stock is deducted with one atomic `UPDATE ... WHERE stock >= quantity` inside the checkout transaction. If any step fails, everything is rolled back.
- **Idempotent checkout:** the `Idempotency-Key` header is stored with the order. The same key returns the original order (HTTP 200) instead of creating another. The user's cart row is locked during checkout, so double clicks are handled one at a time.
- **Order status transitions:** `PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED`. Cancellation is allowed until processing starts (customers: `PENDING` or `CONFIRMED`; admins: up to `PROCESSING`). A delivered order cannot be cancelled. Cancelling restores stock.
- **Payments:** every upload is a new row, so the history is kept. Approving a payment moves a pending order to `CONFIRMED`. An order can only be set to `PROCESSING` after its payment is approved.
- **Receipts** are checked by their real content (JPEG or PNG), limited to 5 MB, and stored in the database so they survive redeployments.
- **Coupons:** the final total can never be negative, and usage is counted atomically at checkout.
- **Security:** passwords are hashed, public registration cannot choose a role, admin endpoints check the role on the backend, and other users' carts, orders and payments are invisible (404).
- **Deleting a product only deactivates it**, so past orders stay valid.

## Author

YOUR NAME
