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

# Google OAuth (for user login)
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/callback

# Google Drive API (for folder sync)
GOOGLE_SERVICE_ACCOUNT_JSON=credentials/service-account.json

# Tavily API (for agentic web search)
TAVILY_API_KEY=tvly-...

# Admin users (comma-separated emails get ADMIN role on login)
ADMIN_EMAILS=your-email@example.com
```

### Google Setup

**OAuth (user login):**
1. Go to Google Cloud Console → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID (Web application)
3. Add redirect URI: `http://localhost:8000/api/auth/callback`

**Service Account (Drive sync):**
1. Create a service account in Google Cloud Console
2. Download JSON key to `backend/credentials/service-account.json`
3. Users share Drive folders with the service account email

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

### 4. Authentication

**Option A: Google OAuth (recommended)**
- Click "Sign in with Google" in the frontend
- Requires OAuth credentials configured

**Option B: API Key (for scripts/testing)**
```bash
curl -H "X-API-Key: gorgonzola" http://localhost:8000/api/...
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

**Completed (Background Processing & OAuth):**
- Google OAuth SSO with session-based authentication
- User and Session models with secure token hashing
- Asyncio job queue with PostgreSQL persistence
- Job worker with crash recovery and structured logging
- Google Drive service with service account authentication
- Drive folder sync with duplicate detection
- Scheduled Drive polling (configurable interval)
- Frontend: Auth context with login/logout
- Frontend: Jobs admin page (stats, filtering, bulk retry)
- Frontend: Drive admin page (folder registration, sync)

**Completed (Agentic Query System):**
- LangGraph integration with StateGraph workflow
- Agent nodes: Retriever, Evaluator, Router, Researcher, Generator
- Tavily web search for external knowledge
- SSE streaming for real-time agent reasoning display
- Frontend: ThinkingSteps component shows agent progress
- Frontend: ChatMessage with internal/external source attribution
- Max iterations guardrail (default: 3)

**Completed (Document Quality & Review):**
- Two-pass metadata validation (rule-based + LLM correction)
- Auto-detection of generic titles, authors, keywords
- `needs_review` flag with `review_reasons` tracking
- Admin document detail page with inline editing
- Re-process and Mark as Reviewed actions
- Needs Review filter on documents list

**Completed (Chatbot Integrations):**
- Telegram bot for document ingestion (PDF upload, URL submission)
- Slack bot for document ingestion (PDF upload, URL submission)
- Shared BotBase abstraction for code reuse
- PDF archival to Google Drive before processing
- Status check for last upload per user
- Markdown rendering for chat responses

**Admin Pages:**
- `/admin/jobs` - Background job monitoring and management
- `/admin/drive` - Google Drive folder sync configuration
- `/admin/documents` - Document list with quality filters
- `/admin/documents/:id` - Document detail with editing

**API Endpoints (Key):**
- `POST /api/query/stream` - SSE streaming agentic query
- `POST /api/query/agent` - Non-streaming agentic query
- `GET /api/documents/{id}` - Document details
- `PUT /api/documents/{id}` - Update title/author
- `POST /api/documents/{id}/reprocess` - Re-run pipeline
- `POST /api/documents/{id}/review` - Clear needs_review flag
- `POST /api/integrations/telegram/webhook` - Telegram bot webhook
- `POST /api/integrations/slack/events` - Slack bot events

## Chatbot Setup

### Telegram Bot

1. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram
2. Copy the bot token to `TELEGRAM_BOT_TOKEN` in `.env`
3. Set the webhook URL (replace with your public URL):
   ```bash
   curl -X POST "http://localhost:8000/api/integrations/telegram/set-webhook?webhook_url=https://your-domain.com/api/integrations/telegram/webhook"
   ```

### Slack Bot

1. Create a Slack App at [api.slack.com/apps](https://api.slack.com/apps)
2. Enable "Event Subscriptions" and set Request URL to `https://your-domain.com/api/integrations/slack/events`
3. Subscribe to bot events: `message.channels`, `message.groups`, `message.im`
4. Add OAuth scopes: `chat:write`, `files:read`
5. Install to workspace and copy tokens to `.env`:
   - `SLACK_BOT_TOKEN` - Bot User OAuth Token (xoxb-...)
   - `SLACK_SIGNING_SECRET` - From Basic Information page

### Drive Uploads Folder

1. Create a folder in Google Drive for PDF archival
2. Share it with your service account email (Editor access)
3. Copy the folder ID to `DRIVE_UPLOADS_FOLDER_ID` in `.env`

The folder ID is the last part of the Drive URL:
`https://drive.google.com/drive/folders/THIS_IS_THE_FOLDER_ID`
