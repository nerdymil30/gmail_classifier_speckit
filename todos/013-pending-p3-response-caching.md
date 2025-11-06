---
status: pending
priority: p3
issue_id: "013"
tags: [code-review, performance, medium, caching, optimization]
dependencies: []
---

# Implement Response Caching for API Calls

## Problem Statement

The application re-fetches Gmail labels and re-classifies emails on every run, even when the same emails are processed multiple times (testing, failures, retries). This wastes API quota, costs money (Claude API), and slows down operations. Implementing intelligent caching can provide near-instant reclassification for unchanged content.

## Findings

**Discovered by:** performance-oracle agent during optimization analysis

**Locations:**
1. `src/gmail_classifier/services/classifier.py:80-82` - Labels fetched every run
2. `src/gmail_classifier/services/claude_client.py:107-168` - No classification caching

**Caching Opportunities:**

**1. Gmail Labels (High Value)**
```python
# Current: Fetched on every classification run
user_labels = self.gmail_client.get_user_labels()  # 200-500ms API call

# Labels rarely change, could be cached for hours
```

**2. Claude Classifications (Medium Value)**
```python
# Current: Same emails reclassified on retry
suggestions = self.claude_client.classify_batch(emails, labels)

# If email content unchanged, classification should be same
```

**3. Gmail Profile (Low Value)**
```python
# Fetched on every run, rarely changes
profile = self.gmail_client.get_profile()
```

**Performance Gains:**

| Operation | Current | Cached | Savings |
|-----------|---------|--------|---------|
| Label fetch | 200-500ms | <1ms | ~500ms |
| Reclassify 100 emails | 10-15s | <1s | ~14s |
| Profile fetch | 100-200ms | <1ms | ~200ms |

**Cost Savings:**
- Claude API: $0.25 per 1M input tokens
- Caching 1,000 email reclassifications: ~$2-5 saved
- Over time: significant cost reduction

**Risk Level:** MEDIUM - Performance and cost optimization opportunity

## Proposed Solutions

### Option 1: Simple In-Memory Cache with TTL (RECOMMENDED for Labels)
**Pros:**
- Simple implementation
- No external dependencies
- Automatic expiration
- Thread-safe with proper locking

**Cons:**
- Lost on process restart
- Not shared across sessions

**Effort:** Small (1 hour)
**Risk:** Low

**Implementation:**

```python
"""Simple caching utilities."""

import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar
from functools import wraps
import threading

T = TypeVar('T')


@dataclass
class CacheEntry:
    """Cached value with expiration."""
    value: Any
    expires_at: float


class SimpleCache:
    """Thread-safe in-memory cache with TTL."""

    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """Get value from cache if not expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry and time.time() < entry.expires_at:
                return entry.value

            # Expired or missing
            if entry:
                del self._cache[key]
            return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Set value in cache with TTL."""
        with self._lock:
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=time.time() + ttl_seconds
            )

    def clear(self) -> None:
        """Clear all cached values."""
        with self._lock:
            self._cache.clear()


def cached(ttl_seconds: int = 3600):
    """Decorator to cache function results.

    Args:
        ttl_seconds: Time to live in seconds (default 1 hour)

    Example:
        @cached(ttl_seconds=3600)
        def expensive_operation():
            return fetch_data()
    """
    cache = SimpleCache()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try cache first
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value

            # Cache miss - call function
            logger.debug(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(cache_key, result, ttl_seconds)
            return result

        # Add cache management methods
        wrapper.clear_cache = cache.clear
        return wrapper

    return decorator


# Usage in EmailClassifier
class EmailClassifier:
    @cached(ttl_seconds=3600)  # Cache for 1 hour
    def get_user_labels(self) -> list[Label]:
        """Get Gmail labels with caching."""
        return self.gmail_client.get_user_labels()
```

### Option 2: SQLite-Based Persistent Cache (RECOMMENDED for Classifications)
**Pros:**
- Survives process restarts
- Can track cache hits/misses
- Query-able cache
- Share across sessions

**Cons:**
- Disk I/O overhead
- More complex

**Effort:** Medium (3-4 hours)
**Risk:** Low

**Implementation:**

```python
"""Persistent cache for classification results."""

import hashlib
import json
from datetime import datetime, timezone, timedelta
import sqlite3
from pathlib import Path

from gmail_classifier.lib.config import Config
from gmail_classifier.models.suggestion import ClassificationSuggestion


class ClassificationCache:
    """Persistent cache for email classifications."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or (Config.HOME_DIR / "classification_cache.db")
        self._init_cache_db()

    def _init_cache_db(self) -> None:
        """Initialize cache database."""
        conn = sqlite3.Connection(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS classification_cache (
                content_hash TEXT PRIMARY KEY,
                email_content TEXT NOT NULL,
                labels_json TEXT NOT NULL,
                suggestion_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_accessed_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 1
            )
            """
        )

        # Index for cleanup
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_last_accessed "
            "ON classification_cache(last_accessed_at)"
        )

        conn.commit()
        conn.close()

    def _compute_hash(self, email_content: str, label_names: list[str]) -> str:
        """Compute cache key from email content and available labels."""
        # Hash includes email content + sorted label names
        data = f"{email_content}|{'|'.join(sorted(label_names))}"
        return hashlib.sha256(data.encode()).hexdigest()

    def get(
        self,
        email_content: str,
        label_names: list[str],
        max_age_hours: int = 48
    ) -> ClassificationSuggestion | None:
        """Get cached classification if available and fresh.

        Args:
            email_content: Email content to classify
            label_names: Available label names
            max_age_hours: Maximum age of cached result (default 48 hours)

        Returns:
            Cached suggestion or None if cache miss
        """
        content_hash = self._compute_hash(email_content, label_names)

        conn = sqlite3.Connection(str(self.db_path))
        cursor = conn.cursor()

        # Calculate cutoff time
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()

        try:
            cursor.execute(
                """
                SELECT suggestion_json, created_at FROM classification_cache
                WHERE content_hash = ? AND created_at > ?
                """,
                (content_hash, cutoff)
            )

            row = cursor.fetchone()
            if not row:
                return None

            # Update access statistics
            cursor.execute(
                """
                UPDATE classification_cache
                SET last_accessed_at = ?,
                    access_count = access_count + 1
                WHERE content_hash = ?
                """,
                (datetime.now(timezone.utc).isoformat(), content_hash)
            )
            conn.commit()

            # Deserialize suggestion
            suggestion_data = json.loads(row[0])
            return ClassificationSuggestion.from_dict(suggestion_data)

        finally:
            conn.close()

    def set(
        self,
        email_content: str,
        label_names: list[str],
        suggestion: ClassificationSuggestion
    ) -> None:
        """Cache classification result.

        Args:
            email_content: Email content
            label_names: Available label names
            suggestion: Classification suggestion to cache
        """
        content_hash = self._compute_hash(email_content, label_names)
        now = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.Connection(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO classification_cache
                (content_hash, email_content, labels_json, suggestion_json,
                 created_at, last_accessed_at, access_count)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    content_hash,
                    email_content[:500],  # Store preview only
                    json.dumps(label_names),
                    json.dumps(suggestion.to_dict()),
                    now,
                    now
                )
            )
            conn.commit()
        finally:
            conn.close()

    def cleanup_old_entries(self, days_to_keep: int = 30) -> int:
        """Remove cache entries older than specified days.

        Args:
            days_to_keep: Number of days to keep cached results

        Returns:
            Number of entries removed
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_to_keep)).isoformat()

        conn = sqlite3.Connection(str(self.db_path))
        try:
            cursor = conn.execute(
                "DELETE FROM classification_cache WHERE created_at < ?",
                (cutoff,)
            )
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        finally:
            conn.close()


# Usage in ClaudeClient
class ClaudeClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or get_claude_api_key()
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = Config.CLAUDE_MODEL
        self.cache = ClassificationCache()  # Add cache

    def classify_batch(
        self,
        emails: list[Email],
        available_labels: list[Label]
    ) -> list[ClassificationSuggestion]:
        """Classify emails with caching."""
        suggestions = []
        label_names = [label.name for label in available_labels]

        for email in emails:
            # Try cache first
            cached = self.cache.get(email.content, label_names, max_age_hours=48)

            if cached:
                # Update email_id (cached suggestion has old ID)
                cached.email_id = email.id
                suggestions.append(cached)
                logger.debug(f"Cache hit for email {email.id}")
            else:
                # Cache miss - classify with API
                suggestion = self._classify_single_email(email, available_labels)
                suggestions.append(suggestion)

                # Cache result
                self.cache.set(email.content, label_names, suggestion)
                logger.debug(f"Cached classification for email {email.id}")

        return suggestions
```

### Option 3: Redis for Distributed Caching
**Pros:**
- Fast in-memory storage
- TTL built-in
- Can share across multiple processes
- Professional solution

**Cons:**
- External dependency (Redis server)
- Overkill for single-user CLI tool
- Adds deployment complexity

**Effort:** Medium (2-3 hours)
**Risk:** Medium

**Not Recommended** - Too complex for this use case.

## Recommended Action

**Implement Both:**
1. **Option 1** for Gmail labels (in-memory, 1 hour TTL)
2. **Option 2** for Claude classifications (SQLite, 48 hour TTL)

This provides best performance (labels) and cost savings (classifications).

## Technical Details

**Affected Files:**
- `src/gmail_classifier/lib/cache.py` (NEW FILE - caching utilities)
- `src/gmail_classifier/services/classifier.py` (use label cache)
- `src/gmail_classifier/services/claude_client.py` (use classification cache)

**Related Components:**
- Label fetching
- Email classification
- Profile fetching (optional)

**Database Changes:**
- New `classification_cache.db` file
- No changes to existing session database

**Cache Configuration:**
```python
# In config.py
CACHE_LABEL_TTL_SECONDS: int = 3600  # 1 hour
CACHE_CLASSIFICATION_MAX_AGE_HOURS: int = 48  # 2 days
CACHE_CLEANUP_DAYS: int = 30  # Keep 30 days
```

## Resources

- [Python Caching Patterns](https://realpython.com/lru-cache-python/)
- [functools.lru_cache](https://docs.python.org/3/library/functools.html#functools.lru_cache)
- [Caching Strategies](https://martinfowler.com/bliki/TwoHardThings.html)
- Related findings: Performance optimization section in detailed review

## Acceptance Criteria

- [ ] `SimpleCache` class implemented
- [ ] `@cached` decorator implemented
- [ ] `ClassificationCache` class implemented
- [ ] Gmail label fetching uses in-memory cache
- [ ] Claude classifications use persistent cache
- [ ] Cache hit/miss logged
- [ ] Cache cleanup command added to CLI
- [ ] Unit test: In-memory cache works with TTL
- [ ] Unit test: Persistent cache stores and retrieves correctly
- [ ] Unit test: Expired cache entries ignored
- [ ] Integration test: Reclassify same emails uses cache
- [ ] Performance benchmark: 100 cached labels fetched in <1ms
- [ ] Manual test: Cache survives process restart

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (performance-oracle agent)
**Actions:**
- Identified repeated API calls for same data
- Calculated potential performance and cost savings
- Noted label fetching as high-value caching target
- Categorized as P3 medium priority (optimization)

**Learnings:**
- Labels rarely change, excellent cache target
- Classification caching can save API costs
- Content hashing prevents duplicate classification work
- TTL prevents stale cache issues
- SQLite good for persistent cache in single-user apps
