# Seller Sync - Functionality & UX Improvement Proposal

## Executive Summary

The current seller sync feature detects data discrepancies but provides **poor user experience** by only showing counts without actionable information or fix workflows. This document proposes improvements to make the sync feature useful and user-friendly.

---

## Current State Analysis

### How Sync Works (Backend)

The `POST /api/sellers/sync` endpoint (api_routes.py:1595-1671):

1. **Fetches all invoices and sellers** from the database
2. **Indexes sellers by NIP** for fast lookup
3. **Iterates through invoices** checking for:
   - **Missing sellers**: Invoices with NIPs not in sellers table
   - **Name discrepancies**: Invoices where seller name doesn't match the stored seller name
4. **Returns detailed results**:
   ```json
   {
     "success": true,
     "missing_sellers": [
       {
         "nip": "1234567890",
         "name": "XYZ Firma",
         "count": 5,
         "invoices": [{...}]
       }
     ],
     "name_discrepancies": [
       {
         "seller_id": 1,
         "seller_nip": "1234567890",
         "seller_name": "ABC Sp. z o.o.",
         "invoice_id": 10,
         "invoice_number": "FV/2024/001",
         "invoice_seller_name": "ABC sp z oo"
       }
     ],
     "summary": {
       "total_sellers": 10,
       "total_invoices": 100,
       "missing_sellers_count": 0,
       "discrepancies_count": 10
     }
   }
   ```

### Current UI Problems

#### ❌ Problem 1: No Visual Feedback
**File**: `templates/sellers/list_refined.html:593`
```javascript
Notifications.success(`Zsynchronizowano. Brakujacych: ${result.summary.missing_sellers_count}, niezgodnosci: ${result.summary.discrepancies_count}`);
```

**Issue**: Toast notification disappears after 3-5 seconds. User sees "10 discrepancies" but has no way to:
- See which invoices have issues
- Understand what the discrepancy is
- Fix the issues

#### ❌ Problem 2: Disconnected Code
- `static/js/sellers/list.js` has a **complete sync results UI** with:
  - Tables showing missing sellers and discrepancies
  - Action buttons to fix issues
  - Full-page sync results view
- `templates/sellers/list_refined.html` has its **own inline JavaScript** that doesn't use the above functionality
- Result: **Wasted code** + **Poor UX**

#### ❌ Problem 3: No Action Path
After sync shows "10 discrepancies", user has NO clear next steps:
- Can't see what the issues are
- Can't fix them individually
- Can't bulk fix
- Must manually search invoices and guess what's wrong

---

## The 10 Discrepancies Explained

When sync reports "niezgodnosci 10", it means there are **10 invoices** where:

```
Stored in Database (sellers table):
  NIP: 1234567890
  Name: "ABC Sp. z o.o."

Stored in Invoice (invoices table):
  seller_nip: "1234567890"  ✓ MATCHES
  seller_name: "ABC sp z oo"  ✗ DOESN'T MATCH
```

### Common Causes:
1. **OCR errors**: "Sp. z o.o." → "sp z oo" (missing dots)
2. **Formatting differences**: "ABC S.A." vs "ABC SA" vs "ABC - S.A."
3. **Manual data entry typos**
4. **Legal name changes** not propagated to all invoices
5. **Accented characters**: "Łódź" vs "Lodz"

---

## Proposed Improvements

### ✅ Improvement 1: Full Sync Results View

**Add sync results UI to `list_refined.html`**

#### UI Structure:
```
┌─────────────────────────────────────────────┐
│ SYNCHRONIZACJA DANYCH                       │
│ ─────────────────────────────────────────── │
│                                             │
│ Summary Stats:                              │
│ • Sprzedawcy w bazie: 45                    │
│ • Faktury w bazie: 234                      │
│ • Brakujący sprzedawcy: 0                   │
│ • Niezgodności nazw: 10                     │
│                                             │
│ [X] Zamknij                                 │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ NIEZGODNOŚCI NAZW (10)                      │
│ ─────────────────────────────────────────── │
│ Nr Faktury  │ Nazwa w bazie │ Nazwa na fakturze │ Akcje          │
│ FV/2024/001 │ ABC Sp. z o.o│ ABC sp z oo       │ [←Użyj bazy]   │
│             │              │                   │ [→Użyj faktury]│
│ FV/2024/015 │ XYZ S.A.     │ XYZ SA            │ [←Użyj bazy]   │
│             │              │                   │ [→Użyj faktury]│
│ ...         │              │                   │                │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ BRAKUJĄCY SPRZEDAWCY (0)                    │
│ ─────────────────────────────────────────── │
│ Wszystko w porządku!                        │
└─────────────────────────────────────────────┘
```

#### Action Buttons Explained:
- **← Użyj z bazy**: Update invoice to use the seller's name from database
  - Changes invoice: "ABC sp z oo" → "ABC Sp. z o.o."
- **→ Użyj z faktury**: Update seller's name in database to match invoice
  - Changes database: "ABC Sp. z o.o." → "ABC sp z oo"
  - Also updates ALL other invoices for this seller

### ✅ Improvement 2: Smart Recommendations

Add intelligence to suggest the best action:

```javascript
function analyzeDiscrepancy(discrepancy) {
  const sellerName = discrepancy.seller_name;
  const invoiceName = discrepancy.invoice_seller_name;

  // Heuristics for recommendation
  const sellerHasDots = sellerName.includes('.');
  const invoiceHasDots = invoiceName.includes('.');
  const sellerIsLonger = sellerName.length > invoiceName.length;

  // Recommend the more complete/formal version
  if (sellerHasDots && !invoiceHasDots) {
    return {
      recommendation: 'use_seller_name',
      reason: 'Nazwa w bazie jest bardziej formalna (zawiera kropki)'
    };
  }

  if (sellerIsLonger) {
    return {
      recommendation: 'use_seller_name',
      reason: 'Nazwa w bazie jest pełniejsza'
    };
  }

  return {
    recommendation: null,
    reason: 'Wybierz ręcznie'
  };
}
```

Display as:
```
│ FV/2024/001 │ ABC Sp. z o.o│ ABC sp z oo │ [←Użyj bazy ✓]    │
│             │              │             │ [→Użyj faktury]   │
│             │              │ 💡 Rekomendacja: Użyj z bazy     │
│             │              │    (nazwa w bazie jest pełniejsza)│
```

### ✅ Improvement 3: Bulk Actions

Add ability to fix multiple discrepancies at once:

```
┌─────────────────────────────────────────────────────┐
│ ☑ Zaznacz wszystkie (10)                            │
│                                                     │
│ [Napraw zaznaczone (10)] ▼                          │
│   ├─ Użyj nazw z bazy dla wszystkich              │
│   ├─ Użyj nazw z faktur dla wszystkich            │
│   └─ Zastosuj rekomendacje (10 pozycji)           │
└─────────────────────────────────────────────────────┘
```

### ✅ Improvement 4: Preview Before Fix

Show preview modal before applying bulk changes:

```
┌─────────────────────────────────────────────┐
│ PODGLĄD ZMIAN                               │
│ ─────────────────────────────────────────── │
│ Nastąpią następujące zmiany:               │
│                                             │
│ Faktura FV/2024/001:                        │
│   Było: "ABC sp z oo"                       │
│   Będzie: "ABC Sp. z o.o."                  │
│                                             │
│ Faktura FV/2024/015:                        │
│   Było: "XYZ SA"                            │
│   Będzie: "XYZ S.A."                        │
│                                             │
│ ... i 8 więcej                              │
│                                             │
│ [Anuluj]  [Zastosuj zmiany (10)]           │
└─────────────────────────────────────────────┘
```

### ✅ Improvement 5: Progress Tracking

For bulk operations, show progress:

```
┌─────────────────────────────────────────────┐
│ NAPRAWIANIE NIEZGODNOŚCI                    │
│ ─────────────────────────────────────────── │
│ Postęp: 7 / 10                              │
│ ████████████████░░░░░  70%                  │
│                                             │
│ ✓ FV/2024/001 - zaktualizowano             │
│ ✓ FV/2024/002 - zaktualizowano             │
│ ✓ FV/2024/003 - zaktualizowano             │
│ ...                                         │
│ ⏳ FV/2024/008 - aktualizuję...             │
└─────────────────────────────────────────────┘
```

### ✅ Improvement 6: Filtering & Search

Add filters to sync results:

```
┌─────────────────────────────────────────────┐
│ Filtruj:                                    │
│ [ ] Pokaż tylko rekomendowane poprawki      │
│ [ ] Pokaż tylko różnice > 3 znaki           │
│ Szukaj: [__________________] 🔍             │
└─────────────────────────────────────────────┘
```

### ✅ Improvement 7: Sync History

Track sync operations in audit log:

```sql
-- Add to audit_log or create sync_history table
CREATE TABLE sync_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    action_type TEXT, -- 'fix_discrepancy', 'add_missing_seller'
    invoice_id INTEGER,
    seller_id INTEGER,
    field_changed TEXT,
    old_value TEXT,
    new_value TEXT,
    user_action TEXT -- 'manual', 'bulk', 'auto'
);
```

Display history:
```
┌─────────────────────────────────────────────┐
│ HISTORIA SYNCHRONIZACJI                     │
│ ─────────────────────────────────────────── │
│ 2024-12-03 14:30 │ Naprawiono 10 niezgodności│
│ 2024-12-01 10:15 │ Dodano 2 sprzedawców      │
│ 2024-11-28 16:45 │ Naprawiono 5 niezgodności │
└─────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Core Sync UI (Priority: HIGH)
1. ✅ Add sync results view HTML structure to `list_refined.html`
2. ✅ Update inline JavaScript to use `showSyncResults()` pattern
3. ✅ Add tables for missing sellers and discrepancies
4. ✅ Connect fix buttons to existing API endpoints
5. ✅ Test workflow: Sync → View Results → Fix → Close

**Estimated Time**: 3-4 hours
**Files to modify**:
- `templates/sellers/list_refined.html` (add HTML structure)
- Template inline JavaScript (connect to sync results)

### Phase 2: Smart Recommendations (Priority: MEDIUM)
1. ✅ Add recommendation logic to frontend
2. ✅ Display recommendation badges
3. ✅ Sort discrepancies by recommendation strength

**Estimated Time**: 2 hours
**Files to modify**:
- Template JavaScript (add `analyzeDiscrepancy()` function)

### Phase 3: Bulk Actions (Priority: MEDIUM)
1. ✅ Add checkboxes to discrepancy rows
2. ✅ Add bulk action buttons
3. ✅ Create new API endpoint: `POST /api/sellers/sync/bulk-fix`
4. ✅ Add preview modal
5. ✅ Add progress tracking UI

**Estimated Time**: 4-5 hours
**Files to modify**:
- `routes/api_routes.py` (new bulk fix endpoint)
- Template HTML/JS (bulk UI)

### Phase 4: Advanced Features (Priority: LOW)
1. ✅ Add filtering and search
2. ✅ Add sync history tracking
3. ✅ Add undo functionality
4. ✅ Add export sync report (CSV/PDF)

**Estimated Time**: 6-8 hours
**Files to modify**:
- Database schema (sync_history table)
- API routes (history endpoints)
- Template UI (filters, history view)

---

## Code Examples

### 1. Sync Results View HTML Structure

Add to `templates/sellers/list_refined.html`:

```html
<!-- Sync Results View (hidden by default) -->
<div id="sync-results-view" class="hidden">
    <div class="sync-results-header">
        <h2>Wyniki synchronizacji</h2>
        <button onclick="closeSyncResults()" class="btn-refined btn-refined-secondary">
            <span class="material-icons">close</span>
            Zamknij
        </button>
    </div>

    <!-- Summary Stats -->
    <div class="sync-summary-grid">
        <div class="sync-stat">
            <span class="sync-stat-value" id="sync-total-sellers">0</span>
            <span class="sync-stat-label">Sprzedawcy w bazie</span>
        </div>
        <div class="sync-stat">
            <span class="sync-stat-value" id="sync-total-invoices">0</span>
            <span class="sync-stat-label">Faktury w bazie</span>
        </div>
        <div class="sync-stat">
            <span class="sync-stat-value text-warning" id="sync-missing-count">0</span>
            <span class="sync-stat-label">Brakujący sprzedawcy</span>
        </div>
        <div class="sync-stat">
            <span class="sync-stat-value text-error" id="sync-discrepancies-count">0</span>
            <span class="sync-stat-label">Niezgodności nazw</span>
        </div>
    </div>

    <!-- All Good Message -->
    <div id="sync-all-good" class="sync-success-message hidden">
        <span class="material-icons">check_circle</span>
        <p>Wszystko zsynchronizowane! Brak niezgodności.</p>
    </div>

    <!-- Discrepancies Table -->
    <div id="discrepancies-card" class="sync-card hidden">
        <div class="sync-card-header">
            <h3>Niezgodności nazw</h3>
            <span class="badge badge-error" id="discrepancies-badge">0</span>
        </div>
        <table class="sync-table">
            <thead>
                <tr>
                    <th>Nr faktury</th>
                    <th>Nazwa w bazie</th>
                    <th>Nazwa na fakturze</th>
                    <th>Akcje</th>
                </tr>
            </thead>
            <tbody id="discrepancies-tbody"></tbody>
        </table>
    </div>

    <!-- Missing Sellers Table -->
    <div id="missing-sellers-card" class="sync-card hidden">
        <div class="sync-card-header">
            <h3>Brakujący sprzedawcy</h3>
            <span class="badge badge-warning" id="missing-sellers-badge">0</span>
        </div>
        <table class="sync-table">
            <thead>
                <tr>
                    <th>NIP</th>
                    <th>Nazwa</th>
                    <th>Liczba faktur</th>
                    <th>Akcje</th>
                </tr>
            </thead>
            <tbody id="missing-sellers-tbody"></tbody>
        </table>
    </div>
</div>
```

### 2. Updated Sync Function

Replace inline sync function in `list_refined.html`:

```javascript
async function syncSellers() {
    const loadingModal = Modals.loading('Synchronizacja...');
    try {
        const result = await API.sellers.sync();
        Modals.close(loadingModal);

        if (result.success) {
            // Show full sync results instead of just notification
            showSyncResults(result);
        } else {
            Notifications.error(result.error || 'Blad synchronizacji');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Sync error:', error);
        Notifications.error('Blad synchronizacji: ' + error.message);
    }
}

function showSyncResults(data) {
    // Update summary stats
    document.getElementById('sync-total-sellers').textContent = data.summary.total_sellers;
    document.getElementById('sync-total-invoices').textContent = data.summary.total_invoices;
    document.getElementById('sync-missing-count').textContent = data.summary.missing_sellers_count;
    document.getElementById('sync-discrepancies-count').textContent = data.summary.discrepancies_count;

    // Reset visibility
    document.getElementById('sync-all-good').classList.add('hidden');
    document.getElementById('missing-sellers-card').classList.add('hidden');
    document.getElementById('discrepancies-card').classList.add('hidden');

    // Populate discrepancies table
    const discrepanciesTbody = document.getElementById('discrepancies-tbody');
    const discrepanciesCard = document.getElementById('discrepancies-card');

    if (data.name_discrepancies.length > 0) {
        discrepanciesCard.classList.remove('hidden');
        discrepanciesTbody.innerHTML = data.name_discrepancies.map(d => {
            const recommendation = analyzeDiscrepancy(d);
            const isSellerRecommended = recommendation.recommendation === 'use_seller_name';

            return `
                <tr>
                    <td class="font-mono">${escapeHtml(d.invoice_number)}</td>
                    <td class="font-medium">${escapeHtml(d.seller_name)}</td>
                    <td class="text-warning">${escapeHtml(d.invoice_seller_name)}</td>
                    <td>
                        <div class="flex gap-2">
                            <button onclick="fixDiscrepancy('use_seller_name', ${d.invoice_id}, ${d.seller_id})"
                                    class="btn-refined btn-refined-${isSellerRecommended ? 'primary' : 'secondary'}">
                                ${isSellerRecommended ? '✓' : ''} ← Użyj z bazy
                            </button>
                            <button onclick="fixDiscrepancy('use_invoice_name', ${d.invoice_id}, ${d.seller_id})"
                                    class="btn-refined btn-refined-${!isSellerRecommended ? 'primary' : 'secondary'}">
                                ${!isSellerRecommended ? '✓' : ''} → Użyj z faktury
                            </button>
                        </div>
                        ${recommendation.reason ? `<p class="text-sm text-gray-600 mt-1">💡 ${recommendation.reason}</p>` : ''}
                    </td>
                </tr>
            `;
        }).join('');
    }

    // Show all good if no issues
    if (data.missing_sellers.length === 0 && data.name_discrepancies.length === 0) {
        document.getElementById('sync-all-good').classList.remove('hidden');
    }

    // Switch views
    document.getElementById('sellers-list-view').classList.add('hidden');
    document.getElementById('sync-results-view').classList.remove('hidden');
}

function analyzeDiscrepancy(discrepancy) {
    const sellerName = discrepancy.seller_name || '';
    const invoiceName = discrepancy.invoice_seller_name || '';

    // Heuristics
    const sellerHasDots = sellerName.includes('.');
    const invoiceHasDots = invoiceName.includes('.');
    const sellerIsLonger = sellerName.length > invoiceName.length;

    if (sellerHasDots && !invoiceHasDots) {
        return {
            recommendation: 'use_seller_name',
            reason: 'Nazwa w bazie zawiera poprawną interpunkcję'
        };
    }

    if (sellerIsLonger) {
        return {
            recommendation: 'use_seller_name',
            reason: 'Nazwa w bazie jest pełniejsza'
        };
    }

    return {
        recommendation: null,
        reason: ''
    };
}

function closeSyncResults() {
    document.getElementById('sync-results-view').classList.add('hidden');
    document.getElementById('sellers-list-view').classList.remove('hidden');
    loadSellers(); // Reload to show any changes
}

async function fixDiscrepancy(action, invoiceId, sellerId) {
    const loadingModal = Modals.loading('Naprawianie...');

    try {
        const result = await API.sellers.fixDiscrepancy(action, invoiceId, sellerId);
        Modals.close(loadingModal);

        if (result.success) {
            Notifications.success(result.message);
            // Re-run sync to refresh inline view
            const syncResult = await API.sellers.sync();
            if (syncResult.success) {
                showSyncResults(syncResult);
            }
        } else {
            Notifications.error(result.error || 'Błąd naprawiania');
        }
    } catch (error) {
        Modals.close(loadingModal);
        Notifications.error('Błąd: ' + error.message);
    }
}
```

### 3. Bulk Fix API Endpoint

Add to `routes/api_routes.py`:

```python
@api_bp.route('/sellers/sync/bulk-fix', methods=['POST'])
def bulk_fix_discrepancies():
    """
    Bulk fix multiple discrepancies at once

    Request body:
    {
        "fixes": [
            {"action": "use_seller_name", "invoice_id": 1, "seller_id": 10},
            {"action": "use_invoice_name", "invoice_id": 2, "seller_id": 11},
            ...
        ]
    }
    """
    try:
        data = request.get_json()
        fixes = data.get('fixes', [])

        if not fixes:
            return jsonify({'success': False, 'error': 'Brak zmian do zastosowania'}), 400

        results = []
        success_count = 0
        error_count = 0

        for fix in fixes:
            action = fix.get('action')
            invoice_id = fix.get('invoice_id')
            seller_id = fix.get('seller_id')

            try:
                if action == 'use_seller_name':
                    # Update invoice
                    invoice_row = current_app.invoice_repo.get_by_id(invoice_id)
                    seller_row = current_app.seller_repo.get_by_id(seller_id)

                    if invoice_row and seller_row:
                        invoice = current_app.invoice_repo.row_to_invoice(invoice_row)
                        seller = current_app.seller_repo.row_to_seller(seller_row)

                        old_name = invoice.seller_name
                        invoice.seller_name = seller.seller_name
                        current_app.invoice_repo.update(invoice.id, invoice)

                        results.append({
                            'invoice_id': invoice_id,
                            'success': True,
                            'message': f'Faktura {invoice.invoice_number}: "{old_name}" → "{seller.seller_name}"'
                        })
                        success_count += 1

                elif action == 'use_invoice_name':
                    # Update seller
                    invoice_row = current_app.invoice_repo.get_by_id(invoice_id)
                    seller_row = current_app.seller_repo.get_by_id(seller_id)

                    if invoice_row and seller_row:
                        invoice = current_app.invoice_repo.row_to_invoice(invoice_row)
                        seller = current_app.seller_repo.row_to_seller(seller_row)

                        old_name = seller.seller_name
                        new_name = current_app.seller_service.normalize_seller_name(invoice.seller_name)
                        current_app.seller_repo.update_name(seller_id, new_name)

                        results.append({
                            'seller_id': seller_id,
                            'success': True,
                            'message': f'Sprzedawca: "{old_name}" → "{new_name}"'
                        })
                        success_count += 1

            except Exception as e:
                results.append({
                    'invoice_id': invoice_id,
                    'success': False,
                    'error': str(e)
                })
                error_count += 1

        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total': len(fixes),
                'success': success_count,
                'errors': error_count
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

---

## Testing Checklist

### Manual Testing
- [ ] Sync with no discrepancies shows "all good" message
- [ ] Sync with discrepancies shows detailed table
- [ ] Fix individual discrepancy (use seller name)
- [ ] Fix individual discrepancy (use invoice name)
- [ ] Bulk fix all discrepancies
- [ ] Close sync results returns to sellers list
- [ ] Recommendations display correctly
- [ ] Preview modal shows correct changes

### Edge Cases
- [ ] Very long seller names (>100 characters)
- [ ] Special characters in names (ąćęłńóśźż, &, -, etc.)
- [ ] Empty/null seller names
- [ ] Large number of discrepancies (100+)
- [ ] Network errors during fix operations
- [ ] Concurrent sync operations

### Performance
- [ ] Sync with 1000+ invoices completes in < 3 seconds
- [ ] Rendering 100+ discrepancies doesn't lag UI
- [ ] Bulk fix operations show progress

---

## User Documentation

### How to Use Seller Sync

1. **Navigate** to Sprzedawcy (Sellers) page
2. **Click** "Synchronizuj" button in top right
3. **Review** sync results:
   - Green summary: Everything is synced
   - Yellow/Red: Issues found
4. **Fix discrepancies**:
   - **← Użyj z bazy**: Updates invoice to match database
   - **→ Użyj z faktury**: Updates database (and all invoices) to match this invoice
5. **Look for 💡 recommendations** - the system suggests which option is better
6. **Use bulk actions** for multiple fixes at once
7. **Close** sync view when done

### Best Practices

- **Run sync weekly** to catch issues early
- **Trust recommendations** - they use smart heuristics
- **Use "Użyj z bazy"** when database name looks more formal/complete
- **Use "Użyj z faktury"** when database has a typo or outdated name
- **Review bulk changes** in preview before applying

---

## Next Steps

### Immediate (Do Now)
1. ✅ Implement Phase 1 (Core Sync UI)
2. ✅ Test with real data
3. ✅ Get user feedback

### Short-term (This Week)
1. ✅ Add smart recommendations
2. ✅ Implement bulk actions
3. ✅ Write user documentation

### Long-term (This Month)
1. ✅ Add filtering and search
2. ✅ Implement sync history
3. ✅ Add undo functionality
4. ✅ Create sync report export

---

## Conclusion

The current sync feature is **functionally correct** but has **poor UX**. The proposed improvements will:

1. **Make issues visible** - show what's wrong, not just counts
2. **Make fixes actionable** - provide clear buttons to fix issues
3. **Make decisions easier** - add smart recommendations
4. **Save time** - bulk actions for multiple fixes
5. **Provide confidence** - preview changes before applying

**Estimated total implementation time**: 15-20 hours across all phases

**Recommended approach**: Start with Phase 1 (Core UI), get user feedback, then proceed to Phases 2-4 based on actual usage patterns.
