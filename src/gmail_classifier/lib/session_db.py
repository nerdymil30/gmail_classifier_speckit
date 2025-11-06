"""SQLite database for session state management."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from gmail_classifier.lib.config import storage_config, app_config
from gmail_classifier.lib.logger import get_logger
from gmail_classifier.lib.migrations import MigrationManager
from gmail_classifier.models.session import ProcessingSession
from gmail_classifier.models.suggestion import ClassificationSuggestion, SuggestedLabel

logger = get_logger(__name__)


class SessionDatabase:
    """SQLite database for processing sessions and classification suggestions."""

    def __init__(self, db_path: Path | None = None):
        """
        Initialize session database.

        Args:
            db_path: Path to SQLite database file (default: storage_config.session_db_path)
        """
        from gmail_classifier.lib.utils import ensure_secure_directory, ensure_secure_file

        self.db_path = db_path or storage_config.session_db_path

        # Ensure parent directory is secure
        ensure_secure_directory(self.db_path.parent, mode=0o700)

        # Run migrations to ensure schema is up to date
        migration_manager = MigrationManager(self.db_path)
        migration_manager.migrate()

        # Persistent connection (replaced _get_connection pattern)
        self._connection: sqlite3.Connection | None = None

        self._init_database()

        # Ensure database file is secure after creation
        ensure_secure_file(self.db_path, mode=0o600)

    @property
    def connection(self) -> sqlite3.Connection:
        """Get or create persistent database connection."""
        if self._connection is None:
            self._connection = sqlite3.Connection(str(self.db_path))
            self._connection.row_factory = sqlite3.Row  # Enable dict-like access
            self._connection.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
            self._connection.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging for better concurrency

            logger.debug("Created persistent database connection")

        return self._connection

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug("Closed database connection")

    def __del__(self):
        """Cleanup connection on garbage collection."""
        self.close()

    def _init_database(self) -> None:
        """
        Initialize database connection settings.

        Note: Schema creation is now handled by the migration system.
        This method only ensures the connection is properly configured.
        """
        try:
            # Just trigger connection creation to ensure it's properly configured
            # The connection property will set up row_factory, foreign_keys, and WAL mode
            _ = self.connection
            logger.debug(f"Initialized session database at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def save_session(self, session: ProcessingSession) -> None:
        """
        Save or update processing session.

        Args:
            session: ProcessingSession to save
        """
        try:
            with self.connection:  # Automatic transaction management
                cursor = self.connection.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO processing_sessions
                    (id, user_email, start_time, end_time, status, total_emails_to_process,
                     emails_processed, suggestions_generated, suggestions_applied,
                     last_processed_email_id, error_log, config)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.id,
                        session.user_email,
                        session.start_time.isoformat(),
                        session.end_time.isoformat() if session.end_time else None,
                        session.status,
                        session.total_emails_to_process,
                        session.emails_processed,
                        session.suggestions_generated,
                        session.suggestions_applied,
                        session.last_processed_email_id,
                        json.dumps(session.error_log),
                        json.dumps(session.config),
                    ),
                )
            logger.debug(f"Saved session {session.id} to database")
        except Exception as e:
            logger.error(f"Failed to save session {session.id}: {e}")
            raise

    def load_session(self, session_id: str) -> ProcessingSession | None:
        """
        Load processing session by ID.

        Args:
            session_id: Session ID to load

        Returns:
            ProcessingSession if found, None otherwise
        """
        cursor = self.connection.cursor()

        cursor.execute(
            "SELECT * FROM processing_sessions WHERE id = ?",
            (session_id,),
        )

        row = cursor.fetchone()

        if not row:
            return None

        return ProcessingSession(
            id=row["id"],
            user_email=row["user_email"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            status=row["status"],
            total_emails_to_process=row["total_emails_to_process"],
            emails_processed=row["emails_processed"],
            suggestions_generated=row["suggestions_generated"],
            suggestions_applied=row["suggestions_applied"],
            last_processed_email_id=row["last_processed_email_id"],
            error_log=json.loads(row["error_log"]) if row["error_log"] else [],
            config=json.loads(row["config"]) if row["config"] else {},
        )

    def list_sessions(
        self,
        user_email: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ProcessingSession]:
        """
        List processing sessions with optional filters.

        Args:
            user_email: Filter by user email
            status: Filter by status
            limit: Maximum number of sessions to return

        Returns:
            List of ProcessingSession instances
        """
        cursor = self.connection.cursor()

        query = "SELECT * FROM processing_sessions WHERE 1=1"
        params = []

        if user_email:
            query += " AND user_email = ?"
            params.append(user_email)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        sessions = []
        for row in rows:
            sessions.append(
                ProcessingSession(
                    id=row["id"],
                    user_email=row["user_email"],
                    start_time=datetime.fromisoformat(row["start_time"]),
                    end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
                    status=row["status"],
                    total_emails_to_process=row["total_emails_to_process"],
                    emails_processed=row["emails_processed"],
                    suggestions_generated=row["suggestions_generated"],
                    suggestions_applied=row["suggestions_applied"],
                    last_processed_email_id=row["last_processed_email_id"],
                    error_log=json.loads(row["error_log"]) if row["error_log"] else [],
                    config=json.loads(row["config"]) if row["config"] else {},
                )
            )

        return sessions

    def save_suggestion(self, session_id: str, suggestion: ClassificationSuggestion) -> None:
        """
        Save classification suggestion.

        Args:
            session_id: Session ID this suggestion belongs to
            suggestion: ClassificationSuggestion to save
        """
        try:
            with self.connection:  # Automatic transaction management
                cursor = self.connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO classification_suggestions
                    (session_id, email_id, suggested_labels, confidence_category,
                     reasoning, created_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        suggestion.email_id,
                        json.dumps([label.to_dict() for label in suggestion.suggested_labels]),
                        suggestion.confidence_category,
                        suggestion.reasoning,
                        suggestion.created_at.isoformat(),
                        suggestion.status,
                    ),
                )
            logger.debug(f"Saved suggestion for email {suggestion.email_id} to database")
        except Exception as e:
            logger.error(f"Failed to save suggestion for email {suggestion.email_id}: {e}")
            raise

    def load_suggestions(
        self,
        session_id: str,
        status: str | None = None,
    ) -> list[ClassificationSuggestion]:
        """
        Load classification suggestions for a session.

        Args:
            session_id: Session ID to load suggestions for
            status: Optional status filter

        Returns:
            List of ClassificationSuggestion instances
        """
        cursor = self.connection.cursor()

        query = "SELECT * FROM classification_suggestions WHERE session_id = ?"
        params = [session_id]

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        suggestions = []
        for row in rows:
            suggested_labels_data = json.loads(row["suggested_labels"])
            suggested_labels = [SuggestedLabel.from_dict(label) for label in suggested_labels_data]

            suggestions.append(
                ClassificationSuggestion(
                    email_id=row["email_id"],
                    suggested_labels=suggested_labels,
                    confidence_category=row["confidence_category"],
                    reasoning=row["reasoning"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    status=row["status"],
                )
            )

        return suggestions

    def update_suggestion_status(
        self,
        session_id: str,
        email_id: str,
        new_status: str,
    ) -> None:
        """
        Update suggestion status.

        Args:
            session_id: Session ID
            email_id: Email ID
            new_status: New status value
        """
        try:
            with self.connection:  # Automatic transaction management
                cursor = self.connection.cursor()
                cursor.execute(
                    """
                    UPDATE classification_suggestions
                    SET status = ?
                    WHERE session_id = ? AND email_id = ?
                    """,
                    (new_status, session_id, email_id),
                )
            logger.debug(f"Updated suggestion status for email {email_id} to {new_status}")
        except Exception as e:
            logger.error(f"Failed to update suggestion status for email {email_id}: {e}")
            raise

    def cleanup_old_sessions(self, days_to_keep: int | None = None) -> int:
        """
        Delete sessions older than specified days.

        Args:
            days_to_keep: Number of days to keep (default: app_config.keep_sessions_days)

        Returns:
            Number of sessions deleted
        """
        days = days_to_keep or app_config.keep_sessions_days

        try:
            with self.connection:  # Automatic transaction management
                cursor = self.connection.cursor()

                # Calculate cutoff date
                cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                cutoff_date = cutoff_date - timedelta(days=days)

                # Delete old sessions (CASCADE will automatically delete related suggestions)
                cursor.execute(
                    "DELETE FROM processing_sessions WHERE start_time < ?",
                    (cutoff_date.isoformat(),),
                )

                deleted_count = cursor.rowcount

            logger.info(f"Cleaned up {deleted_count} old sessions (older than {days} days)")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            raise

    def get_session_stats(self, session_id: str) -> dict:
        """
        Get statistics for a session.

        Args:
            session_id: Session ID

        Returns:
            Dictionary with session statistics
        """
        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT
                status,
                COUNT(*) as count,
                AVG(CASE
                    WHEN suggested_labels != '[]' THEN 1.0
                    ELSE 0.0
                END) as match_rate
            FROM classification_suggestions
            WHERE session_id = ?
            GROUP BY status
            """,
            (session_id,),
        )

        stats = {}
        for row in cursor.fetchall():
            stats[row["status"]] = {
                "count": row["count"],
                "match_rate": row["match_rate"] or 0.0,
            }

        return stats

    # Gmail Operations Audit Log Methods

    def log_gmail_operation(
        self,
        operation_type: str,
        email_id: str,
        label_id: str,
        success: bool,
        timestamp: str,
        session_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        Log a Gmail API operation for audit trail.

        Args:
            operation_type: Type of operation (e.g., 'add_label', 'remove_label')
            email_id: Gmail message ID
            label_id: Gmail label ID
            success: Whether the operation succeeded
            timestamp: ISO format timestamp
            session_id: Optional session ID
            error_message: Optional error message if operation failed
        """
        try:
            with self.connection:
                cursor = self.connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO gmail_operations_log
                    (operation_type, email_id, label_id, timestamp, success,
                     db_synced, error_message, session_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operation_type,
                        email_id,
                        label_id,
                        timestamp,
                        success,
                        0,  # Not synced yet
                        error_message,
                        session_id,
                    ),
                )
            logger.debug(
                f"Logged Gmail operation: {operation_type} for email {email_id}, "
                f"success={success}"
            )
        except Exception as e:
            logger.error(f"Failed to log Gmail operation: {e}")
            # Don't raise - we don't want audit logging to break the main flow
            # But log it as a critical issue
            logger.critical(f"AUDIT LOG FAILURE: {e}")

    def mark_operation_synced(
        self,
        email_id: str,
        label_id: str,
    ) -> None:
        """
        Mark a Gmail operation as synced to database.

        Args:
            email_id: Gmail message ID
            label_id: Gmail label ID
        """
        try:
            with self.connection:
                cursor = self.connection.cursor()
                cursor.execute(
                    """
                    UPDATE gmail_operations_log
                    SET db_synced = 1
                    WHERE email_id = ? AND label_id = ?
                    AND success = 1
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """,
                    (email_id, label_id),
                )
            logger.debug(f"Marked operation synced for email {email_id}")
        except Exception as e:
            logger.error(f"Failed to mark operation as synced: {e}")
            # Don't raise - we don't want this to break the main flow

    def get_unsynced_operations(
        self,
        session_id: str | None = None,
    ) -> list[dict]:
        """
        Get Gmail operations that succeeded but were not synced to database.

        Args:
            session_id: Optional session ID to filter by

        Returns:
            List of unsynced operation records
        """
        cursor = self.connection.cursor()

        query = """
            SELECT *
            FROM gmail_operations_log
            WHERE success = 1 AND db_synced = 0
        """
        params = []

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        query += " ORDER BY timestamp DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        operations = []
        for row in rows:
            operations.append({
                "id": row["id"],
                "operation_type": row["operation_type"],
                "email_id": row["email_id"],
                "label_id": row["label_id"],
                "timestamp": row["timestamp"],
                "session_id": row["session_id"],
            })

        return operations

    def get_operation_log(
        self,
        session_id: str | None = None,
        email_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get Gmail operation log entries.

        Args:
            session_id: Optional session ID to filter by
            email_id: Optional email ID to filter by
            limit: Maximum number of entries to return

        Returns:
            List of operation log records
        """
        cursor = self.connection.cursor()

        query = "SELECT * FROM gmail_operations_log WHERE 1=1"
        params = []

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        if email_id:
            query += " AND email_id = ?"
            params.append(email_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        operations = []
        for row in rows:
            operations.append({
                "id": row["id"],
                "operation_type": row["operation_type"],
                "email_id": row["email_id"],
                "label_id": row["label_id"],
                "timestamp": row["timestamp"],
                "success": bool(row["success"]),
                "db_synced": bool(row["db_synced"]),
                "error_message": row["error_message"],
                "session_id": row["session_id"],
            })

        return operations
