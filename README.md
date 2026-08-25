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
- an asynchronous SQLAlchemy session and an Alembic-managed PostgreSQL schema;
- Redis cache-aside support for catalog reference data.

The booking persistence model exists so search results can account for active
reservations. Booking creation and lifecycle endpoints are not available yet.

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
