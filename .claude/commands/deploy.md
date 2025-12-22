# Deployment Workflow

Guide me through the deployment process for this change.

## CI/CD Pipeline

Deployment is automatic via GitHub Actions:

1. `.github/workflows/test.yml` - Runs tests on all branches
2. `.github/workflows/deploy.yml` - Auto-deploys to production on `main`

### Deploy Process (triggered on push to main)
1. Tests run in CI
2. If tests pass, deployment proceeds:
   - Pull latest code
   - Install dependencies
   - Run database migrations
   - Restart service
   - Health check verification

## Pre-Push Checklist

Before pushing to main:

1. **Run all tests locally:**
   ```bash
   pytest -v
   ```
   All tests must pass.

2. **Review your changes:**
   ```bash
   git diff
   git status
   ```

## Post-Push Verification (CRITICAL)

After EVERY push to main:

1. **Monitor GitHub Actions:**
   ```bash
   gh run list --limit 3
   ```
   Wait for workflow to show `completed` status.

2. **If workflow failed, investigate:**
   ```bash
   gh run view <run_id> --log-failed
   ```

3. **Verify production health:**
   ```bash
   curl -s <APP_URL>/health | jq .
   ```
   The `commit` field should match your pushed commit.

4. **If commit doesn't match or health check fails:**
   - Check workflow logs: `gh run view <run_id> --log`
   - Fix the issue and push again immediately

**Do not consider a push complete until the production commit hash matches your push.**

## Debugging Deploy Issues

### Before making deploy script changes:
1. Read the existing deploy.yml carefully
2. Understand the config loading order (env files can override code defaults)
3. Verify paths before committing

### Common pitfalls:
- Production `.env` file overriding config defaults
- Wrong paths in deploy script
- Each deploy script change requires a full CI cycle to test

### When changes don't appear on production:
1. Check `/health` endpoint for current version
2. Confirm deploy ran: `gh run list`
3. If deploy succeeded but changes missing:
   - `.env` file overriding config value
   - Browser caching (frontend changes)
   - Python bytecode cache (rare)
