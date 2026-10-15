# issues-admin — Zgłoszenia (support-ticket desk)

The admin side of the "Zgłoś problem lub podziel się pomysłem" channel. Salon users file tickets
from the main app's sidebar phone button. Agents answer them here, at
**https://issues.my-way-solutions.com**.

- **What it is:** a separate React SPA with its own build and deploy, on the same Flask backend and DB.
  - Backend: `routes/support_routes.py`, `services/support_ticket_service.py`.
  - Migration: `c5e8a2d4f6b1`.
- **Who gets in:**
  - Accounts: the same as the salon app.
  - Required RBAC module: `support_tickets`. Turn it on in the main app under Poziomy dostępu → Edytuj rolę →
    "Zgłoszenia — panel obsługi". It is seeded ON for superuser only. Read-only access lets an agent view tickets but not answer them.
- **Design system:** this app keeps no copy of it. `@shared/*` resolves to `../frontend/src`, so it uses the main app's
  - `tokens.css` and `components.css`
  - `<Button>` and `<Icon>`
  - toasts
  - `AuthContext` and the fetch client

  `vite.config.ts` and `tsconfig.json` pin `react*` to this app's `node_modules`, so the bundle keeps exactly one React.
- **Layout:** three panes, as in Help Scout, Front and Zendesk Agent Workspace: views, then the queue, then the conversation with properties and "Dane techniczne".
  - Composer:
    - public reply or internal note
    - templates ("Szablony")
    - "Wyślij jako" a status
    - images pasted with Ctrl+V
  - Keyboard: `/` searches, `j`/`k` move between tickets, Ctrl+Enter sends.

## Develop

```bash
cd issues-admin && npm install
VITE_API_PROXY_TARGET=http://localhost:5002 npm run dev   # → http://localhost:5174
```

## Deploy (Vultr, 1 GB RAM — keep the heap flag)

```bash
cd /opt/my-way-issues && git pull origin issues-admin
cd issues-admin && npm install && NODE_OPTIONS=--max-old-space-size=1536 npm run build
```

- nginx: `deploy/nginx/issues-admin.conf`. It serves the internal port :8005 and issues.my-way-solutions.com on :443 through Cloudflare. `/api` and `/auth` go to the staging backend on :8085.
- There is no service to restart: nginx serves `dist/`.
- Backend changes ship with `react-migration`, i.e. with the staging deploy.
