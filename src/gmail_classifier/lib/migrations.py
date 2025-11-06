"""Database migration system for schema evolution."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from gmail_classifier.lib.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Migration:
    """Represents a database migration."""

    version: int
    description: str
    upgrade_sql: list[str]
    downgrade_sql: list[str] | None = None


# Migration registry - all migrations must be registered here in version order
MIGRATIONS = [
    Migration(
        version=1,
        description="Initial schema",
        upgrade_sql=[
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
            """,
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
                    ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS gmail_operations_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT NOT NULL,
                email_id TEXT NOT NULL,
                label_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                db_synced BOOLEAN DEFAULT 0,
                error_message TEXT,
                session_id TEXT,
                FOREIGN KEY (session_id) REFERENCES processing_sessions(id)
                    ON DELETE CASCADE
            )
            """,
            # Single-column indexes
            """
            CREATE INDEX IF NOT EXISTS idx_session_user_email
            ON processing_sessions(user_email)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_session_status
            ON processing_sessions(status)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_suggestion_session
            ON classification_suggestions(session_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_suggestion_email
            ON classification_suggestions(email_id)
            """,
        ],
        downgrade_sql=[
            "DROP INDEX IF EXISTS idx_suggestion_email",
            "DROP INDEX IF EXISTS idx_suggestion_session",
            "DROP INDEX IF EXISTS idx_session_status",
            "DROP INDEX IF EXISTS idx_session_user_email",
            "DROP TABLE IF EXISTS gmail_operations_log",
            "DROP TABLE IF EXISTS classification_suggestions",
            "DROP TABLE IF EXISTS processing_sessions",
        ],
    ),
    Migration(
        version=2,
        description="Add composite indexes for query optimization",
        upgrade_sql=[
            """
            CREATE INDEX IF NOT EXISTS idx_suggestion_session_status
            ON classification_suggestions(session_id, status)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_session_user_status
            ON processing_sessions(user_email, status)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_session_status_start
            ON processing_sessions(status, start_time)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_session_created
            ON processing_sessions(created_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_gmail_ops_email
            ON gmail_operations_log(email_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_gmail_ops_synced
            ON gmail_operations_log(db_synced)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_gmail_ops_session
            ON gmail_operations_log(session_id)
            """,
        ],
        downgrade_sql=[
            "DROP INDEX IF EXISTS idx_gmail_ops_session",
            "DROP INDEX IF EXISTS idx_gmail_ops_synced",
            "DROP INDEX IF EXISTS idx_gmail_ops_email",
            "DROP INDEX IF EXISTS idx_session_created",
            "DROP INDEX IF EXISTS idx_session_status_start",
            "DROP INDEX IF EXISTS idx_session_user_status",
            "DROP INDEX IF EXISTS idx_suggestion_session_status",
        ],
    ),
    Migration(
        version=3,
        description="Add consent timestamp for user privacy tracking",
        upgrade_sql=[
            """
            ALTER TABLE processing_sessions
            ADD COLUMN consent_timestamp TEXT
            """
        ],
        downgrade_sql=None,  # Cannot remove columns in SQLite easily
    ),
]


class MigrationManager:
    """Manages database schema migrations."""

    def __init__(self, db_path: Path):
        """
        Initialize migration manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get database connection with proper settings.

        Returns:
            SQLite connection with foreign keys enabled
        """
        conn = sqlite3.Connection(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_version_table(self, conn: sqlite3.Connection) -> None:
        """
        Create schema_version table if it doesn't exist.

        Args:
            conn: Database connection
        """
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def get_current_version(self) -> int:
        """
        Get current database schema version.

        Returns:
            Current version number (0 if no migrations applied)
        """
        conn = self._get_connection()
        try:
            self._ensure_version_table(conn)
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()[0]
            return result if result is not None else 0
        finally:
            conn.close()

    def migrate(self, target_version: int | None = None) -> None:
        """
        Apply migrations up to target version.

        Args:
            target_version: Version to migrate to (None = latest)

        Raises:
            ValueError: If target version is invalid
            Exception: If migration fails
        """
        current_version = self.get_current_version()

        # Determine target version
        if target_version is None:
            target = max(m.version for m in MIGRATIONS)
        else:
            target = target_version

        # Validate target version
        if target < 0:
            raise ValueError(f"Invalid target version: {target}")

        if current_version >= target:
            logger.info(f"Database already at version {current_version}")
            return

        logger.info(f"Migrating database from version {current_version} to {target}")

        conn = self._get_connection()
        try:
            with conn:
                self._ensure_version_table(conn)

                for migration in MIGRATIONS:
                    if current_version < migration.version <= target:
                        logger.info(
                            f"Applying migration {migration.version}: {migration.description}"
                        )

                        # Execute upgrade SQL
                        for sql in migration.upgrade_sql:
                            conn.execute(sql)

                        # Record migration
                        conn.execute(
                            "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                            (migration.version, migration.description),
                        )

                        logger.info(f"Migration {migration.version} applied successfully")

            logger.info(f"Database migrated to version {target}")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            conn.close()

    def rollback(self, target_version: int) -> None:
        """
        Rollback migrations to target version.

        Args:
            target_version: Version to rollback to

        Raises:
            ValueError: If rollback is not possible
            Exception: If rollback fails
        """
        current_version = self.get_current_version()

        if current_version <= target_version:
            logger.info(f"Database already at or before version {target_version}")
            return

        logger.warning(
            f"Rolling back database from version {current_version} to {target_version}"
        )

        conn = self._get_connection()
        try:
            with conn:
                # Apply downgrades in reverse order
                for migration in reversed(MIGRATIONS):
                    if target_version < migration.version <= current_version:
                        if not migration.downgrade_sql:
                            raise ValueError(
                                f"Migration {migration.version} has no downgrade path"
                            )

                        logger.info(f"Rolling back migration {migration.version}")

                        for sql in migration.downgrade_sql:
                            conn.execute(sql)

                        conn.execute(
                            "DELETE FROM schema_version WHERE version = ?",
                            (migration.version,),
                        )

            logger.info(f"Database rolled back to version {target_version}")

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise
        finally:
            conn.close()

    def get_migration_history(self) -> list[dict]:
        """
        Get history of applied migrations.

        Returns:
            List of migration records with version, description, and applied_at
        """
        conn = self._get_connection()
        try:
            self._ensure_version_table(conn)
            cursor = conn.execute(
                """
                SELECT version, description, applied_at
                FROM schema_version
                ORDER BY version
                """
            )
            rows = cursor.fetchall()
            return [
                {
                    "version": row[0],
                    "description": row[1],
                    "applied_at": row[2],
                }
                for row in rows
            ]
        finally:
            conn.close()
