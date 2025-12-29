"""
Database Migration Script: Migrate Seller Data to Sellers Table

This script:
1. Creates the sellers table if it doesn't exist
2. Extracts unique seller data from existing invoices
3. Populates the sellers table
4. Adds seller_id column to invoices table
5. Links invoices to their sellers
6. Updates invoice counts
7. Validates the migration
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def connect_db():
    """Connect to the database"""
    db_path = Path(__file__).parent / "faktury.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def backup_database():
    """Create a backup of the database before migration"""
    import shutil
    db_path = Path(__file__).parent / "faktury.db"
    backup_path = Path(__file__).parent / f"faktury.db.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"📦 Creating backup: {backup_path.name}")
    shutil.copy2(db_path, backup_path)
    print(f"✅ Backup created successfully")
    return backup_path


def create_sellers_table(conn):
    """Create the sellers table if it doesn't exist"""
    print("\n📋 Creating sellers table...")
    
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sellers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_nip TEXT UNIQUE NOT NULL,
            seller_name TEXT NOT NULL,
            address TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            invoice_count INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_seller_nip ON sellers(seller_nip)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_seller_name_search ON sellers(seller_name)")
    
    conn.commit()
    print("✅ Sellers table created")


def add_seller_id_column(conn):
    """Add seller_id column to invoices table"""
    print("\n📋 Adding seller_id column to invoices table...")
    
    cursor = conn.cursor()
    
    # Check if column already exists
    cursor.execute("PRAGMA table_info(invoices)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'seller_id' not in columns:
        cursor.execute("ALTER TABLE invoices ADD COLUMN seller_id INTEGER REFERENCES sellers(id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_seller ON invoices(seller_id)")
        conn.commit()
        print("✅ seller_id column added")
    else:
        print("ℹ️  seller_id column already exists")


def extract_seller_data(conn):
    """Extract unique seller data from invoices"""
    print("\n🔍 Extracting unique seller data from invoices...")
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT seller_nip, seller_name
        FROM invoices
        WHERE seller_nip IS NOT NULL AND seller_nip != ''
        ORDER BY seller_name
    """)
    
    sellers = cursor.fetchall()
    print(f"✅ Found {len(sellers)} unique sellers with NIP")
    
    # Check for conflicts (same NIP, different names)
    nip_to_names = defaultdict(set)
    for seller in sellers:
        nip_to_names[seller['seller_nip']].add(seller['seller_name'])
    
    conflicts = {nip: names for nip, names in nip_to_names.items() if len(names) > 1}
    
    if conflicts:
        print("\n⚠️  WARNING: Detected conflicts (same NIP, different names):")
        for nip, names in conflicts.items():
            print(f"   NIP {nip}: {', '.join(names)}")
        print("   → Will use the most recent name for each NIP")
    
    return sellers


def populate_sellers_table(conn, sellers):
    """Populate the sellers table with unique seller data"""
    print("\n📝 Populating sellers table...")
    
    cursor = conn.cursor()
    created_count = 0
    skipped_count = 0
    
    # For each unique NIP, get the most recent seller name
    unique_sellers = {}
    for seller in sellers:
        nip = seller['seller_nip']
        name = seller['seller_name']
        
        # Get the most recent invoice for this seller to determine first_seen
        cursor.execute("""
            SELECT MIN(created_at) as first_seen, MAX(created_at) as last_updated
            FROM invoices
            WHERE seller_nip = ?
        """, (nip,))
        dates = cursor.fetchone()
        
        if nip not in unique_sellers:
            unique_sellers[nip] = {
                'name': name,
                'first_seen': dates['first_seen'],
                'last_updated': dates['last_updated']
            }
    
    for nip, data in unique_sellers.items():
        try:
            cursor.execute("""
                INSERT INTO sellers (seller_nip, seller_name, first_seen, last_updated, invoice_count)
                VALUES (?, ?, ?, ?, 0)
            """, (nip, data['name'], data['first_seen'], data['last_updated']))
            created_count += 1
        except sqlite3.IntegrityError:
            # Seller already exists
            skipped_count += 1
    
    conn.commit()
    print(f"✅ Created {created_count} sellers")
    if skipped_count > 0:
        print(f"ℹ️  Skipped {skipped_count} existing sellers")


def link_invoices_to_sellers(conn):
    """Link invoices to their sellers"""
    print("\n🔗 Linking invoices to sellers...")
    
    cursor = conn.cursor()
    
    # Get all sellers
    cursor.execute("SELECT id, seller_nip FROM sellers")
    sellers_map = {row['seller_nip']: row['id'] for row in cursor.fetchall()}
    
    # Update invoices with seller_id
    updated_count = 0
    for nip, seller_id in sellers_map.items():
        cursor.execute("""
            UPDATE invoices
            SET seller_id = ?
            WHERE seller_nip = ? AND (seller_id IS NULL OR seller_id = 0)
        """, (seller_id, nip))
        updated_count += cursor.rowcount
    
    conn.commit()
    print(f"✅ Linked {updated_count} invoices to sellers")


def update_invoice_counts(conn):
    """Update invoice_count for each seller"""
    print("\n🔢 Updating invoice counts...")
    
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sellers
        SET invoice_count = (
            SELECT COUNT(*)
            FROM invoices
            WHERE invoices.seller_id = sellers.id
        )
    """)
    
    conn.commit()
    print(f"✅ Updated invoice counts for all sellers")


def validate_migration(conn):
    """Validate the migration results"""
    print("\n✔️  Validating migration...")
    
    cursor = conn.cursor()
    
    # Check total sellers
    cursor.execute("SELECT COUNT(*) as count FROM sellers")
    seller_count = cursor.fetchone()['count']
    print(f"   • Total sellers: {seller_count}")
    
    # Check invoices with seller_id
    cursor.execute("SELECT COUNT(*) as count FROM invoices WHERE seller_id IS NOT NULL")
    linked_count = cursor.fetchone()['count']
    print(f"   • Invoices linked to sellers: {linked_count}")
    
    # Check invoices without seller_id
    cursor.execute("SELECT COUNT(*) as count FROM invoices WHERE seller_id IS NULL AND seller_nip IS NOT NULL")
    unlinked_count = cursor.fetchone()['count']
    
    if unlinked_count > 0:
        print(f"   ⚠️  Invoices with NIP but not linked: {unlinked_count}")
        cursor.execute("""
            SELECT id, seller_nip, seller_name, invoice_number
            FROM invoices
            WHERE seller_id IS NULL AND seller_nip IS NOT NULL
            LIMIT 5
        """)
        print("   Sample unlinkted invoices:")
        for row in cursor.fetchall():
            print(f"      - Invoice {row['invoice_number']}: {row['seller_name']} (NIP: {row['seller_nip']})")
    else:
        print(f"   ✅ All invoices with NIP are linked to sellers")
    
    # Check invoice counts
    cursor.execute("""
        SELECT s.seller_name, s.invoice_count, COUNT(i.id) as actual_count
        FROM sellers s
        LEFT JOIN invoices i ON s.id = i.seller_id
        GROUP BY s.id
        HAVING s.invoice_count != COUNT(i.id)
        LIMIT 5
    """)
    mismatched = cursor.fetchall()
    
    if mismatched:
        print(f"   ⚠️  Sellers with mismatched invoice counts:")
        for row in mismatched:
            print(f"      - {row['seller_name']}: stored={row['invoice_count']}, actual={row['actual_count']}")
    else:
        print(f"   ✅ All invoice counts are correct")
    
    return unlinked_count == 0 and len(mismatched) == 0


def main():
    """Main migration function"""
    print("=" * 70)
    print("🚀 SELLER DATA MIGRATION SCRIPT")
    print("=" * 70)
    
    try:
        # Backup database
        backup_path = backup_database()
        
        # Connect to database
        conn = connect_db()
        
        # Run migration steps
        create_sellers_table(conn)
        add_seller_id_column(conn)
        sellers = extract_seller_data(conn)
        populate_sellers_table(conn, sellers)
        link_invoices_to_sellers(conn)
        update_invoice_counts(conn)
        
        # Validate
        success = validate_migration(conn)
        
        # Close connection
        conn.close()
        
        print("\n" + "=" * 70)
        if success:
            print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
            print(f"   Backup saved to: {backup_path.name}")
        else:
            print("⚠️  MIGRATION COMPLETED WITH WARNINGS")
            print("   Please review the validation results above")
            print(f"   Backup saved to: {backup_path.name}")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        print(f"   Database backup is available for recovery")
        raise


if __name__ == "__main__":
    main()
