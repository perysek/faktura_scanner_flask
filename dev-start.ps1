<#
.SYNOPSIS
    Starts the full local dev stack for faktura_scanner_flask (react-migration):
    SSH tunnel to the Vultr PostgreSQL DB, the Flask backend, and the Vite frontend.

.DESCRIPTION
    Three pieces, started in order (each skipped if already running on its port):
      1. SSH tunnel   127.0.0.1:5433 -> Vultr:5432 (real production Postgres —
         writes from this app ARE production writes, see .env.local)
      2. Flask backend  http://localhost:5002   (run_dev.py, reads .env + .env.local)
      3. Vite frontend  http://localhost:5173   (proxies /api and /auth to :5002)

    Backend port is 5002, not Flask's default 5001, to avoid colliding with an
    unrelated local project (human-solutions) that also hardcodes 5001.

.PARAMETER Stop
    Stop all three pieces (found by the port they listen on) instead of starting them.

.PARAMETER SkipTunnel
    Don't touch the SSH tunnel (use when it's already running, e.g. from a previous run).

.EXAMPLE
    .\dev-start.ps1
    .\dev-start.ps1 -Stop
#>
param(
    [switch]$Stop,
    [switch]$SkipTunnel
)

$ErrorActionPreference = 'Stop'

# ---- Config -----------------------------------------------------------
$RepoRoot      = $PSScriptRoot
$SshKey        = "$HOME\.ssh\cloudcmd_vultr_ed25519"
$VultrHost     = 'root@70.34.252.120'
$TunnelPort    = 5433
$BackendPort   = 5002
$FrontendPort  = 5173
$PythonExe     = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$FrontendDir   = Join-Path $RepoRoot 'frontend'
$EnvLocalPath  = Join-Path $RepoRoot '.env.local'
# Fallback source if this worktree has no .env.local of its own yet (worktrees
# don't share gitignored files) — sibling checkout where it's known to exist.
$SiblingEnvLocal = "C:\Users\piotrperesiak\PycharmProjects\faktura_scanner_flask\.env.local"

$BackendLog    = Join-Path $RepoRoot '.flask_dev.log'
$BackendErrLog = Join-Path $RepoRoot '.flask_dev.err.log'
$FrontendLog   = Join-Path $RepoRoot '.vite_dev.log'
$FrontendErrLog = Join-Path $RepoRoot '.vite_dev.err.log'

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "    WARN: $msg" -ForegroundColor Yellow }
function Write-Err2($msg) { Write-Host "    ERROR: $msg" -ForegroundColor Red }

function Get-ListenerPid($port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($conn) { return $conn.OwningProcess }
    return $null
}

# ---- Stop mode ----------------------------------------------------------
if ($Stop) {
    Write-Step "Stopping dev stack"
    foreach ($p in @(
        @{ Name = 'Vite frontend'; Port = $FrontendPort },
        @{ Name = 'Flask backend'; Port = $BackendPort },
        @{ Name = 'SSH tunnel';    Port = $TunnelPort }
    )) {
        $procId = Get-ListenerPid $p.Port
        if ($procId) {
            try {
                Stop-Process -Id $procId -Force -Confirm:$false
                Write-Ok "$($p.Name) (PID $procId, port $($p.Port)) stopped"
            } catch {
                Write-Err2 "$($p.Name): failed to stop PID $procId — $($_.Exception.Message)"
            }
        } else {
            Write-Warn2 "$($p.Name): nothing listening on port $($p.Port)"
        }
    }
    return
}

# ---- 1. SSH tunnel to production Postgres --------------------------------
if (-not $SkipTunnel) {
    Write-Step "SSH tunnel  127.0.0.1:$TunnelPort -> Vultr:5432"
    $existing = Get-ListenerPid $TunnelPort
    if ($existing) {
        Write-Ok "already listening on $TunnelPort (PID $existing) — leaving it alone"
    } else {
        if (-not (Test-Path $SshKey)) {
            Write-Err2 "SSH key not found at $SshKey — cannot open tunnel."
            Write-Host "    Fix the `$SshKey path in this script, then re-run." -ForegroundColor Yellow
            exit 1
        }
        Start-Process -FilePath 'ssh' `
            -ArgumentList @('-i', $SshKey, '-N', '-L', "$TunnelPort`:localhost:5432", $VultrHost) `
            -WindowStyle Hidden
        Start-Sleep -Seconds 2
        if (Get-ListenerPid $TunnelPort) {
            Write-Ok "tunnel up on port $TunnelPort"
        } else {
            Write-Err2 "tunnel did not come up — check the SSH key / VPN / network, then retry."
            exit 1
        }
    }
} else {
    Write-Step "SSH tunnel"
    Write-Warn2 "-SkipTunnel passed — assuming something already forwards $TunnelPort -> Vultr:5432"
}

# ---- 2. .env.local (DB credentials, secret key) --------------------------
Write-Step ".env.local"
if (-not (Test-Path $EnvLocalPath)) {
    if (Test-Path $SiblingEnvLocal) {
        Copy-Item $SiblingEnvLocal $EnvLocalPath
        Write-Ok "copied from sibling checkout ($SiblingEnvLocal) — this worktree had none"
    } else {
        Write-Err2 ".env.local missing here AND at $SiblingEnvLocal"
        Write-Host "    Create it with SECRET_KEY + DATABASE_URL=postgresql://faktura_user:<pw>@localhost:$TunnelPort/faktura_db" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Ok "present"
}

# ---- 3. Flask backend ------------------------------------------------------
Write-Step "Flask backend -> http://localhost:$BackendPort"
$existingBackend = Get-ListenerPid $BackendPort
if ($existingBackend) {
    Write-Ok "already listening on $BackendPort (PID $existingBackend) — leaving it alone"
} else {
    if (-not (Test-Path $PythonExe)) {
        Write-Err2 ".venv not found / not Python 3.12 at $PythonExe"
        Write-Host "    Fix:  py -3.12 -m venv .venv --clear ; .\.venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
        exit 1
    }
    $env:DEV_SERVER_PORT = "$BackendPort"
    Start-Process -FilePath $PythonExe -ArgumentList 'run_dev.py' `
        -WorkingDirectory $RepoRoot -WindowStyle Hidden `
        -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErrLog
    Write-Host "    starting, log: $BackendLog" -ForegroundColor DarkGray
    $tries = 0
    while (-not (Get-ListenerPid $BackendPort) -and $tries -lt 15) {
        Start-Sleep -Seconds 1
        $tries++
    }
    if (Get-ListenerPid $BackendPort) {
        Write-Ok "backend listening on $BackendPort"
        # Sanity check per known gotcha: an unrelated local project also binds
        # port 5001 by default; if something answers on OUR port with a bare
        # JSON banner instead of the app's HTML, it's the wrong app.
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:$BackendPort/" -UseBasicParsing -TimeoutSec 5
            if ($resp.Content -match '<html') {
                Write-Ok "sanity check passed (got app HTML)"
            } else {
                Write-Warn2 "response on $BackendPort doesn't look like this app's HTML — check $BackendErrLog"
            }
        } catch {
            Write-Warn2 "could not curl http://localhost:$BackendPort/ yet — check $BackendLog / $BackendErrLog"
        }
    } else {
        Write-Err2 "backend never came up — check $BackendLog and $BackendErrLog"
        exit 1
    }
}

# ---- 4. Vite frontend -------------------------------------------------------
Write-Step "Vite frontend -> http://localhost:$FrontendPort"
$existingFrontend = Get-ListenerPid $FrontendPort
if ($existingFrontend) {
    Write-Ok "already listening on $FrontendPort (PID $existingFrontend) — leaving it alone"
} else {
    if (-not (Test-Path (Join-Path $FrontendDir 'node_modules'))) {
        Write-Err2 "frontend/node_modules missing — run 'npm install' in $FrontendDir first."
        exit 1
    }
    $env:VITE_API_PROXY_TARGET = "http://localhost:$BackendPort"
    Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'dev') `
        -WorkingDirectory $FrontendDir -WindowStyle Hidden `
        -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErrLog
    Write-Host "    starting, log: $FrontendLog" -ForegroundColor DarkGray
    $tries = 0
    while (-not (Get-ListenerPid $FrontendPort) -and $tries -lt 20) {
        Start-Sleep -Seconds 1
        $tries++
    }
    if (Get-ListenerPid $FrontendPort) {
        Write-Ok "frontend listening on $FrontendPort"
    } else {
        Write-Err2 "frontend never came up — check $FrontendLog and $FrontendErrLog"
        exit 1
    }
}

# ---- Summary ----------------------------------------------------------------
Write-Host "`n----------------------------------------------------------" -ForegroundColor Cyan
Write-Host " App:      http://localhost:$FrontendPort" -ForegroundColor White
Write-Host " Backend:  http://localhost:$BackendPort  (proxied by the frontend)" -ForegroundColor White
Write-Host " DB tunnel: 127.0.0.1:$TunnelPort -> Vultr production Postgres" -ForegroundColor White
Write-Host " NOTE: this DB is real production data — writes from this app are real." -ForegroundColor Yellow
Write-Host " Stop everything:  .\dev-start.ps1 -Stop" -ForegroundColor White
Write-Host "----------------------------------------------------------`n" -ForegroundColor Cyan
