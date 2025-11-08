---
status: resolved
priority: p3
issue_id: "032"
tags: [performance, regex, optimization, imap]
dependencies: []
---

# Regex Pattern Recompilation

## Problem Statement

Email validation regex compiled on every credential creation. Unnecessary CPU cycles.

**Locations:** `auth/imap.py:128, 594`

## Solution

Compile once at module level:

```python
import re

# Module-level constant
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# In __post_init__:
if not EMAIL_PATTERN.match(self.email):
    raise ValueError(f"Invalid email format")
```

**Effort:** 15 minutes
