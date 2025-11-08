---
status: pending
priority: p1
issue_id: "016"
tags: [security, cryptographic-failures, imap, critical]
dependencies: []
---

# Missing SSL/TLS Certificate Verification

## Problem Statement

The `IMAPClient` is initialized with `ssl=True` but does not explicitly configure SSL context or certificate verification. While the imapclient library defaults to verification, this leaves the implementation vulnerable to man-in-the-middle (MITM) attacks if default behavior changes or if someone modifies the `use_ssl` parameter.

**Security Risk:** Complete Gmail account compromise via MITM attack
**CWE:** CWE-295 (Improper Certificate Validation)
**OWASP:** A02:2021 – Cryptographic Failures

## Findings

**Location:** `src/gmail_classifier/auth/imap.py:356-361`

**Current Code:**
```python
client = IMAPClient(
    self._server,
    port=self._port,
    ssl=self._use_ssl,  # Only boolean flag, no SSL context
    timeout=30,
)
```

**Attack Scenario:**
1. Attacker positions themselves between user and Gmail IMAP server
2. SSL/TLS handshake occurs without explicit certificate validation
3. Attacker presents fake certificate
4. If verification bypassed, credentials transmitted to attacker in plaintext
5. Complete Gmail account compromise

**Impact:**
- Credentials can be intercepted via man-in-the-middle attacks
- No protection against SSL stripping attacks
- Vulnerable if `use_ssl` parameter modified to `False`

## Proposed Solutions

### Option 1: Explicit SSL Context with Certificate Verification (RECOMMENDED)

**Pros:**
- Enforces certificate validation
- Sets minimum TLS version (1.2+)
- Explicit hostname checking
- Industry best practice

**Cons:**
- Slightly more code
- Breaks if someone expects to disable SSL (this is good!)

**Effort:** Small (1 hour)
**Risk:** Low (only affects invalid certificates, which should fail)

**Implementation:**
```python
import ssl

# In authenticate() method:
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

client = IMAPClient(
    self._server,
    port=self._port,
    ssl=True,  # Always True - remove use_ssl parameter
    ssl_context=ssl_context,
    timeout=30,
)
```

### Option 2: Remove use_ssl Parameter Entirely

**Additional hardening:**
```python
# In __init__, remove use_ssl parameter:
def __init__(
    self,
    server: str = "imap.gmail.com",
    port: int = 993,
    # Remove: use_ssl: bool = True,
) -> None:
    # Always enforce SSL
```

## Recommended Action

1. **Add explicit SSL context** with certificate verification (Option 1)
2. **Remove `use_ssl` parameter** from constructor (Option 2)
3. **Add hostname validation** for Gmail domains
4. **Set minimum TLS 1.2** requirement

## Technical Details

**Affected Files:**
- `src/gmail_classifier/auth/imap.py` (lines 296-300, 356-361)

**Related Components:**
- IMAPAuthenticator class
- All IMAP authentication flows

**Database Changes:** No

**Additional Updates:**
```python
# Add hostname validation warning:
def _warn_if_not_gmail(self, server: str) -> None:
    """Warn if server is not Gmail domain."""
    if not server.endswith("gmail.com") and not server.endswith("googlemail.com"):
        self._logger.warning(
            f"Server {server} is not a recognized Gmail domain. "
            f"SSL certificate validation may fail."
        )
```

## Resources

- **CWE-295:** https://cwe.mitre.org/data/definitions/295.html
- **Python SSL Module:** https://docs.python.org/3/library/ssl.html
- **OWASP Cryptographic Failures:** https://owasp.org/Top10/A02_2021-Cryptographic_Failures/

## Acceptance Criteria

- [ ] SSL context created with `ssl.create_default_context()`
- [ ] Certificate verification explicitly set to `CERT_REQUIRED`
- [ ] Hostname checking enabled
- [ ] Minimum TLS version set to 1.2
- [ ] `use_ssl` parameter removed from constructor
- [ ] Tests verify connection fails with invalid certificate
- [ ] Tests verify connection fails with expired certificate
- [ ] Tests verify minimum TLS 1.2 enforced
- [ ] All existing tests still pass

## Work Log

### 2025-11-08 - Initial Discovery
**By:** Claude Multi-Agent Review System
**Actions:**
- Issue discovered during comprehensive IMAP security audit
- Categorized as P1 Critical
- Estimated effort: 1 hour

**Learnings:**
- imapclient library defaults to verification but explicit is better
- SSL stripping attacks possible without explicit context
- Industry standard is to always enforce certificate validation
- Gmail IMAP uses port 993 with SSL/TLS

## Notes

**Source:** IMAP Implementation Security Audit - 2025-11-08
**Review Agent:** Security-Sentinel
**Priority Justification:** Critical security vulnerability that enables credential theft
**Production Blocker:** YES - Must fix before deploying IMAP feature
