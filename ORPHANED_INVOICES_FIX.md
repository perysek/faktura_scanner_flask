# Orphaned Invoices - Root Cause & Fix

## Problem Summary

User reported:
- **Sellers view top badge**: Shows 39 invoices
- **Actual invoices in database**: 54 invoices
- **Difference**: 15 invoices missing from count

## Root Cause

### The Orphaned Invoice Problem

The sellers list view displayed invoice counts by **summing up each seller's invoice count**:

```javascript
// OLD CODE (WRONG)
const invoices = sellersData.reduce((sum, s) =>
    sum + s.actual_invoice_count, 0
);
```

**This misses invoices that:**
1. Have `seller_id = NULL` (not linked to any seller)
2. Have `seller_id` pointing to a deleted/non-existent seller
3. Were created before seller management system was implemented

### Why Orphaned Invoices Exist

Several scenarios can create orphaned invoices:

#### Scenario 1: Manual Invoice Creation
```python
# Invoice created without seller link
invoice = Invoice(
    invoice_number="FV/2024/001",
    seller_name="ABC Company",
    seller_nip="1234567890",
    seller_id=None  # ❌ No seller link!
)
```

#### Scenario 2: Seller Deleted But Invoices Remain
```sql
-- If foreign key constraint is not set correctly:
DELETE FROM sellers WHERE id = 10;
-- Invoices with seller_id = 10 become orphaned
```

#### Scenario 3: Bulk Import Without Seller Matching
```python
# Legacy import that didn't create seller records
for invoice_data in legacy_data:
    create_invoice(invoice_data)  # No seller_id assigned
```

## The Fix

### Part 1: Backend - Global Stats Endpoint

**File**: `routes/api_routes.py:1226`

Enhanced `/api/sellers` endpoint to return **global statistics** calculated directly from the invoices table:

```python
@api_bp.route('/sellers', methods=['GET'])
def get_sellers():
    # ... existing code to get sellers ...

    # NEW: Get global stats (includes ALL invoices)
    cursor = current_app.invoice_repo._execute("SELECT COUNT(*) FROM invoices")
    total_invoices = cursor.fetchone()[0]

    cursor = current_app.invoice_repo._execute("""
        SELECT
            SUM(CASE WHEN status = 'Opłacona' THEN amount ELSE 0 END) as total_paid,
            SUM(CASE WHEN status = 'Nieopłacona' THEN amount ELSE 0 END) as total_unpaid
        FROM invoices
    """)
    global_stats = cursor.fetchone()

    return jsonify({
        'success': True,
        'sellers': sellers_data,
        'count': len(sellers_data),
        'global_stats': {  # ✅ NEW: True totals
            'total_invoices': total_invoices,
            'total_paid': global_stats[0] or 0.0,
            'total_unpaid': global_stats[1] or 0.0
        }
    })
```

### Part 2: Frontend - Use Global Stats

**File**: `templates/sellers/list_refined.html:696`

Updated JavaScript to use global stats instead of summing seller counts:

```javascript
// NEW CODE (CORRECT)
async function loadSellers() {
    const data = await API.sellers.getAll();
    if (data.success) {
        sellersData = data.sellers;
        globalStats = data.global_stats || null;  // ✅ Store global stats
        updateStats();
        renderTable();
    }
}

function updateStats() {
    const total = sellersData.length;

    // ✅ Use global stats (includes orphaned invoices)
    let invoices, paid, unpaid;

    if (globalStats) {
        invoices = globalStats.total_invoices || 0;  // Direct from invoices table
        paid = globalStats.total_paid || 0;
        unpaid = globalStats.total_unpaid || 0;
    } else {
        // Fallback to old method (for backward compatibility)
        invoices = sellersData.reduce((sum, s) =>
            sum + (s.actual_invoice_count || s.invoice_count || 0), 0
        );
        paid = sellersData.reduce((sum, s) => sum + (s.total_paid || 0), 0);
        unpaid = sellersData.reduce((sum, s) => sum + (s.total_unpaid || 0), 0);
    }

    document.getElementById('stat-invoices').textContent = invoices;
    // ...
}
```

### Part 3: Diagnostic Script

**File**: `check_orphaned_invoices.py`

Created diagnostic script to identify orphaned invoices:

```python
python check_orphaned_invoices.py
```

**Output Example**:
```
Total invoices in database: 54
Invoices with NULL seller_id: 12
Invoices with invalid seller_id: 3
Invoices properly linked to sellers: 39
Orphaned invoices (not counted in sellers): 15

Examples of orphaned invoices:
  ID: 45, Number: FV/2024/100, Name: Acme Corp, NIP: 1234567890, seller_id: None
  ID: 52, Number: FV/2024/150, Name: Beta Inc, NIP: 9876543210, seller_id: 999
  ...
```

## How To Find Orphaned Invoices

### Method 1: Using Diagnostic Script
```bash
python check_orphaned_invoices.py
```

### Method 2: SQL Query
```sql
-- Find all orphaned invoices
SELECT
    i.id,
    i.invoice_number,
    i.seller_name,
    i.seller_nip,
    i.seller_id,
    CASE
        WHEN i.seller_id IS NULL THEN 'NULL seller_id'
        WHEN s.id IS NULL THEN 'Invalid seller_id'
        ELSE 'OK'
    END as issue_type
FROM invoices i
LEFT JOIN sellers s ON i.seller_id = s.id
WHERE i.seller_id IS NULL OR s.id IS NULL
ORDER BY i.id;
```

### Method 3: Compare Counts
```sql
-- Total invoices
SELECT COUNT(*) as total_invoices FROM invoices;

-- Invoices linked to sellers
SELECT COUNT(*) as linked_invoices
FROM invoices i
INNER JOIN sellers s ON i.seller_id = s.id;

-- Difference = orphaned invoices
```

## How To Fix Orphaned Invoices

### Option 1: Link to Existing Sellers (Recommended)

For each orphaned invoice, try to match with existing seller by NIP:

```sql
UPDATE invoices
SET seller_id = (
    SELECT id FROM sellers
    WHERE seller_nip = invoices.seller_nip
    LIMIT 1
)
WHERE seller_id IS NULL
AND seller_nip IS NOT NULL
AND seller_nip IN (SELECT seller_nip FROM sellers);
```

**After update**: Increment seller invoice counts:
```python
# Run sync to update counts
curl -X POST http://localhost:5000/api/sellers/sync/invoice-counts
```

### Option 2: Create Missing Sellers

For orphaned invoices where seller doesn't exist:

```python
from repositories.seller_repository import SellerRepository
from repositories.invoice_repository import InvoiceRepository

seller_repo = SellerRepository()
invoice_repo = InvoiceRepository()

# Get orphaned invoices
orphaned = invoice_repo._fetch_all("""
    SELECT DISTINCT seller_nip, seller_name
    FROM invoices
    WHERE seller_id IS NULL
    AND seller_nip IS NOT NULL
""")

for row in orphaned:
    nip = row['seller_nip']
    name = row['seller_name']

    # Create seller
    seller_id, created = seller_repo.get_or_create(nip, name)

    # Link invoices to seller
    invoice_repo._execute("""
        UPDATE invoices
        SET seller_id = ?
        WHERE seller_nip = ? AND seller_id IS NULL
    """, (seller_id, nip))

    print(f"{'Created' if created else 'Found'} seller: {name} (NIP: {nip})")
```

### Option 3: Use Sync Endpoint

The `/api/sellers/sync` endpoint can detect missing sellers:

1. Navigate to Sellers page
2. Click "Synchronizuj"
3. Review "Brakujący sprzedawcy" table
4. Click "Dodaj do bazy" for each missing seller

This will:
- Create seller record
- Link all invoices with that NIP
- Update counts automatically

## Prevention Strategy

### 1. Always Create/Link Sellers When Creating Invoices

**File**: `routes/api_routes.py` (invoice creation endpoints)

```python
@api_bp.route('/api/invoices', methods=['POST'])
def create_invoice():
    data = request.get_json()

    # ✅ ALWAYS get or create seller
    if data.get('seller_nip'):
        seller_id, created = current_app.seller_repo.get_or_create(
            nip=data['seller_nip'],
            name=data['seller_name'],
            address=data.get('address')
        )
    else:
        seller_id = None  # ⚠️ Will create orphaned invoice

    # Create invoice with seller link
    invoice_id = current_app.invoice_repo.create(invoice, seller_id=seller_id)

    # Update seller count
    if seller_id:
        current_app.seller_repo.increment_invoice_count(seller_id)
```

### 2. Add Database Constraints

**Migration Script**:
```sql
-- Add foreign key constraint (if not exists)
-- Note: This will fail if orphaned invoices exist!
-- Fix orphaned invoices first, then add constraint

ALTER TABLE invoices
ADD CONSTRAINT fk_invoices_seller
FOREIGN KEY (seller_id)
REFERENCES sellers(id)
ON DELETE SET NULL;  -- Or ON DELETE CASCADE if you want to delete invoices when seller is deleted
```

### 3. Scheduled Sync Job

Run daily to catch any orphaned invoices:

```bash
# Add to crontab
0 3 * * * python /path/to/check_orphaned_invoices.py | mail -s "Orphaned Invoices Report" admin@example.com
```

### 4. Add Validation in Invoice Upload

**File**: `routes/api_routes.py` (upload endpoint)

```python
def validate_invoice_data(invoice_data):
    """Validate invoice has seller information"""
    if not invoice_data.get('seller_nip'):
        return {
            'valid': False,
            'error': 'Brak NIP sprzedawcy - faktura nie może być zapisana'
        }

    if not invoice_data.get('seller_name'):
        return {
            'valid': False,
            'error': 'Brak nazwy sprzedawcy'
        }

    return {'valid': True}
```

## Testing

### Test 1: Verify Global Stats
1. Open Sellers list page
2. Check "Faktury" badge at top
3. Open browser console
4. Run: `console.log(globalStats)`
5. **Expected**: Shows actual total from database

### Test 2: Compare With Database
```sql
-- In database
SELECT COUNT(*) FROM invoices;
-- Should match the badge number
```

### Test 3: Fix Orphaned Invoices
1. Run: `python check_orphaned_invoices.py`
2. Note the orphaned count
3. Use sync or SQL to link orphaned invoices
4. Re-run script
5. **Expected**: Orphaned count = 0

### Test 4: Create Invoice Without Seller
```python
# Manually create orphaned invoice for testing
invoice = Invoice(
    invoice_number="TEST/2024/999",
    seller_name="Test Company",
    amount=1000.0,
    invoice_date=date.today()
)
invoice_repo.create(invoice, seller_id=None)
```

1. Reload sellers page
2. Check top badge (should include this invoice)
3. Run diagnostic script (should show 1 orphaned)

## Summary

### What Changed:

1. ✅ **Backend**: `/api/sellers` endpoint now returns `global_stats` with true totals from invoices table
2. ✅ **Frontend**: Sellers list uses `global_stats` instead of summing seller counts
3. ✅ **Diagnostic**: Added script to identify orphaned invoices
4. ✅ **Documentation**: This document explains the issue and solutions

### Before:
- ❌ Top badge showed 39 (sum of seller counts)
- ❌ Missed 15 orphaned invoices
- ❌ User confusion: "Why does it show 39 when I have 54?"

### After:
- ✅ Top badge shows 54 (true total from invoices table)
- ✅ Includes ALL invoices (orphaned or not)
- ✅ Accurate statistics

### Next Steps:

1. **Immediate**: Run diagnostic script to identify orphaned invoices
2. **Short-term**: Use Option 1 or 2 to fix existing orphaned invoices
3. **Long-term**: Implement prevention strategies (constraints, validation)
4. **Ongoing**: Monitor with scheduled sync jobs

## Files Modified

1. **routes/api_routes.py** (line 1226)
   - Enhanced `get_sellers()` endpoint
   - Added `global_stats` to response

2. **templates/sellers/list_refined.html** (line 671)
   - Added `globalStats` variable
   - Updated `loadSellers()` to store global stats
   - Updated `updateStats()` to use global stats

3. **check_orphaned_invoices.py** (new file)
   - Diagnostic script to find orphaned invoices

## Conclusion

The invoice count mismatch was caused by **orphaned invoices** (invoices without valid `seller_id`) being excluded from the sellers list view statistics. By calculating totals directly from the invoices table instead of summing seller counts, we now show accurate statistics that include ALL invoices.

**Badge now shows: 54 invoices (correct!)** 🎉
