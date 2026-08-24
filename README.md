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
- hotel details at `GET /api/v1/hotels/{hotel_id}`;
- room types at `GET /api/v1/hotels/{hotel_id}/rooms`;
- an asynchronous SQLAlchemy session and an Alembic-managed PostgreSQL schema;
- Redis cache-aside support for catalog reference data.

The hotel collection endpoint is intentionally reserved for the availability
search added in the next stage. The booking lifecycle is not available yet.

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
