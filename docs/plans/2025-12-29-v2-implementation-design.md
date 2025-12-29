# v2 Implementation Design

Date: 2025-12-29

## Scope

This document covers the remaining v2 features and security fixes needed for production readiness.

**In scope:**
- Phase 4.3-4.6: Quality control improvements
- Security fixes (6 items from SECURITY_TODO.md)

**Out of scope (moved to v3):**
- Guardrails (cost ceiling, timeout)
- Answer quality validation
- Taxonomy management
- Observability
- LLM-powered intent parsing for document search

---

## Implementation Order

| # | Item | Description | Effort |
|---|------|-------------|--------|
| 1 | 4.5 Slow status | Profile and fix status command latency | Small |
| 2 | 4.3 Author detection | Add author extraction to LLM synthesis | Small |
| 3 | 4.4 Telegram access | Allowlist for authorized users | Small |
| 4 | 4.6 Document search | Search documents via chatbots | Medium |
| 5 | SEC-6 Secrets | Require secrets in production | Small |
| 6 | SEC-5 Upload limits | 350MB PDF upload limit | Small |
| 7 | SEC-3 Webhooks | Enforce webhook verification | Small |
| 8 | SEC-4 API key hash | Hash API keys in database | Medium |
| 9 | SEC-1 OAuth CSRF | State parameter for OAuth | Medium |
| 10 | SEC-2 SSRF | URL validation for ingestion | Medium |

---

## Phase 4: Quality Control

### 4.5 Slow Status Command

**Problem:** Status command in chatbots sometimes responds slowly.

**Root cause investigation:**
- `DriveService` initialization happens on every webhook request, even for status checks
- Two sequential DB queries in `handle_status()` (Job + Document)

**Fix:**
- Lazy-load `DriveService` only when needed for file uploads
- Add logging timestamps to profile actual bottleneck
- Ensure connection pooling is working correctly

**Files:**
- `backend/app/integrations/telegram/webhook.py`
- `backend/app/integrations/slack/events.py`
- `backend/app/integrations/bot_base.py`

---

### 4.3 Author Detection for URLs

**Problem:** Author field often missing for URL sources, even when author is clearly visible on the page (e.g., Substack bylines).

**Current approach:** Relies solely on trafilatura's `extract_metadata()` which parses HTML meta tags.

**Fix:** Add author extraction to LLM synthesis step.

The LLM already processes the full document content to generate title, summary, and keywords. Add author to the output schema:

```python
{
    "title": "...",
    "summary": "...",
    "keywords": [...],
    "author": "..."  # NEW: Extract from bylines, signatures, "Written by...", etc.
}
```

Flow:
1. Trafilatura extracts author from HTML meta tags (first pass)
2. If author is missing or generic, LLM extracts from content (second pass)
3. LLM can see bylines, signatures, "by [Name]" patterns that meta tags miss

**Files:**
- `backend/app/services/pipeline/synthesizer.py` - Update LLM prompt
- `backend/app/services/pipeline/validator.py` - May need adjustment

---

### 4.4 Telegram Bot Access Control

**Problem:** Anyone who discovers the Telegram bot can upload documents.

**Fix:** Add allowlist of authorized Telegram user IDs.

**Implementation:**
- Add `TELEGRAM_ALLOWED_USERS` env var (comma-separated user IDs)
- Check `update.effective_user.id` against allowlist early in `process_update()`
- Return "unauthorized" message for non-allowed users
- Empty allowlist = allow all (development mode)

**Files:**
- `backend/app/core/config.py` - Add setting
- `backend/app/integrations/telegram/bot.py` - Add check

**Slack:** No changes needed. Workspace-level restrictions are sufficient (bot only installed in your workspace).

---

### 4.6 Document Search via Chatbots

**Problem:** Users can upload documents via chatbots but cannot search for them.

**Use cases:**
- "What was that link about separation of concerns we shared yesterday?"
- "Find the PDF Jorge uploaded last week"
- "Show me articles about microservices"

**Approach:** Extend existing HybridSearch with metadata filters (Option A).

The hybrid search already handles natural language well via semantic + keyword search. Add:
- Date range filter (parse "last week", "yesterday", etc.)
- Author filter (parse "by [name]")
- Return document references, not synthesized answers

**Command format:**
```
find <query>
search <query>
```

**Response format:**
```
Found 3 documents:

1. "Separation of Concerns in Microservices"
   Author: Martin Fowler | Added: Dec 15
   https://example.com/article

2. "Clean Architecture Principles"
   Author: Unknown | Added: Dec 12
   [Drive file]

3. ...
```

**Implementation:**

1. Add `search_documents()` method to `bot_base.py`:
   - Parse query for date/author hints
   - Call HybridSearch with filters
   - Format results for chat

2. Extend HybridSearch:
   - Add optional `date_from`, `date_to`, `author` parameters
   - Apply filters to both semantic and keyword search

3. Add command detection in bots:
   - Recognize `find ...` or `search ...` prefix
   - Route to search handler

**Files:**
- `backend/app/integrations/bot_base.py` - Add search handler
- `backend/app/services/search/hybrid.py` - Add filters
- `backend/app/integrations/telegram/bot.py` - Add command routing
- `backend/app/integrations/slack/bot.py` - Add command routing

**v3 enhancement:** LLM-powered intent parsing for more complex queries (Option B).

---

## Phase 5: Security Fixes

### SEC-6: Require Secrets in Production

**Problem:** Default `secret_key` and `admin_api_key` values are insecure if deployed without proper overrides.

**Fix:** Add startup validation.

```python
# In main.py startup
if settings.environment != "development":
    if settings.secret_key == "dev-secret-key-change-in-production":
        raise RuntimeError("SECRET_KEY must be set in production")
    if settings.admin_api_key == "dev-admin-key":
        raise RuntimeError("ADMIN_API_KEY must be set in production")
```

**Files:**
- `backend/app/main.py` - Add startup validation

**Note:** Secrets will be deployed via GitHub Actions, so no complex secret management needed.

---

### SEC-5: Unbounded PDF Upload Size

**Problem:** Upload endpoint reads entire PDF into memory with no size limit.

**Fix:** Add 350MB limit.

**Implementation:**
- Add `MAX_UPLOAD_SIZE_MB` config (default: 350)
- Check `Content-Length` header before reading
- Stream upload with size tracking, reject if exceeded
- Return 413 Payload Too Large with clear message

**Files:**
- `backend/app/core/config.py` - Add setting
- `backend/app/api/documents.py` - Add size check

---

### SEC-3: Webhook Authenticity

**Problem:** Telegram requests not verified. Slack verification skipped if secret not configured.

**Fix: Telegram**
- Add `TELEGRAM_WEBHOOK_SECRET` env var
- Set secret when configuring webhook: `setWebhook?secret_token=...`
- Verify `X-Telegram-Bot-Api-Secret-Token` header matches
- Reject requests with missing/invalid token

**Fix: Slack**
- Already has `slack_signing_secret` config
- Change behavior: require in production, skip only in development
- Reject unsigned requests in production

**Files:**
- `backend/app/core/config.py` - Add Telegram secret setting
- `backend/app/integrations/telegram/webhook.py` - Add verification
- `backend/app/integrations/slack/events.py` - Enforce in production

---

### SEC-4: API Keys Stored in Plaintext

**Problem:** User API keys stored as plaintext in database. DB leak exposes all keys.

**Fix:** Store hashed keys.

**Implementation:**
1. Add migration: `api_key_hash` column to users table
2. Hash algorithm: SHA-256 with server-side pepper (derived from `secret_key`)
3. Update auth to compare hashes with constant-time comparison
4. One-time migration script to hash existing keys
5. Show plaintext key only once at creation time

**Files:**
- `backend/alembic/versions/xxx_add_api_key_hash.py` - Migration
- `backend/app/models/user.py` - Add column
- `backend/app/core/deps.py` - Update auth comparison
- `backend/app/core/security.py` - Add hashing functions

---

### SEC-1: OAuth CSRF / Session Swapping

**Problem:** OAuth flow has no `state` parameter. Vulnerable to login CSRF.

**Fix:** Add state parameter with cookie storage.

**Current flow:**
1. `/login` → redirect to Google (no state)
2. `/callback` → accepts any code

**Fixed flow:**
1. `/login` → generate random state, store in HTTP-only cookie, redirect to Google with state
2. `/callback` → verify state from cookie matches state from Google, reject mismatch

**Implementation:**
- Generate state: `secrets.token_urlsafe(32)`
- Cookie: `oauth_state`, 10-minute expiry, `httponly=True`, `samesite="lax"`
- Add `state` parameter to Google authorization URL
- Validate in callback, clear cookie after use

**Files:**
- `backend/app/api/auth.py` - Add state handling
- `backend/app/services/auth/oauth.py` - Accept state parameter

---

### SEC-2: SSRF via URL Ingestion

**Problem:** URL fetcher accepts any URL, follows redirects, no private IP protection.

**Fix:** Validate URLs and redirect destinations.

**Blocked ranges:**
- Private: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
- Loopback: `127.0.0.0/8`, `localhost`
- Link-local: `169.254.0.0/16`
- Metadata: `169.254.169.254`

**Implementation:**

```python
def validate_url(url: str) -> None:
    """Validate URL is safe to fetch. Raises ValueError if not."""
    parsed = urlparse(url)

    # Require http/https
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid scheme: {parsed.scheme}")

    # Resolve hostname to IP
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {parsed.hostname}")

    # Check against blocked ranges
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        raise ValueError(f"Blocked IP range: {ip}")
```

**Redirect handling:**
- Use `follow_redirects=False`
- Manually follow redirects, validating each destination
- This preserves legitimate redirects (http→https, URL shorteners) while blocking redirect-to-private attacks

```python
async def fetch_with_validated_redirects(url: str, max_redirects: int = 10):
    current_url = url
    for _ in range(max_redirects):
        validate_url(current_url)  # Block private IPs
        response = await client.get(current_url, follow_redirects=False)
        if response.is_redirect:
            current_url = response.headers["location"]
            continue
        return response
    raise ValueError("Too many redirects")
```

**Note:** Slack file downloads go to `files.slack.com` which is safe. If using a shared fetcher, whitelist Slack domains.

**Files:**
- `backend/app/services/pipeline/url_fetcher.py` - Add validation
- `backend/app/core/security.py` - Add `validate_url()` function

---

## Testing Requirements

Each item should include tests:

| Item | Test Coverage |
|------|---------------|
| 4.5 Slow status | Profile logs, verify lazy loading |
| 4.3 Author detection | Test LLM prompt extracts author from bylines |
| 4.4 Telegram access | Test allowlist blocks unauthorized users |
| 4.6 Document search | Test search via bot, filters work |
| SEC-6 Secrets | Test startup fails with default secrets in prod |
| SEC-5 Upload limits | Test 350MB limit, 413 response |
| SEC-3 Webhooks | Test verification rejects invalid tokens |
| SEC-4 API key hash | Test hash comparison, migration |
| SEC-1 OAuth CSRF | Test state validation, reject mismatches |
| SEC-2 SSRF | Test blocks private IPs, allows valid URLs |

---

## Environment Variables (New)

```bash
# Telegram access control
TELEGRAM_ALLOWED_USERS=123456789,987654321

# Telegram webhook verification
TELEGRAM_WEBHOOK_SECRET=your-secret-token

# Upload limits
MAX_UPLOAD_SIZE_MB=350
```

---

## Migration Notes

- SEC-4 requires database migration for `api_key_hash` column
- Existing API keys need one-time hashing migration
- No breaking changes to API contracts
