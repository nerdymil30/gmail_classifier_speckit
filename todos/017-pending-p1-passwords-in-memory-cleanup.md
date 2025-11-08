---
status: resolved
priority: p1
issue_id: "017"
tags: [security, sensitive-data, memory-security, imap, critical]
dependencies: []
---

# Passwords in Memory Without Secure Cleanup

## Problem Statement

Passwords are stored as plain Python strings in the `IMAPCredentials` dataclass without explicit zeroing after use. Python strings are immutable and cannot be securely erased, leaving passwords in memory until garbage collection (which may never happen or leave fragments). Memory dumps, swap files, or debugging tools can reveal passwords.

**Security Risk:** Local attacker can extract passwords via memory dump
**CWE:** CWE-316 (Cleartext Storage of Sensitive Information in Memory)
**OWASP:** A02:2021 – Cryptographic Failures

## Findings

**Location:** `src/gmail_classifier/auth/imap.py:119` (IMAPCredentials dataclass)

**Current Code:**
```python
@dataclass
class IMAPCredentials:
    email: str
    password: str  # Plain string - remains in memory indefinitely
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime | None = None
```

**Attack Scenario:**
1. User authenticates with IMAP credentials containing password string
2. Password stored in memory as immutable string
3. Authentication succeeds or fails, but password remains in memory
4. Attacker with local access runs: `sudo gcore <pid>` (memory dump)
5. Attacker searches dump: `strings core.<pid> | grep -E "[a-z]{16}"` (find app passwords)
6. Password discovered in plaintext from memory

**Additional Attack Vectors:**
- Swap files may contain password data
- Core dumps on crashes
- Debuggers can access process memory
- Memory accessible via `/proc/<pid>/mem` on Linux

## Proposed Solutions

### Option 1: Use bytearray with Secure Cleanup (RECOMMENDED)

**Pros:**
- bytearray is mutable and can be zeroed
- `ctypes.memset()` overwrites memory at C level
- Password cleared on object deletion
- Industry best practice

**Cons:**
- More complex implementation
- Requires manual cleanup calls

**Effort:** Medium (2 hours)
**Risk:** Low (backward compatible via property)

**Implementation:**
```python
import ctypes
from dataclasses import dataclass, field

@dataclass
class IMAPCredentials:
    email: str
    _password_bytes: bytearray = field(default=None, repr=False, init=False)
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime | None = None

    def __init__(self, email: str, password: str, **kwargs):
        self.email = email
        self._password_bytes = bytearray(password.encode('utf-8'))
        self.created_at = kwargs.get('created_at', datetime.now())
        self.last_used = kwargs.get('last_used', None)

    @property
    def password(self) -> str:
        """Get password as string (use sparingly)."""
        if not self._password_bytes:
            raise ValueError("Password has been cleared")
        return self._password_bytes.decode('utf-8')

    def clear_password(self) -> None:
        """Securely clear password from memory."""
        if self._password_bytes:
            # Overwrite with zeros at C memory level
            ctypes.memset(id(self._password_bytes) + 32, 0, len(self._password_bytes))
            self._password_bytes.clear()

    def __del__(self):
        """Cleanup password on object deletion."""
        self.clear_password()

    def __repr__(self) -> str:
        """Exclude password from representation."""
        return (
            f"IMAPCredentials(email='{self.email}', "
            f"created_at={self.created_at.isoformat()}, "
            f"last_used={self.last_used.isoformat() if self.last_used else 'Never'})"
        )
```

## Recommended Action

1. **Implement bytearray password storage** with `clear_password()` method
2. **Update CLI to clear passwords** after authentication failures
3. **Clear passwords after storage** in keyring
4. **Add memory security tests** to verify cleanup

## Technical Details

**Affected Files:**
- `src/gmail_classifier/auth/imap.py:119` - IMAPCredentials dataclass
- `src/gmail_classifier/cli/main.py:391,399` - Add `clear_password()` calls
- `src/gmail_classifier/auth/imap.py:authenticate()` - Clear on errors

**Related Components:**
- IMAPAuthenticator.authenticate()
- CredentialStorage.store_credentials()
- CLI login command

**Database Changes:** No

**Additional Updates:**

```python
# In authenticate() method:
except IMAPAuthenticationError:
    # Clear password from memory on auth failure
    credentials.clear_password()
    raise

# In CLI login command:
if storage.store_credentials(credentials):
    click.echo("✓ Credentials saved securely in system keyring")
    credentials.clear_password()  # Clear from memory after storage
```

## Resources

- **CWE-316:** https://cwe.mitre.org/data/definitions/316.html
- **Secure Memory Handling:** https://pypi.org/project/securemem/
- **Python ctypes:** https://docs.python.org/3/library/ctypes.html

## Acceptance Criteria

- [ ] IMAPCredentials uses bytearray for password storage
- [ ] `clear_password()` method implemented with `ctypes.memset()`
- [ ] Password cleared after failed authentication
- [ ] Password cleared after successful keyring storage
- [ ] `__del__` cleanup implemented
- [ ] Property accessor for backward compatibility
- [ ] Test: verify password cleared from memory
- [ ] Test: verify `clear_password()` can be called multiple times safely
- [ ] Test: verify accessing password after clear raises error
- [ ] All existing tests still pass

## Work Log

### 2025-11-08 - Initial Discovery
**By:** Claude Multi-Agent Review System
**Actions:**
- Issue discovered during comprehensive IMAP security audit
- Categorized as P1 Critical
- Estimated effort: 2 hours

**Learnings:**
- Python strings are immutable and live in memory until GC
- Memory dumps are a real attack vector for local attackers
- Gmail app passwords are 16 characters - perfect target
- Industry practice is to use mutable buffers with explicit cleanup
- ctypes.memset() required for low-level memory zeroing

## Notes

**Source:** IMAP Implementation Security Audit - 2025-11-08
**Review Agent:** Security-Sentinel
**Priority Justification:** Critical memory security issue enabling credential theft
**Production Blocker:** YES - High-value target (Gmail credentials)
