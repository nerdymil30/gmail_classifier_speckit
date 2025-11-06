"""Caching utilities for Gmail Classifier."""

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

from gmail_classifier.lib.config import storage_config
from gmail_classifier.lib.logger import get_logger
from gmail_classifier.models.suggestion import ClassificationSuggestion

logger = get_logger(__name__)

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


class ClassificationCache:
    """Persistent cache for email classifications."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or (storage_config.home_dir / "classification_cache.db")
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
            logger.info(f"Cleaned up {deleted} old cache entries")
            return deleted
        finally:
            conn.close()

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        conn = sqlite3.Connection(str(self.db_path))
        try:
            cursor = conn.cursor()

            # Total entries
            cursor.execute("SELECT COUNT(*) FROM classification_cache")
            total_entries = cursor.fetchone()[0]

            # Total access count
            cursor.execute("SELECT SUM(access_count) FROM classification_cache")
            total_accesses = cursor.fetchone()[0] or 0

            # Average access count
            avg_accesses = total_accesses / total_entries if total_entries > 0 else 0

            return {
                "total_entries": total_entries,
                "total_accesses": total_accesses,
                "avg_accesses_per_entry": round(avg_accesses, 2),
            }
        finally:
            conn.close()

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        conn = sqlite3.Connection(str(self.db_path))
        try:
            cursor = conn.execute("DELETE FROM classification_cache")
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Cleared {deleted} cache entries")
            return deleted
        finally:
            conn.close()
