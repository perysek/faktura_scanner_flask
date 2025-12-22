"""
Debug script to check what's in the staging table
"""
import sqlite3
from pathlib import Path

db_path = Path('faktury.db')
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM upload_staging ORDER BY uploaded_at DESC")
rows = cursor.fetchall()

print(f"Total records in upload_staging: {len(rows)}\n")

if rows:
    for row in rows:
        print(f"ID: {row['id']}")
        print(f"Session ID: {row['session_id']}")
        print(f"Filename: {row['filename']}")
        print(f"File Path: {row['file_path']}")
        print(f"File Size: {row['file_size']}")
        print(f"Email Subject: {row['email_subject']}")
        print(f"Email Sender: {row['email_sender']}")
        print(f"Email Folder: {row['email_folder']}")
        print(f"Email Date: {row['email_date']}")
        print(f"Uploaded At: {row['uploaded_at']}")
        print("-" * 60)
else:
    print("No records found in upload_staging table")

conn.close()
