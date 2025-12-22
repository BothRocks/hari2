# Claude Code Instructions

Project-specific instructions for Claude Code.

## Database Setup

PostgreSQL 17 with pgvector extension.

```bash
# Create database (macOS with Homebrew)
/opt/homebrew/opt/postgresql@17/bin/createdb hari2
/opt/homebrew/opt/postgresql@17/bin/psql hari2 -c "CREATE EXTENSION vector;"

# Run migrations
cd backend
uv run alembic upgrade head
```

Database: `hari2`
Connection: `postgresql+asyncpg://localhost:5432/hari2`

## Testing

All code changes require test coverage.

```bash
pytest -v
```

Tests location: `tests/` following pattern `tests/test_*.py`

## Frontend Design

Use `/frontend-design` for frontend design assistance.

## Deployment

Use `/deploy` for deployment workflow guidance.
