"""
Diagnostic script to find orphaned invoices (invoices without valid seller_id)
"""
from config.database import DatabaseConnection

def check_orphaned_invoices():
    """Find invoices that aren't linked to any seller"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    # Total invoices in database
    cursor.execute("SELECT COUNT(*) FROM invoices")
    total_invoices = cursor.fetchone()[0]
    print(f"Total invoices in database: {total_invoices}")

    # Invoices with NULL seller_id
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE seller_id IS NULL")
    null_seller_id = cursor.fetchone()[0]
    print(f"Invoices with NULL seller_id: {null_seller_id}")

    # Invoices with invalid seller_id (points to non-existent seller)
    cursor.execute("""
        SELECT COUNT(*)
        FROM invoices i
        LEFT JOIN sellers s ON i.seller_id = s.id
        WHERE i.seller_id IS NOT NULL AND s.id IS NULL
    """)
    invalid_seller_id = cursor.fetchone()[0]
    print(f"Invoices with invalid seller_id: {invalid_seller_id}")

    # Invoices properly linked to sellers
    cursor.execute("""
        SELECT COUNT(*)
        FROM invoices i
        INNER JOIN sellers s ON i.seller_id = s.id
    """)
    linked_invoices = cursor.fetchone()[0]
    print(f"Invoices properly linked to sellers: {linked_invoices}")

    # Orphaned invoices
    orphaned = total_invoices - linked_invoices
    print(f"\nOrphaned invoices (not counted in sellers): {orphaned}")

    # Show examples of orphaned invoices
    if orphaned > 0:
        print("\nExamples of orphaned invoices:")
        cursor.execute("""
            SELECT i.id, i.invoice_number, i.seller_name, i.seller_nip, i.seller_id
            FROM invoices i
            LEFT JOIN sellers s ON i.seller_id = s.id
            WHERE i.seller_id IS NULL OR s.id IS NULL
            LIMIT 10
        """)
        rows = cursor.fetchall()
        for row in rows:
            print(f"  ID: {row[0]}, Number: {row[1]}, Name: {row[2]}, NIP: {row[3]}, seller_id: {row[4]}")

    # Show sum of seller invoice counts
    cursor.execute("""
        SELECT SUM(actual_count) as total_from_sellers
        FROM (
            SELECT COUNT(i.id) as actual_count
            FROM sellers s
            LEFT JOIN invoices i ON s.id = i.seller_id
            GROUP BY s.id
        )
    """)
    total_from_sellers = cursor.fetchone()[0] or 0
    print(f"\nSum of all sellers' invoice counts: {total_from_sellers}")
    print(f"Difference: {total_invoices} (actual) - {total_from_sellers} (from sellers) = {total_invoices - total_from_sellers}")

    conn.close()

if __name__ == '__main__':
    check_orphaned_invoices()
