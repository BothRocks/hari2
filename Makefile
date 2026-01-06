.PHONY: dev test

# Start all development services (backend, frontend, ngrok)
# Requires: pip install honcho
dev:
	honcho -f Procfile.dev start

# Run backend tests
test:
	cd backend && uv run pytest -v
