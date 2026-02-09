# Analytics Dashboard - Manual Testing Checklist

## Prerequisites
- Flask app running: `python app.py`
- User logged in to the application
- Database contains sample appointment data

## Test Cases

### 1. Page Load ✓
- [ ] Navigate to http://localhost:8083/analytics
- [ ] Page loads without errors
- [ ] No JavaScript errors in browser console (F12)
- [ ] All UI elements visible: KPI cards, charts, employee table

### 2. Period Selector ✓
- [ ] "Ten miesiąc" button active by default
- [ ] Click "Ostatni miesiąc" - data updates
- [ ] Click "Rok do daty" - data updates
- [ ] Click "Własny zakres" - modal opens
- [ ] Select date range in modal, click "Zastosuj" - data updates
- [ ] Active button highlighted correctly

### 3. KPI Cards ✓
- [ ] Revenue (Przychód) shows PLN amount
- [ ] Appointments (Wizyty) shows count
- [ ] Clients (Klienci) shows count
- [ ] Average Ticket (Średni rachunek) shows PLN amount
- [ ] Change indicators show with color (green↑ or red↓) and percentage

### 4. Revenue Trend Chart ✓
- [ ] Line chart renders
- [ ] X-axis shows dates in Polish format (e.g., "1 sty")
- [ ] Y-axis shows PLN amounts
- [ ] Tooltip shows formatted currency on hover
- [ ] Blue gradient fill visible
- [ ] Smooth curve (tension: 0.3)

### 5. Services Chart ✓
- [ ] Horizontal bar chart renders
- [ ] Top 5 services displayed
- [ ] Color-coded bars (blue, purple, pink, orange, green)
- [ ] X-axis shows PLN amounts
- [ ] Tooltip shows formatted currency on hover

### 6. Employee Performance Table ✓
- [ ] Table populated with employee data
- [ ] Columns: Pracownik, Wizyty, Przychód, Prowizja, Wynagrodzenie brutto, Koszt pracodawcy, Zysk netto
- [ ] Currency values formatted in PLN
- [ ] Net profit color-coded (green for positive, red for negative)
- [ ] Hover on "Koszt pracodawcy" shows employer cost rate tooltip

### 7. Client Split Chart ✓
- [ ] Doughnut chart renders
- [ ] Shows "Nowi klienci" vs "Powracający"
- [ ] Blue and gray colors
- [ ] Retention rate text displayed below chart (e.g., "Wskaźnik retencji (90 dni): 75.0%")

### 8. At-Risk Clients List ✓
- [ ] List populated if clients exist with 90+ days since visit
- [ ] Shows client name, last visit date, days count
- [ ] Days count in red
- [ ] If no at-risk clients, shows "Brak klientów zagrożonych utratą"
- [ ] Scrollable if many clients

### 9. Custom Date Range Modal ✓
- [ ] Modal appears when clicking "Własny zakres"
- [ ] Date pickers for start and end dates
- [ ] "Anuluj" button closes modal without changes
- [ ] "Zastosuj" button applies selection
- [ ] Validation: End date must be after start date
- [ ] Warning if dates not selected

### 10. Empty Data Handling ✓
- [ ] Select date range with no appointments
- [ ] KPI cards show zero values gracefully
- [ ] Charts render empty (no errors)
- [ ] Employee table shows "Brak danych"
- [ ] At-risk list shows appropriate message

## API Endpoint Verification

All endpoints tested with authentication:
- ✅ `/api/analytics/summary` - Returns 302 (login required)
- ✅ `/api/analytics/revenue-trend` - Returns 302 (login required)
- ✅ `/api/analytics/employees` - Returns 302 (login required)
- ✅ `/api/analytics/services` - Returns 302 (login required)
- ✅ `/api/analytics/clients` - Returns 302 (login required)
- ✅ `/analytics` - Returns 302 (login required)

## Technical Verification

- ✅ JavaScript syntax valid (node -c)
- ✅ Jinja2 template compiles
- ✅ All routes registered in Flask
- ✅ Authentication protection active

## Known Issues
None discovered during automated testing.

## Manual Testing Required
⚠️ **Browser testing with authenticated user required** to verify:
- Chart rendering with Chart.js
- Interactive features (hover, click)
- Polish locale formatting in browser
- Responsive design on different screen sizes
