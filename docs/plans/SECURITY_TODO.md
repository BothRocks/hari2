# Security TODOs (v2)

Security findings from the audit, targeted for v2 production readiness.

| # | Issue | Priority | Status |
|---|-------|----------|--------|
| 1 | OAuth CSRF / session swapping | HIGH | Done (3f8f4e9) |
| 2 | SSRF via URL ingestion | HIGH | Done (c96f276) |
| 3 | Webhook authenticity optional | MEDIUM | Done (db76a00) |
| 4 | API keys stored in plaintext | MEDIUM | Done (9e6c69d) |
| 5 | Unbounded PDF upload size | MEDIUM | Not started |
| 6 | Insecure default secrets | LOW | Not started |

---

## 1) OAuth login CSRF / session swapping risk (HIGH) - DONE

**Commit**: 3f8f4e9 - sec: add OAuth CSRF protection with state parameter

**Fix implemented**: State parameter validation in OAuth flow.

---

## 2) SSRF via URL ingestion (HIGH) - DONE

**Commit**: c96f276 - sec: add SSRF protection for URL ingestion

**Fix implemented**: URL validation blocking private IPs and internal networks.

---

## 3) Webhook authenticity is optional (MEDIUM) - DONE

**Commit**: db76a00 - sec: enforce webhook verification in production

**Fix implemented**: Webhook verification required in production environment.

---

## 4) API keys stored in plaintext (MEDIUM) - DONE

**Commit**: 9e6c69d - sec: hash API keys with SHA-256 + pepper

**Fix implemented**: API keys hashed with SHA-256 and server-side pepper.

---

## 5) Unbounded PDF upload size (MEDIUM) - NOT STARTED

**Where**: `backend/app/api/documents.py`

**Issue**: The upload endpoint reads the entire PDF into memory with no size limit.

**Impact**: Memory exhaustion and denial of service.

**Proposed fix**:
- Enforce a maximum upload size at the server level (ASGI middleware or reverse proxy).
- Stream uploads to disk or object storage instead of reading into memory.
- Reject overly large files with a clear error response.

**Note**: nginx config now sets `client_max_body_size 50M` which provides basic protection at the reverse proxy level.

---

## 6) Insecure default secrets (LOW) - NOT STARTED

**Where**: `backend/app/core/config.py`

**Issue**: Default `secret_key` and `admin_api_key` values are insecure if deployed without proper environment overrides.

**Impact**: Token forgery or unauthorized admin access if defaults slip into production.

**Proposed fix**:
- Remove default values and require explicit configuration for production.
- Fail startup if secrets are missing outside `development`.
- Document secure secret generation and rotation.
