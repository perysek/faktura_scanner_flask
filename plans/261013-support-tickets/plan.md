# Wiadomości do administratora serwisu — proposal

**Status:** Proposal, not started. The sidebar row and the `/wiadomosci` route with a placeholder page are live in code (2026-10-13). Everything below is design only.

**Entry point:** sidebar standalone row *Klikam w to co trzeba / ale coś mi nie pasuje* → `/wiadomosci` (`SupportMessagesPage.tsx`).

---

## 1. Who we are designing for

Stylists, nail techs and receptionists. Their phone is their computer, and what they know is Instagram, Facebook and Messenger. They don't know what a "ticket", "status", "priority", "browser" or "URL" is, and they never will. They also have **wet hands, a client in the chair and ~30 seconds**.

Design rules that follow from that:

| Rule | What it means here |
|---|---|
| **Feels like Messenger, not like a helpdesk** | Conversation threads with chat bubbles, no forms with 12 fields. |
| **Tap, don't type** | Every question that can be a big tile with an emoji is one. Only one free-text box. |
| **We collect the technical stuff, not them** | Page, device, app version, recent errors are attached automatically and invisibly. |
| **Zero jargon** | No "zgłoszenie #", "status", "priorytet", "kategoria" in the user's UI. Human phrases only (§5). |
| **Photo beats description** | "Pokaż nam zdjęcie ekranu" is a first-class button, not an afterthought. |
| **Always tell them what happens next** | After sending: "Odpiszemy tutaj. Zobaczysz czerwoną kropkę w menu." |
| **Thumb-friendly** | Tiles ≥ 3rem high, one column on phone, primary button pinned at the bottom. |

---

## 2. The page `/wiadomosci` (user view)

```
┌──────────────────────────────────────────┐
│ Wiadomości do administratora serwisu     │
│ Zgłoszenia błędów i inne wiadomości…     │
├──────────────────────────────────────────┤
│  ┌────────────────────────────────────┐  │
│  │   ✍️  Napisz do nas                 │  │  ← big primary button
│  └────────────────────────────────────┘  │
│                                          │
│  Twoje rozmowy                           │
│  ┌────────────────────────────────────┐  │
│  │ 🐞 Kalendarz nie pokazuje Ani   ● │  │  ← red dot = new reply
│  │ 💬 Czekamy na Twoją odpowiedź      │  │
│  │ „Czy to było na telefonie?” · 10:42│  │
│  ├────────────────────────────────────┤  │
│  │ 💡 Przypomnienie SMS dzień wcześniej│ │
│  │ ✅ Gotowe · wczoraj                 │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

- Empty state (first visit): friendly illustration-free text — "Coś nie działa albo masz pomysł? Napisz — czytamy wszystko." + the same button.
- Threads sorted: *needs your answer* first, then newest activity.
- Closed threads older than 30 days fold into "Starsze rozmowy".

---

## 3. New-message flow (3 taps + 1 sentence)

Full-screen on phone, centered card (max 36rem) on desktop. A progress line of 3 dots, a "Wstecz" link, nothing else.

### Step 1 — "Co się stało?"

```
┌───────────────┐ ┌───────────────┐
│ 🐞            │ │ 🤔            │
│ Coś nie       │ │ Nie wiem, jak │
│ działa        │ │ coś zrobić    │
└───────────────┘ └───────────────┘
┌───────────────┐ ┌───────────────┐
│ 💡            │ │ 💬            │
│ Mam pomysł    │ │ Inna sprawa   │
└───────────────┘ └───────────────┘
```

Maps to `kind`: `bug` / `how_to` / `idea` / `other`. Tapping a tile goes straight to step 2 (no "Dalej" button).

### Step 2 — "Gdzie?"

Tiles named the way *they* name things, not after our modules:

📅 Wizyty i kalendarz · 👩 Klientki · 💅 Usługi i ceny · 📱 SMS-y do klientek · 🌴 Urlopy i wolne · 🔑 Logowanie / hasło · 🧾 Koszty i faktury · ❓ Nie wiem / gdzie indziej

**Pre-selected automatically** from the page the user was on before opening `/wiadomosci` (we remember the previous route, §6). They only confirm with one tap, or change it. For "Mam pomysł" this step is skipped when the previous route is unknown.

### Step 3 — "Opowiedz nam"

```
┌──────────────────────────────────────┐
│ Opowiedz nam, co się stało           │
│ ┌──────────────────────────────────┐ │
│ │ np. „Dodaję wizytę Ani na 15:00, │ │
│ │ klikam Zapisz i nic się nie      │ │
│ │ dzieje”                          │ │
│ └──────────────────────────────────┘ │
│ 🎤 Możesz też nagrać głosem —        │
│    kliknij mikrofon na klawiaturze   │
│                                      │
│ ┌──────────────────────────────────┐ │
│ │ 📷 Dodaj zdjęcie ekranu          │ │  ← opens gallery/camera, up to 3
│ └──────────────────────────────────┘ │
│                                      │
│ Czy to blokuje Ci pracę?             │  ← only for 🐞
│ [ 🔥 Tak, nie mogę pracować ]        │
│ [ 🙂 Nie, mogę poczekać     ]        │
│                                      │
│ ┌──────────────────────────────────┐ │
│ │          Wyślij  ➤               │ │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

- Placeholder text changes per `kind` (bug → "co klikasz i co się dzieje", how_to → "co chcesz zrobić", idea → "co by Ci ułatwiło pracę").
- Minimum 10 characters **or** one photo — whichever comes first. Error copy: "Napisz chociaż jedno zdanie albo dodaj zdjęcie 🙂".
- Small grey hint under the text box: "Nie wpisuj tu numerów telefonów ani danych klientek." (RODO, §9).
- Draft autosaves to `localStorage` per user, so a phone call in the middle doesn't kill it.

### Confirmation

"Dostaliśmy! 🙌 Odpiszemy tutaj — zobaczysz czerwoną kropkę przy *Klikam w to co trzeba*. Zwykle odpowiadamy w ciągu jednego dnia roboczego." + button "Wróć do pracy" (back to the previous route).

For 🔥 blocking: "Zajmiemy się tym jak najszybciej." (no promise of minutes we can't keep).

---

## 4. Conversation view (both sides)

Messenger-style thread at `/wiadomosci/:id`:

- Bubbles: user's on the right (accent colour), admin's on the left with a small "Administrator" label, system events as grey centered lines ("Naprawiamy 🔧 · 14:02").
- Photo attachments as thumbnails, tap to open full-screen.
- Reply box pinned at the bottom with 📷 button.
- When the thread is **Gotowe**, two big buttons replace the reply box:
  - **"Działa, dziękuję ✅"** → closes the thread.
  - **"Nadal nie działa 😕"** → reopens it and focuses the reply box.

---

## 5. Lifecycle (state machine)

```
             user sends
                 │
                 ▼
            ┌─────────┐  admin opens it   ┌─────────┐
            │  new    │ ───────────────▶ │ seen    │
            └─────────┘                   └────┬────┘
                                                │ admin: "biorę się za to"
                                                ▼
   user replies   ┌──────────────┐  admin asks ┌──────────────┐
  ┌──────────────▶│ in_progress  │────────────▶│ waiting_user │
  │               └──────┬───────┘             └──────┬───────┘
  │                      │ admin: fixed/answered      │ no reply 10 days
  │                      ▼                            │ (2 reminders)
  │               ┌──────────────┐                    │
  └── "Nadal nie  │  resolved    │◀───────────────────┘
      działa"     └──────┬───────┘
      (≤14 days)         │ "Działa ✅"  or  7 days silence
                         ▼
                  ┌──────────────┐
                  │   closed     │   (+ declined / duplicate as close reasons)
                  └──────────────┘
```

| Internal status | What the **user** sees | What the **admin** sees |
|---|---|---|
| `new` | ✉️ Wysłane | 🆕 Nowe |
| `seen` | 👀 Przeczytane | Przeczytane |
| `in_progress` | 🔧 Zajmujemy się tym | W toku |
| `waiting_user` | 💬 Czekamy na Twoją odpowiedź | Czeka na użytkownika |
| `resolved` | ✅ Gotowe — sprawdź, czy działa | Rozwiązane (czeka na potwierdzenie) |
| `closed` | Zakończone | Zamknięte · powód |

**Close reasons:** `confirmed` (user tapped ✅), `auto` (7 days silence after resolved / 10 days in waiting_user), `declined` (idea we won't build — must carry a human explanation, shown as "Nie tym razem 🙏 + wyjaśnienie"), `duplicate` (merged into another thread; user sees "Połączyliśmy to z Twoją wcześniejszą wiadomością").

**Transition rules**

- Only the admin moves `new→seen→in_progress→waiting_user/resolved`. `seen` is set automatically on first admin open.
- An admin message with the toggle "Pytam o coś" sets `waiting_user`; any user reply in `waiting_user` flips back to `in_progress`.
- User can reopen `resolved` anytime and `closed` within 14 days → `in_progress`. After 14 days the reply box says "Ta rozmowa jest zamknięta — napisz nową wiadomość" with a button that pre-fills a link to the old one.
- Every transition writes a system message into the thread + a row in the existing activity-history log.
- Auto-close and reminders run in the existing APScheduler (`scheduler.py`) as one daily job, behind the same scheduler lock the SMS jobs use.

---

## 6. What we capture automatically (invisible to the user)

Stored as `context` JSONB on the ticket, shown to the admin in a collapsible "Szczegóły techniczne" panel:

- `route` (page the form was opened from — kept in `sessionStorage` by a tiny listener in `AppShell`, last 5 routes), `opened_at`.
- Device: user agent → parsed to "iPhone · Safari 18" / "Android · Chrome"; viewport; standalone-PWA flag; theme (light/dark).
- App: frontend build hash (`import.meta.env`), backend version.
- Who: user id, role, linked employee, salon (once multi-tenant).
- **Last 10 frontend errors** (a ring buffer filled by `window.onerror` / `unhandledrejection`) and **last 5 failed API calls** (method, path, status, timestamp — no bodies) from the existing `fetch` wrapper.

This is the whole trick: the user writes "nie działa zapisz", we already know it was `POST /api/appointments → 409` on an iPhone two minutes ago.

---

## 7. Admin side (superuser inbox)

Same route `/wiadomosci`, different view when `role === 'superuser'` (the nav row stays identical for everyone).

```
┌ Filtry: [Wszystkie ▾] [🔥 Blokujące] [Czeka na mnie] [Rodzaj ▾] [Szukaj…] ┐
├──────────────────────────────────────────────────────────────────────────┤
│ 🔥 🐞 #41 Kalendarz nie zapisuje   Anna K. · recepcja   Nowe     12 min │
│    🤔 #40 Jak dodać urlop          Ola · stylistka      W toku    2 h   │
│    💡 #38 SMS dzień wcześniej      Kasia · admin        Czeka…    3 d   │
└──────────────────────────────────────────────────────────────────────────┘
```

- Default sort: blocking first, then oldest waiting-on-admin. Age badge turns amber > 1 working day, red > 3.
- Thread view = same conversation + right-hand panel: technical context (§6), admin priority (P1/P2/P3 — independent of the user's 🔥), status buttons, close reason, "Połącz z…" (merge duplicate), optional "Utwórz issue na GitHubie" (stores `github_issue_url`).
- **Internal notes:** yellow bubbles visible only to superusers.
- **Saved replies** (szablony): e.g. "Sprawdziłem — działa. Odśwież stronę (przeciągnij w dół na telefonie) i daj znać 🙂".

---

## 8. Notifications

| Event | User | Admin |
|---|---|---|
| New message from user | — | in-app badge + e-mail (existing e-mail settings); 🔥 blocking → also SMS via Twilio (one per ticket, opt-out in settings) |
| Admin replies / status change | red dot on the sidebar row (`.sidebar-nav-badge` already exists) + dot on mobile header menu | — |
| Reminder in `waiting_user` (day 3, day 7) | in-app + e-mail if the user has one | — |

Unread count: `GET /api/support/unread-count`, polled every 60 s and on route change, from `AuthContext` or a small `SupportUnreadContext`. No websockets in v1.

---

## 9. Data model (PostgreSQL / Alembic)

```
support_tickets
  id, number (human sequence), created_by_user_id → users,
  salon_id (nullable until multi-tenant), kind enum(bug,how_to,idea,other),
  area enum(appointments,clients,services,sms,absences,login,invoices,unknown),
  is_blocking bool, admin_priority smallint null, status enum(§5),
  close_reason enum null, duplicate_of_id → support_tickets null,
  title varchar(120)  -- auto: first sentence of the first message
  context jsonb, github_issue_url text null,
  created_at, updated_at, last_user_activity_at, last_admin_activity_at,
  resolved_at, closed_at, deleted_at  -- soft delete, like the rest of the app

support_messages
  id, ticket_id → support_tickets, author_user_id → users null (null = system),
  author_kind enum(user,admin,system), body text, is_internal bool,
  asks_user bool, created_at, read_by_author_side_at, read_by_other_side_at

support_attachments
  id, message_id → support_messages, storage_path, mime, size_bytes,
  width, height, created_at
```

Indexes: `(created_by_user_id, status)`, `(status, is_blocking, created_at)`, `(ticket_id, created_at)`.

**Privacy / RODO:** screenshots can contain client data — access only for the author and superusers; EXIF stripped and images downscaled to 1600 px on the client before upload; attachments purged 90 days after `closed_at`. Message bodies are plain text, rendered escaped.

---

## 10. API

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/api/support/tickets` | any (own) / superuser (all, filters) | |
| POST | `/api/support/tickets` | any | multipart: kind, area, body, is_blocking, context, ≤3 images × 5 MB. Rate limit 5/h/user |
| GET | `/api/support/tickets/:id` | author / superuser | marks read for the caller's side |
| POST | `/api/support/tickets/:id/messages` | author / superuser | superuser may set `is_internal`, `asks_user` |
| POST | `/api/support/tickets/:id/confirm` · `/reopen` | author | §5 rules |
| PATCH | `/api/support/tickets/:id` | superuser | status, admin_priority, close_reason, duplicate_of_id, github_issue_url |
| GET | `/api/support/unread-count` | any | |

Backend layering follows the app's usual routes → service → repository split; all transition rules live in one `SupportTicketService`, never in routes.

---

## 11. Delivery phases

1. **F1 — core loop:** migrations, repository/service with the state machine, user form (3 steps), user thread view, superuser list + thread, manual statuses. Tests for every transition.
2. **F2 — notifications:** unread badge, e-mail to admin, 🔥 SMS, reminder + auto-close job.
3. **F3 — context capture:** route history, error ring buffer, failed-request log, screenshots with client-side resize/EXIF strip.
4. **F4 — admin comfort:** saved replies, internal notes, merge duplicates, GitHub issue export, simple stats (first-response time, resolution time, reopen rate, tickets per area).

---

## 12. Open questions (need Piotr's call)

1. **Who is "administrator serwisu"?** Assumed: you, as `superuser`. Should a salon's own `admin` also see their salon's messages (read-only), or is this strictly user ↔ platform operator?
2. **Multi-tenant:** is `salon_id` already a thing in this app, or do we add the nullable column now and fill it later?
3. **🔥 SMS to you:** OK with Twilio cost per blocking report, or e-mail only?
4. **Response-time promise:** is "w ciągu jednego dnia roboczego" a promise you want printed on the screen?
5. **Field-test users:** can 2–3 of the Booksy/Fresha-comparison testers try a clickable mock of §3 before F1 starts?
