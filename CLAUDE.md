# Claude Code Instructions

Project-specific instructions for Claude Code.

## Quick Start

### 1. Database Setup

PostgreSQL 17 with pgvector extension:

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

### 2. Environment Variables

Create `backend/.env`:

```bash
DATABASE_URL=postgresql+asyncpg://localhost:5432/hari2
SECRET_KEY=your-secret-key-here
ADMIN_API_KEY=gorgonzola

# LLM APIs (at least one required)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

### 3. Run the Application

```bash
# Terminal 1: Backend
cd backend
uv run uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

Backend: http://localhost:8000
Frontend: http://localhost:5173

### 4. Frontend Authentication

Set API key in browser console:
```javascript
localStorage.setItem('api_key', 'gorgonzola')
```

## Uploading Documents

### Using the Script

```bash
# Upload a URL
./scripts/upload.sh https://example.com/article

# Upload a PDF
./scripts/upload.sh document.pdf
```

### Using curl

```bash
# URL
curl -X POST http://localhost:8000/api/documents/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: gorgonzola" \
  -d '{"url": "https://example.com/article"}'

# PDF
curl -X POST http://localhost:8000/api/documents/upload \
  -H "X-API-Key: gorgonzola" \
  -F "file=@document.pdf"
```

## Testing

All code changes require test coverage.

```bash
cd backend
uv run pytest -v
```

Tests location: `backend/tests/` following pattern `test_*.py`

## Key Technical Notes

### PostgreSQL Enum Types
The `processing_status` enum values are uppercase: `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`.

Raw SQL must cast strings to enum type:
```sql
WHERE processing_status = 'COMPLETED'::processingstatus
```

### asyncpg Parameter Binding
Use `cast(:param as type)` instead of `:param::type` syntax:
```sql
-- Correct
embedding <=> cast(:embedding as vector)

-- Wrong (asyncpg syntax error)
embedding <=> :embedding::vector
```

## Frontend Design

Use `/frontend-design` for frontend design assistance.

## Deployment

Use `/deploy` for deployment workflow guidance.

## MVP Status

**Completed (Phase 1-8):**
- FastAPI backend with async PostgreSQL
- Document ingestion pipeline (URL + PDF)
- Extractive summarization (Sumy/TextRank)
- LLM synthesis (Anthropic Claude)
- Vector embeddings (OpenAI)
- Hybrid search (keyword + semantic)
- RAG query endpoint
- React frontend with chat interface
- Admin dashboard for document management
