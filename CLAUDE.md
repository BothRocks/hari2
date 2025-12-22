# Claude Code Instructions

Project-specific instructions for Claude Code.

## Testing

**All code changes require test coverage.**

```bash
# Run tests
pytest -v

# Run with coverage
pytest -v --cov=. --cov-report=term-missing
```

Tests location: `tests/` following pattern `tests/test_*.py`

### Test Markers
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.live` - Live API tests (external services)

## Database Migrations

Using Alembic. Migrations run automatically during deployment.

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply locally
alembic upgrade head

# Check current version
alembic current
```

**Important:** Auto-generated migrations often include spurious changes. Always review and clean up to include only intended changes.

## Deployment

Use `/deploy` slash command for deployment workflow guidance.

Pushing to `main` triggers automatic deployment via GitHub Actions.

## Common Commands

```bash
# Activate venv
source .venv/bin/activate

# Run locally
python -m uvicorn api:app --host 0.0.0.0 --port 8001

# Run tests
pytest -v

# Check CI status
gh run list --limit 5
```
