# EVE Healthcare Backend Engineering - Interview Guide & Deep Dive

This document prepares you to explain every design decision, architectural pattern, and database mechanism during technical interviews.

---

## Part 1: Deep Dive Explanations

### 1. Architecture Explanation
The application employs a **Separation of Concerns (SoC)** layered architecture:
- **Transport Layer (`api/routes/`)**: Focuses exclusively on HTTP communication. It parses requests, enforces schema validation via Pydantic, extracts JWT identity via FastAPI dependencies, and formats HTTP responses.
- **Service Layer (`services/`)**: The core brain of the application. It enforces domain business rules, coordinates multi-entity operations, enforces the booking state machine, and handles atomic database transactions.
- **Repository Layer (`repositories/`)**: Isolates raw SQLAlchemy data queries from business logic. This makes queries reusable, simplifies unit test mocking, and ensures business logic remains database-agnostic.
- **Domain Models (`models/`)**: Represents relational tables using SQLAlchemy 2.0 type-annotated declarative mappings.
- **Data Transfer Objects (`schemas/`)**: Pydantic v2 schemas defining incoming request contracts and outgoing response formats, preventing unintentional data exposure (such as password hashes).

---

### 2. Database Relationship Explanation
The relational model reflects a healthcare marketplace:
- **`DiagnosticCentre` to `DiagnosticTest` (Many-to-Many via `CentreTest`)**:
  A centre can offer multiple tests, and a test can be conducted at multiple centres. Rather than duplicating prices or tying price to a test globally, `CentreTest` acts as an association table with a **composite primary key `(centre_id, test_id)`** and a `price` column. This reflects real-world healthcare where different clinics have different equipment and overheads.
- **`User` to `Booking` (One-to-Many)**:
  A patient (`User`) can have multiple appointment bookings. `bookings.user_id` has a foreign key to `users.id` with `ON DELETE RESTRICT` to ensure patient appointment history is never accidentally orphaned.
- **`Booking` to `Payment` (One-to-Many / One-to-One in practice)**:
  `payments.booking_id` references `bookings.id`. Tracking payments in a dedicated entity separates appointment scheduling from financial transaction records.
- **`PaymentWebhookEvent`**:
  An independent ledger table storing webhook deliveries with a database-level `UNIQUE` constraint on `event_id`.

---

### 3. Why PostgreSQL?
1. **ACID Transaction Guarantees**: Healthcare scheduling and financial records require strict Atomicity and Consistency. If a payment succeeds, the booking status and payment record must update together or not at all.
2. **Strict Integrity Constraints**: PostgreSQL enforces relational constraints (foreign keys, check constraints, composite keys, and unique indexes) at the storage engine level.
3. **Robust Concurrency Control (MVCC)**: Multi-Version Concurrency Control handles concurrent bookings and webhook deliveries without coarse-grained table locking.
4. **Data Integrity Types**: Native support for precise `NUMERIC(10, 2)` eliminates floating-point rounding errors inherent to financial calculations.

---

### 4. Why FastAPI?
1. **Fast & Modern**: Built on Starlette and Pydantic, FastAPI is one of the highest-performing Python web frameworks.
2. **Automatic Schema Validation**: Pydantic v2 validates request bodies before code execution, rejecting malformed JSON with standardized `422 Unprocessable Entity` responses.
3. **Declarative Dependency Injection (`Depends`)**: Provides a clean mechanism for scoped database sessions (`get_db`), token authentication (`get_current_user`), and role authorization (`get_current_admin`).
4. **Automated Documentation**: Generates interactive OpenAPI (Swagger UI) documentation directly from Python type annotations.

---

### 5. Why JWT (JSON Web Tokens)?
1. **Stateless Authorization**: The server does not need to query a session store (like Redis or a DB sessions table) for every HTTP request. The token cryptographically asserts identity, role, and expiration.
2. **Role Claims Embedded**: By embedding `"role": "PATIENT"` or `"ADMIN"` and `"sub": user_id` into the signed payload, authorization checks execute immediately upon decoding and signature verification.
3. **Decoupled Architecture**: Enables seamless horizontal scaling across stateless container replicas behind a load balancer without sticky sessions.

---

### 6. How Password Hashing Works
We use **Argon2id** (via `argon2-cffi`):
- **Why Not SHA-256 or MD5?** General-purpose hash functions are designed to be fast. An attacker using modern GPUs can compute billions of SHA-256 hashes per second.
- **Why Argon2id over bcrypt?** Argon2 was the winner of the Password Hashing Competition (PHC). Argon2id is a hybrid variant that is both CPU-intensive and **memory-hard**, preventing attackers from running parallel brute-force attacks on GPUs or ASICs.
- **Salting**: Each password hash automatically receives a unique cryptographically random salt to defeat precomputed rainbow table attacks.

---

### 7. How Authorization Works
Authorization follows a strict two-layer model:
1. **Role-Based Access Control (RBAC)**:
   - Evaluated via `get_current_admin` dependency in `api/deps.py`.
   - If `current_user.role != "ADMIN"`, request is immediately rejected with `403 Forbidden`.
   - Used to guard centre and test catalog management endpoints.
2. **Resource Ownership Authorization (Anti-IDOR)**:
   - When a patient retrieves (`GET /api/v1/bookings/{id}`) or cancels a booking, `BookingService` verifies:
     ```python
     if current_user.role != UserRole.ADMIN.value and booking.user_id != current_user.id:
         raise AuthorizationError("You do not have access to this booking.")
     ```
   - The user ID is retrieved exclusively from the cryptographically verified JWT token, never trusted from client parameters.

---

### 8. How Payment Simulation Works
In `POST /api/v1/payments`:
1. Looks up the booking by `booking_id`.
2. Validates ownership (patient owns booking or is admin).
3. Asserts the booking is in `PENDING` status.
4. Generates a unique provider payment reference (e.g. `pay_sim_...`).
5. In a **single atomic database transaction**:
   - Creates a `Payment` entity with `status = "SUCCESS"` (or `"FAILED"`).
   - Updates `booking.status = "CONFIRMED"` (or `"FAILED"`).
   - Commits both changes simultaneously.

---

### 9. EXACTLY How Webhook Idempotency Works
Webhook idempotency prevents duplicate processing when payment providers retry delivery:
1. **Incoming Request**: The provider sends a webhook containing `event_id`.
2. **Pre-Check**: Query `PaymentWebhookEvent` for `event_id`. If it already exists, return `200 OK` with `"already_processed"`.
3. **Open Transaction**: If not found, start a database transaction.
4. **Insert Ledger Record**: Insert `PaymentWebhookEvent(event_id=..., ...)`.
5. **State Transition**: Locate the booking, apply state machine transition (`PENDING` -> `CONFIRMED`), and record the payment.
6. **Commit**: Persist all changes atomically.

---

### 10. Why `event_id` Has a UNIQUE Constraint
In distributed systems, checking `if event_exists: return` in application code is susceptible to a **Time-of-Check to Time-of-Use (TOCTOU) race condition**. If two duplicate webhooks hit different server instances at the same millisecond, both instances might execute the check before either has committed the insert.

The **database-level `UNIQUE` constraint on `event_id`** serves as the ultimate source of truth. The database engine's B-Tree index locking enforces that exactly one transaction acquires the write lock and succeeds, while the second transaction fails immediately with a unique constraint violation (`IntegrityError`).

---

### 11. What Happens If Two Identical Webhooks Arrive Concurrently?
1. Both requests arrive at worker 1 and worker 2 simultaneously.
2. Both query `SELECT ... FROM payment_webhook_events WHERE event_id = 'evt_123'` and both find 0 rows.
3. Both start a database transaction.
4. Worker 1 inserts `evt_123` and commits.
5. Worker 2 attempts to insert `evt_123`. PostgreSQL detects the unique index violation and raises an `IntegrityError`.
6. Worker 2's `try...except IntegrityError` block catches the exception and issues `db.rollback()`.
7. Worker 2 queries the current booking state and returns a clean `200 OK` response:
   ```json
   {
     "status": "already_processed",
     "event_id": "evt_123",
     "message": "Webhook event was processed concurrently (idempotent response)."
   }
   ```
8. **Result**: Zero duplicate payments, zero duplicate bookings, zero state corruption, zero 500 errors.

---

### 12. Booking State Transition Explanation
Booking status transitions are strictly governed by a centralized dictionary in `BookingService`:
```python
VALID_TRANSITIONS = {
    BookingStatus.PENDING.value: {
        BookingStatus.CONFIRMED.value,
        BookingStatus.FAILED.value,
        BookingStatus.CANCELLED.value,
    },
    BookingStatus.CONFIRMED.value: set(),
    BookingStatus.FAILED.value: set(),
    BookingStatus.CANCELLED.value: set(),
}
```
- A booking begins as `PENDING`.
- From `PENDING`, it can transition to `CONFIRMED` (payment success), `FAILED` (payment failed), or `CANCELLED` (user cancellation).
- `CONFIRMED`, `FAILED`, and `CANCELLED` are terminal states. A cancelled appointment cannot be confirmed, and a failed appointment cannot be paid for without creating a fresh booking.

---

### 13. Important Database Indexes
1. **`users.email` (UNIQUE)**: Guarantees unique user accounts and provides $O(1)$ B-Tree index lookup during login.
2. **`payment_webhook_events.event_id` (UNIQUE)**: Enforces idempotency at the database storage layer and speeds up pre-check queries.
3. **`payments.provider_payment_id` (UNIQUE)**: Prevents recording duplicate financial transactions from payment gateways.
4. **`bookings.user_id`**: Accelerates patient booking history queries (`GET /api/v1/bookings`).
5. **`bookings.status`**: Optimizes queries filtering pending or confirmed bookings.
6. **`centre_tests (centre_id, test_id)` (Composite PK)**: Enforces that a centre cannot offer the same test twice with conflicting prices, and provides fast index scans on joins.

---

### 14. Important Trade-offs
1. **Synchronous vs. Asynchronous Database Driver**:
   - *Decision*: Synchronous SQLAlchemy 2.0 with connection pooling.
   - *Rationale*: Eliminates asynchronous event-loop transaction bugs and makes transaction demarcation obvious for junior engineers.
2. **Snapshot Amount in `bookings.amount`**:
   - *Decision*: Duplicate the test price from `centre_tests` into `bookings.amount` at booking creation.
   - *Rationale*: Denormalizes one field to guarantee financial immutability. If test prices increase next month, past bookings remain historically accurate.
3. **Relational Table Idempotency Ledger vs. Redis**:
   - *Decision*: Store webhook events in PostgreSQL rather than an in-memory Redis cache.
   - *Rationale*: Guarantees ACID transactional durability alongside payment records without introducing extra infrastructure.

---

### 15. What Could Be Improved for Production?
1. **Capacity & Slot Limits**: Add a `slots` or `capacity` model per centre with row-level locks (`SELECT ... FOR UPDATE`) to prevent overbooking the same time slot.
2. **Transactional Outbox Pattern**: When a booking is confirmed, insert an event into an `outbox` table within the same transaction to reliably publish email/SMS notifications via a background worker.
3. **Payment Signature Verification**: Support provider-specific public key signatures (e.g., Stripe RSA or webhook timestamp tolerance verification against replay attacks).
4. **Rate Limiting**: Add IP-based and user-based token bucket rate limiting on auth endpoints (`/login`, `/signup`).

---

## Part 2: 15 Realistic Interview Questions & Model Answers

### Q1: Why did you choose to store `amount` on the `bookings` table when the price is already in `centre_tests`?
> **Answer**: "This is the principle of **historical snapshot pricing**. In a diagnostic healthcare system, test prices frequently change due to inflation, seasonal discounts, or clinic renegotiations. If we computed the booking amount on the fly via a foreign key join to `centre_tests`, updating a test's price from ₹500 to ₹800 tomorrow would retroactively alter the reported amount of bookings completed six months ago, corrupting financial reports and tax audits. By capturing `amount` as a snapshot in `bookings.amount` at the moment of creation, the booking contract remains permanently immutable."

---

### Q2: What happens if two identical payment webhooks arrive at the exact same millisecond? Walk me through the execution.
> **Answer**: "Both requests will pass the initial `SELECT` pre-check because neither transaction has committed yet. Both requests will enter the write block. One transaction will successfully execute the `INSERT` into `payment_webhook_events`. The second transaction will attempt the same insert, but PostgreSQL's B-Tree unique index on `event_id` will immediately reject it with an `IntegrityError`. Our service catches `IntegrityError`, issues a `db.rollback()`, queries the current state, and safely returns an idempotent `200 OK` with status `already_processed`. As a result, no duplicate payment is created, no duplicate booking is created, and the client receives a successful response."

---

### Q3: Why is checking for duplicate webhook events in Redis or Python memory insufficient?
> **Answer**: "In a production cloud deployment, backend servers are distributed across multiple container instances or worker processes behind a load balancer. A Python in-memory `set` or dictionary is local to a single process; if request 1 hits Container A and request 2 hits Container B, Container B's memory knows nothing about request 1. Even with Redis, network partitions or race conditions between Redis check and SQL commit can allow duplicates. The relational database is our single source of truth; enforcing uniqueness via a database constraint guarantees consistency regardless of container topology."

---

### Q4: How did you implement Role-Based Access Control, and how do you protect against IDOR vulnerabilities?
> **Answer**: "We implement authorization in two tiers. First, for administrative endpoints like adding centres or tests, we use a FastAPI dependency `get_current_admin` that decodes the JWT and validates `current_user.role == 'ADMIN'`, returning `403 Forbidden` if unauthorized. Second, to prevent Insecure Direct Object References (IDOR), endpoints that access individual bookings never rely on a client-supplied user ID. Instead, `BookingService` checks that `booking.user_id == current_user.id` (where `current_user` is extracted strictly from the validated JWT subject). If a patient attempts to access another patient's booking ID, the service raises an `AuthorizationError`."

---

### Q5: Why did you use Argon2id instead of bcrypt or MD5 for password hashing?
> **Answer**: "MD5 and SHA-256 are general cryptographic hash functions designed to be fast, making them easily crackable by modern GPUs capable of billions of computations per second. While bcrypt was the industry standard for many years, it is only compute-hard, not memory-hard. Argon2id, which won the Password Hashing Competition, is a hybrid algorithm that requires both significant CPU time and substantial RAM to compute. This memory-hardness effectively neutralizes GPU and ASIC cracking attacks."

---

### Q6: Walk me through your booking state machine. What prevents a user from confirming a cancelled booking?
> **Answer**: "Our state machine is centralized in `BookingService.VALID_TRANSITIONS`. It explicitly maps each status to allowed destination statuses: `PENDING` can transition to `CONFIRMED`, `FAILED`, or `CANCELLED`. The states `CONFIRMED`, `FAILED`, and `CANCELLED` are terminal and map to empty sets. When a transition is requested, `BookingService.validate_transition` asserts that the target status exists in the current status's allowed set. If someone attempts to confirm a booking that is currently `CANCELLED`, the service raises an `InvalidStateTransitionError`, mapped to an HTTP 400 Bad Request."

---

### Q7: Why use SQLAlchemy 2.0 styled syntax (`select(...)`) instead of legacy 1.x `session.query(...)`?
> **Answer**: "SQLAlchemy 2.0 unified the query interface across Core and ORM using standard `select()` constructs. It provides full type-annotation compatibility with Python's typing system (`Mapped[...]` and `mapped_column`), enables static type checking via Mypy, and eliminates the ambiguity between Core SQL expressions and ORM query objects."

---

### Q8: What database indexes did you create and why?
> **Answer**: 
> 1. `users.email` (UNIQUE): Ensures account uniqueness and speeds up login lookups to $O(1)$.
> 2. `payment_webhook_events.event_id` (UNIQUE): Enforces webhook idempotency and enables fast deduplication pre-checks.
> 3. `payments.provider_payment_id` (UNIQUE): Ensures provider transaction IDs are never recorded twice.
> 4. `bookings.user_id`: Essential for filtering appointments by patient (`SELECT * FROM bookings WHERE user_id = ?`).
> 5. `bookings.status`: Optimizes operational queries for pending appointments.
> 6. Composite primary key on `centre_tests(centre_id, test_id)`: Uniquely identifies test offerings per centre and optimizes foreign key joins."

---

### Q9: How are database transactions handled during simulated payment processing?
> **Answer**: "In `PaymentService.simulate_payment`, both the creation of the `Payment` record and the status update of the `Booking` record occur within the same SQLAlchemy session. We execute `PaymentRepository.create(db, payment)` and `BookingRepository.update(db, booking)` followed by a single `db.commit()`. If an exception occurs prior to commit, neither entity is written, maintaining absolute ACID consistency."

---

### Q10: How do you prevent internal database connection strings and SQL traces from leaking to API clients?
> **Answer**: "In `app/main.py`, we implement custom FastAPI exception handlers for `IntegrityError`, `SQLAlchemyError`, and standard `Exception`. When a database violation occurs, our handler logs the internal technical details to the application logger, but returns a sanitized JSON response:
> `{"detail": "A database constraint violation occurred."}` with an HTTP 409 status code. Raw database error messages, table names, and query parameters are never exposed to the client."

---

### Q11: Why did you model `centre_tests` as an association table with a price rather than putting `price` directly in `diagnostic_tests`?
> **Answer**: "Putting price on `diagnostic_tests` assumes that every diagnostic clinic in the country charges the exact same fee for a test. In reality, a specialized central hospital in Indiranagar may have higher equipment costs and charge ₹600 for a CBC, while a smaller community clinic in another district might charge ₹400. Modelling `centre_tests` with `centre_id`, `test_id`, and `price` represents real-world many-to-many pricing dynamics."

---

### Q12: How does your JWT authentication handle token expiration?
> **Answer**: "When we generate a token in `create_access_token`, we include an `exp` (expiration) timestamp claim set to `current_time + ACCESS_TOKEN_EXPIRE_MINUTES`. In our `get_current_user` dependency, `pyjwt.decode()` validates both the cryptographic signature and the `exp` claim. If the current time exceeds `exp`, PyJWT raises `jwt.ExpiredSignatureError`. Our dependency catches this and raises `AuthenticationError('Authentication token has expired.')`, which returns an HTTP 401 Unauthorized."

---

### Q13: What is the purpose of Alembic in this project? Why not just use `Base.metadata.create_all()`?
> **Answer**: "`Base.metadata.create_all()` only creates tables if they do not exist; it cannot alter existing columns, add indexes, or rename fields on an active database without dropping data. Alembic provides version-controlled, incremental migration scripts that can upgrade and downgrade database schemas safely in production environments."

---

### Q14: How does the application handle appointment date validation?
> **Answer**: "We validate appointment dates at the request boundary using a Pydantic `field_validator` in `BookingCreateRequest`. The validator checks that the provided `appointment_at` datetime is strictly in the future compared to the current UTC timestamp. If a client attempts to book an appointment in the past, Pydantic immediately rejects the request with an HTTP 422 Unprocessable Entity before database queries are made."

---

### Q15: If this service were deployed to handle 10,000 requests per second, what bottlenecks would arise and how would you resolve them?
> **Answer**: 
> 1. **Database Connection Pool Exhaustion**: PostgreSQL connections are resource-intensive. We would deploy **PgBouncer** in transaction pooling mode between FastAPI and PostgreSQL.
> 2. **Catalogue Read Queries**: Tests and centre offerings rarely change during the day. We would place a **Redis caching layer** in front of `GET /api/v1/centres` and `GET /api/v1/tests` with cache invalidation on admin updates.
> 3. **Appointment Concurrency**: To prevent overbooking specific time slots, we would implement slot reservation using Redis distributed locks or PostgreSQL row-level locks (`SELECT ... FOR UPDATE`) on appointment slots.
> 4. **Asynchronous Webhook Processing**: We would decouple webhook reception from processing: the webhook endpoint writes the raw payload to an append-only queue (Kafka or AWS SQS) and immediately acknowledges 200 OK, while background workers process idempotency and state transitions."
