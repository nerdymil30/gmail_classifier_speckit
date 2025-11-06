---
status: pending
priority: p2
issue_id: "007"
tags: [code-review, security, high, file-permissions]
dependencies: []
---

# Enforce Secure File Permissions on Sensitive Files

## Problem Statement

Sensitive files (credentials.json, session database, log files) are created without explicit permission checks or enforcement. Files may have world-readable permissions (644 or 664), exposing OAuth secrets, session data, and potentially sensitive log information to other users on the system.

**CWE:** CWE-732 (Incorrect Permission Assignment for Critical Resource)

## Findings

**Discovered by:** security-sentinel agent during file security audit

**Locations:**
1. `src/gmail_classifier/auth/gmail_auth.py:126-139` - credentials.json read without permission check
2. `src/gmail_classifier/lib/session_db.py:27-29` - Database created without permission setting
3. `src/gmail_classifier/lib/config.py:66` - Log directory created without permission setting

**Current Issues:**

**credentials.json (OAuth Client Secrets):**
```python
# No permission check before reading
with open(self.credentials_path) as f:
    creds_data = json.load(f)
```

**session.db (Contains email IDs and metadata):**
```python
self.db_path = db_path or Config.SESSION_DB_PATH
self.db_path.parent.mkdir(parents=True, exist_ok=True)
self._init_database()  # No permission enforcement
```

**Log files (May contain sensitive debug info):**
```python
LOG_DIR: Path = HOME_DIR / "logs"
# Directory created with default permissions
```

**Risk Level:** HIGH - Sensitive data exposure to other system users

## Proposed Solutions

### Option 1: Runtime Permission Checks and Enforcement (RECOMMENDED)
**Pros:**
- Detects and fixes insecure permissions
- Warns users about security issues
- Automatically secures files on first run
- Minimal code changes

**Cons:**
- Cannot prevent initial insecure creation

**Effort:** Medium (2-3 hours)
**Risk:** Low

**Implementation:**

```python
import os
import stat
from pathlib import Path

def ensure_secure_file(file_path: Path, mode: int = 0o600) -> None:
    """Ensure file has secure permissions, fix if needed."""
    if not file_path.exists():
        # Create with secure permissions
        file_path.touch(mode=mode)
        return

    current_mode = stat.S_IMODE(os.stat(file_path).st_mode)

    # Check if permissions are too permissive
    if current_mode & (stat.S_IRWXG | stat.S_IRWXO):
        logger.warning(
            f"Insecure permissions detected on {file_path}: "
            f"{oct(current_mode)}. Fixing to {oct(mode)}."
        )
        os.chmod(file_path, mode)

def ensure_secure_directory(dir_path: Path, mode: int = 0o700) -> None:
    """Ensure directory has secure permissions."""
    dir_path.mkdir(parents=True, exist_ok=True, mode=mode)

    # Verify and fix if needed
    current_mode = stat.S_IMODE(os.stat(dir_path).st_mode)
    if current_mode != mode:
        os.chmod(dir_path, mode)

# In gmail_auth.py
def _load_credentials_from_file(self) -> Credentials:
    """Load credentials with security checks."""
    # Verify credentials.json permissions
    if not self.credentials_path.exists():
        raise FileNotFoundError(...)

    # Check permissions
    file_stat = os.stat(self.credentials_path)
    file_mode = stat.S_IMODE(file_stat.st_mode)

    # Warn if too permissive
    if file_mode & (stat.S_IRWXG | stat.S_IRWXO):
        logger.warning(
            f"credentials.json has insecure permissions ({oct(file_mode)}). "
            f"Recommended: 600 (owner read/write only). "
            f"Run: chmod 600 {self.credentials_path}"
        )

        # Optionally auto-fix
        if Config.AUTO_FIX_PERMISSIONS:
            os.chmod(self.credentials_path, 0o600)
            logger.info(f"Fixed permissions on {self.credentials_path}")

    # Continue loading...

# In session_db.py
def __init__(self, db_path: Optional[Path] = None):
    self.db_path = db_path or Config.SESSION_DB_PATH

    # Ensure parent directory is secure
    ensure_secure_directory(self.db_path.parent, mode=0o700)

    # Initialize database
    self._init_database()

    # Ensure database file is secure
    ensure_secure_file(self.db_path, mode=0o600)

# In config.py
@classmethod
def ensure_directories(cls) -> None:
    """Create necessary directories with secure permissions."""
    ensure_secure_directory(cls.HOME_DIR, mode=0o700)
    ensure_secure_directory(cls.LOG_DIR, mode=0o700)
    ensure_secure_directory(cls.SESSION_DB_PATH.parent, mode=0o700)
```

### Option 2: Strict Mode (Refuse to Run on Insecure Permissions)
**Pros:**
- Forces users to fix permissions manually
- Maximum security awareness
- No auto-fix ambiguity

**Cons:**
- User friction on first run
- May confuse non-technical users
- Breaks existing setups

**Effort:** Small (1 hour)
**Risk:** Medium (user experience)

**Implementation:**
```python
def validate_file_permissions(file_path: Path, required_mode: int = 0o600) -> None:
    """Validate file has secure permissions, raise if not."""
    if not file_path.exists():
        return

    current_mode = stat.S_IMODE(os.stat(file_path).st_mode)

    if current_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise PermissionError(
            f"Insecure permissions on {file_path}: {oct(current_mode)}. "
            f"Required: {oct(required_mode)}. "
            f"Fix with: chmod {oct(required_mode)[-3:]} {file_path}"
        )
```

### Option 3: Permission Check Only (Warning Mode)
**Pros:**
- Non-intrusive
- Educates users
- No breaking changes

**Cons:**
- Users may ignore warnings
- Files remain insecure

**Effort:** Small (1 hour)
**Risk:** Low

**Not Recommended** - Users will ignore warnings, files remain vulnerable.

## Recommended Action

**Implement Option 1** - Auto-fix with warnings. This provides security without user friction.

Add configuration option:
```python
# In config.py
AUTO_FIX_PERMISSIONS: bool = os.getenv("AUTO_FIX_PERMISSIONS", "true").lower() == "true"
```

## Technical Details

**Affected Files:**
- `src/gmail_classifier/auth/gmail_auth.py` (credentials.json handling)
- `src/gmail_classifier/lib/session_db.py` (database file creation)
- `src/gmail_classifier/lib/config.py` (directory creation)
- `src/gmail_classifier/lib/logger.py` (log file creation)

**Related Components:**
- File I/O operations
- Directory initialization
- Security checks

**Database Changes:** No

**Required Permissions:**
- `credentials.json`: 600 (owner read/write only)
- `session.db`: 600 (owner read/write only)
- Log directory: 700 (owner access only)
- Log files: 600 (owner read/write only)
- Home directory: 700 (owner access only)

## Resources

- [File Permissions Best Practices](https://www.redhat.com/sysadmin/linux-file-permissions-explained)
- [Python os.chmod Documentation](https://docs.python.org/3/library/os.html#os.chmod)
- [OWASP: Insecure File Permissions](https://owasp.org/www-community/vulnerabilities/Insecure_Configuration_Management)
- Related findings: 001-pending-p1-oauth-port-hijacking.md, 002-pending-p1-oauth-csrf-vulnerability.md

## Acceptance Criteria

- [ ] `ensure_secure_file()` utility function implemented
- [ ] `ensure_secure_directory()` utility function implemented
- [ ] credentials.json permissions checked on load
- [ ] Database file permissions set to 600 on creation
- [ ] Log directory permissions set to 700
- [ ] Warning logged when insecure permissions detected
- [ ] AUTO_FIX_PERMISSIONS config option implemented
- [ ] Unit test: Secure permissions enforced
- [ ] Unit test: Insecure permissions detected and warned
- [ ] Manual test: Verify chmod 777 credentials.json triggers warning
- [ ] Manual test: Verify auto-fix corrects permissions
- [ ] Documentation: Security setup guide added to README

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (security-sentinel agent)
**Actions:**
- Discovered during file security audit
- Identified as CWE-732 vulnerability
- Found multiple files with insecure permissions
- Categorized as P2 high priority

**Learnings:**
- File permissions often overlooked in Python applications
- Default umask may create world-readable files
- Security-sensitive files need explicit permission setting
- Python's Path.mkdir() respects umask, doesn't guarantee secure permissions
