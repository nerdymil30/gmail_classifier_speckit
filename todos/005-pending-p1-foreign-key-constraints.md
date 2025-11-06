---
status: pending
priority: p1
issue_id: "005"
tags: [code-review, data-integrity, critical, database, sqlite]
dependencies: []
---

# Enable SQLite Foreign Key Constraints

## Problem Statement

SQLite foreign key constraints are NOT enabled in database connections. SQLite requires explicit `PRAGMA foreign_keys = ON` to enforce referential integrity. Without this, orphaned records can exist in `classification_suggestions` table when sessions are deleted, causing data corruption.

## Findings

**Discovered by:** data-integrity-guardian agent during database schema analysis

**Location:** `src/gmail_classifier/lib/session_db.py:31-35`

**Current Code:**
```python
def _get_connection(self) -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.Connection(str(self.db_path))
    conn.row_factory = sqlite3.Row
    return conn  # Foreign keys NOT enabled!
```

**Schema Definition (lines 63-78):**
```sql
CREATE TABLE IF NOT EXISTS classification_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    email_id TEXT NOT NULL,
    -- ...
    FOREIGN KEY (session_id) REFERENCES processing_sessions(id)
    -- But this constraint is NOT enforced!
)
```

**Data Corruption Scenario:**
1. Classification suggestions saved for session X
2. User runs cleanup command or manually deletes session X from database
3. WITHOUT foreign keys enabled: Orphaned suggestions remain in table
4. System attempts to `load_suggestions(session_id="X")`
5. Returns suggestions for non-existent session
6. User tries to apply labels → confusion and errors

**Risk Level:** CRITICAL - Referential integrity not enforced, orphaned data possible

## Proposed Solutions

### Option 1: Enable PRAGMA in Connection (RECOMMENDED)
**Pros:**
- Simple one-line fix
- Enforces referential integrity at database level
- Prevents orphaned records
- Standard SQLite best practice

**Cons:** None

**Effort:** Small (5 minutes)
**Risk:** Low

**Implementation:**
```python
def _get_connection(self) -> sqlite3.Connection:
    """Get database connection with foreign keys enabled."""
    conn = sqlite3.Connection(str(self.db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # CRITICAL FIX
    return conn
```

### Option 2: Add CASCADE Deletion to Schema (RECOMMENDED - Additional)
**Pros:**
- Automatically deletes child records when parent deleted
- Cleaner data management
- Eliminates need for manual cascade deletion in code

**Cons:**
- Requires schema migration for existing databases

**Effort:** Small (15 minutes)
**Risk:** Low

**Implementation:**
```python
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
            ON DELETE CASCADE  -- Auto-delete suggestions when session deleted
    )
    """
)
```

### Option 3: Application-Level Integrity Checks
**Pros:**
- More control over deletion behavior
- Can add custom logic

**Cons:**
- Error-prone (easy to forget checks)
- Duplicates database functionality
- Slower than database-level enforcement

**Effort:** Large (requires checking all delete operations)
**Risk:** High (easy to miss cases)

**Not Recommended** - Database should handle referential integrity.

## Recommended Action

**Implement BOTH Option 1 and Option 2:**
1. Enable foreign keys in connection (immediate fix)
2. Add CASCADE deletion to schema (clean data management)

## Technical Details

**Affected Files:**
- `src/gmail_classifier/lib/session_db.py`
  - Line 31-35: `_get_connection()` method
  - Line 63-78: `classification_suggestions` table schema

**Related Components:**
- Session deletion operations
- Suggestion queries
- Database cleanup operations

**Database Changes:**
- Enable PRAGMA foreign_keys (runtime change)
- Modify schema to add ON DELETE CASCADE (schema migration needed)

**Migration Strategy:**
For existing databases, add migration in `_init_database()`:
```python
# Check if constraint exists with CASCADE
cursor.execute("PRAGMA foreign_key_list(classification_suggestions)")
fk_list = cursor.fetchall()

# If CASCADE not present, recreate table
if not any('CASCADE' in str(fk) for fk in fk_list):
    logger.info("Migrating classification_suggestions table to add CASCADE")
    cursor.execute("ALTER TABLE classification_suggestions RENAME TO _old_suggestions")
    # Create new table with CASCADE
    cursor.execute(CREATE_TABLE_SQL)
    # Copy data
    cursor.execute("INSERT INTO classification_suggestions SELECT * FROM _old_suggestions")
    cursor.execute("DROP TABLE _old_suggestions")
```

## Resources

- [SQLite Foreign Key Documentation](https://www.sqlite.org/foreignkeys.html)
- [SQLite PRAGMA foreign_keys](https://www.sqlite.org/pragma.html#pragma_foreign_keys)
- [SQLite ON DELETE CASCADE](https://www.sqlite.org/foreignkeys.html#fk_actions)
- Related findings: 003-pending-p1-database-transaction-boundaries.md

## Acceptance Criteria

- [ ] `PRAGMA foreign_keys = ON` added to `_get_connection()`
- [ ] `ON DELETE CASCADE` added to foreign key constraint
- [ ] Unit test: Foreign key constraint enforced (INSERT with invalid session_id fails)
- [ ] Unit test: CASCADE deletion works (delete session deletes suggestions)
- [ ] Integration test: Cannot create orphaned suggestions
- [ ] Migration test: Existing databases migrated correctly
- [ ] Manual test: Delete session and verify suggestions auto-deleted
- [ ] Verify cleanup_old_sessions() still works correctly
- [ ] Code reviewed and approved

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (data-integrity-guardian agent)
**Actions:**
- Discovered foreign keys not enabled during schema analysis
- Identified potential for orphaned records
- Verified schema has foreign key definitions but not enforced
- Categorized as P1 critical data integrity issue

**Learnings:**
- SQLite foreign keys are disabled by default
- Must explicitly enable with PRAGMA on each connection
- ON DELETE CASCADE prevents orphaned child records
- This is a common SQLite gotcha in Python applications
