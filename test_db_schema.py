"""Test script to verify database schema"""
import sqlite3
from pathlib import Path

db_path = Path('faktury.db')


if not db_path.exists():
    print(f"❌ Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Check if upload_staging table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='upload_staging'")
result = cursor.fetchone()

if result:
    print("✅ upload_staging table exists")
    
    # Get table schema
    cursor.execute("PRAGMA table_info(upload_staging)")
    columns = cursor.fetchall()
    
    print("\nTable columns:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    # Check indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='upload_staging'")
    indexes = cursor.fetchall()
    
    print("\nIndexes:")
    for idx in indexes:
        print(f"  - {idx[0]}")
else:
    print("❌ upload_staging table does NOT exist")

conn.close()
