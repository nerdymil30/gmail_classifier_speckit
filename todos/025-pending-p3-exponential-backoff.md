---
status: pending
priority: p3
issue_id: "025"
tags: [performance, retry-logic, imap]
dependencies: []
---

# Exponential Backoff Too Aggressive

## Problem Statement

Retry timing: 3s, 6s, 12s, 24s, 48s = 93 seconds total. Users wait 1.5 minutes for transient network glitches.

**Impact:** 50% slower failure detection than necessary

## Solution

Cap at 15s with jitter: 2s, 4s, 8s, 15s, 15s = 44 seconds:

```python
def calculate_backoff(attempt: int, base: float = 2.0, max_delay: float = 15.0):
    delay = min(base * (2 ** attempt), max_delay)
    jitter = delay * 0.25 * (2 * random.random() - 1)
    return delay + jitter
```

**Performance Gain:** 93s → 44s (50% faster)

**Effort:** 30 minutes
