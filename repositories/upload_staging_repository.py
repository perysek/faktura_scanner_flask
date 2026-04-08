"""
Upload Staging Repository - Manages temporary file uploads
"""
from typing import Any, List, Optional

import psycopg2
import psycopg2.extras

from config.database import get_db_connection
from database.models import UploadStaging


class UploadStagingRepository:
    """Repository for managing upload staging data"""

    def __init__(self, db_path: str = None):
        # db_path kept for backward compatibility but ignored — uses DATABASE_URL
        pass

    def _get_connection(self) -> psycopg2.extensions.connection:
        """Get a pooled connection via Flask g (returned by teardown hook)."""
        return get_db_connection()

    def create(self, staging: UploadStaging) -> int:
        """Add a file to upload staging. Returns ID of created entry."""
        query = """
            INSERT INTO upload_staging
            (session_id, filename, file_path, file_size, email_subject,
             email_sender, email_folder, email_date, uploaded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (
            staging.session_id,
            staging.filename,
            staging.file_path,
            staging.file_size,
            staging.email_subject,
            staging.email_sender,
            staging.email_folder,
            staging.email_date,
            staging.uploaded_at
        ))
        staging_id = cursor.fetchone()['id']
        conn.commit()
        return staging_id

    def get_by_session(self, session_id: str) -> List[Any]:
        """Get all staged files for a session"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM upload_staging
            WHERE session_id = %s
            ORDER BY uploaded_at ASC
        """, (session_id,))
        rows = cursor.fetchall()
        return rows

    def row_to_upload_staging(self, row: Any) -> UploadStaging:
        """Convert database row to UploadStaging object"""
        from datetime import datetime
        uploaded_at = row['uploaded_at']
        if isinstance(uploaded_at, str):
            uploaded_at = datetime.fromisoformat(uploaded_at)
        return UploadStaging(
            id=row['id'],
            session_id=row['session_id'],
            filename=row['filename'],
            file_path=row['file_path'],
            file_size=row['file_size'],
            email_subject=row['email_subject'],
            email_sender=row['email_sender'],
            email_folder=row['email_folder'],
            email_date=row['email_date'],
            uploaded_at=uploaded_at or datetime.now()
        )

    def delete_by_filename(self, session_id: str, filename: str) -> bool:
        """Delete a staged file by filename for specific session"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM upload_staging
            WHERE session_id = %s AND filename = %s
        """, (session_id, filename))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted

    def delete_by_session(self, session_id: str) -> int:
        """Delete all staged files for a session. Returns count deleted."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM upload_staging
            WHERE session_id = %s
        """, (session_id,))
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count

    def cleanup_old_uploads(self, hours: int = 24) -> int:
        """Clean up staged uploads older than specified hours"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM upload_staging
            WHERE uploaded_at < NOW() - INTERVAL '1 hour' * %s
        """, (hours,))
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count
