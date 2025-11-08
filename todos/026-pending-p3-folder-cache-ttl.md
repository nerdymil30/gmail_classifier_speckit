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
