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
- an asynchronous SQLAlchemy session and an Alembic-managed PostgreSQL schema.

The hotel catalog, search, and booking lifecycle are intentionally unavailable
while their legacy implementations are being replaced in the next stages.
