"""
Upload Staging Repository - Manages temporary file uploads
"""
import sqlite3
from typing import List

from database.models import UploadStaging


class UploadStagingRepository:
    """Repository for managing upload staging data"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create(self, staging: UploadStaging) -> int:
        """
        Add a file to upload staging
        
        Args:
            staging: UploadStaging object
            
        Returns:
            int: ID of created staging entry
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO upload_staging 
            (session_id, filename, file_path, file_size, email_subject, 
             email_sender, email_folder, email_date, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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
        
        staging_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return staging_id
    
    def get_by_session(self, session_id: str) -> List[sqlite3.Row]:
        """
        Get all staged files for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of Row objects with staged files
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM upload_staging 
            WHERE session_id = ?
            ORDER BY uploaded_at ASC
        """, (session_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return rows
    
    def row_to_upload_staging(self, row: sqlite3.Row) -> UploadStaging:
        """
        Convert database Row to UploadStaging object
        
        Args:
            row: sqlite3.Row object
            
        Returns:
            UploadStaging object
        """
        from datetime import datetime
        
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
            uploaded_at=datetime.fromisoformat(row['uploaded_at']) if row['uploaded_at'] else datetime.now()
        )
    
    def delete_by_filename(self, session_id: str, filename: str) -> bool:
        """
        Delete a staged file by filename for specific session
        
        Args:
            session_id: Session identifier
            filename: Name of file to delete
            
        Returns:
            bool: True if deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM upload_staging 
            WHERE session_id = ? AND filename = ?
        """, (session_id, filename))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def delete_by_session(self, session_id: str) -> int:
        """
        Delete all staged files for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            int: Number of files deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM upload_staging 
            WHERE session_id = ?
        """, (session_id,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted_count
    
    def cleanup_old_uploads(self, hours: int = 24) -> int:
        """
        Clean up staged uploads older than specified hours
        
        Args:
            hours: Age threshold in hours (default 24)
            
        Returns:
            int: Number of files deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM upload_staging 
            WHERE datetime(uploaded_at) < datetime('now', '-' || ? || ' hours')
        """, (hours,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted_count
