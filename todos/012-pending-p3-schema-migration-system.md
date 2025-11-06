---
status: pending
priority: p3
issue_id: "012"
tags: [code-review, data-integrity, medium, database, migrations]
dependencies: [003-pending-p1-database-transaction-boundaries, 005-pending-p1-foreign-key-constraints]
---

# Add Database Schema Migration System

## Problem Statement

The database schema is initialized with `CREATE TABLE IF NOT EXISTS` but has no migration strategy. When schema changes are needed (adding columns, modifying constraints, adding indexes), existing databases will fail with "no such column" or constraint errors. There's no versioning or upgrade path.

## Findings

**Discovered by:** data-integrity-guardian agent during schema analysis

**Location:** `src/gmail_classifier/lib/session_db.py:37-99`

**Current Approach:**
```python
def _init_database(self) -> None:
    """Initialize database with schema."""
    conn = self._get_connection()
    cursor = conn.cursor()

    # Creates table if doesn't exist
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS processing_sessions (...)
        """
    )

    # But no version tracking or migrations!
```

**Problem Scenarios:**

**Scenario 1: Adding New Column**
```python
# New version adds column
CREATE TABLE processing_sessions (
    ...
    consent_timestamp TEXT  -- NEW COLUMN
)

# But CREATE TABLE IF NOT EXISTS does nothing for existing tables
# Queries fail: "no such column: consent_timestamp"
```

**Scenario 2: Modifying Constraints**
```python
# Want to add CHECK constraint
CHECK(emails_processed >= 0)

# Cannot modify existing table constraints in SQLite
# Need to recreate table
```

**Scenario 3: Adding Indexes**
```python
# Add new composite index
CREATE INDEX idx_new_pattern ...

# CREATE INDEX IF NOT EXISTS works
# But no tracking of which indexes applied when
```

**Risk Level:** MEDIUM - Blocks future schema evolution

## Proposed Solutions

### Option 1: Version-Based Migration System (RECOMMENDED)
**Pros:**
- Industry standard approach
- Clear version tracking
- Can rollback if needed
- Migration history preserved
- Simple to implement

**Cons:**
- Need to write migration functions
- Schema changes require code

**Effort:** Medium (3-4 hours initial setup)
**Risk:** Low

**Implementation:**

```python
"""Database migration system."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import logging

logger = logging.getLogger(__name__)


@dataclass
class Migration:
    """Represents a database migration."""
    version: int
    description: str
    upgrade_sql: list[str]
    downgrade_sql: list[str] | None = None


# Migration registry
MIGRATIONS = [
    Migration(
        version=1,
        description="Initial schema",
        upgrade_sql=[
            """
            CREATE TABLE processing_sessions (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                status TEXT NOT NULL DEFAULT 'in_progress',
                total_emails_to_process INTEGER DEFAULT 0,
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
            CREATE TABLE classification_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                email_id TEXT NOT NULL,
                suggested_labels TEXT NOT NULL,
                confidence_category TEXT NOT NULL,
                reasoning TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                FOREIGN KEY (session_id) REFERENCES processing_sessions(id) ON DELETE CASCADE
            )
            """,
        ],
        downgrade_sql=[
            "DROP TABLE IF EXISTS classification_suggestions",
            "DROP TABLE IF EXISTS processing_sessions",
        ]
    ),
    Migration(
        version=2,
        description="Add composite indexes",
        upgrade_sql=[
            "CREATE INDEX idx_suggestion_session_status ON classification_suggestions(session_id, status)",
            "CREATE INDEX idx_session_user_status ON processing_sessions(user_email, status)",
        ],
        downgrade_sql=[
            "DROP INDEX IF EXISTS idx_suggestion_session_status",
            "DROP INDEX IF EXISTS idx_session_user_status",
        ]
    ),
    Migration(
        version=3,
        description="Add consent timestamp",
        upgrade_sql=[
            "ALTER TABLE processing_sessions ADD COLUMN consent_timestamp TEXT"
        ],
        downgrade_sql=None  # Cannot remove columns in SQLite easily
    ),
]


class MigrationManager:
    """Manages database schema migrations."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.Connection(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_version_table(self, conn: sqlite3.Connection) -> None:
        """Create schema_version table if not exists."""
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
        """Get current database schema version."""
        conn = self._get_connection()
        try:
            self._ensure_version_table(conn)
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()[0]
            return result if result is not None else 0
        finally:
            conn.close()

    def migrate(self, target_version: int | None = None) -> None:
        """Apply migrations up to target version.

        Args:
            target_version: Version to migrate to (None = latest)
        """
        current_version = self.get_current_version()
        target = target_version if target_version else max(m.version for m in MIGRATIONS)

        if current_version >= target:
            logger.info(f"Database already at version {current_version}")
            return

        logger.info(f"Migrating database from version {current_version} to {target}")

        conn = self._get_connection()
        try:
            with conn:
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
                            (migration.version, migration.description)
                        )

                        logger.info(f"Migration {migration.version} applied successfully")

            logger.info(f"Database migrated to version {target}")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            conn.close()

    def rollback(self, target_version: int) -> None:
        """Rollback migrations to target version.

        Args:
            target_version: Version to rollback to
        """
        current_version = self.get_current_version()

        if current_version <= target_version:
            logger.info(f"Database already at or before version {target_version}")
            return

        logger.warning(f"Rolling back database from version {current_version} to {target_version}")

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
                            (migration.version,)
                        )

            logger.info(f"Database rolled back to version {target_version}")

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise
        finally:
            conn.close()


# Update SessionDatabase to use migrations
class SessionDatabase:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Config.SESSION_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Run migrations
        migration_manager = MigrationManager(self.db_path)
        migration_manager.migrate()

        # Connection setup...
```

### Option 2: Alembic (Professional Migration Tool)
**Pros:**
- Industry-standard tool (used with SQLAlchemy)
- Auto-generates migrations
- Branching, merging migrations
- Command-line interface

**Cons:**
- Heavy dependency for SQLite
- Overkill for this project
- Requires learning Alembic

**Effort:** Large (1-2 days)
**Risk:** Low

**Not Recommended** - Too complex for current needs.

### Option 3: Manual Migration Scripts
**Pros:**
- Simple SQL scripts
- Version control in git
- Run manually by users

**Cons:**
- Error-prone
- User must remember to run
- No automatic tracking

**Effort:** Small (1 hour)
**Risk:** High

**Not Recommended** - Users will forget to run migrations.

## Recommended Action

**Implement Option 1** - Version-based migration system integrated into `SessionDatabase`.

**Migration Workflow:**
1. Database version checked on startup
2. Missing migrations applied automatically
3. Migration history recorded in `schema_version` table
4. Rollback capability for development

## Technical Details

**Affected Files:**
- `src/gmail_classifier/lib/session_db.py` (integrate migrations)
- `src/gmail_classifier/lib/migrations.py` (NEW FILE - migration definitions)

**Related Components:**
- Database initialization
- Schema evolution
- Application startup

**Database Changes:**
- Add `schema_version` table
- Refactor schema creation into migrations

**Future Migrations:**
- v2: Composite indexes (from todo #009)
- v3: Additional columns as needed
- v4: Constraint modifications

## Resources

- [Database Migration Patterns](https://martinfowler.com/articles/evodb.html)
- [SQLite ALTER TABLE Limitations](https://www.sqlite.org/lang_altertable.html)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- Related findings: 003-pending-p1-database-transaction-boundaries.md

## Acceptance Criteria

- [ ] `migrations.py` module created with migration definitions
- [ ] `MigrationManager` class implemented
- [ ] `schema_version` table tracks applied migrations
- [ ] Migrations applied automatically on startup
- [ ] Rollback functionality implemented
- [ ] Migration v1: Initial schema
- [ ] Migration v2: Composite indexes
- [ ] Unit test: Migrations applied in order
- [ ] Unit test: Rollback works correctly
- [ ] Unit test: Already-migrated database skips migrations
- [ ] Integration test: Fresh database migrates to latest
- [ ] CLI command: `gmail-classifier migrate --version N`
- [ ] CLI command: `gmail-classifier db-version` (show current version)

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (data-integrity-guardian agent)
**Actions:**
- Discovered lack of migration strategy during schema analysis
- Identified future schema evolution blocker
- Recognized SQLite ALTER TABLE limitations
- Categorized as P3 medium priority (future-proofing)

**Learnings:**
- Schema versioning essential for production applications
- SQLite has limited ALTER TABLE support
- Migration system should be integrated, not manual
- Version tracking prevents migration conflicts
