---
status: resolved
priority: p3
issue_id: "028"
tags: [security, information-disclosure, imap]
dependencies: []
---

# Error Messages Expose Internal Details

## Problem Statement

Error messages log full exception details, potentially exposing internal information that aids attackers.

**CWE:** CWE-209 (Information Exposure Through Error Messages)

## Solution

Sanitize error messages, hash emails in logs:

```python
def _sanitize_error(self, error: Exception) -> str:
    error_str = str(error).lower()
    if 'invalid' in error_str or 'credentials' in error_str:
        return "Authentication credentials rejected"
    elif 'ssl' in error_str or 'tls' in error_str:
        return "SSL/TLS connection error"
    return "Connection error"

def _hash_email(self, email: str) -> str:
    return hashlib.sha256(email.encode()).hexdigest()[:12]
```

**Effort:** 1 hour
