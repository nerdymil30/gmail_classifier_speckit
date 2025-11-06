---
status: pending
priority: p3
issue_id: "011"
tags: [code-review, architecture, medium, refactoring, separation-of-concerns]
dependencies: []
---

# Refactor Auth Module to Separate Gmail and Claude Concerns

## Problem Statement

The `auth/gmail_auth.py` module violates the Single Responsibility Principle by containing both Gmail OAuth2 authentication logic (lines 1-191) AND Claude API key management (lines 207-262). This mixing of concerns makes the module harder to test, maintain, and understand.

## Findings

**Discovered by:** architecture-strategist and pattern-recognition-specialist agents

**Location:** `src/gmail_classifier/auth/gmail_auth.py`

**Current Structure:**
```
gmail_auth.py (261 lines)
├─ GmailAuthenticator class (Gmail OAuth2)  [lines 14-191]
│  ├─ authenticate()
│  ├─ _save_credentials_to_keyring()
│  ├─ _load_credentials_from_keyring()
│  └─ OAuth flow management
│
├─ get_gmail_credentials() helper            [lines 194-204]
│
└─ Claude API functions (WRONG MODULE!)      [lines 207-262]
   ├─ setup_claude_api_key()
   ├─ get_claude_api_key()
   └─ validate_claude_api_key()
```

**Issues:**
1. Module named "gmail_auth" contains Claude authentication
2. Difficult to find Claude auth functions (unexpected location)
3. Cannot import Gmail auth without Claude dependencies
4. Testing requires mocking both Gmail and Claude
5. Violates Single Responsibility Principle

**Risk Level:** MEDIUM - Technical debt, maintainability issue

## Proposed Solutions

### Option 1: Create Separate auth/claude_auth.py (RECOMMENDED)
**Pros:**
- Clear separation of concerns
- Parallel structure (gmail_auth.py, claude_auth.py)
- Easy to locate authentication code
- Independent testing

**Cons:**
- Need to update imports

**Effort:** Small (1 hour)
**Risk:** Low

**Implementation:**

**New file: `src/gmail_classifier/auth/claude_auth.py`**
```python
"""Claude API authentication and key management."""

import os
import logging
from typing import Optional

import anthropic
import keyring

from gmail_classifier.lib.config import Config

logger = logging.getLogger(__name__)

# Keyring configuration
KEYRING_SERVICE = "gmail_classifier"
KEYRING_KEY = "anthropic_api_key"


def setup_claude_api_key(api_key: str) -> None:
    """Store Claude API key in system keyring.

    Args:
        api_key: Anthropic API key (starts with 'sk-ant-')

    Raises:
        ValueError: If API key format is invalid
    """
    if not api_key or not api_key.startswith("sk-ant-"):
        raise ValueError("Invalid Claude API key format")

    # Validate key works
    if not validate_claude_api_key(api_key):
        raise ValueError("Claude API key validation failed")

    # Store in keyring
    keyring.set_password(KEYRING_SERVICE, KEYRING_KEY, api_key)
    logger.info("Claude API key stored successfully")


def get_claude_api_key() -> Optional[str]:
    """Retrieve Claude API key from keyring or environment.

    Returns:
        API key if found, None otherwise

    Priority:
        1. Environment variable (ANTHROPIC_API_KEY)
        2. System keyring
    """
    # Try environment variable first
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        logger.debug("Using Claude API key from environment")
        return api_key

    # Try keyring
    api_key = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY)
    if api_key:
        logger.debug("Using Claude API key from keyring")
        return api_key

    logger.warning("No Claude API key found in environment or keyring")
    return None


def validate_claude_api_key(api_key: str) -> bool:
    """Validate Claude API key by making a test request.

    Args:
        api_key: API key to validate

    Returns:
        True if key is valid, False otherwise
    """
    try:
        client = anthropic.Anthropic(api_key=api_key)

        # Make minimal test request
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}],
        )

        logger.debug("Claude API key validation successful")
        return True

    except anthropic.AuthenticationError:
        logger.error("Claude API key authentication failed")
        return False
    except Exception as e:
        logger.error(f"Claude API key validation error: {e}")
        return False


def delete_claude_api_key() -> None:
    """Remove Claude API key from keyring."""
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_KEY)
        logger.info("Claude API key removed from keyring")
    except keyring.errors.PasswordDeleteError:
        logger.warning("No Claude API key found in keyring")
```

**Update: `src/gmail_classifier/auth/__init__.py`**
```python
"""Authentication module for Gmail and Claude."""

from gmail_classifier.auth.gmail_auth import (
    GmailAuthenticator,
    get_gmail_credentials,
)
from gmail_classifier.auth.claude_auth import (
    setup_claude_api_key,
    get_claude_api_key,
    validate_claude_api_key,
    delete_claude_api_key,
)

__all__ = [
    # Gmail authentication
    "GmailAuthenticator",
    "get_gmail_credentials",
    # Claude authentication
    "setup_claude_api_key",
    "get_claude_api_key",
    "validate_claude_api_key",
    "delete_claude_api_key",
]
```

**Remove from `gmail_auth.py`:**
- Lines 207-262 (Claude functions)

**Update imports:**
```python
# Old
from gmail_classifier.auth.gmail_auth import get_claude_api_key

# New
from gmail_classifier.auth.claude_auth import get_claude_api_key
```

### Option 2: Create Unified Credentials Manager
**Pros:**
- Single point for all credential management
- Could support multiple providers
- More extensible architecture

**Cons:**
- More complex refactoring
- Overkill for current needs
- Would need Protocol/ABC definitions

**Effort:** Medium (3-4 hours)
**Risk:** Medium

**Not Recommended** - Simple separation is sufficient.

### Option 3: Keep As-Is with Better Documentation
**Pros:**
- No code changes
- Zero risk

**Cons:**
- Doesn't fix the architectural issue
- Still violates SRP
- Confusion persists

**Effort:** Small (5 minutes)
**Risk:** None

**Not Recommended** - Band-aid solution.

## Recommended Action

**Implement Option 1** - Create separate `auth/claude_auth.py` module with clear separation.

**Migration Strategy:**
1. Create `claude_auth.py` with all Claude functions
2. Update `__init__.py` exports
3. Update all imports across codebase
4. Remove Claude functions from `gmail_auth.py`
5. Run tests to ensure nothing broke

## Technical Details

**Affected Files:**
- `src/gmail_classifier/auth/gmail_auth.py` (remove Claude functions)
- `src/gmail_classifier/auth/claude_auth.py` (NEW FILE)
- `src/gmail_classifier/auth/__init__.py` (update exports)
- `src/gmail_classifier/services/claude_client.py` (update imports)
- `src/gmail_classifier/cli/main.py` (update imports)

**Related Components:**
- Authentication system
- Claude API client
- CLI commands

**Database Changes:** No

**Import Changes:**
```bash
# Find all files importing Claude auth from gmail_auth
grep -r "from gmail_classifier.auth.gmail_auth import.*claude" src/

# Update to new import
# from gmail_classifier.auth.gmail_auth import get_claude_api_key
# to
# from gmail_classifier.auth.claude_auth import get_claude_api_key
```

## Resources

- [Single Responsibility Principle](https://en.wikipedia.org/wiki/Single-responsibility_principle)
- [Python Module Organization](https://docs.python.org/3/tutorial/modules.html)
- Related findings: ARCH-1 in detailed review

## Acceptance Criteria

- [ ] `auth/claude_auth.py` created with all Claude functions
- [ ] `setup_claude_api_key()` moved and working
- [ ] `get_claude_api_key()` moved and working
- [ ] `validate_claude_api_key()` moved and working
- [ ] `delete_claude_api_key()` added (new utility)
- [ ] `auth/__init__.py` exports both Gmail and Claude functions
- [ ] All imports updated across codebase
- [ ] Claude functions removed from `gmail_auth.py`
- [ ] Unit tests pass for both modules
- [ ] Manual test: Claude authentication workflow works
- [ ] Manual test: Gmail authentication workflow unaffected
- [ ] Documentation updated

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (architecture-strategist agent)
**Actions:**
- Discovered mixed concerns during module analysis
- Identified Single Responsibility Principle violation
- Noted naming confusion (gmail_auth contains Claude code)
- Categorized as P3 medium priority (technical debt)

**Learnings:**
- Separation of concerns critical for maintainability
- Module names should reflect contents
- Authentication modules should be provider-specific
- Clear boundaries make testing easier
