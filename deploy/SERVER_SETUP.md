# Server Setup Guide

One-time setup steps for deploying Hari2 to production.

## Prerequisites

- Hetzner server with Ubuntu/Debian
- PostgreSQL 17 with pgvector extension
- nginx installed
- certbot installed
- `uv` installed globally (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node.js 20+ installed

## 1. Create Database

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE hari2;
\c hari2
CREATE EXTENSION vector;
\q
```

## 2. Setup Application Directory

```bash
# Clone repo (as hari user)
cd ~
git clone git@github.com:YOUR_USERNAME/hari2.git app2
cd app2

# Create backend env file
cp deploy/.env.production.example backend/.env
# Edit backend/.env with actual values
nano backend/.env

# Install backend dependencies
cd backend
uv sync

# Run migrations
uv run alembic upgrade head

# Build frontend
cd ../frontend
npm ci
npm run build
```

## 3. Setup Google Service Account

```bash
mkdir -p ~/app2/backend/credentials
# Copy your service-account.json to:
# ~/app2/backend/credentials/service-account.json
chmod 600 ~/app2/backend/credentials/service-account.json
```

## 4. Install Systemd Services

```bash
# Copy service files
sudo cp ~/app2/deploy/systemd/*.service /etc/systemd/system/

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable hari2-backend hari2-worker
sudo systemctl start hari2-backend hari2-worker

# Check status
sudo systemctl status hari2-backend
sudo systemctl status hari2-worker
```

## 5. Configure nginx

```bash
# Copy nginx config
sudo cp ~/app2/deploy/nginx/hari2.both.rocks.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/hari2.both.rocks.conf /etc/nginx/sites-enabled/

# Get SSL certificate
sudo certbot --nginx -d hari2.both.rocks

# Test and reload nginx
sudo nginx -t
sudo systemctl reload nginx
```

## 6. Configure GitHub Actions

Add these secrets to the repository (Settings > Secrets and variables > Actions):

| Secret | Value |
|--------|-------|
| `SSH_HOST` | Server IP address |
| `SSH_USER` | `hari` |
| `SSH_PRIVATE_KEY` | Contents of the deploy SSH private key |

## 7. Setup Deploy SSH Key

On the server:

```bash
# Add the deploy public key to authorized_keys
echo "ssh-ed25519 AAAA... github-actions-deploy" >> ~/.ssh/authorized_keys
```

## 8. Configure Sudoers for Service Restart

The deploy script needs to restart services without a password:

```bash
sudo visudo -f /etc/sudoers.d/hari-deploy
```

Add:
```
hari ALL=(ALL) NOPASSWD: /bin/systemctl restart hari2-backend
hari ALL=(ALL) NOPASSWD: /bin/systemctl restart hari2-worker
```

## 9. Update Google OAuth Redirect URI

In Google Cloud Console, update the OAuth client's authorized redirect URI:
- Add: `https://hari2.both.rocks/api/auth/callback`

## Verification

```bash
# Check services
sudo systemctl status hari2-backend
sudo systemctl status hari2-worker

# Check logs
journalctl -u hari2-backend -f
journalctl -u hari2-worker -f

# Test health endpoint
curl https://hari2.both.rocks/health
```

## Troubleshooting

### Service won't start
```bash
journalctl -u hari2-backend -n 50 --no-pager
```

### Database connection issues
```bash
sudo -u postgres psql -c "SELECT 1 FROM pg_database WHERE datname='hari2'"
```

### nginx errors
```bash
sudo nginx -t
sudo tail -f /var/log/nginx/error.log
```
