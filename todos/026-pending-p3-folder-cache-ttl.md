---
status: resolved
priority: p3
issue_id: "026"
tags: [performance, caching, imap]
dependencies: []
---

# Folder Cache Never Invalidates

## Problem Statement

Folder list cached indefinitely. New labels invisible until app restart, unbounded memory growth.

**Impact:** Stale metadata, memory leak

## Solution

Add 10-minute TTL to folder cache:

```python
@dataclass
class CacheEntry:
    data: list[EmailFolder]
    created_at: datetime
    ttl: timedelta = timedelta(minutes=10)

    def is_stale(self) -> bool:
        return datetime.now() - self.created_at > self.ttl
```

**Effort:** 1 hour

## Implementation Details

**Files Modified:**
- `/Users/ravivedula/Library/CloudStorage/Dropbox/1-projects/Coding/gmail_classifier_speckit/src/gmail_classifier/email/fetcher.py`
  - Added `CacheEntry` dataclass (lines 120-141) with TTL support
  - Updated `FolderManager._folder_cache` to use `CacheEntry` type (line 167)
  - Enhanced `list_folders()` with TTL validation and `force_refresh` parameter (lines 172-225)

**Tests Added:**
- `/Users/ravivedula/Library/CloudStorage/Dropbox/1-projects/Coding/gmail_classifier_speckit/tests/unit/test_imap_folders.py`
  - `test_list_folders_force_refresh_bypasses_cache()` - Validates force_refresh parameter
  - `test_list_folders_cache_expires_after_ttl()` - Validates TTL expiration behavior

**Features Implemented:**
1. CacheEntry dataclass with `data`, `created_at`, and `ttl` fields
2. `is_stale()` method to check cache validity (default 10 minutes)
3. TTL validation in `list_folders()` before returning cached data
4. `force_refresh` parameter to bypass cache when needed
5. Proper logging for cache hits, misses, and force refreshes

**Resolution Date:** 2025-11-09
