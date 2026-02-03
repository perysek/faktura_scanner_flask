"""
Automated script to fix orphaned invoices by linking them to sellers
"""
from config.database import DatabaseConnection
from datetime import datetime


def fix_orphaned_invoices():
    """
    Automatically fix all orphaned invoices by:
    1. Linking to existing sellers (by NIP)
    2. Creating missing sellers
    3. Updating seller invoice counts
    """
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    print("=" * 60)
    print("FIXING ORPHANED INVOICES")
    print("=" * 60)

    # Step 1: Count orphaned invoices
    cursor.execute("""
        SELECT COUNT(*)
        FROM invoices i
        LEFT JOIN sellers s ON i.seller_id = s.id
        WHERE i.seller_id IS NULL OR s.id IS NULL
    """)
    total_orphaned = cursor.fetchone()[0]

    if total_orphaned == 0:
        print("\n✅ No orphaned invoices found! All invoices are properly linked.")
        return

    print(f"\nFound {total_orphaned} orphaned invoices to fix\n")

    # Step 2: Link orphaned invoices to existing sellers (by NIP)
    print("Step 1: Linking invoices to existing sellers by NIP...")
    cursor.execute("""
        UPDATE invoices
        SET seller_id = (
            SELECT id FROM sellers
            WHERE seller_nip = invoices.seller_nip
            LIMIT 1
        )
        WHERE seller_id IS NULL
        AND seller_nip IS NOT NULL
        AND seller_nip IN (SELECT seller_nip FROM sellers)
    """)
    linked_count = cursor.rowcount
    conn.commit()
    print(f"  ✓ Linked {linked_count} invoices to existing sellers")

    # Step 3: Fix invoices with invalid seller_id (points to deleted seller)
    print("\nStep 2: Fixing invoices with invalid seller_id...")
    cursor.execute("""
        UPDATE invoices
        SET seller_id = (
            SELECT id FROM sellers
            WHERE seller_nip = invoices.seller_nip
            LIMIT 1
        )
        WHERE seller_id IS NOT NULL
        AND seller_id NOT IN (SELECT id FROM sellers)
        AND seller_nip IS NOT NULL
        AND seller_nip IN (SELECT seller_nip FROM sellers)
    """)
    fixed_invalid = cursor.rowcount
    conn.commit()
    print(f"  ✓ Fixed {fixed_invalid} invoices with invalid seller_id")

    # Step 4: Create missing sellers and link invoices
    print("\nStep 3: Creating missing sellers...")
    cursor.execute("""
        SELECT DISTINCT seller_nip, seller_name
        FROM invoices
        WHERE (seller_id IS NULL OR seller_id NOT IN (SELECT id FROM sellers))
        AND seller_nip IS NOT NULL
        AND seller_nip NOT IN (SELECT seller_nip FROM sellers)
    """)
    missing_sellers = cursor.fetchall()

    created_count = 0
    for row in missing_sellers:
        nip = row[0]
        name = row[1]

        # Create seller
        cursor.execute("""
            INSERT INTO sellers (seller_nip, seller_name, invoice_count, first_seen, last_updated)
            VALUES (?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (nip, name))
        seller_id = cursor.lastrowid

        # Link invoices to new seller
        cursor.execute("""
            UPDATE invoices
            SET seller_id = ?
            WHERE seller_nip = ?
            AND (seller_id IS NULL OR seller_id NOT IN (SELECT id FROM sellers))
        """, (seller_id, nip))

        invoice_count = cursor.rowcount
        created_count += 1
        print(f"  ✓ Created seller: {name[:40]} (NIP: {nip}) - linked {invoice_count} invoices")

    conn.commit()

    # Step 5: Handle invoices without NIP (can't auto-fix)
    cursor.execute("""
        SELECT COUNT(*)
        FROM invoices
        WHERE (seller_id IS NULL OR seller_id NOT IN (SELECT id FROM sellers))
        AND (seller_nip IS NULL OR seller_nip = '')
    """)
    no_nip_count = cursor.fetchone()[0]

    if no_nip_count > 0:
        print(f"\n⚠️  Warning: {no_nip_count} invoices have no NIP and cannot be auto-fixed")
        print("    These invoices need manual review:")
        cursor.execute("""
            SELECT id, invoice_number, seller_name, amount
            FROM invoices
            WHERE (seller_id IS NULL OR seller_id NOT IN (SELECT id FROM sellers))
            AND (seller_nip IS NULL OR seller_nip = '')
            LIMIT 10
        """)
        for row in cursor.fetchall():
            print(f"      ID: {row[0]}, Number: {row[1]}, Name: {row[2]}, Amount: {row[3]}")
        if no_nip_count > 10:
            print(f"      ... and {no_nip_count - 10} more")

    # Step 6: Recalculate all seller invoice counts
    print("\nStep 4: Recalculating seller invoice counts...")
    cursor.execute("""
        UPDATE sellers
        SET invoice_count = (
            SELECT COUNT(*)
            FROM invoices
            WHERE invoices.seller_id = sellers.id
        ),
        last_updated = CURRENT_TIMESTAMP
    """)
    updated_sellers = cursor.rowcount
    conn.commit()
    print(f"  ✓ Updated invoice counts for {updated_sellers} sellers")

    # Step 7: Verify fix
    print("\nStep 5: Verifying fix...")
    cursor.execute("""
        SELECT COUNT(*)
        FROM invoices i
        LEFT JOIN sellers s ON i.seller_id = s.id
        WHERE i.seller_id IS NULL OR s.id IS NULL
    """)
    remaining_orphaned = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM invoices")
    total_invoices = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM invoices i
        INNER JOIN sellers s ON i.seller_id = s.id
    """)
    properly_linked = cursor.fetchone()[0]

    print(f"  Total invoices: {total_invoices}")
    print(f"  Properly linked: {properly_linked}")
    print(f"  Still orphaned: {remaining_orphaned}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✓ Linked to existing sellers: {linked_count}")
    print(f"✓ Fixed invalid seller_id: {fixed_invalid}")
    print(f"✓ Created new sellers: {created_count}")
    print(f"✓ Total fixed: {total_orphaned - remaining_orphaned}")

    if remaining_orphaned > 0:
        print(f"⚠️  Remaining orphaned (need manual review): {remaining_orphaned}")
        print("\nThese invoices have no NIP and cannot be automatically linked.")
        print("You can manually assign sellers to these invoices via the web UI.")
    else:
        print("\n🎉 All orphaned invoices have been fixed!")

    print("\nNext steps:")
    print("1. Reload the Sellers page - invoice counts should now be correct")
    print("2. Run check_orphaned_invoices.py to verify the fix")
    print("3. If any invoices remain orphaned, review them manually")

    conn.close()


if __name__ == '__main__':
    try:
        fix_orphaned_invoices()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
