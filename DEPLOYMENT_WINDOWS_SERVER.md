# Windows Server 2016 — Local Company Server Deployment Guide
## Flask / Jinja2 / PostgreSQL Internal Web Apps

> This guide is the canonical reference for deploying any Python-Flask internal
> company tool on the shared Windows Server 2016 machine.
>
> **The only thing that changes between apps is the port number.**
> Every app follows this exact procedure.

---

## Architecture Overview

```
Company LAN users
        │
        ▼
http://SERVER_IP:PORT
        │
        ▼
Waitress WSGI server  (binds 0.0.0.0:PORT)
        │   managed as a Windows Service by NSSM
        │   auto-starts on boot, auto-restarts on crash
        ▼
Flask app  (app:create_app())
        │   .env loaded by python-dotenv
        ▼
PostgreSQL :5432  (one shared instance, one DB per app)
        │
        ▼
C:\Apps\<app-name>\data\   (uploads, PDFs, temp files)
```

**Why Waitress, not Gunicorn?** Gunicorn only works on Linux. Waitress is the
standard Windows-compatible WSGI production server for Flask/Django. It is a
pure-Python drop-in replacement — same interface, same production quality.

**Why no Nginx/IIS reverse proxy?** Internal LAN tools don't need TLS
termination or domain routing — direct port access is simpler and has zero
operational overhead. Add IIS as a reverse proxy only if you need HTTPS or
a friendly domain name on the LAN.

---

## Server-Level Prerequisites
*One-time setup on the Windows Server — skip if already done.*

### P1 — Python 3.11 (64-bit)

Download from python.org: **Python 3.11.x Windows installer (64-bit)**

```
Installer options (check BOTH):
  ☑ Add python.exe to PATH
  ☑ Install for all users
Custom install path: C:\Python311\
```

Verify in a new PowerShell:
```powershell
python --version   # Python 3.11.x
pip --version      # pip 23.x
```

### P2 — Git

Download from git-scm.com: **Git for Windows**

```
Installer options:
  - "Git from the command line and also from 3rd-party software"
  - Leave all other defaults
```

Verify:
```powershell
git --version   # git version 2.x.x.windows.x
```

### P3 — Node.js 20 LTS

Download from nodejs.org: **Node.js 20 LTS Windows Installer (64-bit)**

```
Default install path: C:\Program Files\nodejs\
```

Verify:
```powershell
node --version   # v20.x.x
npm --version    # 10.x.x
```

### P4 — PostgreSQL

Download from postgresql.org: **PostgreSQL 16 Windows x86-64 installer**

```
Installation directory: C:\Program Files\PostgreSQL\16\
Data directory:         C:\Program Files\PostgreSQL\16\data\
Port:                   5432  (default — keep this)
Password for postgres:  [set a strong password, save it somewhere safe]
Locale:                 Polish, Poland  (or Default)
```

After install, verify PostgreSQL service is running:
```powershell
Get-Service -Name postgresql*   # Status: Running
```

### P5 — Tesseract OCR (only for apps that use OCR)

Download from UB-Mannheim: **https://github.com/UB-Mannheim/tesseract/wiki**
Use the Windows 64-bit installer.

```
Install path: C:\Program Files\Tesseract-OCR\
During install: check "Polish" language data
```

Add to system PATH:
```
Control Panel → System → Advanced System Settings → Environment Variables
System variables → Path → Edit → New → C:\Program Files\Tesseract-OCR\
```

Verify (new PowerShell window):
```powershell
tesseract --version        # tesseract 5.x.x
tesseract --list-langs     # must include: pol
```

### P6 — Poppler (only for apps that use OCR/pdf2image)

Download Windows binaries: https://github.com/oschwartz10612/poppler-windows/releases
Latest release: `Release-xx.xx.x-x.zip`

```
Extract to: C:\poppler\
Add to PATH: C:\poppler\Library\bin\
```

Verify:
```powershell
pdfinfo --version   # pdfinfo version x.xx.x
```

### P7 — NSSM (Non-Sucking Service Manager)

Download from nssm.cc: **nssm-2.24.zip**

```
Extract to: C:\nssm\
Copy C:\nssm\win64\nssm.exe to C:\Windows\System32\
```

This makes `nssm` available in any terminal without a PATH change.

Verify:
```powershell
nssm version   # NSSM 2.24
```

---

## Per-App Deployment Procedure
*Repeat this entire section for each new app. Use a unique port number.*

### Step 0 — Decide on the port number

Every app on the server uses a different port. Keep a central log:

| App | Port | Directory |
|-----|------|-----------|
| FakturaScanner (MyWay) | 8083 | `C:\Apps\faktura-scanner\` |
| Next App | XXXX | `C:\Apps\next-app-name\` |

Pick a port not already in use. Check:
```powershell
netstat -ano | findstr "LISTENING" | findstr ":80"   # replace :80 with port range
# or
Get-NetTCPConnection -State Listen | Sort-Object LocalPort | Format-Table
```

Internal company convention: start from **8083**, increment by 1 for each
new app (8083, 8084, 8085, …).

---

### Step 1 — Create the app directory

```powershell
New-Item -ItemType Directory -Path "C:\Apps\<app-name>"
```

Replace `<app-name>` with a lowercase-hyphenated name (e.g. `faktura-scanner`).

---

### Step 2 — Clone the repository

```powershell
cd C:\Apps\<app-name>
git clone https://github.com/perysek/<repo-name>.git .
```

If the repo is private, set up a GitHub personal access token first:
```powershell
git config --global credential.helper manager
# Git will prompt for username/token on first clone
```

---

### Step 3 — Create the Python virtual environment

```powershell
cd C:\Apps\<app-name>
python -m venv .venv
.venv\Scripts\activate
```

Your prompt should now show `(.venv)`.

---

### Step 4 — Add Waitress to requirements

**Waitress is the Windows production WSGI server — gunicorn does not work on Windows.**

Edit `requirements.txt` — remove or comment out `gunicorn` and add `waitress`:

```
# gunicorn==21.2.0   # Linux only — not used on Windows
waitress==3.0.1      # Windows production WSGI server
```

Then install:
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

If the app uses Playwright (for web scraping), install the browser:
```powershell
python -m playwright install chromium
```

---

### Step 5 — Build TailwindCSS

`output.css` is gitignored — it must be built on the server.

```powershell
npm install
npm run build:css

# Verify
Test-Path static\css\output.css   # True
```

---

### Step 6 — Create data directories

```powershell
New-Item -ItemType Directory -Force -Path "C:\Apps\<app-name>\data\uploads"
New-Item -ItemType Directory -Force -Path "C:\Apps\<app-name>\data\pdfs"
New-Item -ItemType Directory -Force -Path "C:\Apps\<app-name>\data\temp"

# Log directory
New-Item -ItemType Directory -Force -Path "C:\Logs\<app-name>"
```

---

### Step 7 — Create the PostgreSQL database

Open pgAdmin 4 (installed with PostgreSQL) or use `psql`:

```powershell
# Open psql as postgres superuser
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres
```

Inside psql:
```sql
CREATE USER <app>_user WITH PASSWORD 'choose_a_strong_password';
CREATE DATABASE <app>_db OWNER <app>_user;
GRANT ALL PRIVILEGES ON DATABASE <app>_db TO <app>_user;
\q
```

Replace `<app>` with your app's short name (e.g. `faktura`).

Test the connection:
```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U <app>_user -h localhost -d <app>_db -c "SELECT version();"
# Should print PostgreSQL version
```

---

### Step 8 — Configure environment variables (.env)

```powershell
copy .env.example .env
notepad .env
```

Fill in:

```env
# Flask
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
FLASK_ENV=production

# PostgreSQL
DATABASE_URL=postgresql://<app>_user:<password>@localhost:5432/<app>_db

# Tesseract (Windows path — only for OCR apps)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

# Poppler (Windows path — only for OCR apps)
POPPLER_PATH=C:\poppler\Library\bin

# File storage — Windows absolute paths
UPLOAD_FOLDER=C:\Apps\<app-name>\data\uploads
PDF_FOLDER=C:\Apps\<app-name>\data\pdfs
TEMP_DIR=C:\Apps\<app-name>\data\temp
```

Generate the SECRET_KEY:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
# Copy the output and paste into .env
```

---

### Step 9 — Initialize the database schema

```powershell
cd C:\Apps\<app-name>
.venv\Scripts\activate

# Load .env variables into current PowerShell session
Get-Content .env | Where-Object { $_ -notmatch "^#" -and $_ -match "=" } | ForEach-Object {
    $parts = $_ -split "=", 2
    [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
}

# Build the entire schema from empty. Alembic is the single source of truth
# (improvement #1): the baseline migration creates the invoice domain + roles,
# then the rest of the chain adds everything else. The app no longer creates
# the schema at boot, so this step is required on a fresh database.
.venv\Scripts\alembic.exe upgrade head
```

Expected (baseline runs first):
```
INFO  [alembic.runtime.migration] Running upgrade -> 000_baseline, Baseline: invoice-domain + roles tables
INFO  [alembic.runtime.migration] Running upgrade 000_baseline -> 001, Create users...
INFO  [alembic.runtime.migration] Running upgrade 001 -> ..., Create clients...
...
```

Verify:
```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U <app>_user -h localhost -d <app>_db -c "\dt"
# Lists all created tables
```

---

### Step 10 — Create the Waitress launch script

Create `C:\Apps\<app-name>\run_production.py`:

```python
"""
Production entry point — run via NSSM Windows Service.
Waitress serves Flask on 0.0.0.0:PORT so all LAN clients can reach it.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from waitress import serve
from app import create_app

PORT = int(os.environ.get("SERVER_PORT", 8083))

if __name__ == "__main__":
    app = create_app()
    print(f"Starting production server on port {PORT}")
    serve(
        app,
        host="0.0.0.0",
        port=PORT,
        threads=4,          # 4 threads handles concurrent requests well
        connection_limit=100,
        channel_timeout=180,  # 180s — matches OCR timeout in gunicorn.conf.py
        url_scheme="http",
    )
```

Add `SERVER_PORT` to `.env`:
```env
SERVER_PORT=8083
```

Test that it starts correctly:
```powershell
cd C:\Apps\<app-name>
.venv\Scripts\activate
python run_production.py
# Should print: Starting production server on port 8083
# Ctrl+C to stop
```

Open a browser on the server and verify: `http://localhost:8083/`

---

### Step 11 — Create the Windows Service with NSSM

Open **PowerShell as Administrator**:

```powershell
# Install the service
nssm install <app-name> "C:\Apps\<app-name>\.venv\Scripts\python.exe" "C:\Apps\<app-name>\run_production.py"

# Configure service properties
nssm set <app-name> AppDirectory   "C:\Apps\<app-name>"
nssm set <app-name> DisplayName    "<App Display Name>"
nssm set <app-name> Description    "Flask web app — <description>"
nssm set <app-name> Start          SERVICE_AUTO_START

# Logging — stdout and stderr go to log files
nssm set <app-name> AppStdout      "C:\Logs\<app-name>\service.log"
nssm set <app-name> AppStderr      "C:\Logs\<app-name>\error.log"
nssm set <app-name> AppRotateFiles 1
nssm set <app-name> AppRotateBytes 10485760   # 10 MB rotation

# Restart policy — restart 5 seconds after any crash
nssm set <app-name> AppExit        Default Restart
nssm set <app-name> AppRestartDelay 5000

# Start the service now
nssm start <app-name>
```

Verify it started:
```powershell
Get-Service -Name "<app-name>"
# Status: Running

# Check the log
Get-Content "C:\Logs\<app-name>\service.log" -Tail 20
# Should show: Starting production server on port XXXX
```

---

### Step 12 — Open the port in Windows Firewall

Open **PowerShell as Administrator**:

```powershell
New-NetFirewallRule `
    -DisplayName "<App Display Name> Web Port" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 8083 `
    -Action Allow `
    -Profile Domain,Private

# Replace 8083 with your app's port number
```

Verify:
```powershell
Get-NetFirewallRule -DisplayName "*<App Display Name>*" | Format-Table DisplayName, Enabled, Direction
```

---

### Step 13 — Verify the full deployment

```powershell
# 1. Service is running
Get-Service -Name "<app-name>"   # Running

# 2. Port is listening
Get-NetTCPConnection -LocalPort 8083 -State Listen   # should show one entry

# 3. App responds locally
Invoke-WebRequest -Uri "http://localhost:8083/" -UseBasicParsing | Select-Object StatusCode
# StatusCode: 200

# 4. View recent logs
Get-Content "C:\Logs\<app-name>\service.log" -Tail 30
Get-Content "C:\Logs\<app-name>\error.log" -Tail 30
```

Then test from another computer on the LAN:
```
http://<SERVER_IP>:<PORT>/
```

---

## Updating the App (after code changes)

```powershell
# 1. Connect to the server and open PowerShell as Administrator

# 2. Stop the service
nssm stop <app-name>

# 3. Pull latest code
cd C:\Apps\<app-name>
git pull origin main   # or your branch name

# 4. Install any new Python dependencies
.venv\Scripts\activate
pip install -r requirements.txt

# 5. Rebuild CSS if templates changed
npm run build:css

# 6. Run any new database migrations
Get-Content .env | Where-Object { $_ -notmatch "^#" -and $_ -match "=" } | ForEach-Object {
    $parts = $_ -split "=", 2
    [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
}
.venv\Scripts\alembic.exe upgrade head

# 7. Restart the service
nssm start <app-name>

# 8. Verify
Get-Service -Name "<app-name>"   # Running
Get-Content "C:\Logs\<app-name>\service.log" -Tail 20
```

---

## NSSM Service Management Cheatsheet

```powershell
# Start / stop / restart
nssm start  <app-name>
nssm stop   <app-name>
nssm restart <app-name>

# Edit service config (opens GUI)
nssm edit <app-name>

# Remove service permanently
nssm stop <app-name>
nssm remove <app-name> confirm

# Status
Get-Service -Name "<app-name>"

# All apps on the server at once
Get-Service | Where-Object { $_.Name -like "*salon*" -or $_.Name -like "*app*" }
```

---

## Log Access

```powershell
# Live tail of app stdout
Get-Content "C:\Logs\<app-name>\service.log" -Wait -Tail 50

# Live tail of errors
Get-Content "C:\Logs\<app-name>\error.log" -Wait -Tail 50

# Search for errors in logs
Select-String -Path "C:\Logs\<app-name>\service.log" -Pattern "ERROR|CRITICAL|Exception"

# Windows Event Log (service start/stop/crash events)
Get-EventLog -LogName System -Source "NSSM*" -Newest 20
```

---

## Multi-App Port Registry

Each app deployed on this server must be registered here. Update this table
whenever a new app is deployed.

| App Name | Service Name | Port | Directory | Deployed |
|---|---|---|---|---|
| MyWay Beauty Salon | `faktura-scanner` | 8083 | `C:\Apps\faktura-scanner\` | — |
| _(next app)_ | `<service-name>` | 8084 | `C:\Apps\<app>\` | — |

**Rule:** Never reuse a port number, even if an app is removed. Increment
from the last used port.

---

## Troubleshooting

### Service installed but won't start

```powershell
# Check error log for startup exception
Get-Content "C:\Logs\<app-name>\error.log" -Tail 40

# Check that python.exe path is correct
Test-Path "C:\Apps\<app-name>\.venv\Scripts\python.exe"   # must be True

# Test the command manually (as the user NSSM runs as)
cd C:\Apps\<app-name>
.venv\Scripts\python.exe run_production.py
# If this fails, you'll see the actual error
```

### Port already in use

```powershell
# Find what's using the port
netstat -ano | findstr ":<PORT>"

# Get process name from PID
Get-Process -Id <PID>
```

### 500 Internal Server Error

```powershell
# App is running but throwing exceptions — check error log
Get-Content "C:\Logs\<app-name>\error.log" -Tail 100

# Temporarily run with DEBUG=true to get more detail
# Add to .env: DEBUG=true
# Then restart: nssm restart <app-name>
# REMEMBER to remove DEBUG=true after diagnosing
```

### DATABASE_URL not set / database connection refused

```powershell
# Verify .env has DATABASE_URL
Select-String -Path "C:\Apps\<app-name>\.env" -Pattern "DATABASE_URL"

# Test PostgreSQL is running
Get-Service -Name "postgresql*"

# Test the connection manually
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U <app>_user -h localhost -d <app>_db -c "SELECT 1"
```

### Tesseract not found (OCR apps)

```powershell
# Verify TESSERACT_CMD in .env points to the correct path
Select-String -Path "C:\Apps\<app-name>\.env" -Pattern "TESSERACT_CMD"

# Test Tesseract directly
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
```

### CSS missing / styles broken

```powershell
# output.css is gitignored — it must be rebuilt after every git pull
cd C:\Apps\<app-name>
npm run build:css
Test-Path static\css\output.css   # must be True
nssm restart <app-name>
```

### Alembic migration fails on fresh deploy

```powershell
# Make sure DATABASE_URL is loaded into the process environment
# then check alembic current state:
cd C:\Apps\<app-name>
.venv\Scripts\activate
.venv\Scripts\alembic.exe current

# If "None" (no migration run yet), run upgrade:
.venv\Scripts\alembic.exe upgrade head

# If errors, check PostgreSQL user has permissions:
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "\du"
```

---

## Quick Reference: Differences from Linux/Vultr Deployment

| Concern | Linux (Vultr) | Windows Server 2016 |
|---|---|---|
| WSGI server | `gunicorn` | `waitress` |
| Service manager | `systemd` | **NSSM** |
| Start on boot | `systemctl enable` | `nssm set ... SERVICE_AUTO_START` |
| Service restart on crash | `Restart=always` in unit file | `nssm set ... AppExit Default Restart` |
| View logs | `journalctl -u <app>` | `Get-Content C:\Logs\...\service.log` |
| Reload service | `systemctl restart <app>` | `nssm restart <app-name>` |
| Firewall | `ufw allow PORT` | `New-NetFirewallRule ... -LocalPort PORT` |
| Reverse proxy | Nginx | None (direct port access on LAN) |
| Python path | `/opt/<app>/.venv/bin/python` | `C:\Apps\<app>\.venv\Scripts\python.exe` |
| Env vars | `EnvironmentFile=.env` in unit | `load_dotenv()` in `run_production.py` |
| CSS build | `npm run build:css` | same |

---

## Deployment Checklist

Before declaring the deployment complete:

- [ ] Service created with `nssm install`
- [ ] Service set to `SERVICE_AUTO_START`
- [ ] Port is unique and documented in the port registry table above
- [ ] Firewall rule added for the port
- [ ] `.env` created from `.env.example` with real values
- [ ] `SECRET_KEY` is a fresh 32-byte hex string (not the example placeholder)
- [ ] `DATABASE_URL` points to the correct local PostgreSQL database
- [ ] `npm run build:css` ran and `output.css` exists
- [ ] `alembic upgrade head` completed without errors
- [ ] Service status is `Running`
- [ ] App responds at `http://localhost:<PORT>/` from the server
- [ ] App responds at `http://<SERVER_IP>:<PORT>/` from a LAN client
- [ ] Log files are being written to `C:\Logs\<app-name>\`
- [ ] `DEBUG=true` is NOT in production `.env`

---

*Last updated from codebase audit: 2026-05-04*
*Source: DEPLOYMENT_VULTR.md, vultr_deployment.txt, requirements.txt, gunicorn.conf.py, app.py*
