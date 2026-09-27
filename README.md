# EVE Healthcare - Diagnostic Test Booking & Payment Backend Service

A production-quality backend engineering service for diagnostic appointment scheduling and simulated payments with database-enforced webhook idempotency.

---

## 1. Project Overview

EVE Healthcare provides a centralized backend service enabling patients to discover diagnostic tests offered across partner diagnostic centres, book timed appointments with snapshotted pricing, and complete simulated payments. The service also ingests asynchronous payment provider webhooks with guaranteed idempotency and concurrency protection.

The system prioritizes software engineering fundamentals:
- **Clean modular layered architecture** separating transport (REST), business rules (Services), persistence (Repositories), and data models (SQLAlchemy/Pydantic).
- **Strict relational database integrity** with foreign keys, composite primary keys, and unique indexes.
- **Snapshot pricing** ensuring historical booking auditability regardless of future catalog price fluctuations.
- **State machine lifecycle enforcement** preventing invalid booking transitions.
- **Database-enforced webhook idempotency** that guarantees safety against duplicate transmissions and concurrent race conditions.

---

## 2. Architecture

The codebase follows a clean, decoupled architecture:

```text
app/
├── main.py                  # FastAPI entry point, exception handlers, lifespan management
├── core/
│   ├── config.py            # Environment configuration via Pydantic BaseSettings
│   ├── database.py          # SQLAlchemy 2.0 engine, SessionLocal, declarative Base
│   └── security.py          # Argon2id password hashing, PyJWT tokens, HMAC signatures
├── models/                  # SQLAlchemy 2.0 ORM entities (relational domain models)
│   ├── base.py              # TimestampMixin and UTC timezone helpers
│   ├── user.py              # User model with role-based access
│   ├── centre.py            # DiagnosticCentre model
│   ├── test.py              # DiagnosticTest catalog model
│   ├── centre_test.py       # CentreTest association model with custom pricing
│   ├── booking.py           # Booking model with snapshot amount
│   ├── payment.py           # Payment model with provider payment references
│   └── webhook_event.py     # Webhook event ledger with UNIQUE event_id
├── schemas/                 # Pydantic v2 validation contracts & DTOs
│   ├── auth.py              # User registration, login, and token models
│   ├── centre.py            # Centre requests, responses, and test assignments
│   ├── test.py              # Test requests, responses, and pricing models
│   ├── booking.py           # Booking creation, details, and cancellation schemas
│   ├── payment.py           # Payment simulation requests and responses
│   └── webhook.py           # Webhook payloads and idempotent responses
├── repositories/            # Data access layer (pure database queries)
│   ├── booking_repository.py
│   └── payment_repository.py
├── services/                # Business logic layer (orchestration, validation, state rules)
│   ├── booking_service.py   # Booking creation, price snapshotting, cancellation state machine
│   ├── payment_service.py   # Payment simulation and atomic booking updates
│   └── webhook_service.py   # Webhook idempotency, race resolution, state transitions
├── api/
│   ├── deps.py              # FastApi dependencies: DB session, JWT auth, RBAC, HMAC auth
│   └── routes/              # Thin HTTP route handlers
│       ├── auth.py          # /api/v1/auth
│       ├── centres.py       # /api/v1/centres
│       ├── tests.py         # /api/v1/tests
│       ├── bookings.py      # /api/v1/bookings
│       └── payments.py      # /api/v1/payments & /api/v1/payments/webhook
├── db/
│   └── seed.py              # Idempotent development data seeder
└── utils/
    ├── enums.py             # Domain enumerations (UserRole, BookingStatus, etc.)
    └── exceptions.py        # Centralized domain exceptions mapped to HTTP statuses
```

### Architectural Principles:
1. **Thin Controllers**: Route handlers in `api/routes/` perform no business logic; they validate DTO schemas, invoke service methods, and return response models.
2. **Encapsulated Business Logic**: State transitions, price lookups, and authorization assertions reside in `services/`.
3. **Dedicated Data Access**: Database queries and eager loads are isolated in `repositories/`.
4. **Resilient Error Translation**: Internal SQLAlchemy errors or database schema details are intercepted by global handlers in `main.py` and converted to uniform client error formats.

---

## 3. Tech Stack

- **Language**: Python 3.12+
- **Framework**: FastAPI (high-performance asynchronous/synchronous REST APIs, automatic OpenAPI/Swagger)
- **Database**: PostgreSQL 16 (relational database with ACID transactional guarantees)
- **ORM**: SQLAlchemy 2.0 (type-annotated declarative ORM)
- **Migrations**: Alembic (version-controlled schema migrations)
- **Validation**: Pydantic v2 (fast C-based schema validation and serialization)
- **Password Hashing**: Argon2id (`argon2-cffi`, winner of the Password Hashing Competition)
- **Authentication**: JWT (`pyjwt`, stateless bearer token authorization)
- **Testing**: Pytest + HTTPX (`TestClient` with in-memory SQLite isolation)
- **Linter & Formatter**: Ruff (fast PEP 8 compliance and import sorting)
- **Containerization**: Docker & Docker Compose

---

## 4. Features

1. **User Authentication & Authorization**:
   - Secure patient registration and login.
   - Argon2id password hashing with salt and memory-hardness.
   - JWT tokens with identity (`sub`), role claim (`role`), and expiration (`exp`).
   - Role-Based Access Control (`PATIENT` vs. `ADMIN`).
   - Strict resource ownership checks (patients can only view or cancel their own bookings).

2. **Diagnostic Centres & Tests Catalog**:
   - Query diagnostic centres with location and active status.
   - Query diagnostic tests with descriptions and parameter info.
   - Centre detail view exposing available tests along with centre-specific pricing.
   - Protected Admin endpoints for creating, updating, and deactivating centres and tests.
   - Protected Admin endpoints to assign or update test pricing per diagnostic centre.

3. **Diagnostic Test Booking & Snapshot Pricing**:
   - Authenticated patients book appointments for specific tests at designated centres.
   - Validates that the appointment date is in the future.
   - Validates that the centre is active and offers the test.
   - **Snapshot Pricing**: Copies the current price from `centre_tests` into `bookings.amount` at booking creation time, protecting historical booking records from future catalog price changes.
   - Booking cancellation endpoint for pending bookings.

4. **Booking State Machine**:
   - Centralized, deterministic status transition validation.
   - Allowed transitions:
     - `PENDING` -> `CONFIRMED`
     - `PENDING` -> `FAILED`
     - `PENDING` -> `CANCELLED`
   - Terminal states (`CONFIRMED`, `FAILED`, `CANCELLED`) cannot transition backwards.

5. **Simulated Payment Gateway**:
   - `POST /api/v1/payments`: Simulates synchronous provider payment execution producing `SUCCESS` or `FAILED`.
   - Atomically updates booking status to `CONFIRMED` or `FAILED` within a single database transaction.

6. **Idempotent Payment Webhook**:
   - `POST /api/v1/payments/webhook`: Ingests asynchronous payment provider notifications.
   - Database-level `UNIQUE` constraint on `event_id` in `payment_webhook_events`.
   - Returns 200 OK idempotent response if event was previously processed.
   - Handles concurrent duplicate delivery race conditions via transaction rollback and duplicate detection.
   - Optional HMAC-SHA256 signature verification via `X-Webhook-Signature` header.

---

## 5. Database Design

```mermaid
erDiagram
    users ||--o{ bookings : "places"
    diagnostic_centres ||--o{ centre_tests : "offers"
    diagnostic_tests ||--o{ centre_tests : "offered at"
    diagnostic_centres ||--o{ bookings : "hosts"
    diagnostic_tests ||--o{ bookings : "booked for"
    bookings ||--o{ payments : "has"

    users {
        int id PK
        string email UK
        string password_hash
        string full_name
        string role
        timestamp created_at
        timestamp updated_at
    }

    diagnostic_centres {
        int id PK
        string name
        string location
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    diagnostic_tests {
        int id PK
        string name
        text description
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    centre_tests {
        int centre_id PK, FK
        int test_id PK, FK
        decimal price
    }

    bookings {
        int id PK
        int user_id FK
        int centre_id FK
        int test_id FK
        timestamp appointment_at
        decimal amount "Snapshot price"
        string status
        timestamp created_at
        timestamp updated_at
    }

    payments {
        int id PK
        int booking_id FK
        string provider_payment_id UK
        decimal amount
        string status
        timestamp created_at
        timestamp updated_at
    }

    payment_webhook_events {
        int id PK
        string event_id UK
        string event_type
        text payload
        timestamp processed_at
        timestamp created_at
    }
```

### Table Specifications:

- **`users`**:
  - `id`: Integer Primary Key, Autoincrement.
  - `email`: `VARCHAR(255)`, `UNIQUE`, Indexed, `NOT NULL`.
  - `password_hash`: `VARCHAR(255)`, `NOT NULL` (Argon2id encoded hash).
  - `full_name`: `VARCHAR(255)`, `NOT NULL`.
  - `role`: `VARCHAR(50)`, default `'PATIENT'`, `NOT NULL`.
  - `created_at`, `updated_at`: `TIMESTAMP WITH TIME ZONE`.

- **`diagnostic_centres`**:
  - `id`: Integer Primary Key, Autoincrement.
  - `name`: `VARCHAR(255)`, Indexed, `NOT NULL`.
  - `location`: `VARCHAR(255)`, `NOT NULL`.
  - `is_active`: `BOOLEAN`, default `TRUE`, Indexed, `NOT NULL`.
  - `created_at`, `updated_at`: `TIMESTAMP WITH TIME ZONE`.

- **`diagnostic_tests`**:
  - `id`: Integer Primary Key, Autoincrement.
  - `name`: `VARCHAR(255)`, Indexed, `NOT NULL`.
  - `description`: `TEXT`, Nullable.
  - `is_active`: `BOOLEAN`, default `TRUE`, Indexed, `NOT NULL`.
  - `created_at`, `updated_at`: `TIMESTAMP WITH TIME ZONE`.

- **`centre_tests`**:
  - Composite Primary Key: `(centre_id, test_id)`.
  - `centre_id`: Foreign Key to `diagnostic_centres.id` (`ON DELETE CASCADE`).
  - `test_id`: Foreign Key to `diagnostic_tests.id` (`ON DELETE CASCADE`).
  - `price`: `NUMERIC(10, 2)`, `NOT NULL`.

- **`bookings`**:
  - `id`: Integer Primary Key, Autoincrement.
  - `user_id`: Foreign Key to `users.id` (`ON DELETE RESTRICT`), Indexed, `NOT NULL`.
  - `centre_id`: Foreign Key to `diagnostic_centres.id` (`ON DELETE RESTRICT`), Indexed, `NOT NULL`.
  - `test_id`: Foreign Key to `diagnostic_tests.id` (`ON DELETE RESTRICT`), Indexed, `NOT NULL`.
  - `appointment_at`: `TIMESTAMP WITH TIME ZONE`, `NOT NULL`.
  - `amount`: `NUMERIC(10, 2)`, `NOT NULL` (**Price snapshotted at creation**).
  - `status`: `VARCHAR(50)`, Indexed, default `'PENDING'`, `NOT NULL`.
  - `created_at`, `updated_at`: `TIMESTAMP WITH TIME ZONE`.

- **`payments`**:
  - `id`: Integer Primary Key, Autoincrement.
  - `booking_id`: Foreign Key to `bookings.id` (`ON DELETE RESTRICT`), Indexed, `NOT NULL`.
  - `provider_payment_id`: `VARCHAR(255)`, `UNIQUE`, Indexed, `NOT NULL`.
  - `amount`: `NUMERIC(10, 2)`, `NOT NULL`.
  - `status`: `VARCHAR(50)`, `NOT NULL`.
  - `created_at`, `updated_at`: `TIMESTAMP WITH TIME ZONE`.

- **`payment_webhook_events`**:
  - `id`: Integer Primary Key, Autoincrement.
  - `event_id`: `VARCHAR(255)`, `UNIQUE`, Indexed, `NOT NULL`.
  - `event_type`: `VARCHAR(100)`, `NOT NULL`.
  - `payload`: `TEXT`, `NOT NULL`.
  - `processed_at`: `TIMESTAMP WITH TIME ZONE`, `NOT NULL`.
  - `created_at`: `TIMESTAMP WITH TIME ZONE`, `NOT NULL`.

---

## 6. Booking & Payment Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING : Patient creates Booking\n(Price snapshotted)
    
    PENDING --> CONFIRMED : Simulated Payment (SUCCESS)\nor Webhook (payment.succeeded)
    PENDING --> FAILED : Simulated Payment (FAILED)\nor Webhook (payment.failed)
    PENDING --> CANCELLED : Patient cancels Booking\nor Admin cancels
    
    CONFIRMED --> [*] : Terminal State
    FAILED --> [*] : Terminal State
    CANCELLED --> [*] : Terminal State
```

1. **Creation**: A patient requests an appointment for an active test at an active centre. The system queries `centre_tests` to obtain the current price, snapshots it into `booking.amount`, and sets `booking.status = PENDING`.
2. **Settlement**:
   - **Path A (Direct Simulation)**: The patient calls `POST /api/v1/payments`. If simulated as `SUCCESS`, a payment record is generated and the booking atomically transitions from `PENDING` to `CONFIRMED`. If `FAILED`, it transitions to `FAILED`.
   - **Path B (Asynchronous Webhook)**: The simulated provider sends a webhook to `POST /api/v1/payments/webhook`. Upon verifying idempotency, the event is recorded and the booking transitions from `PENDING` to `CONFIRMED` or `FAILED`.
3. **Cancellation**: Before payment occurs, the patient may cancel the pending appointment via `POST /api/v1/bookings/{id}/cancel`. Once confirmed, direct cancellation is blocked by the state machine.

---

## 7. Webhook Idempotency Explanation

### Why In-Memory Caching is Insufficient
In production distributed environments, multiple application worker processes run behind a load balancer. If an in-memory `set` or dictionary is used to track `event_id`, concurrent or subsequent duplicate requests landing on different worker processes will not see the in-memory cache and will execute duplicate logic.

### Database-Level Guarantee
Idempotency is implemented using the `payment_webhook_events` relational table with a **database-level `UNIQUE` constraint on `event_id`**:

```sql
CREATE UNIQUE INDEX ix_payment_webhook_events_event_id ON payment_webhook_events (event_id);
```

### Execution Protocol:
1. **Validate**: Validate payload structure (`event_id`, `event_type`, `provider_payment_id`, `booking_id`, `amount`).
2. **Pre-check**: Query `PaymentWebhookEvent` for existing `event_id`. If found, return immediate `200 OK` with status `"already_processed"`.
3. **Atomic Transaction**:
   - Insert `PaymentWebhookEvent(event_id=..., ...)`.
   - Insert or update `Payment(provider_payment_id=..., status=...)`.
   - Apply state transition on `Booking` (`PENDING` -> `CONFIRMED` / `FAILED`).
   - Commit database transaction.
4. **Concurrency Race Condition Handling**:
   If two identical webhooks arrive at the exact same millisecond and both pass step 2 before either commits, the database `UNIQUE` constraint triggers an `IntegrityError` on the second transaction.
   The service catches `IntegrityError`, issues a `db.rollback()`, queries the current state, and safely returns a `200 OK` with status `"already_processed"`.

---

## 8. API Endpoint Table

| Method | Endpoint | Access | Description | Success Status |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/signup` | Public | Register new patient account | `201 Created` |
| `POST` | `/api/v1/auth/login` | Public | Authenticate & retrieve JWT token | `200 OK` |
| `GET` | `/api/v1/auth/me` | Authenticated | Get current authenticated user profile | `200 OK` |
| `GET` | `/api/v1/centres` | Public | List diagnostic centres | `200 OK` |
| `POST` | `/api/v1/centres` | Admin Only | Create diagnostic centre | `201 Created` |
| `GET` | `/api/v1/centres/{id}` | Public | Get centre details with test pricing | `200 OK` |
| `PATCH` | `/api/v1/centres/{id}` | Admin Only | Update/deactivate centre | `200 OK` |
| `POST` | `/api/v1/centres/{id}/tests` | Admin Only | Assign test & set price at centre | `200 OK` |
| `DELETE` | `/api/v1/centres/{id}/tests/{test_id}` | Admin Only | Remove test from centre | `204 No Content` |
| `GET` | `/api/v1/tests` | Public | List diagnostic tests | `200 OK` |
| `POST` | `/api/v1/tests` | Admin Only | Create diagnostic test in catalog | `201 Created` |
| `GET` | `/api/v1/tests/{id}` | Public | Get diagnostic test details | `200 OK` |
| `PATCH` | `/api/v1/tests/{id}` | Admin Only | Update/deactivate test | `200 OK` |
| `GET` | `/api/v1/bookings` | Authenticated | List own bookings (Admin lists all) | `200 OK` |
| `POST` | `/api/v1/bookings` | Authenticated | Create booking with snapshot price | `201 Created` |
| `GET` | `/api/v1/bookings/{id}` | Authenticated | Get booking details (Owner/Admin) | `200 OK` |
| `POST` | `/api/v1/bookings/{id}/cancel` | Authenticated | Cancel pending booking (Owner/Admin) | `200 OK` |
| `POST` | `/api/v1/payments` | Authenticated | Simulate payment for booking | `201 Created` |
| `POST` | `/api/v1/payments/webhook` | Webhook Auth | Idempotent payment webhook | `200 OK` |
| `GET` | `/health` | Public | Healthcheck and service info | `200 OK` |

---

## 9. Local Setup (Without Docker)

### Prerequisites:
- Python 3.12+
- Git

### Steps:
```bash
# 1. Clone repository
git clone https://github.com/example/eve-healthcare-assignment.git
cd eve-healthcare-assignment

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment variables
# Copy template into .env (uses SQLite for local zero-dependency run, or configure PostgreSQL)
cp .env.example .env

# 6. Apply database migrations
alembic upgrade head

# 7. Seed development data (Admin, Patient, Centres, Tests, Prices)
python -m app.db.seed

# 8. Start local server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The interactive OpenAPI Swagger UI is available at:
`http://localhost:8000/docs`

---

## 10. Docker Setup

### Prerequisites:
- Docker and Docker Compose

### Commands:
```bash
# 1. Clone repository
git clone https://github.com/example/eve-healthcare-assignment.git
cd eve-healthcare-assignment

# 2. Configure environment file
cp .env.example .env

# 3. Build and launch containers
docker compose up --build
```

`docker-compose.yml` automatically:
1. Boots PostgreSQL 16 on port 5432 with health check.
2. Waits until PostgreSQL is healthy.
3. Runs Alembic database migrations (`alembic upgrade head`).
4. Seeds development users, centres, tests, and offerings (`python -m app.db.seed`).
5. Starts the FastAPI Uvicorn service on `http://localhost:8000`.

To stop containers:
```bash
docker compose down -v
```

---

## 11. Environment Variables

| Variable | Description | Default |
|---|---|---|
| `PROJECT_NAME` | Name of the service | `EVE Healthcare Diagnostic Booking & Payment Service` |
| `ENVIRONMENT` | Runtime environment (`development`, `production`, `test`) | `development` |
| `DATABASE_URL` | SQLAlchemy connection string | `postgresql://postgres:postgres@localhost:5432/eve_healthcare` |
| `JWT_SECRET_KEY` | Cryptographic secret for signing JWTs | *(Set via .env)* |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| Expiration window for access tokens | `1440` (24 hours) |
| `WEBHOOK_SECRET` | Secret key for simulated webhook HMAC validation | `dev-simulated-payment-webhook-secret-key` |
| `SEED_ADMIN_EMAIL` | Default development admin user email | `admin@evehealth.com` |
| `SEED_ADMIN_PASSWORD` | Default development admin user password | `AdminSecret123!` |
| `SEED_PATIENT_EMAIL` | Default development patient user email | `patient@evehealth.com` |
| `SEED_PATIENT_PASSWORD`| Default development patient user password | `PatientSecret123!` |

---

## 12. Running Tests

Tests execute against an isolated in-memory database and require zero external services.

```bash
# Run entire test suite
pytest -v

# Run with linter and formatter check
ruff check .
ruff format --check .
```

### Test Coverage Highlights (41 Tests):
- **Authentication**: User signup, duplicate email prevention, login validation, bad passwords, JWT decoding, protected endpoint rejection.
- **Diagnostic Catalog**: Centre/test creation, public listing, detail retrieval with prices, admin-only protection.
- **Bookings**: Booking creation, snapshot pricing immutability, foreign key verification, owner authorization checks, admin access, cancellation rules.
- **State Machine**: Valid transitions, blocked invalid transitions (cancelling a cancelled booking, paying for a confirmed booking).
- **Payments**: Successful simulation, failed simulation, atomic booking updates.
- **Webhooks**: Idempotent duplicate processing, no duplicate records created, invalid booking handling, HMAC signature verification.
- **Database**: Unique constraints (`users.email`, `payments.provider_payment_id`, `payment_webhook_events.event_id`, `centre_tests` composite primary key).

---

## 13. Example API Requests

### 1. User Signup
```bash
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sarah.connor@example.com",
    "password": "StrongPassword123!",
    "full_name": "Sarah Connor"
  }'
```

### 2. User Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sarah.connor@example.com",
    "password": "StrongPassword123!"
  }'
```
Response:
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in_seconds": 86400,
  "user": {
    "id": 3,
    "email": "sarah.connor@example.com",
    "full_name": "Sarah Connor",
    "role": "PATIENT"
  }
}
```

### 3. List Diagnostic Centres
```bash
curl -X GET http://localhost:8000/api/v1/centres
```

### 4. Get Centre Details (with Available Tests & Prices)
```bash
curl -X GET http://localhost:8000/api/v1/centres/1
```
Response:
```json
{
  "id": 1,
  "name": "EVE Central Diagnostic Hub",
  "location": "100 Feet Rd, Indiranagar, Bengaluru",
  "is_active": true,
  "tests": [
    {
      "id": 1,
      "name": "Complete Blood Count (CBC)",
      "description": "Evaluates overall health and detects anemia/infection.",
      "is_active": true,
      "price": 450.00
    }
  ]
}
```

### 5. Create Booking
```bash
curl -X POST http://localhost:8000/api/v1/bookings \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "centre_id": 1,
    "test_id": 1,
    "appointment_at": "2026-10-15T10:30:00Z"
  }'
```
Response:
```json
{
  "id": 1,
  "user_id": 3,
  "centre_id": 1,
  "centre_name": "EVE Central Diagnostic Hub",
  "test_id": 1,
  "test_name": "Complete Blood Count (CBC)",
  "appointment_at": "2026-10-15T10:30:00Z",
  "amount": 450.00,
  "status": "PENDING"
}
```

### 6. Simulate Payment
```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "booking_id": 1,
    "simulate_status": "SUCCESS"
  }'
```
Response:
```json
{
  "id": 1,
  "booking_id": 1,
  "provider_payment_id": "pay_sim_9a7d32e18f20b4c8",
  "amount": 450.00,
  "status": "SUCCESS"
}
```

### 7. Send Payment Webhook (Idempotent)
```bash
curl -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "X-Webhook-Secret: dev-simulated-payment-webhook-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_live_20260927_001",
    "event_type": "payment.succeeded",
    "provider_payment_id": "pay_prov_771892",
    "booking_id": 1,
    "amount": 450.00
  }'
```
First Response (`200 OK`):
```json
{
  "status": "processed",
  "event_id": "evt_live_20260927_001",
  "message": "Webhook processed successfully.",
  "booking_status": "CONFIRMED",
  "payment_status": "SUCCESS"
}
```

Repeated Webhook Request (Exact same payload):
Second Response (`200 OK`):
```json
{
  "status": "already_processed",
  "event_id": "evt_live_20260927_001",
  "message": "Webhook event was previously processed (idempotent response).",
  "booking_status": "CONFIRMED",
  "payment_status": "SUCCESS"
}
```

---

## 14. Assumptions

1. **Snapshot Pricing**: Test prices at diagnostic centres can fluctuate over time. Therefore, when a booking is created, the price is looked up from `centre_tests` and permanently stored in `bookings.amount`. If an administrator increases the price of "CBC" tomorrow, existing bookings and payments retain their original contracted price.
2. **Synchronous Payment Simulation vs. Webhooks**: Both direct simulation (`POST /api/v1/payments`) and asynchronous webhook intake (`POST /api/v1/payments/webhook`) are supported. In real healthcare payment integrations, users may pay on a hosted checkout page, making webhooks the authoritative source of truth.
3. **Simulated Webhook Authentication**: Rather than mocking real third-party signature libraries, webhooks accept either a pre-shared secret header (`X-Webhook-Secret`) or an HMAC-SHA256 signature (`X-Webhook-Signature`) computed over the raw payload body using `WEBHOOK_SECRET`.
4. **Terminal Booking States**: Once a booking reaches `CONFIRMED`, `FAILED`, or `CANCELLED`, it cannot transition back to `PENDING`. Confirmed bookings cannot be directly cancelled via the simple cancel endpoint without a dedicated refund/cancellation workflow.
5. **Single-Test Bookings**: Each booking represents an appointment for one specific diagnostic test at one centre. Multiple tests in a single cart would require a `booking_items` child table.

---

## 15. Error Handling

All API errors return consistent JSON responses:
```json
{
  "detail": "Descriptive error message"
}
```

HTTP status codes strictly reflect the error type:
- `400 Bad Request`: Business rule violations (e.g., center does not offer test, invalid state machine transition).
- `401 Unauthorized`: Missing, expired, or invalid JWT credentials, or failed webhook signature.
- `403 Forbidden`: Authenticated user lacks permission (e.g., patient attempting admin operation, or viewing another patient's booking).
- `404 Not Found`: Entity not found (booking, centre, or test).
- `409 Conflict`: Unique constraint conflicts (duplicate email).
- `422 Unprocessable Entity`: Request body schema validation errors.
- `500 Internal Server Error`: Unhandled errors masked to prevent credential or internal query disclosure.

---

## 16. Security Considerations

1. **Password Storage**: Passwords are never saved in plaintext; Argon2id hashing provides memory-hard protection against brute force and GPU cracking.
2. **Stateless Authorization**: JWT signatures are validated using an environment-provided secret key; expired tokens are rejected.
3. **OWASP Insecure Direct Object References (IDOR)**: The authenticated user identity is retrieved exclusively from the validated JWT subject (`sub`). Clients cannot supply an arbitrary `user_id` to read or modify other patients' bookings.
4. **Data Isolation**: Database connection credentials and secret keys are loaded strictly from environment variables.
5. **Safe Database Masking**: `IntegrityError` and `SQLAlchemyError` are caught by custom exception handlers to ensure SQL table names, connection strings, and stack traces are never leaked to clients.

---

## 17. Trade-offs

1. **Synchronous SQLAlchemy vs. Async SQLAlchemy**:
   - *Choice*: Used synchronous SQLAlchemy 2.0 with session per request (`get_db`).
   - *Trade-off*: Simpler code, explicit transaction demarcation, and lower cognitive complexity for junior engineers during code review, at the expense of pure async I/O throughput under tens of thousands of concurrent connections.
2. **Webhook Pre-Check + Constraint Fallback**:
   - *Choice*: Performed a SELECT pre-check on `event_id` before entering the write transaction, backed by a hard database `UNIQUE` constraint.
   - *Trade-off*: Adds one read query for legitimate incoming events, but avoids initiating write locks on redundant webhook retries and guarantees 100% race-condition protection.
3. **Database-backed Idempotency Ledger vs. Redis**:
   - *Choice*: Stored webhook events in a PostgreSQL table rather than Redis.
   - *Trade-off*: Uses relational database storage and disk I/O, but guarantees ACID transactional consistency alongside the payment and booking updates without introducing external distributed cache dependencies.

---

## 18. What Would Be Improved With More Time

1. **Multi-Test Cart Bookings**: Introduce a `booking_items` table to allow patients to book multiple tests in a single appointment slot.
2. **Refund Workflow**: Build a dedicated refund state machine (`REFUND_REQUESTED` -> `REFUNDED`) for cancelling confirmed appointments.
3. **Appointment Scheduling Concurrency**: Add slot-based capacity limits per diagnostic centre (e.g., maximum 5 blood draws per 30-minute interval) using PostgreSQL row-level locking (`SELECT ... FOR UPDATE`).
4. **Automated Notification Service**: Outbox pattern with event publishing (e.g., email / SMS confirmation once booking is `CONFIRMED`).
5. **Observability**: Add Prometheus metrics endpoint and structured JSON logging with correlation IDs (`X-Request-ID`).
