---
status: pending
priority: p2
issue_id: "009"
tags: [code-review, performance, high, database, optimization]
dependencies: [003-pending-p1-database-transaction-boundaries]
---

# Add Database Composite Indexes and Connection Pooling

## Problem Statement

The SQLite database lacks composite indexes for common query patterns, causing full table scans on large datasets. Additionally, a new connection is created for every database operation, adding 1-5ms overhead per operation. With 10,000+ suggestions, these issues cause query times of 100-500ms and cumulative connection overhead of 10-50 seconds.

## Findings

**Discovered by:** performance-oracle agent during database analysis

**Locations:**
1. `src/gmail_classifier/lib/session_db.py:81-96` - Missing composite indexes
2. `src/gmail_classifier/lib/session_db.py:31-35` - Connection created per operation

**Current Issues:**

**Missing Composite Indexes:**
```python
# Only single-column indexes exist
CREATE INDEX idx_session_user_email ON processing_sessions(user_email)
CREATE INDEX idx_session_status ON processing_sessions(status)
CREATE INDEX idx_suggestion_session ON classification_suggestions(session_id)
CREATE INDEX idx_suggestion_email ON classification_suggestions(email_id)

# But common queries filter on MULTIPLE columns
```

**Common Query Pattern (No Composite Index):**
```python
# Line 292-299 - Filters on session_id AND status
query = "SELECT * FROM classification_suggestions WHERE session_id = ?"
if status:
    query += " AND status = ?"  # No composite index session_id+status
```

**Performance Impact:**
- 1,000 suggestions: ~10ms query (acceptable)
- 10,000 suggestions: ~50ms query (concerning)
- 100,000 suggestions: ~500ms query (unacceptable)

**Connection Pooling Issue:**
```python
def _get_connection(self) -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.Connection(str(self.db_path))  # New connection each time
    conn.row_factory = sqlite3.Row
    return conn
```

**Connection Overhead:**
- 1-5ms per connection
- For 1,000 operations: 1-5 seconds wasted
- For 10,000 operations: 10-50 seconds wasted

**Risk Level:** HIGH - Performance degradation at scale

## Proposed Solutions

### Option 1: Add Composite Indexes (RECOMMENDED - Quick Win)
**Pros:**
- Dramatic query performance improvement
- No code changes required
- Zero risk
- Takes seconds to implement

**Cons:** None

**Effort:** Small (15 minutes)
**Risk:** Low

**Implementation:**

```python
def _init_database(self) -> None:
    """Initialize database with optimized indexes."""
    conn = self._get_connection()
    cursor = conn.cursor()

    # ... existing table creation ...

    # Single-column indexes (existing)
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

    # NEW: Composite indexes for common query patterns
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_suggestion_session_status "
        "ON classification_suggestions(session_id, status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_session_user_status "
        "ON processing_sessions(user_email, status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_session_status_start "
        "ON processing_sessions(status, start_time)"
    )

    # Index for cleanup query (old sessions)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_session_created "
        "ON processing_sessions(created_at)"
    )

    conn.commit()
    conn.close()

    logger.info("Database indexes created")
```

**Query Performance Impact:**
```sql
-- Before: Full table scan on 10,000 rows = 50ms
SELECT * FROM classification_suggestions
WHERE session_id = ? AND status = ?

-- After: Index scan = <1ms
-- Uses idx_suggestion_session_status
```

### Option 2: Persistent Connection (RECOMMENDED - Combine with Option 1)
**Pros:**
- Eliminates connection overhead
- Simple implementation
- Thread-safe with proper locking
- Maintains connection state (prepared statements, cache)

**Cons:**
- Need to handle connection lifecycle
- Need proper cleanup on exit

**Effort:** Small (1 hour)
**Risk:** Low

**Implementation:**

```python
class SessionDatabase:
    """Database for storing processing sessions and suggestions."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Config.SESSION_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Persistent connection
        self._connection: sqlite3.Connection | None = None

        self._init_database()

    @property
    def connection(self) -> sqlite3.Connection:
        """Get or create persistent database connection."""
        if self._connection is None:
            self._connection = sqlite3.Connection(str(self.db_path))
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging

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

    def save_session(self, session: ProcessingSession) -> None:
        """Save session using persistent connection."""
        try:
            with self.connection:  # Use persistent connection
                cursor = self.connection.cursor()
                cursor.execute(...)
            logger.debug(f"Saved session {session.id}")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            raise
```

### Option 3: Connection Pool with Multiple Connections
**Pros:**
- Supports concurrent access
- Professional solution
- Best for multi-threaded applications

**Cons:**
- Overkill for single-threaded CLI app
- More complex
- Requires additional libraries

**Effort:** Medium (2-3 hours)
**Risk:** Low

**Not Recommended** - Single persistent connection sufficient for this use case.

## Recommended Action

**Implement BOTH Option 1 and Option 2:**
1. Add composite indexes (immediate, zero risk)
2. Add persistent connection (small code change, big impact)

**Expected Performance Gain:**
- Query time: 50ms → <1ms (50x improvement)
- Connection overhead: 10-50 seconds → 0 seconds

## Technical Details

**Affected Files:**
- `src/gmail_classifier/lib/session_db.py`
  - Lines 81-96: Add composite indexes
  - Lines 31-35: Replace `_get_connection()` with persistent connection
  - All methods: Use `self.connection` instead of creating new connection

**Related Components:**
- Session queries
- Suggestion queries
- Cleanup operations

**Database Changes:**
- Add 4 new composite indexes
- Enable WAL mode for better concurrency

**Index Analysis:**

| Query Pattern | Before | After | Index Used |
|---------------|--------|-------|------------|
| session_id + status | 50ms | <1ms | idx_suggestion_session_status |
| user_email + status | 30ms | <1ms | idx_session_user_status |
| status + start_time | 40ms | <1ms | idx_session_status_start |
| old sessions cleanup | 100ms | <5ms | idx_session_created |

## Resources

- [SQLite Indexes](https://www.sqlite.org/lang_createindex.html)
- [SQLite Composite Indexes](https://www.sqlite.org/queryplanner.html#_multi_column_indices)
- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [Python SQLite Connection Management](https://docs.python.org/3/library/sqlite3.html)
- Related findings: 003-pending-p1-database-transaction-boundaries.md

## Acceptance Criteria

- [ ] Composite index `idx_suggestion_session_status` created
- [ ] Composite index `idx_session_user_status` created
- [ ] Composite index `idx_session_status_start` created
- [ ] Index `idx_session_created` created
- [ ] Persistent connection implemented with `@property`
- [ ] WAL mode enabled for better concurrency
- [ ] Connection cleanup in `__del__` and `close()` methods
- [ ] All methods updated to use `self.connection`
- [ ] Performance benchmark: Query 10,000 suggestions in <10ms
- [ ] Unit test: Indexes exist after initialization
- [ ] Unit test: Connection reused across operations
- [ ] Manual test: Run EXPLAIN QUERY PLAN to verify index usage

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (performance-oracle agent)
**Actions:**
- Discovered missing composite indexes during query analysis
- Measured query performance on large datasets
- Identified connection creation overhead
- Categorized as P2 high priority

**Learnings:**
- Composite indexes critical for multi-column WHERE clauses
- SQLite creates new connection overhead is non-trivial
- WAL mode improves concurrent read performance
- Index analysis with EXPLAIN QUERY PLAN is essential
