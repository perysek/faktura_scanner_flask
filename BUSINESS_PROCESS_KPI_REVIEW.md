# Business Process & KPI Framework — MyWay Beauty Salon

Brief proposal for a process-based monthly KPI set and an annual management-review
mechanism, structured the way ISO 9001:2015 (Cl. 4.4, 9.1.3, 9.3) and IATF
16949:2016 (Cl. 9.3.1.1 / 9.3.2.1) require a quality management system to work:
identify the processes, measure each one on **effectiveness** and **efficiency**,
set a target per indicator, and when a target is missed, the yearly review turns
that miss into a scheduled corrective action — not just a number that stays red.

This is a proposal, not an implementation. Every indicator below is calculable
from data that already exists in this application (confirmed against the live
schema); none require new user input or a new data source. Status column shows
whether the underlying query already exists, is proposed-but-not-built (from the
prior conversation's dataviz session), or needs a new aggregation against
existing tables.

## 1. Definitions (ISO 9000:2015 §3.7.10 / §3.7.11)

| Term | Definition | Practical meaning here |
|---|---|---|
| **Effectiveness** | "The extent to which planned activities are realised and planned results are achieved." | Did the process deliver its intended *outcome* — the goal-attainment question. |
| **Efficiency** | "The relationship between the result achieved and the resources used." | How much output per unit of resource (time, cost, headcount) — the resource-cost question. |

Both are required IATF 16949 management-review inputs (§9.3.2.1: "measures of
process effectiveness, measures of process efficiency"), which is exactly the
one-effectiveness + one-efficiency-per-process structure used below.

## 2. Business Process Map

Ten processes cover the application's full scope — the client-facing service
loop, the internal resource/cost engine behind it, and the support/governance
processes that keep the data honest.

| # | Process | Description |
|---|---|---|
| P1 | **Rezerwacja i realizacja wizyt** (Booking & Appointment Fulfillment) | From a client's booking request through appointment completion — scheduling, confirmation, status transitions, cancellations, no-shows. |
| P2 | **Świadczenie usług i jakość obsługi** (Service Delivery & Quality) | The core value-creation act: a stylist performs the booked service; quality is captured via post-visit client rating and price discipline. |
| P3 | **Zarządzanie relacjami z klientem i retencja** (Client Relationship Management & Retention) | Acquiring, retaining and re-engaging clients; identifying at-risk relationships and tracking preferences. |
| P4 | **Zarządzanie cennikiem i ofertą usług** (Service Catalogue & Pricing Management) | Defining services/categories/addons, maintaining catalogue prices and their history, keeping pricing current. |
| P5 | **Zarządzanie zasobami ludzkimi** (Human Resources / Staff Management) | Staffing capacity, scheduling load, absences, compensation structure (salary/commission/employer cost). |
| P6 | **Komunikacja z klientem — przypomnienia SMS** (Client Communication / Reminders) | Automated SMS reminders, confirmations and post-visit rating requests, and whether they're actually delivered. |
| P7 | **Zarządzanie finansami i rentownością** (Financial & Profitability Management) | Revenue, direct costs, margin — the process that aggregates the financial output of P1–P6. |
| P8 | **Zaopatrzenie i zarządzanie dostawcami** (Procurement & Supplier / Invoice Management) | OCR-based invoice capture, supplier tracking, payment terms and timeliness. |
| P9 | **Zarządzanie danymi i dostępem** (Data Import & System Administration) | Bulk data sync from the external booking platform, user access control — the support process akin to IT/document control. |
| P10 | **Analiza biznesowa i przegląd zarządzania** (Business Analytics & Management Review) | The monitoring/measurement/review process itself (ISO Cl. 9.1.3 / 9.3) — this document's own home process. |

## 3. Process KPI Table

One effectiveness + one efficiency indicator per process, each a single value per
finished month. **Status**: 🟢 already computed by an existing endpoint · 🟡
proposed in the prior dataviz session, endpoint not yet wired · 🔵 new
aggregation needed, but only against tables/columns confirmed to already exist.

| # | Process | Effectiveness indicator | Formula | Efficiency indicator | Formula | Status |
|---|---|---|---|---|---|---|
| P1 | Booking & Fulfillment | **Wskaźnik realizacji wizyt** | `completed ÷ total_scheduled` | **Obłożenie salonu** | `completed ÷ theoretical_capacity` | 🟢 `/analytics/occupancy` |
| P2 | Service Delivery & Quality | **Średnia ocena satysfakcji klientów** | `AVG(satisfaction_score)`, 1–5 scale | **Przychód na godzinę świadczenia usługi** | `Σ price_charged ÷ (Σ duration_minutes / 60)` | 🟡 satisfaction / 🔵 revenue-per-hour (uses `appointment_services.duration_minutes`, not currently aggregated anywhere) |
| P3 | Client Relationship & Retention | **Wskaźnik retencji klientów (90 dni)** | `retention_rate` | **Średnia liczba wizyt na klienta (12 mies.)** | `Σ(visit_count × client_count) ÷ Σ client_count` | 🟢 retention / 🟡 visit frequency |
| P4 | Catalogue & Pricing | **Udział usług z aktualizowaną ceną (12 mies.)** | services with ≥1 `service_price_history` row in trailing 12mo ÷ active services | **Wskaźnik realizacji ceny katalogowej** | `avg_charged ÷ catalogue_price` (aggregate) | 🔵 both — `service_price_history` exists, not queried this way |
| P5 | HR / Staff Management | **Średnie wykorzystanie zespołu** | `MEAN(utilisation_pct)` across active employees | **Koszt personelu na wizytę** | `employee_costs ÷ completed` | 🟡 utilisation / 🟢 cost (combines `/analytics/profit` + `/analytics/occupancy`) |
| P6 | Client Communication (SMS) | **Wskaźnik niestawiennictwa przy dostarczonym przypomnieniu** | no-show rate among appointments with a *delivered* SMS reminder | **Wskaźnik skutecznej dostawy SMS** | `delivered ÷ sent` (`sms_reminders.status`) | 🔵 both — needs a join of `sms_reminders`/`sms_events` to `appointments.status`, not built |
| P7 | Financial & Profitability | **Marża zysku netto** | `profit_margin_pct` | **Wskaźnik kosztów całkowitych** | `(employee_costs + invoice_costs) ÷ revenue` | 🟢 both — `/analytics/profit` |
| P8 | Procurement & Suppliers | **Terminowość płatności faktur** | invoices paid by `payment_due_date` ÷ total invoices | **Poziom automatyzacji przetwarzania faktur** | `AVG(ocr_confidence)` | 🔵 both — `invoices` table has both fields, neither aggregated today |
| P9 | Data Import & Administration | **Wskaźnik powodzenia importów danych** | completed imports ÷ total import attempts | **Średni czas trwania importu** | `AVG(finished_at − started_at)` | 🔵 both — `import_logs` table, no reporting query exists |
| P10 | Business Analytics & Mgmt Review | **Odsetek wskaźników z osiągniętym celem rocznym** | indicators (of this table) meeting their annual target ÷ 20 | **Terminowość zamknięcia działań korygujących** | corrective actions closed on time ÷ actions opened | 🔵 self-referential — computed from the Annual Review Record (§5), not the app DB |

Twenty indicators total (10 processes × 2). Roughly a third are live today, a
third were scoped in this session but not yet built, and a third need a new
query against data the app already stores but has never reported on.

## 4. Monthly → Annual Rollup

- **Monthly value**: every indicator above is a rate/ratio/average, computed for
  the calendar month using the existing period-selector mechanism (`current_month`
  or a specific past month via the custom-range picker).
- **Annual value**: recompute over the full calendar year (`current_year`
  equivalent, Jan 1 – Dec 31), **not** a naive average of the 12 monthly values.
  Ratio-type KPIs have unequal monthly denominators (a slow August and a busy
  December shouldn't count equally in the year figure), so the annual number
  must be recomputed against the full-year numerator/denominator, exactly the
  way `get_date_ranges('current_year')` already works in this app.
- **Year-over-year trend**: the app's `current_year` period already resolves a
  `previous_start/previous_end` window one year back — YoY comparison is a
  native capability, not new work.

## 5. Annual Management Review (ISO 9.3 / IATF 9.3.1.1–9.3.3.1)

IATF 16949 §9.3.1.1 requires management review **at least annually**, more often
if risk to performance increases. §9.3.2.1 requires "measures of process
effectiveness" and "measures of process efficiency" as review inputs — precisely
the 20-indicator table above. §9.3.3 requires the review to produce **documented
decisions and actions**, with an owner and a deadline, retained as evidence; per
IATF, an action plan is mandatory whenever a target is not met.

**Review procedure, once per year (or quarterly checkpoint if a process is
trending badly enough to warrant closer watch):**

1. For every row in the table below, compare **Actual (year)** to **Target
   (year)** — target is set/adjusted by management at the *start* of each year,
   informed by the prior year's actual and trend.
2. If target is met: record it, no action required.
3. If target is missed: this becomes a **mandatory agenda item** — state the
   likely root cause (referencing the monthly trend line, not just the single
   annual number — a miss after 11 good months reads differently than a miss
   after a steady 12-month decline), define one corrective action, assign an
   owner, set a due date.
4. Carry open corrective actions into the next year's review as a standing input
   (ISO 9.3.2 "status of actions from previous reviews") — this is what P10's own
   efficiency indicator (on-time closure rate) measures.

### Annual Review Record — template

| Process | Indicator | Type | Year | Target | Actual | Prior-Year Actual | Trend | Target Met? | Root Cause (if missed) | Corrective Action | Owner | Due Date | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | Wskaźnik realizacji wizyt | Eff. | 20XX | | | | ▲/▼/= | Y/N | | | | | |
| P1 | Obłożenie salonu | Eff. | 20XX | | | | ▲/▼/= | Y/N | | | | | |
| … | … | … | … | | | | | | | | | | |

(One row per indicator per year — 20 rows for a full annual cycle. Blank
templates are intentional; targets are a management decision each cycle, not
something this document should presume.)

## 6. Suggested build order

Not part of the framework itself, just a practical note: the 🟢/🟡 rows cost
nothing beyond wiring existing endpoints into a KPI view. The 🔵 rows (P2's
revenue-per-hour, all of P4/P6/P8/P9) each need one new aggregation query — none
of them are large, but P6 (SMS-effectiveness) is the one genuinely new *join*
across modules that don't talk to each other today, and is probably the
highest-value one to build first: it's the only indicator here that tells you
whether money currently being spent on SMS reminders is doing anything.

---

**References**

- [ISO 9001 – Clause 9.3.2 Management Review Inputs](https://msspassociation.org/training-courses/iso-standards-in-plain-english/iso-9001-clauses/iso-9001-clause-9-3-2-management-review-inputs)
- [ISO 9001 – Clause 9.3.3 Management Review Outputs](https://msspassociation.org/training-courses/iso-standards-in-plain-english/iso-9001-clauses/iso-9001-clause-9-3-3-management-review-outputs)
- [IATF 16949:2016 Clause 9.3.1.1 / 9.3.2.1 / 9.3.3.1 — Pretesh Biswas](https://preteshbiswas.com/2023/08/09/iatf-169492016-clause-9-3-1-1-management-review-clause-9-3-2-1-management-review-inputs-and-clause-9-3-3-1-management-review-outputs/)
- [ISO 9000:2015 — Quality management systems, Fundamentals and vocabulary](https://www.iso.org/obp/ui/#iso:std:iso:9000:ed-4:v1:en)
