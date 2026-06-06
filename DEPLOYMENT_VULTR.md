# MyWay Beauty Salon — Vultr Ubuntu Deployment Guide

Complete step-by-step guide for deploying on a fresh Vultr Ubuntu 22.04 VPS,
including PostgreSQL setup and migration of existing data from a SQLite database.

---

## Overview

```
Your Local Machine                    Vultr VPS (Ubuntu 22.04)
──────────────────                    ─────────────────────────
GitHub repo         ──── git clone ──► /opt/my-way-beauty-salon/
faktury.db (SQLite) ──── scp      ──► /root/faktury_backup.db
                                            │
                                            ▼
                                      PostgreSQL
                                      /opt/my-way-beauty-salon/
                                      ├── .venv/
                                      ├── .env          (secrets)
                                      ├── data/
                                      │   ├── uploads/
                                      │   ├── pdfs/
                                      │   └── temp/
                                      └── static/css/output.css

                                      Gunicorn (systemd service)
                                            │
                                      Nginx (port 80 → 127.0.0.1:8083)
```

---

## Prerequisites

- Vultr account at vultr.com
- SSH key pair (generate with `ssh-keygen -t ed25519` if you don't have one)
- Your existing `faktury.db` file (for data migration — skip if fresh start)
- GitHub access to `perysek/faktura_scanner_flask`

---

## Step 1 — Create the Vultr Instance

1. Log in to vultr.com → **Deploy** → **Cloud Compute**
2. Choose settings:
   - **Location:** Amsterdam or Warsaw (closest to Poland)
   - **Image:** Ubuntu 22.04 LTS x64
   - **Plan:** 2 vCPU / 4 GB RAM (~$24/mo) — recommended for OCR workloads.
     Minimum viable: 1 vCPU / 2 GB RAM (~$12/mo)
   - **SSH Keys:** Add your public key (`~/.ssh/id_ed25519.pub`)
   - **Server Hostname:** `my-way-beauty-salon`
3. Click **Deploy Now** — wait ~60 seconds for provisioning
4. Note your server's **IP address** from the Vultr dashboard

---

## Step 2 — Initial Server Setup

```bash
# Connect as root
ssh root@YOUR_SERVER_IP

# Create a dedicated deploy user
adduser deploy
usermod -aG sudo deploy

# Copy your SSH key to the deploy user so you can log in as them
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy

# From now on, use the deploy user
su - deploy
```

> **Why a non-root user?** Running the app as root means a bug or exploit has
> full server access. `deploy` can use `sudo` when needed but runs the app
> without elevated privileges.

---

## Step 3 — Install System Dependencies

```bash
sudo apt-get update && sudo apt-get upgrade -y

# Python 3.11 + build tools
sudo apt-get install -y python3.11 python3.11-venv python3-pip build-essential git

# Tesseract OCR + Polish language pack
sudo apt-get install -y tesseract-ocr tesseract-ocr-pol

# Poppler — required by pdf2image for PDF → image conversion
sudo apt-get install -y poppler-utils

# Native libraries required by OpenCV and Pillow
sudo apt-get install -y libgl1-mesa-glx libglib2.0-0

# Nginx — reverse proxy
sudo apt-get install -y nginx

# Verify Tesseract has Polish language data
tesseract --list-langs
# Expected output must include: pol
```

---

## Step 4 — Install Node.js (for TailwindCSS build)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify
node --version   # v20.x.x
npm --version    # 10.x.x
```

---

## Step 5 — Install and Configure PostgreSQL

```bash
sudo apt-get install -y postgresql postgresql-contrib

# Verify PostgreSQL is running
sudo systemctl status postgresql
# Should show: active (running)
```

Create the database and application user:

```bash
sudo -u postgres psql << 'SQL'
CREATE USER faktura_user WITH PASSWORD 'choose_a_strong_password_here';
CREATE DATABASE faktura_db OWNER faktura_user;
GRANT ALL PRIVILEGES ON DATABASE faktura_db TO faktura_user;
\q
SQL
```

Test the connection works:

```bash
psql -U faktura_user -h localhost -d faktura_db -c "SELECT version();"
# Should print the PostgreSQL version — if it works, the DB is ready
```

---

## Step 6 — Deploy the Application

```bash
# Create application directory
sudo mkdir -p /opt/my-way-beauty-salon
sudo chown deploy:deploy /opt/my-way-beauty-salon

# Clone the repository (PostgreSQL branch)
git clone https://github.com/perysek/faktura_scanner_flask.git /opt/my-way-beauty-salon

cd /opt/my-way-beauty-salon

# Checkout the branch with the PostgreSQL migration
git checkout feat/ui-improvements-todos

# Verify you're on the right commits
git log --oneline -4
# Expected:
# 25e9c62 feat: add Vultr VPS deployment configuration
# e9ec67e feat: migrate from SQLite to PostgreSQL
# 8000758 feat: add Render deployment configuration
# ...
```

---

## Step 7 — Set Up Python Virtual Environment

```bash
cd /opt/my-way-beauty-salon

# Create virtualenv
python3.11 -m venv .venv

# Activate it
source .venv/bin/activate

# Install all Python dependencies (includes gunicorn, psycopg2-binary, etc.)
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 8 — Build TailwindCSS

```bash
cd /opt/my-way-beauty-salon

# Install Node.js dependencies
npm install

# Build the compiled CSS (creates static/css/output.css)
npm run build:css

# Verify the output file was created
ls -lh static/css/output.css
```

---

## Step 9 — Create Data Directories

```bash
mkdir -p /opt/my-way-beauty-salon/data/uploads
mkdir -p /opt/my-way-beauty-salon/data/pdfs
mkdir -p /opt/my-way-beauty-salon/data/temp

# Log directory for Gunicorn
sudo mkdir -p /var/log/my-way-beauty-salon
sudo chown deploy:deploy /var/log/my-way-beauty-salon
```

---

## Step 10 — Configure Environment Variables

```bash
cd /opt/my-way-beauty-salon

# Copy the template
cp .env.example .env

# Generate a secure SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"
# Copy the printed value — you'll paste it into .env

# Edit the .env file
nano .env
```

Fill in your `.env` with actual values:

```env
SECRET_KEY=paste_the_generated_32_byte_hex_key_here
FLASK_ENV=production

# Set to 'true' ONLY when the site is served over HTTPS end-to-end (after Step 17).
# Over plain HTTP a Secure cookie is dropped by the browser and login breaks.
SESSION_COOKIE_SECURE=false

DATABASE_URL=postgresql://faktura_user:choose_a_strong_password_here@localhost:5432/faktura_db

TESSERACT_CMD=/usr/bin/tesseract
POPPLER_PATH=/usr/bin

UPLOAD_FOLDER=/opt/my-way-beauty-salon/data/uploads
PDF_FOLDER=/opt/my-way-beauty-salon/data/pdfs
TEMP_DIR=/opt/my-way-beauty-salon/data/temp
```

> **Security:** `.env` contains credentials. It is already in `.gitignore` and
> must never be committed. Check with `git status` — it should not appear.
>
> **`SECRET_KEY` is validated at boot.** The app refuses to start if it is unset,
> shorter than 32 characters, or a known placeholder (e.g. the `.env.example`
> default). It signs both session cookies and CSRF tokens — a weak or shared key
> lets anyone forge a superuser session. Always paste a freshly generated value.
>
> **Enable `SESSION_COOKIE_SECURE=true` once HTTPS is live** (Step 17). Until then
> leave it `false`, or the browser will drop the session cookie over HTTP and
> nobody can log in.

---

## Step 11 — Initialize the Database Schema

This creates **all** tables in PostgreSQL. Alembic is the single source of
truth (improvement #1): the chain's baseline migration creates the invoice
domain (invoices, sellers, audit_log, …) and roles, then the rest of the chain
adds users, employees, clients, appointments, services, absences, etc.

> **The app no longer creates the schema at boot.** `initialize_database()` is
> gone from `create_app()`. Running `alembic upgrade head` is now a *required*
> deploy step on a fresh database — without it the app will warn at boot and
> 500 on the first query.

```bash
cd /opt/my-way-beauty-salon

# Load environment variables from .env
export $(grep -v '^#' .env | xargs)

# Build the entire schema from empty — the ONLY way schema is applied
alembic upgrade head
```

Expected Alembic output (note the baseline runs first):
```
INFO  [alembic.runtime.migration] Running upgrade  -> 000_baseline, Baseline: invoice-domain + roles tables
INFO  [alembic.runtime.migration] Running upgrade 000_baseline -> 001, Create users and employees tables
INFO  [alembic.runtime.migration] Running upgrade 001 -> ee7039bc78b2, Create clients table
...
```

Verify tables were created:

```bash
psql -U faktura_user -h localhost -d faktura_db -c "\dt"
# Should list: invoices, sellers, audit_log, users, employees, clients,
#              services, appointments, etc.
```

---

## Step 12 — Migrate Existing SQLite Data (skip if fresh install)

This step imports your existing invoice records from the old `faktury.db` SQLite
database into PostgreSQL.

### 12a — Copy the SQLite file to the server

Run this on your **local machine** (not the server):

```bash
scp /path/to/faktury.db deploy@YOUR_SERVER_IP:/root/faktury_backup.db
```

If the old database is on **another Vultr server** (e.g. your existing running app):

```bash
# On your local machine — download from old server then upload to new server
scp deploy@OLD_SERVER_IP:/path/to/faktury.db ./faktury_backup.db
scp ./faktury_backup.db deploy@NEW_SERVER_IP:/root/faktury_backup.db
```

### 12b — Run the migration script

Back on the **new server**:

```bash
cd /opt/my-way-beauty-salon
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)

python scripts/migrate_sqlite_to_postgres.py /root/faktury_backup.db
```

Expected output:
```
Source SQLite: /root/faktury_backup.db
  sellers: 12 inserted, 0 skipped
  invoices: 87 inserted, 0 skipped
  audit_log: 243 inserted, 0 skipped
  duplicate_detection: 0 rows (empty)
  upload_staging: 0 rows (empty)

Migration complete.
```

### 12c — Verify data arrived

```bash
   psql -U faktura_user -h localhost -d faktura_db \
     -c "SELECT COUNT(*) as total_invoices FROM invoices;"

psql -U faktura_user -h localhost -d faktura_db \
  -c "SELECT COUNT(*) as total_sellers FROM sellers;"
```

Numbers should match what was in your old app.

---

## Step 13 — Create the systemd Service

This makes the app start automatically on boot and restart on crashes.

```bash
sudo nano /etc/systemd/system/my-way-beauty-salon.service
```

Paste the following:

```ini
[Unit]
Description=MyWay Faktura Scanner — Flask Application
After=network.target postgresql.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/opt/my-way-beauty-salon
EnvironmentFile=/opt/my-way-beauty-salon/.env
ExecStart=/opt/my-way-beauty-salon/.venv/bin/gunicorn \
    -c gunicorn.conf.py \
    "app:create_app()"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable my-way-beauty-salon    # start on boot
sudo systemctl start my-way-beauty-salon

# Verify it started correctly
sudo systemctl status my-way-beauty-salon
```

Expected status output:
```
● my-way-beauty-salon.service - MyWay Faktura Scanner — Flask Application
     Loaded: loaded (/etc/systemd/system/my-way-beauty-salon.service; enabled)
     Active: active (running) since ...
```

Check for startup errors:

```bash
journalctl -u my-way-beauty-salon -n 50
# Look for: [INFO] Listening at: http://127.0.0.1:8083
```

---

## Step 14 — Configure Nginx

Nginx sits in front of Gunicorn — it handles HTTPS, serves static files faster,
and protects Gunicorn from direct internet exposure.

```bash
sudo nano /etc/nginx/sites-available/my-way-beauty-salon
```

**Option A — Access via domain name (recommended):**

```nginx
server {
    listen 80;
    server_name your-domain.com;          # replace with your domain or IP

    client_max_body_size 16M;             # matches Flask MAX_CONTENT_LENGTH

    # Serve compiled CSS/JS/images directly — bypasses Python entirely
    location /static {
        alias /opt/my-way-beauty-salon/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass         http://127.0.0.1:8083;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_read_timeout 180s;           # matches Gunicorn timeout for OCR
        proxy_send_timeout 180s;
    }
}
```

**Option B — Access via IP address directly on port 80:**

```nginx
server {
    listen 80;
    server_name _;                         # matches any hostname/IP

    client_max_body_size 16M;

    location /static {
        alias /opt/my-way-beauty-salon/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass         http://127.0.0.1:8083;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
    }
}
```

Enable and test:

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/my-way-beauty-salon /etc/nginx/sites-enabled/

# Remove default nginx site to avoid conflicts
sudo rm /etc/nginx/sites-enabled/default

# Test configuration — must say "syntax is ok" before restarting
sudo nginx -t

# Apply
sudo systemctl restart nginx
```

---

## Step 15 — Configure Firewall

```bash
sudo ufw allow OpenSSH         # SSH — never block this or you'll lock yourself out
sudo ufw allow 'Nginx Full'    # HTTP (80) and HTTPS (443)
sudo ufw enable

# Verify
sudo ufw status
```

Expected output:
```
Status: active
To                         Action      From
--                         ------      ----
OpenSSH                    ALLOW       Anywhere
Nginx Full                 ALLOW       Anywhere
```

> Port 8083 should NOT be open in the firewall — Gunicorn binds to localhost
> only (127.0.0.1:8083) and Nginx proxies to it internally. This is the
> correct production setup.

---

## Step 16 — Verify the Deployment

```bash
# 1. Check service is running
sudo systemctl status my-way-beauty-salon
sudo systemctl status nginx
sudo systemctl status postgresql

# 2. Check the app responds
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost/
# Expected: HTTP 200

# 3. Check Gunicorn logs
tail -f /var/log/my-way-beauty-salon/access.log

# 4. Check application logs
journalctl -u my-way-beauty-salon -f
```

Open in your browser: **http://YOUR_SERVER_IP/** (or your domain)

You should see the login page with your invoice data intact.

---

## Step 17 — SSL with Let's Encrypt (optional, requires a domain name)

If you have a domain pointing to your server's IP:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com

# Certbot auto-configures HTTPS and sets up automatic renewal
# Verify renewal works
sudo certbot renew --dry-run
```

After this, the app is accessible at `https://your-domain.com`.

---

## Maintenance Commands

### Restart the app after code changes

```bash
sudo systemctl restart my-way-beauty-salon
```

### Rotate the SECRET_KEY (after any suspected exposure)

Rotating the key invalidates every active session — all users are logged out.
That is the intended effect: it instantly revokes any forged or stolen cookie.

```bash
cd /opt/my-way-beauty-salon
NEW=$(python3 -c "import secrets; print(secrets.token_hex(32))")
sudo sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$NEW|" .env
sudo systemctl restart my-way-beauty-salon
```

### Pull latest code from GitHub

```bash
cd /opt/my-way-beauty-salon
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)

# Pull new code
git pull origin feat/ui-improvements-todos

# Install any new Python dependencies
pip install -r requirements.txt

# Rebuild CSS if templates changed
npm run build:css

# Run any new database migrations
alembic upgrade head

# Restart the service
sudo systemctl restart my-way-beauty-salon

# Verify
sudo systemctl status my-way-beauty-salon
```

### View live application logs

```bash
# Systemd journal (application stdout/stderr)
journalctl -u my-way-beauty-salon -f

# Gunicorn request log
tail -f /var/log/my-way-beauty-salon/access.log

# Gunicorn error log
tail -f /var/log/my-way-beauty-salon/error.log

# Nginx access log
tail -f /var/log/nginx/access.log
```

### Database backup

```bash
# Backup PostgreSQL to a file
pg_dump -U faktura_user -h localhost faktura_db > /root/faktura_pg_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
psql -U faktura_user -h localhost faktura_db < /root/faktura_pg_YYYYMMDD_HHMMSS.sql
```

### Check PostgreSQL data

```bash
psql -U faktura_user -h localhost -d faktura_db

# Useful queries inside psql:
# \dt                          — list all tables
# SELECT COUNT(*) FROM invoices;
# SELECT * FROM invoices ORDER BY created_at DESC LIMIT 5;
# \q                           — quit
```

---

## Troubleshooting

### App won't start — `DATABASE_URL environment variable is not set`

```bash
# Check .env exists and has DATABASE_URL
cat /opt/my-way-beauty-salon/.env | grep DATABASE_URL

# Check the systemd service has EnvironmentFile pointing to .env
sudo systemctl cat my-way-beauty-salon | grep EnvironmentFile
```

### App starts but shows 502 Bad Gateway

```bash
# Gunicorn not running or crashed
sudo systemctl status my-way-beauty-salon
journalctl -u my-way-beauty-salon -n 30

# Check Gunicorn is actually listening
ss -tlnp | grep 8083
```

### Tesseract not found

```bash
# Check Tesseract path
which tesseract
# Should be: /usr/bin/tesseract

# Check .env TESSERACT_CMD matches
grep TESSERACT_CMD /opt/my-way-beauty-salon/.env
# Should be: TESSERACT_CMD=/usr/bin/tesseract

# Verify Polish language installed
tesseract --list-langs | grep pol
```

### Migration script errors — `UniqueViolation`

The migration skips rows that already exist (by unique key). If you see
`skipped: N`, it means those records were already in PostgreSQL. This is safe.

### Permission denied on data directories

```bash
# Fix ownership — must match the User= in the systemd service
sudo chown -R deploy:deploy /opt/my-way-beauty-salon/data
sudo chown -R deploy:deploy /var/log/my-way-beauty-salon
```

---

## Architecture Summary

```
Internet
    │
    ▼
Nginx :80 / :443
    │  serves /static directly from disk (fast)
    │  proxies everything else to Gunicorn
    ▼
Gunicorn :8083 (localhost only)
    │  2 workers, 180s timeout
    │  managed by systemd (auto-restart, boot start)
    ▼
Flask app (app:create_app())
    │  loads .env via python-dotenv
    │  all config via environment variables
    ▼
PostgreSQL :5432 (localhost only)
    │  database: faktura_db
    │  user: faktura_user
    ▼
/opt/my-way-beauty-salon/data/   (PDFs, uploads, temp OCR files)
```

---

## Cost Reference

| Component | Cost |
|-----------|------|
| 2 vCPU / 4 GB VPS | ~$24/month |
| 1 vCPU / 2 GB VPS (minimum) | ~$12/month |
| PostgreSQL (self-hosted on same server) | included |
| Automatic backups (Vultr feature) | +20% of instance price |
| SSL via Let's Encrypt | free |
