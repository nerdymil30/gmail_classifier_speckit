---
status: pending
priority: p3
issue_id: "027"
tags: [code-quality, duplication, imap]
dependencies: []
---

# Duplicated Validation Logic

## Problem Statement

Email/password validation duplicated in `IMAPCredentials.__post_init__` and `IMAPAuthenticator._validate_credentials()`. Two sources of truth, inefficient regex recompilation.

## Solution

Remove `_validate_credentials()`, use dataclass validation only:

```python
def authenticate(self, credentials: IMAPCredentials):
    # Dataclass already validated in __post_init__
    self._warn_if_not_gmail(credentials.email)
    # Remove: self._validate_credentials(credentials)
```

**Effort:** 30 minutes
