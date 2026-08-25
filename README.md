# FastAPI Hotel Booking

An API-only hotel catalog and booking service built with FastAPI, PostgreSQL,
Redis, and Celery.

The project is currently being rebuilt around a database-backed catalog,
transaction-safe reservations, structured logging, and reproducible tooling.
Complete setup and API documentation will be added in the documentation stage.

## Development status

The API foundation currently provides:

- a health endpoint at `GET /health`;
- user registration at `POST /api/v1/auth/register`;
- OAuth2 Bearer tokens at `POST /api/v1/auth/token`;
- the current user endpoint at `GET /api/v1/auth/me`;
- availability search at `GET /api/v1/hotels`;
- hotel details at `GET /api/v1/hotels/{hotel_id}`;
- room types at `GET /api/v1/hotels/{hotel_id}/rooms`;
- authenticated reservation creation, confirmation, listing, and cancellation;
- Celery workflows for hold expiration and confirmation emails;
- an asynchronous SQLAlchemy session and an Alembic-managed PostgreSQL schema;
- Redis cache-aside support for catalog reference data.

## Catalog seed

Apply migrations and load the local USD catalog:

```bash
uv run alembic upgrade head
uv run python -m app.catalog.seed
```

The seed command is idempotent. Re-running it updates the catalog by hotel slug
and room type code without creating duplicates.

Catalog cache keys are versioned and expire automatically. A cache miss or Redis
failure falls back to PostgreSQL, so Redis is never the source of catalog data.
The cache and Celery broker use separate Redis logical databases through
`REDIS_CACHE_URL` and `CELERY_BROKER_URL`.

## Hotel search

Search requires `city`, `date_from`, and `date_to`. Optional filters are
`min_price`, `max_price`, `limit`, and `offset`.

```bash
curl "http://localhost:8000/api/v1/hotels?city=Seattle&date_from=2027-01-10&date_to=2027-01-13&min_price=100.00&max_price=250.00"
```

Dates use the half-open interval `[date_from, date_to)`, so a new stay may begin
on another booking's checkout date. Searches are limited to 30 nights. Each room
result includes the current `rooms_left`, its one-night USD price, and the total
cost for the requested stay.

Confirmed bookings and unexpired reservation holds occupy inventory. Cancelled,
expired, and time-expired holds do not affect availability. Search results are
calculated directly in PostgreSQL and are not cached.

## Booking lifecycle

Booking endpoints require an OAuth2 Bearer token:

```text
GET    /api/v1/bookings
GET    /api/v1/bookings/{booking_id}
POST   /api/v1/bookings
POST   /api/v1/bookings/{booking_id}/confirm
DELETE /api/v1/bookings/{booking_id}
```

Creating a booking places a 15-minute `created` hold. Confirming it changes the
status to `confirmed`; deleting it performs a soft transition to `cancelled`.
An unconfirmed hold becomes effectively `expired` as soon as its deadline
passes, even if no background worker has run yet.

```text
created ──> confirmed ──> cancelled
   │
   └──────> expired
```

The API calculates and stores a price snapshot in USD using `Decimal`, so later
catalog price changes do not alter an existing booking. Confirmation and
cancellation are idempotent when the booking is already in the requested final
state. A booking owned by another user is returned as `404`, avoiding disclosure
of its existence.

Reservation creation locks the selected room type in PostgreSQL while it counts
overlapping active bookings and inserts the new hold in one transaction. This
serializes concurrent requests for the same inventory and prevents successful
bookings from exceeding `RoomType.quantity`.

## Background workflows

Start a worker and Beat in separate terminals after PostgreSQL and Redis are
available:

```bash
uv run celery -A app.tasks.celery:celery worker --loglevel=INFO
uv run celery -A app.tasks.celery:celery beat --loglevel=INFO
```

Beat periodically runs two workflows:

- `bookings.expire_holds` persists due `created` holds as `expired` with one
  idempotent PostgreSQL update;
- `notifications.dispatch_pending` publishes due notification IDs for delivery.

Availability does not depend on Beat running on time. Search and reservation
creation ignore a `created` hold as soon as its `expires_at` deadline passes,
even before the background update persists the `expired` status.

Confirming a booking writes both the `confirmed` status and one notification
outbox row in the same transaction. Redis or SMTP downtime therefore cannot
roll back the booking. The dispatcher can publish the same ID more than once;
the worker uses a PostgreSQL delivery lease to prevent parallel sends and to
recover work abandoned by a crashed process.

Temporary delivery failures use exponential backoff and become `failed` after
`NOTIFICATION_MAX_ATTEMPTS`. Permanent SMTP rejection fails immediately. Logs
contain notification and booking IDs, but never the full recipient address.

Local SMTP defaults to Mailpit at `localhost:1025`; its web interface normally
runs at `http://localhost:8025`. SMTP authentication and a production mail
provider are intentionally outside the current project scope.

Email delivery is at-least-once. A worker crash after SMTP accepts a message but
before PostgreSQL records `sent` can produce a duplicate. Exactly-once delivery
would require an email provider with an idempotency key, which plain SMTP does
not provide.
