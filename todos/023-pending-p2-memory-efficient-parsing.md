---
status: pending
priority: p2
issue_id: "023"
tags: [performance, memory, imap, optimization]
dependencies: []
---

# Memory Inefficient Email Parsing

## Problem Statement

Full email bodies loaded into memory including large attachments. 1000 emails at 500KB average = 500MB memory consumption, causing potential OOM errors.

**Impact:** 70% memory waste, potential out-of-memory crashes

## Solution

Add body size limits (100KB), skip attachments, implement truncation:

```python
def fetch_emails(
    self,
    session_id: uuid.UUID,
    limit: int = 100,
    max_body_size: int = 100_000,  # 100KB max
):
    fetch_fields = [
        "BODY.PEEK[HEADER]",
        f"BODY.PEEK[TEXT]<0.{max_body_size}>",  # Partial fetch
        "FLAGS",
        "INTERNALDATE",
        "RFC822.SIZE"
    ]
```

**Memory Improvement:** 500MB → 100MB (70% reduction)

**Effort:** 3 hours
