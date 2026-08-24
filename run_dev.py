"""
Local development runner.

Usage:
    1. Open SSH tunnel in a separate terminal:
       ssh -i ssh_vultr -N -L 5432:localhost:5432 root@<VULTR_IP>

    2. Fill in .env.local with real DB credentials (copy from Vultr .env)

    3. Run this file:
       python run_dev.py
"""
import os
from dotenv import load_dotenv

# Load base .env first, then let .env.local override specific values.
# override=True means .env.local wins on any key that appears in both files.
load_dotenv('.env')
load_dotenv('.env.local', override=True)

# Verify the tunnel / database URL is configured before importing anything else.
db_url = os.environ.get('DATABASE_URL', '')
if not db_url in db_url:
    print()
    print("=" * 60)
    print("  ERROR: DATABASE_URL not configured in .env.local")
    print("  Edit .env.local and replace <DB_USER>, <DB_PASSWORD>,")
    print("  and <DB_NAME> with values from the Vultr server's .env")
    print("=" * 60)
    print()
    raise SystemExit(1)

from app import create_app

app = create_app()

if __name__ == '__main__':
    # Port override (2026-08-18): another local project's own run_dev.py
    # also hardcodes 5001 — when both are running at once, whichever bound
    # first silently "wins" the port and the other's requests get served by
    # the wrong app (discovered via a login failure that was actually this
    # project's frontend talking to a different project's backend). Default
    # stays 5001 for the common case; override with DEV_SERVER_PORT when
    # another process already holds it.
    port = int(os.environ.get('DEV_SERVER_PORT', 5001))
    print()
    print("=" * 60)
    print("  MyWay Dev Server — connecting to Vultr PostgreSQL")
    print(f"  DB: {db_url.split('@')[-1]}")   # show host/dbname, hide credentials
    print(f"  URL: http://localhost:{port}")
    print("=" * 60)
    print()
    app.run(
        debug=True,
        host='127.0.0.1',   # local only, not exposed on the network
        port=port,
        use_reloader=True,  # auto-restart on file changes
    )
