---
status: pending
priority: p2
issue_id: "024"
tags: [architecture, testing, dependency-injection, imap]
dependencies: []
---

# Missing Dependency Injection

## Problem Statement

Concrete dependencies hardcoded (imapclient, keyring), making code impossible to test without real IMAP server and OS keyring.

**Impact:** Untestable code, tight coupling, violates Dependency Inversion Principle

## Solution

Introduce Protocol-based DI with adapter pattern:

```python
# Create protocols
from typing import Protocol

@runtime_checkable
class IMAPAuthProtocol(Protocol):
    def authenticate(self, credentials) -> IMAPSessionInfo: ...
    def disconnect(self, session_id: UUID) -> None: ...

class IMAPClientAdapter(Protocol):
    def connect(self, server: str, port: int) -> IMAPClient: ...

# Update classes
class FolderManager:
    def __init__(self, authenticator: IMAPAuthProtocol):  # Protocol, not concrete
        self._authenticator = authenticator
```

**Benefits:** Easy mocking, testable without network, swappable implementations

**Effort:** 4 hours
