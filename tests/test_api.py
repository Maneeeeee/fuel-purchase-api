import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Admin, Product, Purchase, User
from app.security import hash_api_key

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


ADMIN_KEY = "test-secret-key"
ADMIN = {"X-Admin-Key": ADMIN_KEY}


@pytest.fixture(autouse=True)
def client():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        db.add(Admin(username="admin", api_key_hash=hash_api_key(ADMIN_KEY)))
        db.commit()
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


def make_product(client, price=500.0, litres=1000.0, name="Petrol 95"):
    res = client.post("/api/admin/products/", headers=ADMIN,
                      json={"name": name, "price_per_litre": price, "available_litres": litres})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def make_user(client, username="john", balance=10000.0, **extra):
    body = {"first_name": "John", "last_name": "Doe", "username": username,
            "birthdate": "1990-01-01", "account_balance": balance, **extra}
    res = client.post("/api/admin/users/", headers=ADMIN, json=body)
    assert res.status_code == 201, res.text
    return res.json()["id"]


# ---------- admin auth ----------

def test_admin_auth_required(client):
    body = {"name": "Petrol", "price_per_litre": 500, "available_litres": 100}
    res = client.post("/api/admin/products/", json=body)
    assert res.status_code == 401
    assert "error" in res.json()
    res = client.post("/api/admin/products/", headers={"X-Admin-Key": "wrong-key"}, json=body)
    assert res.status_code == 401


def test_admin_key_longer_than_bcrypt_limit_is_rejected_not_500(client):
    res = client.post("/api/admin/products/", headers={"X-Admin-Key": "x" * 200},
                      json={"name": "P", "price_per_litre": 1, "available_litres": 1})
    assert res.status_code == 401


def test_hash_api_key_rejects_over_72_bytes():
    with pytest.raises(ValueError):
        hash_api_key("x" * 73)


# ---------- products ----------

def test_create_and_update_product(client):
    res = client.post("/api/admin/products/", headers=ADMIN,
                      json={"name": "Petrol 95", "price_per_litre": 500.0, "available_litres": 1000.0})
    assert res.status_code == 201
    data = res.json()
    assert data["price_per_litre"] == "500.00"
    assert data["available_litres"] == "1000.00"

    patch = client.patch(f"/api/admin/products/{data['id']}/", headers=ADMIN,
                         json={"price_per_litre": 520.0, "available_litres": 800.0})
    assert patch.status_code == 200
    assert patch.json()["price_per_litre"] == "520.00"
    assert patch.json()["available_litres"] == "800.00"


def test_patch_missing_product_404(client):
    assert client.patch("/api/admin/products/999/", headers=ADMIN, json={"name": "x"}).status_code == 404


@pytest.mark.parametrize("body", [
    {"name": "D", "price_per_litre": -10, "available_litres": 100},
    {"name": "D", "price_per_litre": 1.005, "available_litres": 100},     # >2 decimals
    {"name": "D", "price_per_litre": 99999999999, "available_litres": 1}, # overflows column
    {"name": "   ", "price_per_litre": 1, "available_litres": 1},
])
def test_product_validation(client, body):
    res = client.post("/api/admin/products/", headers=ADMIN, json=body)
    assert res.status_code == 422
    assert "error" in res.json()


@pytest.mark.parametrize("field", ["name", "price_per_litre", "available_litres"])
def test_product_patch_null_is_422_not_500(client, field):
    pid = make_product(client)
    res = client.patch(f"/api/admin/products/{pid}/", headers=ADMIN, json={field: None})
    assert res.status_code == 422


# ---------- users ----------

def test_create_and_update_user(client):
    uid = make_user(client)
    dup = client.post("/api/admin/users/", headers=ADMIN, json={
        "first_name": "Jane", "last_name": "Doe", "username": "john", "birthdate": "1995-05-05"})
    assert dup.status_code == 400
    assert dup.json()["error"] == "Username already exists."

    patch = client.patch(f"/api/admin/users/{uid}/", headers=ADMIN, json={"account_balance": 15000.0})
    assert patch.status_code == 200
    assert patch.json()["account_balance"] == "15000.00"


def test_user_default_balance_is_decimal_zero(client):
    res = client.post("/api/admin/users/", headers=ADMIN, json={
        "first_name": "A", "last_name": "B", "username": "zero", "birthdate": "2000-01-01"})
    assert res.status_code == 201
    assert res.json()["account_balance"] == "0.00"
    with TestingSessionLocal() as db:
        assert isinstance(db.query(User).filter_by(username="zero").one().account_balance, Decimal)


def test_user_validation(client):
    future = (date.today() + timedelta(days=1)).isoformat()
    base = {"first_name": "A", "last_name": "B", "username": "u", "birthdate": "2000-01-01"}
    for override in ({"birthdate": future}, {"username": "   "}, {"account_balance": -1},
                     {"account_balance": 123456789012345}):
        res = client.post("/api/admin/users/", headers=ADMIN, json={**base, **override})
        assert res.status_code == 422, override


def test_username_is_trimmed(client):
    make_user(client, username="  padded  ")
    pid = make_product(client)
    res = client.post("/api/purchases/", headers={"X-Username": "padded"},
                      json={"product_id": pid, "litres": 1})
    assert res.status_code == 201


def test_user_patch_null_is_422_and_username_conflict_400(client):
    a = make_user(client, "alice")
    make_user(client, "bob")
    assert client.patch(f"/api/admin/users/{a}/", headers=ADMIN, json={"first_name": None}).status_code == 422
    assert client.patch(f"/api/admin/users/{a}/", headers=ADMIN, json={"account_balance": None}).status_code == 422
    res = client.patch(f"/api/admin/users/{a}/", headers=ADMIN, json={"username": "bob"})
    assert res.status_code == 400
    assert client.patch("/api/admin/users/999/", headers=ADMIN, json={"first_name": "x"}).status_code == 404


def test_username_race_integrity_error_returns_400(client, monkeypatch):
    """Both requests pass the pre-check; the DB unique constraint decides."""
    make_user(client, "taken")
    from sqlalchemy.orm import Query

    real_first = Query.first
    calls = {"n": 0}

    def fake_first(self):
        # Make only the username pre-check in create_user miss.
        if "users.username" in str(self) and calls["n"] == 0 and "admins" not in str(self):
            calls["n"] += 1
            return None
        return real_first(self)

    monkeypatch.setattr(Query, "first", fake_first)
    res = client.post("/api/admin/users/", headers=ADMIN, json={
        "first_name": "X", "last_name": "Y", "username": "taken", "birthdate": "2000-01-01"})
    assert res.status_code == 400
    assert res.json()["error"] == "Username already exists."


# ---------- routes without trailing slash ----------

def test_no_trailing_slash_does_not_redirect(client):
    def call(method, url, **kw):
        res = client.request(method, url, follow_redirects=False, **kw)
        assert res.status_code < 300, (method, url, res.status_code)
        return res

    pid = call("POST", "/api/admin/products", headers=ADMIN,
               json={"name": "P", "price_per_litre": 1, "available_litres": 10}).json()["id"]
    uid = call("POST", "/api/admin/users", headers=ADMIN, json={
        "first_name": "A", "last_name": "B", "username": "slashy",
        "birthdate": "2000-01-01", "account_balance": 10}).json()["id"]
    call("PATCH", f"/api/admin/products/{pid}", headers=ADMIN, json={"name": "Q"})
    call("PATCH", f"/api/admin/users/{uid}", headers=ADMIN, json={"first_name": "C"})
    user = {"X-Username": "slashy"}
    call("POST", "/api/purchases", headers=user, json={"product_id": pid, "litres": 1})
    assert len(call("GET", "/api/purchases", headers=user).json()) == 1


# ---------- purchases ----------

def test_purchase_flow_success_and_failures(client):
    pid = make_product(client)
    make_user(client)
    h = {"X-Username": "john"}

    assert client.post("/api/purchases/", json={"product_id": pid, "litres": 10}).status_code == 400
    assert client.post("/api/purchases/", headers={"X-Username": "ghost"},
                       json={"product_id": pid, "litres": 10}).status_code == 404

    stock = client.post("/api/purchases/", headers=h, json={"product_id": pid, "litres": 1500})
    assert stock.status_code == 400 and stock.json()["error"] == "Not enough fuel available."

    bal = client.post("/api/purchases/", headers=h, json={"product_id": pid, "litres": 50})
    assert bal.status_code == 400 and bal.json()["error"] == "Insufficient balance."

    ok = client.post("/api/purchases/", headers=h, json={"product_id": pid, "litres": 10})
    assert ok.status_code == 201
    data = ok.json()
    assert data["product"] == "Petrol 95"
    assert data["litres"] == "10.00"
    assert data["total_price"] == "5000.00"
    assert data["remaining_balance"] == "5000.00"
    assert data["remaining_stock_litres"] == "990.00"

    history = client.get("/api/purchases/", headers=h).json()
    assert len(history) == 1
    assert history[0]["total_price"] == "5000.00"


@pytest.mark.parametrize("litres", [0, -5])
def test_non_positive_litres_is_400(client, litres):
    pid = make_product(client)
    make_user(client)
    res = client.post("/api/purchases/", headers={"X-Username": "john"},
                      json={"product_id": pid, "litres": litres})
    assert res.status_code == 400
    assert res.json()["error"] == "Litres must be greater than zero."


@pytest.mark.parametrize("litres", [0.005, 99999999999, "abc"])
def test_bad_litres_precision_is_422_and_stock_untouched(client, litres):
    pid = make_product(client)
    make_user(client)
    res = client.post("/api/purchases/", headers={"X-Username": "john"},
                      json={"product_id": pid, "litres": litres})
    assert res.status_code == 422
    with TestingSessionLocal() as db:
        assert db.get(Product, pid).available_litres == Decimal("1000.00")


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_422_not_500(client, token):
    pid = make_product(client)
    make_user(client)
    raw = {"Content-Type": "application/json"}
    res = client.post("/api/purchases/", headers={"X-Username": "john", **raw},
                      content='{"product_id": %d, "litres": %s}' % (pid, token))
    assert res.status_code == 422
    res = client.post("/api/admin/products/", headers={**ADMIN, **raw},
                      content='{"name": "x", "price_per_litre": %s, "available_litres": 1}' % token)
    assert res.status_code == 422


def test_out_of_range_ids_are_422(client):
    make_user(client)
    res = client.post("/api/purchases/", headers={"X-Username": "john"},
                      json={"product_id": 2**40, "litres": 1})
    assert res.status_code == 422
    assert client.patch(f"/api/admin/users/{2**40}/", headers=ADMIN, json={"first_name": "x"}).status_code == 422


def test_unknown_product_404(client):
    make_user(client)
    res = client.post("/api/purchases/", headers={"X-Username": "john"},
                      json={"product_id": 999, "litres": 1})
    assert res.status_code == 404


def test_price_rounds_half_up(client):
    pid = make_product(client, price=0.05, litres=100)
    make_user(client, balance=100)
    res = client.post("/api/purchases/", headers={"X-Username": "john"},
                      json={"product_id": pid, "litres": 0.1})   # 0.005 -> 0.01
    assert res.status_code == 201
    assert res.json()["total_price"] == "0.01"


def test_history_isolated_per_user_and_paginated(client):
    pid = make_product(client, price=1, litres=1000)
    make_user(client, "alice", 1000)
    make_user(client, "bob", 1000)
    for _ in range(3):
        client.post("/api/purchases/", headers={"X-Username": "alice"}, json={"product_id": pid, "litres": 1})
    client.post("/api/purchases/", headers={"X-Username": "bob"}, json={"product_id": pid, "litres": 1})

    alice = client.get("/api/purchases/", headers={"X-Username": "alice"}).json()
    assert len(alice) == 3
    assert [p["id"] for p in alice] == sorted((p["id"] for p in alice), reverse=True)
    assert len(client.get("/api/purchases/?limit=2", headers={"X-Username": "alice"}).json()) == 2
    assert len(client.get("/api/purchases/?limit=2&offset=2", headers={"X-Username": "alice"}).json()) == 1
    assert client.get("/api/purchases/?limit=0", headers={"X-Username": "alice"}).status_code == 422


def test_created_at_is_iso_utc_with_z(client):
    pid = make_product(client)
    make_user(client)
    client.post("/api/purchases/", headers={"X-Username": "john"}, json={"product_id": pid, "litres": 1})
    created = client.get("/api/purchases/", headers={"X-Username": "john"}).json()[0]["created_at"]
    assert created.endswith("Z")
    assert "+" not in created


# ---------- database / misc ----------

def test_sqlite_foreign_keys_enforced():
    with TestingSessionLocal() as db:
        db.add(Purchase(user_id=9999, product_id=9999, product_name="x", litres=1, total_price=1))
        with pytest.raises(IntegrityError):
            db.commit()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_real_validation_handler_is_used(client):
    res = client.post("/api/admin/products/", headers=ADMIN,
                      json={"name": "x", "price_per_litre": -1, "available_litres": 1})
    body = res.json()
    assert res.status_code == 422
    assert "error" in body and "details" in body


# ---------- concurrency (needs a real PostgreSQL; SQLite ignores row locks) ----------

PG_URL = os.getenv("TEST_POSTGRES_URL")


@pytest.mark.skipif(not PG_URL, reason="set TEST_POSTGRES_URL to run the concurrency test")
def test_concurrent_purchases_never_oversell():
    pg = create_engine(PG_URL)
    Session = sessionmaker(bind=pg)
    Base.metadata.drop_all(pg)
    Base.metadata.create_all(pg)
    with Session() as db:
        db.add(Product(name="P", price_per_litre=Decimal("10.00"), available_litres=Decimal("50.00")))
        db.add(User(first_name="a", last_name="b", username="racer", birthdate=date(2000, 1, 1),
                    account_balance=Decimal("10000.00")))
        db.commit()

    def pg_db():
        with Session() as s:
            yield s

    app.dependency_overrides[get_db] = pg_db
    c = TestClient(app)

    def buy(_):
        return c.post("/api/purchases/", headers={"X-Username": "racer"},
                      json={"product_id": 1, "litres": 5}).status_code

    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            codes = list(pool.map(buy, range(20)))
        assert codes.count(201) == 10 and codes.count(400) == 10
        with Session() as db:
            assert db.get(Product, 1).available_litres == Decimal("0.00")
            assert db.get(User, 1).account_balance == Decimal("9500.00")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(pg)
