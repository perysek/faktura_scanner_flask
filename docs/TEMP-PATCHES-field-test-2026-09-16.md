# Temporary field-test patches — receptionist compensation visibility (2026-09-16)

**Status: ACTIVE. This entire file describes patches meant to be reverted once
receptionist-role field testing is done — do not treat any of this as
permanent product behavior.**

## Why

MyWay was field-tested with real receptionist-role accounts starting
2026-09-17. Receptionists should not see real compensation figures
(base salary, commission rates, derived commission amounts) or the
employee analytics/revenue section. Nothing about payroll, commission
calculation, or stored data changed — every patch below is display-layer
only (hide/redact what non-superusers *see*), never a change to what's
computed or stored.

**No database values were ever mutated as part of this work.** An earlier,
more drastic idea (bulk-overwrite every employee's real `base_salary`/
`commission_rate` to a dummy value in production) was proposed and then
explicitly rejected in favor of the masking approach below — see git log
on `react-migration` around 2026-09-16 for that discussion; it was never
implemented, there is nothing from it to roll back.

## Branch / deploy scope

All patches are on `react-migration` only, deployed to the Vultr
`my-way-react-preview` service (public at `https://staging.my-way-solutions.com`,
which enters via its own nginx vhost on :443 and reaches Gunicorn on
`127.0.0.1:8085`; raw `:8003` is a separate on-box-only site to the same
backend). **`invoices-app` (port 8083, the main live Flask/Jinja2 app) was
never touched by any of this.**

## What changed, where, and how to revert

Each item below is one commit on `react-migration`. Revert with
`git revert <sha>` (or `git log -p <sha>` to see the exact diff first).
They're independent — you can revert one without the others (e.g. if you
decide to keep the stat-card mask but restore the per-service commission
column).

### 1. `f923fd0` — Hide employee compensation and analytics from non-superusers
Backend + legacy Jinja + React. Scope: `base_salary`/`commission_rate` on
the employee view/edit/create pages, and the whole "Analizy i wyniki"
analytics/revenue section.
- `config/admin_view.py`: new `redact_compensation()` helper (server-side
  choke-point, blanks the two fields for non-superusers).
- `routes/api_routes.py`: `GET /employees`, `GET /employees/<id>` redact
  via that helper; `PUT /employees/<id>` now preserves the existing value
  for non-superuser requests instead of nulling it (this part is a real
  bug fix, not just a temp patch — see note below, **do not blindly
  revert this half**).
- `routes/main_routes.py` + `templates/employees/{view,edit,create}.html`:
  same redaction/hiding for the legacy Flask-rendered pages (still
  independently reachable from the SPA).
- `frontend/src/pages/employees/EmployeeDetailPage.tsx`: analytics section
  gated on `isSuperuser`.
- `frontend/src/pages/employees/EmployeeFormPage.tsx`: compensation inputs
  hidden for non-superusers.

**Revert caveat:** `PUT /employees/<id>`'s "preserve existing value when
the caller can't/didn't send it" behavior fixes a genuine full-row-overwrite
data-loss bug (the same class of bug already fixed there for
`skills`/`specializations` before this session — see the `D-Sec4` comment
a few lines above it). If you revert `f923fd0` wholesale, that bug comes
back for `base_salary`/`commission_rate`: any non-superuser editing any
other field on an employee will silently null their real compensation
values. Recommend reverting everything in this commit EXCEPT that PUT-side
preserve-on-absence logic, or re-applying just that fix afterward.

### 2. `ca62927` — Fix TS build break from `f923fd0`
Pure fixup, no behavior change beyond making `f923fd0` build. Revert
`f923fd0` and this one together, or not at all.

### 3. `cbab99a` — Hide per-service commission (UI-only)
React only, no backend/API change (API still returns raw values here —
this was explicitly requested as UI-only this round).
- `frontend/src/pages/employees/EmployeeDetailPage.tsx`: "Przypisane
  usługi" table — `Prowizja` column (header + cell) hidden for
  non-superusers.
- `frontend/src/pages/appointments/WizytaDetailPage.tsx`: "Usługi" section
  summary — the total-commission row hidden for non-superusers.

Known gap, never addressed (flagged at the time, not asked for): the
"Dodaj usługę" assign-service form on `EmployeeDetailPage.tsx` still has
its own visible `Prowizja (%)` input when assigning a *new* service to an
employee — only the display table was masked, not that input.

### 4. (this commit) — Mask the "Śr. prowizja" stat-card with "N/A"
React only, UI-only, no backend/API change.
- `frontend/src/pages/employees/EmployeesListPage.tsx`: the "Śr. prowizja"
  stat-card on the Pracownicy (employees list) page top stats row now
  shows literal text `N/A` for non-superusers instead of the computed
  average-commission zł amount. Card stays visible (not hidden), only the
  value changes. Superusers still see the real computed value.

## How to fully revert everything (once field testing is over)

```bash
git checkout react-migration
git revert <this-commit-sha> cbab99a ca62927 f923fd0 --no-commit
# then manually re-apply the PUT-preserve-on-absence fix described above
# under commit 1 before committing, unless you're OK reintroducing that bug
git commit
git push origin react-migration
```

Then redeploy `my-way-react-preview` (pull + `cd frontend && npm run
build` + `systemctl restart my-way-react-preview` on the Vultr box — see
`Skill(vultr-ssh)`).

## Not covered by any of this (deliberately, ask if that changes)

- `routes/analytics_routes.py`'s `/employees/<id>/analytics/*` endpoints
  are not locked server-side — the analytics UI is hidden, but the raw
  endpoints are still reachable by a non-superuser who calls them
  directly. Explicitly confirmed acceptable for this test window.
- The commission-related fields listed above are the only masking done.
  No other financial/PII field was touched.
