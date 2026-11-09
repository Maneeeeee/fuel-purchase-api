# Fuel Purchase API

A robust REST API for a fuel purchasing system built with FastAPI, SQLAlchemy 2.0, Alembic, SQLite (default for zero-setup local evaluation), and PostgreSQL with Docker Compose.

---

## Tech Stack
- **Framework**: FastAPI (Python 3.12)
- **Database**: SQLite (default, zero configuration required) & PostgreSQL 16 (supported via Docker)
- **ORM & Migrations**: SQLAlchemy 2.0 & Alembic
- **Validation**: Pydantic v2 & Pydantic-Settings
- **Security**: Direct bcrypt hashing for Admin API keys (`Admin` model: `username`, `api_key_hash`)
- **Testing**: Pytest & HTTPX TestClient
- **Containerization**: Docker & Docker Compose

---

## Quickstart (Instant Local Setup with SQLite)

The application defaults to SQLite (`sqlite:///./fuel.db`), so you can run and evaluate it immediately without installing or configuring external database servers.

### 1. Clone & Set Up Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate       # On Linux/macOS
# or:
.\.venv\Scripts\Activate.ps1   # On Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements-dev.txt
```

### 3. Apply Migrations

```bash
alembic upgrade head
```

### 4. Create an Administrator Account

Run the provided setup script:

```bash
python -m scripts.create_admin --username admin --api-key secret-admin-key
```

*(If `--api-key` is omitted, a cryptographically secure random key is automatically generated and displayed.)*

### 5. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is live at `http://localhost:8000`.  
Interactive Swagger documentation is available at `http://localhost:8000/docs`.

---

## Alternative: Run with Docker Compose (PostgreSQL)

If you prefer running in containers with a dedicated PostgreSQL database:

```bash
docker compose up --build -d
```

Migrations are applied automatically during container startup. Create an admin user:

```bash
docker compose exec app python -m scripts.create_admin --username admin --api-key secret-admin-key
```

To stop containers:
```bash
docker compose down
```

---

## Running Automated Tests

Run the full automated test suite with `pytest`:

```bash
pytest -v
```

Tests run in isolation against an in-memory SQLite database. All business logic, rounding rules, decimals, error formats, and boundary conditions are tested.

To run the optional concurrency stress test against PostgreSQL:
```bash
TEST_POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/fuel_test pytest -v
```

---

## API Endpoints Reference

### Key Conventions
- **Authentication**:
  - **Admin endpoints**: Require header `X-Admin-Key: <admin-api-key>` (optionally pass `X-Admin-Username: <username>` for direct O(1) indexed lookup).
  - **User endpoints**: Support either header `X-Username: <username>` or `Authorization: Bearer <token>`. Missing authentication returns `401 Unauthorized`.
- **Response Format**: All errors return uniform JSON: `{"error": "<detail>"}`.
- **Precision**: Money and fuel amounts use `Decimal` with up to 2 decimal places.

---

### User Authentication & Token Support (Optional Feature)

To issue a secure revocable API token for a registered user:

```http
POST /api/auth/token
Content-Type: application/json

{
  "username": "john",
  "user_id": 1
}
```

**Response (`200 OK`):**
```json
{
  "access_token": "<cryptographic-token-hex>",
  "token_type": "bearer"
}
```

Pass this token in subsequent user requests:
`Authorization: Bearer <token>`. If the token is missing, invalid, or belongs to another user, the API responds with `401 Unauthorized` (`{"error": "Invalid user authentication token."}`). Users can also authenticate directly using `X-Username: <username>`.

---

### Administrator Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/admin/products/` | List all fuel products |
| `POST` | `/api/admin/products/` | Create a fuel product |
| `PATCH` | `/api/admin/products/{product_id}/` | Update product price, stock, or details |
| `GET` | `/api/admin/users/` | List all users |
| `POST` | `/api/admin/users/` | Create a user |
| `PATCH` | `/api/admin/users/{user_id}/` | Update user details or account balance |

#### Example: Create Product
```http
POST /api/admin/products/
X-Admin-Key: secret-admin-key
Content-Type: application/json

{
  "name": "Petrol 95",
  "price_per_litre": 500.00,
  "available_litres": 1000.00
}
```

#### Example: Create User
```http
POST /api/admin/users/
X-Admin-Key: secret-admin-key
Content-Type: application/json

{
  "first_name": "John",
  "last_name": "Doe",
  "username": "john",
  "birthdate": "1990-01-01",
  "account_balance": 10000.00
}
```

---

### User Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/token/` | Issue a bearer token for a user (optional auth) |
| `POST` | `/api/purchases/` | Purchase fuel |
| `GET` | `/api/purchases/` | Retrieve user's purchase history |

#### Example: Purchase Fuel
```http
POST /api/purchases/
X-Username: john
Content-Type: application/json

{
  "product_id": 1,
  "litres": 10
}
```

**Success Response (`201 Created`):**
```json
{
  "id": 1,
  "product": "Petrol 95",
  "litres": "10.00",
  "total_price": "5000.00",
  "remaining_balance": "5000.00",
  "remaining_stock_litres": "990.00"
}
```

**Insufficient Stock (`400 Bad Request`):**
```json
{
  "error": "Not enough fuel available."
}
```

**Insufficient Balance (`400 Bad Request`):**
```json
{
  "error": "Insufficient balance."
}
```

#### Example: Purchase History
```http
GET /api/purchases/
X-Username: john
```

**Response (`200 OK`):**
```json
[
  {
    "id": 1,
    "product": "Petrol 95",
    "litres": "10.00",
    "total_price": "5000.00",
    "created_at": "2026-11-08T12:00:00Z"
  }
]
```
