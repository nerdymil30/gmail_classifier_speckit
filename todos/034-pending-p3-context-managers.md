---
status: resolved
priority: p3
issue_id: "034"
tags: [code-quality, resource-management, imap]
dependencies: []
---

# Missing Context Managers for IMAP Connections

## Problem Statement

IMAP connections created without context managers. File descriptor leaks possible if authentication fails between creation and login.

**Location:** `auth/imap.py:356-361`

## Solution

Implement context manager protocol:

```python
@dataclass
class IMAPSessionInfo:
    # ... existing fields ...

    def __enter__(self) -> "IMAPSessionInfo":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.connection:
            try:
                self.connection.logout()
            except:
                pass
```

**Effort:** 1 hour
