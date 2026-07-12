# MyWay Beauty — User Manual

*A complete guide to the salon management &amp; invoice-scanning application.*

> **About this manual.** This document describes every module of the application as it exists in the codebase at the time of writing: what each screen does, how modules relate to one another, which business rules and validation constraints govern user actions, and how the role-based access control (RBAC) system shapes what each person can see and do. Screenshot placeholders (📸) mark spots where a captured screen would help a new user orient themselves — replace them with real screenshots before distributing this manual.
>
> The application's working language is Polish (all screen labels, buttons and messages are in Polish). This manual is written in English but quotes the exact Polish label next to every screen element it references, so you can match instructions to what you actually see on screen.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Roles &amp; Permissions (RBAC)](#3-roles--permissions-rbac)
4. [Dashboard](#4-dashboard)
5. [Invoices &amp; Cost Tracking](#5-invoices--cost-tracking)
6. [Clients](#6-clients)
7. [Services](#7-services)
8. [Employees](#8-employees)
9. [Appointments &amp; Calendar](#9-appointments--calendar)
10. [Public Online Booking](#10-public-online-booking)
11. [SMS Notifications](#11-sms-notifications)
12. [Income](#12-income)
13. [Analytics](#13-analytics)
14. [Absences &amp; Leave Management](#14-absences--leave-management)
15. [Settings](#15-settings)
16. [Appendix](#16-appendix)

---

## 1. Introduction

MyWay Beauty is a single Flask web application that actually does two distinct jobs under one roof:

1. **A cost/invoice scanner** — the original purpose of the codebase. Staff upload supplier invoices (PDF or photographed paper receipts), the system OCR-scans them, extracts the seller, amounts and dates automatically, and tracks which are paid, unpaid or overdue.
2. **A full salon management system** — clients, services, employees, appointment scheduling (day/week/month calendars), a public online-booking page for customers, automated SMS reminders and ratings, staff income/commission tracking, business analytics, and employee absence/leave management.

These two halves share the same login, the same navigation sidebar, and the same permission system, but they are otherwise independent: invoice data never touches appointment data, and — as noted in [§4](#4-dashboard) — the app's main **Pulpit** (Dashboard) screen only reflects the invoice side, while salon KPIs live on the separate **Analityka** (Analytics) and **Przychody** (Income) pages.

**Who uses it:**

| Role | Typical person |
|---|---|
| `superuser` | The salon owner. Has every permission plus exclusive tools (Roles admin, hard-deletes, the "Widok administratora" owner-visibility toggle, the Power Editor). |
| `admin` | A manager. Near-superuser access to daily operations, but cannot manage roles, cannot see/edit another superuser's account, and cannot use the most destructive correction tools. |
| `receptionist` | Front-desk staff — appointments and clients, no financial/cost visibility. |
| `stylist` | A service-providing employee — appointments and clients, plus (if they supervise others) limited absence-approval powers. |
| `accountant` | Bookkeeping — invoices, reports, and read-only service price history. No client/appointment access. |

Custom roles beyond these five can also be created by a superuser (see [§3](#3-roles--permissions-rbac)).

---

## 2. Getting Started

### 2.1 The public landing page

Anyone who is not logged in and visits the site's root address sees a marketing landing page (hero section, feature overview, a short "Zgodność z KSeF" section about Polish e-invoicing compliance, and an FAQ) rather than the application itself. A **"Zaloguj się"** (Log in) button in the top navigation and footer is the only way into the real app from here.

📸 *Screenshot placeholder — public landing page hero section, showing the "Zaloguj się" button and top navigation (`docs/screenshots/landing-hero.png`).*

### 2.2 Logging in

The login screen (`/auth/login`) asks for **Adres e-mail**, **Hasło** (password), and an optional **"Zapamiętaj mnie"** (remember me) checkbox.

- A successful login always starts a **30-day sliding session** — every request you make resets the 30-day clock, so as long as you use the app at least once a month you effectively stay logged in indefinitely, whether or not you ticked "Zapamiętaj mnie" (that checkbox only affects a secondary browser-level remember cookie, not the session length itself).
- Login failures show a generic error message — the system never reveals whether the problem was the email or the password, to avoid leaking which email addresses have accounts.
- A deactivated account (see [§3.5](#35-managing-users)) cannot log in even with the correct password.

📸 *Screenshot placeholder — login screen (`docs/screenshots/login.png`).*

### 2.3 Forgotten password

Click **"Zapomniałem hasła"** on the login screen to reach the self-service reset flow. There is no outbound email involved: after you submit your address, if an account exists for it, the very next screen displays the reset link directly (with a "click to copy" box and a **"Przejdź do formularza"** button) — valid for **one hour**. If no account matches, the same neutral confirmation screen appears with no link, so the flow can't be used to discover which email addresses are registered. Once on the reset page, enter a new password (minimum 8 characters) twice to confirm.

Already logged in and just want to change your password deliberately? Use **Profil → Zmień hasło**, which asks for your current password first.

### 2.4 Navigating the app

Once logged in, the left **sidebar** is the primary navigation surface. It only shows the modules your role has access to — for example, a `receptionist` never sees an "Faktury" (Invoices) link at all, because their role has no `invoices` module permission. This filtering happens automatically; there is nothing to configure per-user.

On phones and narrow tablets (below the desktop breakpoint) the sidebar collapses into a slide-in drawer, and every page instead shows a short title in a mobile header bar (e.g. "Kalendarz", "Pulpit", "Ustawienia e-mail") so you always know where you are without the full sidebar visible.

📸 *Screenshot placeholder — desktop sidebar showing module links filtered to an example role (`docs/screenshots/sidebar-desktop.png`).*

If you are a `superuser`, the very bottom of the sidebar has two additional checkboxes covered in [§3.6](#36-widok-administratora-admin-view--dane-własne-own-data) — **"Widok administratora"** and **"Dane własne"**. These do not appear for any other role.

### 2.5 A note on the app's tone of voice

Toast messages and confirmations throughout the app are deliberately written with personality rather than generic corporate copy — expect a slightly teasing, sometimes savage tone when *you* make a mistake (an empty required field, an invalid NIP, a bad date), and a calmer, reassuring tone when something goes wrong that is not your fault (a server error, a permission problem, a session that expired). This is intentional app design, not a bug — don't be alarmed if a validation error sounds a little sharper than you'd expect from typical business software.

---

## 3. Roles &amp; Permissions (RBAC)

### 3.1 How access control works, conceptually

Every screen and every write action in the app is gated by a **module**. The full list of modules is: `invoices`, `appointments`, `clients`, `employees`, `services`, `settings`, `reports`, `data_correction`, `data_import`, `absences`, and `service_prices`.

A **role** (e.g. `stylist`) is granted access to a set of modules. For most modules that's a simple yes/no, but some modules support finer-grained flags on top of "has access":

- **Tylko do odczytu (read-only)** — the role can view the module's data but never create/edit/delete anything in it.
- **Tylko własne dane (own data)** — the role only ever sees records tied to its own linked employee, never anyone else's.
- Two module-specific extras: **"Edycja historii zmian ceny"** (can edit/delete service price-history entries — only meaningful on the `services` module) and **"Wysyłanie SMS"** (can manually trigger an SMS from the appointment page — only meaningful on the `appointments` module).

Two features sit *outside* this per-role system entirely and deserve to be understood separately: the **supervisor** relationship ([§3.7](#37-supervisors-a-relationship-not-a-role)) and the **"Widok administratora" / "Dane własne"** owner-visibility toggles ([§3.6](#36-widok-administratora-admin-view--dane-własne-own-data)), both of which layer on top of, rather than replace, the role system.

### 3.2 The five built-in roles

This table is the *default* access matrix seeded when the app was set up. A superuser can change any of this at any time from the Roles screen ([§3.3](#33-managing-roles-superuser-only)) — treat this as "how the app behaves out of the box," not an unchangeable law.

| Module | superuser | admin | receptionist | stylist | accountant |
|---|:---:|:---:|:---:|:---:|:---:|
| Faktury / Koszty (`invoices`) | ✅ | ✅ | — | — | ✅ |
| Wizyty (`appointments`) | ✅ (+SMS) | ✅ (+SMS) | ✅ | ✅ | — |
| Klienci (`clients`) | ✅ | ✅ | ✅ | ✅ | — |
| Pracownicy (`employees`) | ✅ | ✅ | — | — | — |
| Usługi (`services`) | ✅ (+cena) | ✅ (+cena) | — | — | — |
| Ustawienia (`settings`) | ✅ | ✅ | — | — | — |
| Historia / Raporty (`reports`) | ✅ | ✅ | — | — | ✅ |
| Korekta danych (`data_correction`) | ✅ | — | — | — | — |
| Import danych (`data_import`) | ✅ | ✅ | — | — | — |
| Nieobecności — pełne zarządzanie (`absences`) | ✅ | ✅ | — | — | — * |
| Ceny usług — historia (`service_prices`) | ✅ (edycja) | ✅ (edycja) | — | — | ✅ (**tylko odczyt**) |

`*` A `stylist` with no direct `absences` module access can still reach the absence-management screens for their own team if they are registered as a **supervisor** of other employees — see [§3.7](#37-supervisors-a-relationship-not-a-role). That access is narrower than the full module grant: it covers approving/rejecting requests and logging manual absences for direct reports, but never the category-management tab.

Both **Przychody** (Income, [§12](#12-income)) and **Analityka** (Analytics, [§13](#13-analytics)) are gated by the `appointments` module, not by a module of their own — anyone who can see the appointments calendar can also open Income and Analytics.

Note, importantly: because `stylist`/`receptionist` accounts have no automatic "own data only" restriction seeded on `appointments`, a normal stylist login sees *everyone's* income, commissions and analytics by default, not just their own — "own data" is a deliberately configurable flag an admin can turn on for a custom role, not a built-in stylist behaviour.

### 3.3 Managing roles (superuser only)

From the sidebar, superuser accounts see a **System → Role** section leading to the roles list. Here you can:

- See every role, a green/hollow dot per module indicating access, and a **"Systemowa"** badge on protected built-in roles (the `superuser` role itself cannot be deleted).
- **Create a new custom role** — pick a system name (lowercase, underscores only) and a display name, then toggle module access on/off. Sub-flags (read-only, own-data, etc.) aren't available at creation time — only once the role exists.
- **Edit an existing role's permissions** — a per-module row with the main access toggle plus, once that's on, the read-only/own-data/service-price/SMS sub-flags described in [§3.1](#31-how-access-control-works-conceptually).
- **Delete a custom role** (not available for the five protected built-ins).

Changes to a role take effect immediately for every user who holds it — there is no per-user permission cache to clear or re-login required.

📸 *Screenshot placeholder — role edit screen showing per-module toggles and sub-flags (`docs/screenshots/roles-edit.png`).*

### 3.4 Managing users

**System → Użytkownicy** (available to both `superuser` and `admin`) lists every login account: name, email, role badge (gold styling for superuser accounts), linked employee, active/inactive status, and last login.

An `admin` account can manage every non-superuser account, but is explicitly blocked from: creating a new superuser account, editing or deactivating an existing superuser account, or assigning the superuser role to anyone — the role dropdown itself simply won't offer "superuser" unless you are already logged in as one.

**Creating a user**: full name, email, password (min. 8 characters, confirmed twice), a role, and — importantly — an **employee** to link the login to. Only employees who don't already have a linked account appear in that dropdown, because the relationship is strictly one login per employee.

**Editing a user** is split into two independent forms on the same page: account details (name/email/role/linked employee/active toggle), and a separate password-reset form. A superuser can reset anyone's password directly from this screen without knowing their old one (distinct from the self-service change-password flow in your own profile).

A user can never delete their own account, and non-superusers can never delete a superuser's account.

### 3.5 Login accounts vs. employee records

It's worth internalising this distinction early, since several modules depend on it: a **user** (login credentials + role) and an **employee** (name, position, pay, schedule, calendar) are two separate database records, optionally linked one-to-one via the employee's **"Konto użytkownika"** field (set when creating/editing the employee — see [§8](#8-employees)). Not every employee needs a login (e.g. someone whose schedule is tracked but who never uses the app), and in principle a login could exist with no linked employee, though most staff-facing features (My Visits, absence requests, being assignable as a supervisor) require the link to be present.

### 3.6 "Widok administratora" (Admin View) &amp; "Dane własne" (Own Data)

This is a superuser-only pair of session toggles that exists to solve one specific problem: **the salon owner is also often a working stylist**, generating real appointments, income and commission — data that must not silently pollute staff performance reports, client history stats, or business analytics for everyone else (or even for the owner's own default view).

By default (both toggles OFF), any employee record linked to a `superuser`-role account is invisible everywhere in the app: the employee directory, appointment/calendar dropdowns, client visit-history stats, income summaries, and nearly every analytics figure. Nothing is actually deleted or hidden in the database — the owner's appointments and income records exist and are computed normally, they are simply excluded from every query's result set, and direct navigation to that employee's profile page returns a "not found" error.

- **"Widok administratora"** (checkbox at the bottom of the sidebar, superuser-only) reveals the hidden employee everywhere — turn it on to see your own salon activity as an owner.
- **"Dane własne"**, nested under it and only clickable while admin view is ON, *inverts* the filter instead of removing it: with both checked, every employee-scoped screen shows **only** your own linked employee's data, hiding everyone else's — a useful way to preview "what does my own dashboard look like" without wading through the whole team's numbers.
- Turning admin view back OFF always force-clears "Dane własne" too, so the sub-toggle can never silently persist into a session where its parent is off.
- Both flags are stored in your session (not the database) and ride the same 30-day session, so they persist across browser restarts until you flip them again or log out.

📸 *Screenshot placeholder — sidebar footer showing the "Widok administratora" and "Dane własne" checkboxes in their active (gold-highlighted) state (`docs/screenshots/admin-view-toggle.png`).*

> **Note:** these two toggles have no effect at all on non-employee-scoped screens — the invoice list, the services catalogue, settings, and the roles/users admin screens are never filtered by them.

### 3.7 Supervisors — a relationship, not a role

Any employee can be designated a **supervisor** of one or more other employees, entirely independent of their login role. A `stylist` who supervises three junior colleagues gains limited absence-management powers (approving/rejecting their team's leave requests, logging manual absences for them) without ever being promoted to `admin`.

This relationship is set from the **supervisor's own** employee-edit page ([§8.5](#85-assigning-supervisors--direct-reports)), not from the subordinate's page, and the UI actively prevents circular hierarchies (you cannot make two employees each other's supervisor).

Being a supervisor grants access to the **Nieobecności** (Absences) management screens even without the `absences` module permission, but only a scoped view: your own team's requests, not the whole salon's, and never the category-management tab (that stays superuser/admin-only). Full detail in [§14](#14-absences--leave-management).

---

## 4. Dashboard

The **Pulpit** (Dashboard) screen is reachable both at the site root once logged in and via the sidebar's "Pulpit" link. Any logged-in user can open it — it has no module-permission gate.

> ⚠️ **Important to know:** this Dashboard is entirely invoice/cost-focused. It predates the salon-management features and was never extended to cover them — you will **not** find today's appointments, salon revenue, or staff KPIs here. Those live on separate pages: [Analityka](#13-analytics), [Przychody](#12-income), and — for "what am I doing today" — the mobile-first **Moje wizyty** page ([§9.9](#99-moje-wizyty--the-employee-mobile-page)).

What it actually shows:

- A hero **Brutto** (gross invoice total) card plus five smaller stat cards: Wszystkie (all invoices), Opłacone (paid), Nieopłacone (unpaid), Netto, VAT (the latter two derived client-side from the gross figure).
- A 12-month bar chart of invoice totals.
- Four panels: recent invoices, overdue payments (with urgency-tinted days-overdue), upcoming payments (days-until), and top suppliers by invoice count.
- A manual **"Odśwież"** (refresh) button.

📸 *Screenshot placeholder — Dashboard (Pulpit) with the stat cards and monthly invoice chart (`docs/screenshots/dashboard.png`).*

---

## 5. Invoices &amp; Cost Tracking

*Module permission: `invoices` (superuser, admin, accountant by default).*

This is the app's original purpose: capturing supplier invoices — the salon's costs — whether typed in by hand, scanned from a PDF/photo, or pulled automatically from an inbox.

### 5.1 Core concepts

- An **Invoice** (Faktura) always belongs to a **Seller** (Sprzedawca) — a supplier, identified primarily by NIP (Polish tax ID). Sellers are a separate directory you manage alongside invoices.
- An invoice's status is always exactly one of two values: **Opłacona** (paid) or **Nieopłacona** (unpaid). There is no separate "overdue" status stored anywhere — "Przeterminowana" (overdue) is a label the screen computes on the fly whenever an invoice is still unpaid and its due date has already passed. Marking an invoice paid or unpaid is done with a single click on its status badge in the list — there's no separate "mark as paid" button to hunt for.
- Every invoice can optionally have a scanned PDF/image attached, an OCR confidence score, and a duplicate flag.

### 5.2 Adding an invoice manually

**Faktura → Nowa faktura** opens a three-section form: document details (number, status, issue date, due date, payment terms), seller details (name, NIP, bank account, address), and the amount/currency. You can optionally attach a scanned file here too. This path is for invoices you're keying in by hand with no OCR involved.

### 5.3 Uploading and scanning invoices (OCR)

The **Wgraj** (Upload) page is a three-step wizard:

1. **Wybierz źródło (choose source)** — either drag-and-drop one or more PDF/JPG/PNG files onto the drop zone, or use the **"Import z e-mail"** card to pull attachments straight from a configured mailbox (see [§5.4](#54-automatic-email-import)). Files are staged, not saved yet.
2. **Przegląd plików (review files)** — the staged list, with the option to remove any file before processing. Click **"Przetwórz dokumenty"** to run OCR.
3. **Wyniki OCR (OCR results)** — for each file, the system shows what it extracted (seller, invoice number, dates, amount), a colour-coded OCR-confidence badge (green ≥80%, amber ≥60%, red below), any validation warnings, and a duplicate-invoice flag if one was detected. Nothing is saved to the invoice list until you review this screen and click **"Zapisz i zakończ"**.

📸 *Screenshot placeholder — upload wizard step 3, showing an extracted invoice with its OCR-confidence badge (`docs/screenshots/upload-ocr-review.png`).*

**How the OCR actually reads a file:** text-based PDFs (i.e., not scanned images) are read directly — this path is always treated as 100% confident, since there's no recognition involved. Scanned/photographed documents go through image OCR with automatic image cleanup (denoising, deskewing, contrast correction) and are retried with different cleanup profiles if the first pass leaves too many fields unrecognised; the reported confidence reflects the OCR engine's own word-level certainty. Either way, the numbers/dates/names extracted are matched with regular-expression patterns tuned specifically for Polish invoices (KSeF-format numbers, NIP formats, IBAN, several date formats, and Polish-specific payment terms like "POBRANIE" for cash-on-delivery).

**Duplicate detection**: the system flags a possible duplicate when the same invoice number appears for the same seller (matched by NIP, or by name if no NIP is available) — a different supplier reusing the same invoice number never triggers a false positive. On the OCR wizard, a flagged duplicate is shown as a warning but doesn't block saving; you decide.

**Password-protected PDFs**: if a supplier always encrypts their invoices, register that password once under **Sprzedawcy → (edit a seller) → Hasła PDF**, tied either to the specific seller or to the sender's email address pattern (e.g. `%@enea.pl` matches any email from that domain). The next time a matching encrypted PDF is uploaded or arrives by email, it unlocks automatically; if no matching password is registered, the system falls back to trying every stored password before giving up.

### 5.4 Automatic email import

Rather than a background job, email import is something you trigger on demand from the upload wizard's **"Import z e-mail"** card: pick which mailbox folder(s) to search and a date range, and the system connects over IMAP, searches for emails whose subject or body contains an invoice-related keyword (Polish and English variants of "faktura", "invoice", "do zapłaty", etc.), and downloads any PDF attachments it finds. Those downloaded files then rejoin the exact same Step 2/3 review flow as a manual upload — there's no separate "email invoices" list to check elsewhere.

IMAP credentials are configured once under **Ustawienia → E-mail** ([§15.1](#151-emailimap-settings)) — a superuser or admin sets this up, and after that any user with `invoices` access can trigger an import.

### 5.5 Sellers

**Sprzedawcy** (Sellers) is the supplier directory: name, NIP, address, and a running invoice count. From here you can:

- Create a new seller, with a live duplicate-NIP/duplicate-name check as you type.
- Edit a seller's name/address and, from the same page, register PDF passwords for them.
- View every invoice linked to a seller.
- Use **"Sync sprzedawców"** tooling (from the invoice list's actions bar, or the seller sync screens) to catch and repair drift — invoices whose linked seller no longer matches by NIP or name, invoices referencing a seller that's since been deleted, or sellers whose invoices were OCR'd under a slightly different spelling.
- Deleting a seller **cascades**: every invoice linked to that seller is deleted along with it. The confirmation screen shows you the full list of invoices that would be removed before you commit.

### 5.6 History

**Historia** (History) is a searchable audit log covering every entity type in the app — not just invoices — showing who changed what field, from what value to what value, and when.

### 5.7 Data Import from caldis.pl (superuser/admin only)

*Module permission: `data_import`.*

Under **Import** is a separate, unrelated tool: a one-off (or repeatable) migration utility that scrapes historical appointment/visit data out of caldis.pl, an external booking platform the salon previously used, via an automated browser session, and inserts it into this app's appointments/services/income tables — auto-creating client records where needed.

Because the source site uses bot-detection (reCAPTCHA), the very first step each time the saved login session expires (after roughly 30 days) is clicking **"Reconnect"**, which opens a visible browser window on the server for you to log in manually; after that, imports for a given date range can run unattended. Progress streams live to the page (a scrolling log + progress bar), and each run's outcome (records inserted, clients auto-created, rows skipped and why, errors) is kept in a 20-entry history table underneath, along with the "dry run" option for previewing before committing.

📸 *Screenshot placeholder — Data Import page mid-run, showing the live log and progress bar (`docs/screenshots/data-import.png`).*

---

## 6. Clients

*Module permission: `clients` (superuser, admin, receptionist, stylist by default).*

### 6.1 The client list

**Klienci** shows every client with a live search box, filter chips (**Aktywni** / **VIP** / **Nieaktywni**), and sortable columns including last visit, next visit, completed-visit count, and no-show count. VIP status is computed automatically (active + 3 or more visits in the last 8 weeks) and shown as a gold ring on the client's avatar; a red ring instead flags a client with more than 2 no-shows. A small 6-month sparkline per row gives an at-a-glance visit trend.

📸 *Screenshot placeholder — client list with filter chips and VIP/no-show avatar rings (`docs/screenshots/clients-list.png`).*

### 6.2 Creating a client

**"Dodaj klienta"** opens a short form: first/last name (required), phone, email, date of birth, and free-text notes. As you type the name and/or phone, the system runs a live duplicate check and shows inline warnings ranked by confidence (an exact phone match is treated as high-confidence; a swapped-name or near-typo match as medium; an initials-only match as low). A high- or medium-confidence match must be explicitly confirmed ("Zapisać mimo to?") before the form will submit — this is a warning system, not a hard block, and it never merges records automatically.

> **Where duplicates actually creep in:** the public online-booking flow ([§10](#10-public-online-booking)) also creates client records automatically for guests who don't already match by phone or email — and that path does **not** run the same duplicate-warning check the staff-facing forms do. A guest who books with a slightly different name spelling or a new phone number will silently create a new client rather than surfacing a warning. If your client list has more duplicates than expected, online bookings are the most likely source.

### 6.3 Client detail &amp; history

A client's detail page shows their basic/contact info, notes, and two dates the system manages for you and that you cannot edit directly: **Pierwsza wizyta** (first visit) and **Ostatnia wizyta** (last visit) — both are set automatically the moment a staff member marks one of the client's appointments as **completed** (see [§9](#9-appointments--calendar)), not when an appointment is merely booked.

Below that, **Historia wizyt** (visit history, desktop/tablet only — hidden on phones) lists their last 50 appointments with date, time, employee, status and amount, each linking through to the full appointment record.

### 6.4 Preferred employee ("Preferencje klienta")

On the same detail page, the **Preferencje klienta** card lets you record that this client prefers a specific stylist for a given service (or for an entire service category). Add one with the inline form — pick a service or category, then an employee; the two dropdowns filter each other so you only ever see combinations that actually make sense (an employee who doesn't perform that service won't appear). These preferences are what powers the "suggested employee" hint elsewhere in the app when booking a returning client.

You can also regenerate preferences in bulk for every active client at once from the **"Aktualizuj preferencje"** button on the client list — this looks at each client's completed-visit history and auto-fills preferences for whichever service/employee combinations cover the bulk of their past visits, without touching any preference you added by hand.

### 6.5 Deactivating vs. deleting a client

The client list and the client edit form both offer a clean, fully reversible **"Klient aktywny"** toggle (deactivate/reactivate) — an inactive client simply drops out of the default list view but nothing about their record is touched.

> ⚠️ **Known quirk:** the button at the bottom of an active client's *detail* page is labelled **"Dezaktywuj"**, but clicking it actually performs a full delete (the client is excluded from every screen in the app, not just hidden from the default filter) rather than the reversible deactivation described above. There is no "recently deleted" screen to undo this from inside the app — recovering a client removed this way currently requires a direct database action. Until this is fixed, prefer the deactivate toggle on the edit form or the small deactivate icon on the list row (both correctly reversible) over the detail page's button.

---

## 7. Services

*Module permission: `services` (superuser, admin by default); the price-history sub-feature uses a separate `service_prices` permission that also grants accountants read-only access.*

### 7.1 Categories, main services, and addons

Services are organised into **Kategorie** (categories, e.g. "Fryzjerstwo", "Manicure") that you manage on **Usługi → Kategorie**. Every service is one of two types:

- **Główna** (main) — a bookable, standalone service; must belong to a category.
- **Dodatkowa** (addon) — a small add-on/microservice (e.g. a treatment upsell) that cannot be booked in advance on its own; it can only be added to an **already in-progress** visit (see [§9.6](#96-adding-addon-services-mid-visit)). Addons have no category of their own.

Renaming a category automatically renames it on every service that carries it; deleting a category that still has services attached asks you to choose between removing just the category (its services stay, now with an orphaned category label) or cascading the removal to its services too.

### 7.2 Which addons go with which main services

By default, an addon with no compatibility rules configured is offered alongside **every** main service. The moment you explicitly link an addon to specific main services (from a main service's detail page → **"Kompatybilne mikrousługi"** → **"Dodaj mikrousługę"**), it becomes scoped to only those — remove all its links again and it reverts to being universally compatible. This is what determines the list of addons a stylist can offer to add mid-visit.

📸 *Screenshot placeholder — a main service's detail page showing the "Kompatybilne mikrousługi" card (`docs/screenshots/service-addons.png`).*

### 7.3 Pricing &amp; price history

Every service has a catalogue price and duration. Changing a service's price doesn't just overwrite the old number — the system keeps a full dated history of every price the service has ever had, with an optional **"Powód zmiany ceny"** (reason) you can attach when the change is meaningful. The current price is always the open (undated-end) entry in that history.

The history is visible to anyone with `service_prices` access (which includes accountants, but as **read-only** by default — they can view but never delete an entry). Deleting a history entry is restricted to whoever holds the "Edycja historii zmian ceny" sub-flag (superuser/admin by default); deleting the *current* price entry automatically reopens the previous one as the new live price, and the very last remaining entry for a service can never be deleted (a service must always have at least one price on record).

The services list shows a small trend indicator next to any service whose price changed within the last 90 days, and inactive services can be revealed with the **"Pokaż nieaktywne"** checkbox — a soft-deleted or deactivated service never simply disappears from the record, only from the default view.

---

## 8. Employees

*Module permission: `employees` (superuser, admin by default).*

### 8.1 Employee records

Beyond name and contact details, an employee record carries: position, employment status (**Aktywny / Na urlopie / Zwolniony**), hire/termination dates, a base monthly salary, a commission percentage, an employer-cost overhead rate (defaults to 22%, modelling Polish ZUS/tax overhead on top of pay), skills and specializations, a work schedule, and a daily appointment cap.

**"Widok administratora" note:** as covered in [§3.6](#36-widok-administratora-admin-view--dane-własne-own-data), the employee record linked to the salon owner's own superuser login is invisible in this list (and everywhere else employee-scoped) unless a superuser has switched that toggle on.

### 8.2 Employment type ("Forma zatrudnienia")

**Pracownicy → Formy zatrudnienia** is a small reference table (e.g. Umowa o pracę, B2B, Umowa zlecenie) you attach to each employee, each carrying three informational flags: whether a minimum wage applies, whether pay is guaranteed regardless of commission, and whether commission is included in the base figure. An employment type in active use by any employee cannot be deleted.

### 8.3 Linking an employee to a login account

An employee can optionally be linked to a **users** login account (see [§3.5](#35-login-accounts-vs-employee-records)) via the "Konto użytkownika" dropdown on the create/edit forms — this is what unlocks employee-facing features like **Moje wizyty** and self-service absence requests. Only employees without an existing link appear as candidates when creating a new user, and the relationship is strictly one-to-one in both directions.

### 8.4 Per-employee custom pricing

On an employee's profile, the **"Przypisane usługi"** card lists every service they're assigned to perform, with an inline form to add more. Each assignment can optionally override the catalogue price, commission rate, and duration just for that employee — leave any of those fields blank and it simply inherits the service's (or the employee's own default) value. A small `*` marks prices that have been individually overridden so you can tell at a glance which ones aren't the catalogue default.

The same profile also has a five-tab **"Analizy i wyniki"** panel (Przegląd / Przychody / Wizyty / Umiejętności / Satysfakcja) with employee-specific performance metrics — a drill-down distinct from the salon-wide Analytics dashboard covered in [§13](#13-analytics). The **Umiejętności** tab in particular shows a manually-set 1–5 skill rating alongside an automatically-computed average client satisfaction score for each of the employee's assigned services.

### 8.5 Assigning supervisors &amp; direct reports

To make one employee the supervisor of others, open **that supervisor's own** edit page and use the **"Podwładni (bezpośredni)"** picker — a checklist of every other active employee. Anyone who is already *your* supervisor is shown greyed out with a "konflikt" label and cannot be selected, preventing circular reporting chains. Saving replaces the supervisor's entire direct-report list with whatever is checked — it's not additive.

There is deliberately no equivalent "pick my own supervisor" control on an employee's own page; the relationship is always set from the supervisor's side. See [§3.7](#37-supervisors-a-relationship-not-a-role) and [§14](#14-absences--leave-management) for what this relationship actually unlocks.

---

## 9. Appointments &amp; Calendar

*Module permission: `appointments` (superuser, admin, receptionist, stylist by default).*

This is the operational heart of the salon-management half of the app.

### 9.1 Appointment statuses

Every appointment moves through a small, strictly-enforced set of statuses:

```
scheduled ──┬──► confirmed ──┬──► in_progress ──► completed
            │                ├──► cancelled
            └──► cancelled   └──► no_show
```

- **scheduled** — booked, no client confirmation received yet (or confirmation isn't in use).
- **confirmed** — the client answered a confirmation SMS positively.
- **in_progress** — the visit has actually started (a stylist can start a visit directly from `scheduled`, e.g. for a walk-in, without needing a confirmation step first).
- **completed / cancelled / no_show** — final states. Reaching **completed** is what generates the income record for that visit (see [§12](#12-income)).

Several transitions are also **time-gated**, not just status-gated: you can't mark a visit `in_progress` or `no_show` more than 30 minutes before its scheduled start, and you can't mark it `completed` outside a 30-minute window around its scheduled end. This exists to stop accidental or wildly-early status changes; if you genuinely need to fix a stale/forgotten visit from days ago, that's what the "past visits" correction tool and the Power Editor ([§9.10](#910-power-editor-superuseradmin-data-correction)) are for — both bypass these time windows deliberately.

### 9.2 Calendar views

Three interchangeable calendar layouts, plus a plain sortable table, are all available from the Appointments menu:

- **Dzień** (day) — employee columns across an hourly timeline; hovering a visit block lifts it slightly with a shadow for emphasis. Defaults to today.
- **Tydzień** (week) — the same per-employee layout spread across seven day-columns.
- **Miesiąc** (month) — a compact monthly grid, each day showing its visits as small cards with a "+N more" overflow link on busy days.
- **Lista** — a conventional searchable, sortable table view for when you want to scan or filter rather than browse visually.

All three calendar views also overlay **approved** employee absences directly on the grid, so a stylist's day off is visible at a glance alongside their bookings — see the note in [§9.5](#95-absence-conflicts-when-booking) about *pending* absences not being shown here.

📸 *Screenshot placeholder — Dzień (day) calendar view with employee columns and a hovered appointment block (`docs/screenshots/calendar-day.png`).*
📸 *Screenshot placeholder — Miesiąc (month) calendar view with a "+N more" overflow day (`docs/screenshots/calendar-month.png`).*

### 9.3 Booking an appointment (staff-side)

**"Nowy termin"** opens a form: pick a client (searchable dropdown), an employee, one or more services (up to a system-wide cap of a few per visit), then a date and an available time slot. The system computes price, total duration, and commission automatically from the effective per-employee pricing described in [§8.4](#84-per-employee-custom-pricing).

Before saving, the system checks, in order: that the slot falls inside the employee's working hours, that neither the employee nor the client already has an overlapping appointment, and finally that the employee has no absence — approved *or* still pending — covering that time (see [§9.5](#95-absence-conflicts-when-booking)). Any failure shows a clear, specific inline message pointing at the exact field that needs fixing, rather than a generic "something went wrong."

### 9.4 Editing, rescheduling &amp; conflicts

The edit form re-runs the same conflict/working-hours/absence checks live as you change the date, time, or employee, so you see a problem before you even submit. If the salon reschedules a visit the client had already confirmed by SMS, their confirmation is automatically reset and a fresh confirmation-request text goes out for the new time.

### 9.5 Absence conflicts when booking

This is a subtle but important rule: **both an approved absence and a still-pending absence *request* block a new appointment from being saved** for that employee at that time — the system will not let you double-book someone whose leave is only awaiting a decision. The two cases differ only in how the warning is presented: an *approved* conflict is treated as a hard, unambiguous error (the offending field is highlighted and reset); a *pending* conflict shows a lighter warning toast, since it's not yet a certainty that leave will actually be granted.

> ⚠️ **Known quirk:** only *approved* absences are shown visually on the calendars and factored into the public booking page's "available slots" — a pending request does not visually block a time slot anywhere. This means a slot can look perfectly free right up until you try to save the appointment, at which point the pending-absence rule above rejects it. If a booking unexpectedly fails with an absence-related message, check the Absences screen for a pending request on that employee before assuming it's a bug.

### 9.6 Adding addon services mid-visit

Once (and only once) a visit's status is **in_progress**, the appointment page offers an **"Dodaj mikrousługę"** action showing every addon service that (a) is compatible with the visit's already-booked main service(s) per the rules in [§7.2](#72-which-addons-go-with-which-main-services), and (b) the assigned employee is qualified to perform. Adding one immediately updates the visit's running total — its price/commission are captured at the moment it's added, not recalculated later even if rates change afterward.

### 9.7 Completing a visit

Marking a visit **completed** — whichever of the several ways you do it (the status dropdown, the dedicated "Zakończ wizytę" action, or an employee finishing it from their own phone) — always, exactly once, creates the visit's [income record](#12-income) and updates the client's last-visit date. If you edit a completed visit and change its status back to something else, the associated income record is removed again, keeping the two in sync.

### 9.8 Cancelling &amp; no-shows

A cancellable visit (anything not yet `completed`) can be cancelled by staff from the appointment page, or by the client themselves via the cancellation link in their confirmation SMS (see [§11.4](#114-client-facing-sms-links)). Cancelling immediately stops any pending automated SMS (reminders, rating requests) tied to that visit so nothing fires for a visit that's no longer happening. **No-show** is a distinct terminal status from cancellation, used when the client simply never arrived — it's recorded the same way any other status change is, subject to the same time-gating described in [§9.1](#91-appointment-statuses).

### 9.9 "Moje wizyty" — the employee mobile page

Any staff member with a linked employee record can open **Moje wizyty** on their phone to see just today's appointments — large, tappable cards with time, client and service. For any visit starting within the next 20 minutes (or already under way), a **"Pobierz link do wizyty"** button reveals a personal one-time link they can use to mark the visit **started** and later **completed** directly from their phone, without needing to navigate the full desktop interface. The page quietly refreshes itself if a status changes elsewhere (e.g. a receptionist edits it from the desk) so it never shows stale information.

📸 *Screenshot placeholder — Moje wizyty mobile page showing today's appointment cards (`docs/screenshots/my-visits-mobile.png`).*

### 9.10 Power Editor (superuser/admin data correction)

*Module permission: `data_correction`, superuser-only by default.*

For fixing historical mistakes that the normal time-gated workflow won't allow (a visit from last week that never got marked completed, a wrong price on a closed visit, etc.), **Korekta danych** provides two dedicated tools with a visually distinct dark theme so you always know you're in "power user" territory:

- A single-visit **power editor**, with an unrestricted "save anyway" override that bypasses the usual conflict/time-window checks, and keyboard shortcuts to jump between adjacent appointments.
- A **bulk editable table** for correcting many visits at once.

There is also a **"past visits" scanner** elsewhere in the appointments tooling that finds visits still stuck in a non-final status well after they should have ended, letting you resolve them in bulk with the correct historical payment date (so revenue lands in the month the visit actually happened, not the month you happen to be fixing it).

---

## 10. Public Online Booking

The **`/booking`** page requires no login at all — it's the salon's public self-service booking widget, meant to be linked from your website or social media. It walks a visitor through five steps:

1. **Usługi** — choose up to a few main services (never addons — those are only ever added mid-visit by staff).
2. **Specjalista** — pick from the employees able to perform the chosen service(s), each shown with their effective price, duration, and a summary of which days/hours they work.
3. **Termin** — a calendar that shades in which days have any free slot long enough for the chosen services, then a slot picker for the chosen day. Same-day bookings automatically hide any slot starting within the next 30 minutes, to leave a minimum travel/prep buffer.
4. **Dane kontaktowe** — first/last name, phone (required), email (optional), and notes.
5. **Potwierdzenie** — a confirmation screen with the booked details and a note to call the salon directly for any changes (self-service reschedule/cancel isn't offered inline here, though a cancel link may arrive later by SMS if that message type is enabled).

📸 *Screenshot placeholder — public booking wizard, step 3 (calendar + time-slot picker) (`docs/screenshots/booking-step3.png`).*

Behind the scenes, this reuses the exact same booking logic as staff-side booking ([§9.3](#93-booking-an-appointment-staff-side)) — the same working-hours, double-booking and absence-conflict checks apply identically, so nothing a public visitor books can violate a rule staff themselves are bound by. The system matches the visitor to an existing client record by phone first, then email, and only creates a brand-new client if neither matches — see the duplicate-client caveat in [§6.2](#62-creating-a-client).

---

## 11. SMS Notifications

*Configuration under Settings (superuser/admin); manual sending on the appointment page requires the `appointments` module plus the specific "Wysyłanie SMS" sub-flag.*

### 11.1 Settings

**Ustawienia → SMS** holds your Twilio account credentials and a master **is_active** switch — with it off, no SMS of any kind will send, regardless of what's configured below it. From here you can also send a one-off test message to verify the setup, and browse a full send log.

### 11.2 Message types &amp; what triggers them

The system ships with a small set of built-in message types, each independently toggle-able, each with its own editable Polish text template (supporting placeholders like the client's name, the date/time, and the relevant link):

| Type | Default timing | Purpose |
|---|---|---|
| Prośba o potwierdzenie (confirmation request) | ~48h before | Asks the client to confirm or decline, includes a confirm link |
| Przypomnienie 1 | 24h before | Reminder, no interactive link |
| Przypomnienie 2 | 2h before | Final reminder |
| Wiadomość po wizycie | 30 min after completion | Includes the rating link |

You can also create additional custom message types beyond these four (built-in ones can't be deleted, only disabled). A background check runs every 15 minutes, sending whatever reminders are due and whatever post-visit rating messages have reached their scheduled delay.

A fifth type, **"Anulowanie wizyty (nieobecność pracownika)"**, ships disabled and isn't sent automatically at all — it's triggered manually, as the opt-in "send SMS to client" checkbox in the [absence conflict-resolution modal](#143-approving-or-rejecting-supervisoradmin) when a supervisor cancels a client's visit because no replacement stylist was available. Its template can include a **{booking_url}** placeholder (toggled with its own "Dołącz link do rezerwacji online" checkbox, same mechanism as the confirm/cancel/rate links) — this links straight to the public online-booking page so the client can pick a new time themselves instead of having to call in.

Separately from all of the above, every appointment also automatically schedules a short reminder text **to the assigned employee** roughly 20 minutes before the visit, containing their personal "start/end visit" link ([§9.9](#99-moje-wizyty--the-employee-mobile-page)) — this one isn't a configurable message type, it's built into the booking flow itself.

### 11.3 Manually sending an SMS

On an appointment's detail page, staff with the SMS-sending permission see a **"📱 Wyślij SMS"** dropdown listing every enabled message type, greying out any that have already been sent for this visit so you don't accidentally duplicate one.

### 11.4 Client-facing SMS links

Each link a client receives is a unique, single-use token — no login required to use them:

- **Confirm/decline** — the client accepts or declines the visit; accepting also flips the appointment to `confirmed`.
- **Cancel** — self-service cancellation, available for as long as the visit hasn't started or already been resolved.
- **Rate** — a simple 1–5 star widget the client can only submit once; already-rated visits show a read-only star display if revisited.

Cancelling a visit (by any route) immediately cancels any of its own outstanding scheduled texts, so a cancelled visit never generates a stray late reminder or rating request afterwards.

---

## 12. Income

*Module permission: `appointments` — Income has no permission of its own.*

**Przychody** is a simple, focused reporting page: pick a month, and see gross revenue, net revenue (after discounts), total commissions paid out, total discounts given, visit count and average ticket size for that month — plus the same figures broken down per employee in a table underneath.

Income records are never created or edited by hand anywhere in the app — every one is generated automatically, exactly once, the moment a visit is marked **completed** ([§9.7](#97-completing-a-visit)), by summing that visit's main service(s) and any addons added during it. Deleting an appointment soft-deletes its income record in lockstep (excluding it from every report without destroying history), and restoring the appointment restores the income record right along with it.

**Commission math:** a visit's commission is locked in at the moment each service is added to it (at booking time for pre-selected services, at add-time for mid-visit addons) using whichever rate applies at that instant — the employee's own default commission rate, or a per-service override if one exists (see [§8.4](#84-per-employee-custom-pricing)). Changing an employee's commission rate later never retroactively changes the commission on visits already recorded.

📸 *Screenshot placeholder — Income (Przychody) monthly summary with the per-employee breakdown table (`docs/screenshots/income-dashboard.png`).*

---

## 13. Analytics

*Module permission: `appointments` — like Income, Analytics has no permission of its own.*

**Analityka** is the salon's business-intelligence dashboard: pick a period (this month, last month, year-to-date, or a custom range) and the whole page — KPI cards, charts, and tables — updates together, each figure also showing its percentage change against the equivalent prior period (except for custom ranges, which have no natural "previous period" to compare against).

Top to bottom, the dashboard covers:

- **Headline KPIs** — revenue, visit count, unique clients, average ticket, each with a period-over-period change.
- **Profit breakdown** — employee costs (salaries + the ZUS-style overhead rate), invoice/supplier costs, and the resulting net profit.
- **Revenue trend** and **service breakdown** charts for the selected period, plus a full profit-structure chart (revenue vs. employee costs vs. invoice costs vs. net).
- A rolling **12-month trend** of revenue/costs/profit — this section is always the trailing 12 months from today, independent of whatever period you've selected above it.
- **Employee performance** — a table of visits, revenue, commission, gross pay, employer cost, net profit and average satisfaction per employee. (Gross pay here is the greater of the employee's guaranteed base salary or their earned commission for the period — commission tops up the base once it exceeds it, rather than stacking on top.)
- **Clients** — new vs. returning clients with a retention rate, a top-10-clients leaderboard, and an "at risk" list of clients who haven't visited in 90+ days.
- **Peak hours** heatmap alongside three headline rates: salon occupancy, cancellation rate, and no-show rate.
- **Service price analysis** — catalogue price vs. what's actually being charged after discounts, per service.
- **Business insights** — a short list of automatically-generated observations (e.g. "employee costs exceed 60% of revenue," "3 unpaid invoices are overdue," "a client segment is at churn risk") that flags things worth your attention without you having to dig for them.

📸 *Screenshot placeholder — Analytics dashboard KPI row and revenue-trend chart (`docs/screenshots/analytics-kpis.png`).*

Per-employee, a separate and more detailed analytics drill-down lives on that employee's own profile page ([§8.4](#84-per-employee-custom-pricing)) rather than here — this dashboard is the salon-wide view.

The [Widok administratora / Dane własne](#36-widok-administratora-admin-view--dane-własne-own-data) toggles apply throughout this page just as they do everywhere else employee-scoped data appears — a superuser previewing with "Dane własne" on will see analytics narrowed to just their own activity.

---

## 14. Absences &amp; Leave Management

*Module permission: `absences` (superuser, admin by default) — plus the separate **supervisor** access path described in [§3.7](#37-supervisors-a-relationship-not-a-role).*

### 14.1 Categories

**Nieobecności → Kategorie** (superuser/admin only) is where absence types are defined — e.g. "Urlop wypoczynkowy" (paid vacation), "Zwolnienie lekarskie (L4)" (sick leave), "Wyjście prywatne" (a short personal errand). Each category is configured as either:

- **Full-day** — requests span a date range (`date_from` → `date_to`).
- **Time-slot** — requests are within a single day, with a specific start/end time (used for short personal absences rather than full days off).

A category can optionally be **tracked**, meaning the system maintains a running balance against a limit — with a configurable accounting period (yearly, resetting on a chosen day of the year; monthly, resetting on a chosen day of the month; or a rolling window of N days), a default limit (in days or hours, matching the category's granularity), and a warning threshold percentage (e.g. warn once 80% of the limit is used).

### 14.2 Requesting time off (employee self-service)

Any employee with a linked login uses **Moje nieobecności** to submit a request: pick a category, the relevant dates/times, and one of their assigned **supervisors** as the approver (the dropdown only offers supervisors actually assigned to them — see [§8.5](#85-assigning-supervisors--direct-reports); an employee with no supervisor assigned sees a warning instead of the form and cannot submit at all). The same page also lists their own request history, with the ability to cancel a still-pending request or cancel an already-approved one (freeing the calendar back up).

If the category is tracked and the request would push the employee over their limit, **the request is blocked outright** at submission time — self-service requests can never exceed a tracked balance; anything closer to the limit but not over it submits fine with only an informational warning.

📸 *Screenshot placeholder — Moje nieobecności request form with category/date fields (`docs/screenshots/absence-request-form.png`).*

### 14.3 Approving or rejecting (supervisor/admin)

**Nieobecności → Wnioski** is a three-tab management screen. Superusers/admins see all three tabs in full and every employee's requests; a supervisor with no broader module access sees only their own team's requests on the first two tabs, and never the third:

1. **Wnioski** — pending requests awaiting a decision, with approve/reject actions. Approving a request that overlaps an existing client appointment opens a conflict-resolution modal instead of approving silently: a table of every conflicting appointment, each with a "zmień stylistę" (reassign) and "zmień termin" (reschedule) action. Reassigning shows only employees who can actually perform the service, aren't absent, and aren't already booked at that time — anyone not on the client's list of preferred stylists is flagged with a small warning icon so you can weigh that before picking. If nobody is available to reassign to, the modal falls back to a cancel-the-visit option with an opt-in "send the client an SMS" checkbox. Once every conflict on the list is resolved (reassigned, rescheduled, or cancelled), the main **Zatwierdź** button unlocks — an always-available secondary **Zatwierdź mimo to** button lets you approve with conflicts still outstanding if you'd rather sort them out manually afterwards. A **"Zastosuj do wszystkich pozostałych konfliktów tego pracownika"** checkbox on the reassign/cancel steps applies the same choice to every other conflict at once instead of clicking through them one by one, and a **"Historia rozwiązań"** link (shown once there's at least one prior action) opens a read-only log of what was reassigned/rescheduled/cancelled, by whom, and when.
2. **L4 / Manualne** — the same screen used to log an absence directly (see [§14.4](#144-logging-an-absence-manually)), plus a list of previously manually-entered absences.
3. **Kategorie** — category management, visible only to superuser/admin (this tab is hidden entirely from supervisor-only access, and hidden on phones for everyone).

Rejecting a request requires typing a reason, which the employee then sees against their own request history.

### 14.4 Logging an absence manually

Rather than waiting for an employee to self-request (useful for something like a same-day sick note called in over the phone), a supervisor or admin can log an absence directly for someone from the **"L4 / Manualne"** tab. Manual entries are **auto-approved** immediately — no separate approval step — and, unlike self-service requests, exceeding a tracked limit only produces a warning rather than a hard block, since a supervisor logging real, already-happened leave shouldn't be prevented from recording it accurately. A supervisor cannot use this to log an absence for *themselves* (that always has to go through the normal self-service request form) unless they're also an admin/superuser.

> ⚠️ **Known quirk:** the manual-entry employee dropdown currently offers every active employee in the salon, not just the acting supervisor's own direct reports — a supervisor could, in principle, log a manual absence for someone outside their team. Treat this as an honesty-system control for now rather than a hard boundary if you rely on the supervisor hierarchy for strict access separation.

### 14.5 Balances, limits &amp; adjustments

**Bilanse nieobecności** shows a spreadsheet-style table — one row per employee per tracked category — with used-vs-limit, a progress bar, and a status badge (ok / warning / exceeded / unlimited). From here an admin/superuser can:

- Set an **individual limit override** for one employee on one category (e.g. a senior employee gets more vacation days than the category default).
- Record a **manual balance adjustment** — a positive or negative correction with a mandatory reason (e.g. carrying over unused days from last year, or correcting a data-entry mistake). Adjustments are cumulative and never expire on their own the way normal usage resets each period.

Both changes are captured in a per-employee audit trail so you can always see who adjusted what balance, and why.

### 14.6 How this connects back to booking appointments

As described in [§9.5](#95-absence-conflicts-when-booking), the appointment system checks this module's data on every booking/edit: **both pending and approved absences block a new appointment** for that employee at that time, distinguished only by the strength of the warning shown (hard error for approved, softer warning for pending). Unlike before, a not-yet-decided request is no longer invisible while it waits: the day and week calendars now show pending absences too, using the same hatched block as an approved one but dashed and lighter, with a small clock icon and an "oczekuje na akceptację" tooltip so it reads as provisional rather than settled. The appointments **list view** carries the same signal per-row — a clock icon next to the employee's name means they have a pending request overlapping that visit's time, and a filled "event-busy" icon means an *approved* absence overlaps it (a genuine conflict, since that absence was approved after the appointment already existed). The public booking page's slot availability, however, still only reacts to *approved* absences — a pending request alone doesn't remove those slots from what clients can self-book.

Submitting a new absence request also gets a heads-up of its own: if the requested period overlaps appointments you already have booked, a confirmation modal lists them before the request goes through. It's informational only and never blocks the submission — your supervisor will see the same conflicts (and the full resolution toolkit above) when they come to approve it.

---

## 15. Settings

*Module permission: `settings` (superuser, admin by default) for most of this section; the Email page specifically is gated by `invoices` since it exists to support invoice ingestion.*

### 15.1 Email/IMAP settings

**Ustawienia → E-mail** configures the mailbox the [invoice email-import feature](#54-automatic-email-import) reads from: IMAP server and port (with built-in setup notes for Gmail app-passwords and Outlook/Office 365), address, and password. A **"Testuj połączenie"** button verifies the credentials without saving anything, and the password itself is deliberately never written to the on-disk settings file — if an environment-level credential is configured on the server, it always takes priority over whatever is typed into this form.

📸 *Screenshot placeholder — Email/IMAP settings page with the connection-test button (`docs/screenshots/settings-email.png`).*

### 15.2 SMS settings

Covered in full in [§11.1](#111-settings) — Twilio credentials, message-type configuration, and the send log all live under **Ustawienia → SMS**.

---

## 16. Appendix

### 16.1 Glossary of recurring Polish UI terms

| Polish | English | Where it appears |
|---|---|---|
| Wizyta | Appointment / visit | Appointments |
| Nieobecność | Absence | Absences |
| Sprzedawca | Seller / supplier | Invoices |
| Faktura | Invoice | Invoices |
| Opłacona / Nieopłacona | Paid / Unpaid | Invoices |
| Przeterminowana | Overdue (computed, not stored) | Invoices |
| Pracownik | Employee | Employees |
| Klient | Client | Clients |
| Usługa | Service | Services |
| Mikrousługa / Dodatkowa | Addon service | Services, mid-visit |
| Bilans | Balance | Absences |
| Widok administratora | Admin View (owner-visibility toggle) | Sidebar, superuser only |
| Dane własne | Own Data (owner-visibility sub-toggle) | Sidebar, superuser only |
| Podwładni / Przełożony | Direct reports / Supervisor | Employees, Absences |
| Korekta danych | Data correction | Power Editor |
| Pulpit | Dashboard | Main navigation |

### 16.2 Known quirks worth remembering

These are real, currently-present behaviours in the application (not hypothetical edge cases) collected throughout this manual — repeated here as a single checklist:

- **Dashboard ≠ salon KPIs.** The main "Pulpit" only reflects invoices/costs; appointment/revenue KPIs live on Analytics and Income instead ([§4](#4-dashboard)).
- **The "Dezaktywuj" button on an active client's detail page actually deletes, not deactivates**, with no in-app undo. Use the list-row icon or the edit-form toggle instead ([§6.5](#65-deactivating-vs-deleting-a-client)).
- **Online bookings bypass the staff duplicate-client warning system** — check for near-duplicate clients periodically if you get a lot of web bookings ([§6.2](#62-creating-a-client)).
- **Pending absence requests don't show on calendars or block public-booking slots visually** — they only reject the booking at save time ([§9.5](#95-absence-conflicts-when-booking), [§14.6](#146-how-this-connects-back-to-booking-appointments)).
- **The manual-absence entry dropdown isn't restricted to a supervisor's own team** — treat the supervisor hierarchy as informational rather than a hard security boundary for that one screen ([§14.4](#144-logging-an-absence-manually)).

### 16.3 Screenshot index

All screenshot placeholders used throughout this manual, for easy batch capture:

| File | Section | Contents |
|---|---|---|
| `landing-hero.png` | 2.1 | Public landing page hero |
| `login.png` | 2.2 | Login screen |
| `sidebar-desktop.png` | 2.4 | Desktop sidebar navigation |
| `roles-edit.png` | 3.3 | Role permission editor |
| `admin-view-toggle.png` | 3.6 | Admin View / Own Data sidebar toggles |
| `dashboard.png` | 4 | Pulpit (Dashboard) |
| `upload-ocr-review.png` | 5.3 | OCR upload wizard, results step |
| `data-import.png` | 5.7 | Caldis.pl data import, running |
| `clients-list.png` | 6.1 | Client list with filters |
| `service-addons.png` | 7.2 | Service addon-compatibility card |
| `calendar-day.png` | 9.2 | Day calendar view |
| `calendar-month.png` | 9.2 | Month calendar view |
| `my-visits-mobile.png` | 9.9 | Moje wizyty mobile page |
| `booking-step3.png` | 10 | Public booking wizard, slot picker |
| `income-dashboard.png` | 12 | Income monthly summary |
| `analytics-kpis.png` | 13 | Analytics KPI row + revenue chart |
| `absence-request-form.png` | 14.2 | Absence request form |
| `settings-email.png` | 15.1 | Email/IMAP settings |
