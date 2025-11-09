---
status: resolved
priority: p3
issue_id: "033"
tags: [code-quality, pythonic, performance, imap]
dependencies: []
---

# Non-Pythonic Flag Checking

## Problem Statement

Using `b"".join(flags)` for membership checks (O(n)) instead of set (O(1)).

**Location:** `email/fetcher.py:71`

## Solution

Use set for flag checking:

```python
# Before:
flags_bytes = b"".join(flags)
if b"\\Sent" in flags_bytes:
    folder_type = "SENT"

# After:
flags_set = set(flags)
if b"\\Sent" in flags_set:
    folder_type = "SENT"
```

**Effort:** 15 minutes
