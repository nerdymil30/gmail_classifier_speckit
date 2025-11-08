---
status: resolved
priority: p3
issue_id: "030"
tags: [code-quality, type-hints, imap]
dependencies: []
---

# Missing Type Hints in Critical Locations

## Problem Statement

Generic `tuple` and `dict` types instead of specific type hints. Type safety compromised, unclear API contracts.

## Solution

Add specific type hints using TypedDict:

```python
from typing import TypedDict

class IMAPFetchData(TypedDict):
    BODY[]: bytes
    FLAGS: tuple[bytes, ...]
    INTERNALDATE: datetime

def _parse_email(self, msg_id: int, data: IMAPFetchData) -> Email:
    ...

def from_imap_response(
    flags: tuple[bytes, ...],  # Not just tuple
    delimiter: bytes,
    name: str
) -> "EmailFolder":
    ...
```

**Effort:** 1 hour
