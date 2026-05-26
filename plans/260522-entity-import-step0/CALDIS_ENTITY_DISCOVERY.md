# Caldis.pl Entity Page Discovery

**Investigated:** 2026-05-26 by perysek + Claude  
**Session file used:** assets/temp/caldis_session.json  
**Browser:** Chrome (export button selector captured from DevTools)

---

## 1. Clients

**Listing URL:** `https://caldis.pl/Client`  
**Total rows in production today:** 773  
**Pagination:** Unknown — export captures all rows in one file; not investigated further  
**Export button present:** YES  
**Export format:** XLSX  
**Direct download URL:** triggered via dropdown click at selector:
`body > nav > div.container-fluid.navbar-main > div.navbar-toolbar > div.toolbar-filters > div:nth-child(3) > div > ul > li:nth-child(2) > a`  
Full XPath: `/html/body/nav/div[1]/div[2]/div[2]/div[2]/div/ul/li[2]/a`

> Phase 04 should click this element (or replay the POST/GET it triggers) rather than
> constructing a direct download URL — the network request URL is not yet captured.

### Column Layout (22 columns in export)

| Caldis Column | App DB Field | Notes |
|---|---|---|
| `Nazwa` | `clients.first_name` + `clients.last_name` | **Combined field** — split on first space. Single-word entries → `first_name=Nazwa`, `last_name=''` (empty string; DB is NOT NULL) |
| `Telefon` | `clients.phone` | Mixed formats: `509626642` and `501 127 731` — strip spaces in `normalize_phone()` before insert |
| `Data ostatniej wizyty` | `clients.last_visit_date` | Format: `2026-03-30 10:00:00` — truncate to `DATE` on insert |
| `Notatki` | `clients.notes` | Free text, keep as-is; most rows are empty |
| `E-mail` | `clients.email` | **0/773 populated in production** — skip column entirely; always NULL on import |
| `ClientTypeText` | (ignored) | Values: "Firma" (569), "Osoba" (204) — not in app schema |
| `Kraj`, `Miasto`, `Ulica`, `Kod pocztowy` | (ignored) | Address fields not in app schema |
| `NIP`, `PESEL`, `VAT UE`, `Inny identyfikator podatkowy` | (ignored) | Tax/ID fields not in app schema |
| `Pole dodatkowe 1–6` | (ignored) | All empty in production |
| `Zgoda marketingowa` | (ignored) | Not in app schema |
| `Karnety` | (ignored) | Not in app schema |

### Quirks / Gotchas

- **No stable client ID column.** The XLSX contains no caldis-side identifier. Phase 04's
  match logic must use `(normalized_phone, normalized_name)` — fuzzy matching, not ID-based.
  This is the biggest reliability risk in the entire Step-0 pipeline.
- **`Nazwa` is a single combined field.** Example values: "Adam Wiśniewski", "Agata",
  "Agnieszka Majzner". Split on first space only. If no space, use full value as
  `first_name` and `''` as `last_name`.
- **Phone format inconsistency.** Two formats observed: plain digits `509626642` and
  spaced `501 127 731`. `normalize_phone()` must strip all non-digit characters.
- **`ClientTypeText` values are misleading.** 569/773 rows show "Firma" even though they
  are individual salon clients. Treat this column as noise; do not map it.
- **`last_visit_date` has time component.** Store only the date part (`::date` cast or
  `.date()` in Python) — the time is always an appointment slot, not meaningful as a
  standalone field.
- **2/773 rows have no phone.** `normalize_phone()` must handle NULL input gracefully.

### Fixture File

`tests/fixtures/caldis_entities/clients_sample.xlsx` — 10 anonymised rows  
Real `Nazwa` values replaced with "FirstName X." pattern; phones replaced with `500XXXXXX`.

---

## 2. Employees

**Status:** SKIPPED — only one new employee to be added manually. No caldis export needed.  
**Fixture file:** N/A

### Column → App Field Mapping

| Caldis Column | App DB Field | Notes |
|---|---|---|
| (not investigated) | employees.first_name | manual add |
| (not investigated) | employees.last_name | manual add |
| (none in caldis) | employees.commission_rate | NOT synced — set manually in app |
| (none in caldis) | employees.base_salary | NOT synced — set manually in app |

---

## 3. Services

**Listing URL:** `https://caldis.pl/Services`  
**Total services today:** Not counted — pagination observed  
**Export button present:** NO — DOM table only  
**Service addons handling:** Not a concept in caldis. Addons exist only in the app DB.
Services are a flat list. `service_addons` table is out of scope for all Step-0 phases.

### How Data Is Loaded

Services are loaded via XHR (jQuery AJAX), not rendered server-side:

- **XHR request URL pattern:**
  `https://caldis.pl/Services/List?f.Pagination.CurrentPage=1&f.Order.Name=Name&f.Order.Descending=True&f.Search=&X-Requested-With=XMLHttpRequest&_=<timestamp>`
- **DOM table selector:** `#dynamic-content > div > table`
- **Full XPath:** `/html/body/div[4]/div/div/div/table`

Phase 04 should hit the XHR URL directly (increment `CurrentPage` for pagination)
rather than scraping the rendered DOM.

> The `_=<timestamp>` query param is a jQuery cache-buster. Phase 04 should either
> omit it or supply `int(time.time() * 1000)` — caldis does not validate it.

### Column → App Field Mapping

| Caldis Column | App DB Field | Notes |
|---|---|---|
| `NAZWA` | `services.name` | direct |
| `Cena brutto` | `services.price` | Format: `#.00` (decimal, no "zł" suffix in XHR response) |
| `czas usługi` | `services.duration_minutes` | Integer minutes, no decimals |
| (none in caldis) | `services.category` | Default to `'Inne'` on insert; no category concept in caldis |
| (none in caldis) | `services.description` | NULL on insert |

### Quirks

- **No export button** — DOM/XHR scraping required. Phase 04 is more complex for services
  than for clients.
- **No category field in caldis.** App DB has `services.category NOT NULL`. All imported
  services must be assigned a default category (recommend `'Inne'`) or inferred from the
  name using a keyword map if desired.
- **Pagination:** `CurrentPage` param confirmed present. Phase 04 must loop pages until
  the response table is empty or a total-count indicator is reached.
- **Response format:** HTML fragment returned by the XHR (jQuery replaces
  `#dynamic-content`), not JSON. Phase 04 must parse HTML, not JSON.

### Fixture File

N/A — services contain no PII. Phase 03 and Phase 05 unit tests use 4–5 synthetic rows
written directly in the test file:

```python
SYNTHETIC_SERVICES = [
    {"NAZWA": "Strzyżenie damskie", "Cena brutto": "150.00", "czas usługi": "60"},
    {"NAZWA": "Koloryzacja", "Cena brutto": "250.00", "czas usługi": "120"},
    {"NAZWA": "Manicure hybrydowy", "Cena brutto": "100.00", "czas usługi": "60"},
    {"NAZWA": "Trwała ondulacja", "Cena brutto": "200.00", "czas usługi": "90"},
]
```

---

## 4. Cross-Cutting Findings

- **Auth state:** `caldis_session.json` is sufficient for the clients export button.
  Services XHR URL also works with the same session cookie. No additional permissions
  or sub-accounts needed.
- **Rate limits:** Not observed during manual investigation.
- **Browser language:** Polish UI throughout (`NAZWA`, `Cena brutto`, `czas usługi`,
  `Klienci`, etc.). No locale switch needed or available.
- **Concurrent access:** Not tested. Assumed safe — caldis is a read-heavy SaaS with
  session isolation.
- **No stable entity IDs:** Neither clients nor services expose a caldis-side primary key
  in their exports. All matching must be by normalised name + phone (clients) or
  normalised name (services).

---

## 5. Implementation Recommendations for Phase 04

Based on these findings, Phase 04 should:

1. **Clients:** Click the export dropdown button (selector documented above) using
   Playwright, wait for the XLSX download, read via `pandas.read_excel()`. No DOM
   scraping needed — one button click produces the full 773-row export.
2. **Services:** Hit the XHR endpoint directly with a `requests.Session` (or Playwright
   `page.evaluate` + `fetch`) using the caldis session cookie. Loop `CurrentPage`
   until response HTML contains no `<tr>` rows. Parse HTML with `BeautifulSoup`.
3. **Employees:** Skip entirely — manual add of one person.
4. **Service addons:** Skip entirely — not a concept in caldis.

### Estimated Phase 04 Effort

~3 hours as originally estimated:
- ~1 h: clients export (button click + XLSX parse — straightforward, mirrors Step-1)
- ~2 h: services XHR loop + HTML parse (more complex; pagination + HTML response)

The main risk is the services HTML response format — if caldis returns a full-page
reload instead of a fragment, the table selector must be adjusted.
