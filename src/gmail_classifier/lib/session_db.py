"""SQLite database for session state management."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from gmail_classifier.lib.config import Config
from gmail_classifier.lib.logger import get_logger
from gmail_classifier.models.session import ProcessingSession
from gmail_classifier.models.suggestion import ClassificationSuggestion, SuggestedLabel

logger = get_logger(__name__)


class SessionDatabase:
    """SQLite database for processing sessions and classification suggestions."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize session database.

        Args:
            db_path: Path to SQLite database file (default: Config.SESSION_DB_PATH)
        """
        self.db_path = db_path or Config.SESSION_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.Connection(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn

    def _init_database(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create processing_sessions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processing_sessions (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                status TEXT NOT NULL,
                total_emails_to_process INTEGER NOT NULL,
                emails_processed INTEGER DEFAULT 0,
                suggestions_generated INTEGER DEFAULT 0,
                suggestions_applied INTEGER DEFAULT 0,
                last_processed_email_id TEXT,
                error_log TEXT,
                config TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Create classification_suggestions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS classification_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                email_id TEXT NOT NULL,
                suggested_labels TEXT NOT NULL,
                confidence_category TEXT NOT NULL,
                reasoning TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                FOREIGN KEY (session_id) REFERENCES processing_sessions(id)
            )
            """
        )

        # Create indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_session_user_email "
            "ON processing_sessions(user_email)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_session_status "
            "ON processing_sessions(status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_suggestion_session "
            "ON classification_suggestions(session_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_suggestion_email "
            "ON classification_suggestions(email_id)"
        )

        conn.commit()
        conn.close()

        logger.debug(f"Initialized session database at {self.db_path}")

    def save_session(self, session: ProcessingSession) -> None:
        """
        Save or update processing session.

        Args:
            session: ProcessingSession to save
        """
        conn = self._get_connection()
        cursor = conn.cursor()

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

        conn.commit()
        conn.close()

        logger.debug(f"Saved session {session.id} to database")

    def load_session(self, session_id: str) -> Optional[ProcessingSession]:
        """
        Load processing session by ID.

        Args:
            session_id: Session ID to load

        Returns:
            ProcessingSession if found, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM processing_sessions WHERE id = ?",
            (session_id,),
        )

        row = cursor.fetchone()
        conn.close()

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
        user_email: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[ProcessingSession]:
        """
        List processing sessions with optional filters.

        Args:
            user_email: Filter by user email
            status: Filter by status
            limit: Maximum number of sessions to return

        Returns:
            List of ProcessingSession instances
        """
        conn = self._get_connection()
        cursor = conn.cursor()

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
        conn.close()

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
        conn = self._get_connection()
        cursor = conn.cursor()

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

        conn.commit()
        conn.close()

        logger.debug(f"Saved suggestion for email {suggestion.email_id} to database")

    def load_suggestions(
        self,
        session_id: str,
        status: Optional[str] = None,
    ) -> List[ClassificationSuggestion]:
        """
        Load classification suggestions for a session.

        Args:
            session_id: Session ID to load suggestions for
            status: Optional status filter

        Returns:
            List of ClassificationSuggestion instances
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM classification_suggestions WHERE session_id = ?"
        params = [session_id]

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

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
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE classification_suggestions
            SET status = ?
            WHERE session_id = ? AND email_id = ?
            """,
            (new_status, session_id, email_id),
        )

        conn.commit()
        conn.close()

        logger.debug(f"Updated suggestion status for email {email_id} to {new_status}")

    def cleanup_old_sessions(self, days_to_keep: Optional[int] = None) -> int:
        """
        Delete sessions older than specified days.

        Args:
            days_to_keep: Number of days to keep (default: Config.KEEP_SESSIONS_DAYS)

        Returns:
            Number of sessions deleted
        """
        days = days_to_keep or Config.KEEP_SESSIONS_DAYS

        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff date
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta

        cutoff_date = cutoff_date - timedelta(days=days)

        # Delete old suggestions first (foreign key constraint)
        cursor.execute(
            """
            DELETE FROM classification_suggestions
            WHERE session_id IN (
                SELECT id FROM processing_sessions
                WHERE start_time < ?
            )
            """,
            (cutoff_date.isoformat(),),
        )

        # Delete old sessions
        cursor.execute(
            "DELETE FROM processing_sessions WHERE start_time < ?",
            (cutoff_date.isoformat(),),
        )

        deleted_count = cursor.rowcount

        conn.commit()
        conn.close()

        logger.info(f"Cleaned up {deleted_count} old sessions (older than {days} days)")

        return deleted_count

    def get_session_stats(self, session_id: str) -> dict:
        """
        Get statistics for a session.

        Args:
            session_id: Session ID

        Returns:
            Dictionary with session statistics
        """
        conn = self._get_connection()
        cursor = conn.cursor()

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

        conn.close()

        return stats
