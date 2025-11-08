---
status: pending
priority: p3
issue_id: "029"
tags: [security, rate-limiting, authentication, imap]
dependencies: []
---

# Missing Rate Limiting on Authentication

## Problem Statement

No rate limiting on authentication attempts. Attackers can try unlimited passwords, enabling brute-force attacks.

**CWE:** CWE-307 (Improper Restriction of Excessive Authentication Attempts)

## Solution

Track failed attempts, implement exponential lockout:

```python
class IMAPAuthenticator:
    def __init__(self):
        self._failed_attempts = defaultdict(list)
        self._lockout_until = {}

    def _check_rate_limit(self, email: str):
        now = datetime.now()

        # Check lockout
        if email in self._lockout_until and now < self._lockout_until[email]:
            remaining = (self._lockout_until[email] - now).total_seconds()
            raise IMAPAuthenticationError(f"Try again in {int(remaining)}s")

        # Clean old attempts (>15 min)
        cutoff = now - timedelta(minutes=15)
        self._failed_attempts[email] = [a for a in self._failed_attempts[email] if a > cutoff]

        # Check count
        if len(self._failed_attempts[email]) >= 5:
            lockout_min = 2 ** min(len(self._failed_attempts[email]) - 4, 6)
            self._lockout_until[email] = now + timedelta(minutes=lockout_min)
            raise IMAPAuthenticationError(f"Locked for {lockout_min} minutes")
```

**Effort:** 2 hours
