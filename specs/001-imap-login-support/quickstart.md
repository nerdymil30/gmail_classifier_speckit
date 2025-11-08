# Quickstart: IMAP Login Support

**Feature**: 001-imap-login-support
**Date**: 2025-11-07

This guide helps developers get started with implementing and testing IMAP authentication support for the Gmail classifier.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Gmail Setup](#gmail-setup)
3. [Development Environment](#development-environment)
4. [Project Structure](#project-structure)
5. [Implementation Order](#implementation-order)
6. [Testing Strategy](#testing-strategy)
7. [Usage Examples](#usage-examples)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- Python 3.11+ installed
- `.finance` virtual environment set up
- macOS, Linux, or Windows with credential manager support

### Gmail Account Requirements
- Gmail account with IMAP enabled
- 2FA enabled (recommended)
- App-specific password generated (if 2FA enabled)

### Development Tools
- `uv` for dependency management
- `pytest` for testing
- `ruff` for linting
- `mypy` for type checking

---

## Gmail Setup

### Step 1: Enable IMAP

1. Go to Gmail Settings → **See all settings**
2. Navigate to **Forwarding and POP/IMAP** tab
3. Under **IMAP access**, select **Enable IMAP**
4. Click **Save Changes**

### Step 2: Generate App Password (if 2FA enabled)

1. Go to [Google Account](https://myaccount.google.com/)
2. Navigate to **Security** → **Signing in to Google**
3. Select **App passwords**
4. Create new app password:
   - **App**: Mail
   - **Device**: Other (custom name) → "Gmail Classifier"
5. Copy the 16-character app password (format: `xxxx-xxxx-xxxx-xxxx`)
6. **Store securely** - you won't see it again!

### Step 3: Verify IMAP Settings

| Setting | Value |
|---------|-------|
| **IMAP Server** | imap.gmail.com |
| **Port** | 993 |
| **Security** | SSL/TLS |
| **Username** | Your full Gmail address |
| **Password** | App password (or Gmail password if no 2FA) |

---

## Development Environment

### Activate Virtual Environment

```bash
# Activate the .finance virtual environment
source ~/Dropbox/1-projects/Coding/.finance/bin/activate

# Verify Python version
python --version  # Should be 3.11+
```

### Install Dependencies

```bash
# Sync dependencies using uv
uv sync --all-extras --dev

# Install IMAP client library (requires user approval per CLAUDE.md)
# ASK USER: "Do you want me to install imapclient>=3.0.0?"
pip list | grep -i imapclient  # Check if already installed
# If approved:
pip install imapclient>=3.0.0
```

### Verify Installation

```bash
# Test import
python -c "from imapclient import IMAPClient; print('IMAPClient available')"

# Test keyring
python -c "import keyring; print('Keyring available')"
```

---

## Project Structure

### New Files (To Be Created)

```
src/gmail_classifier/
├── auth/
│   ├── __init__.py
│   ├── oauth.py         # Existing OAuth2 auth
│   └── imap.py          # NEW: IMAP authentication (P1)
├── storage/
│   ├── __init__.py
│   ├── session.py       # Existing session state
│   └── credentials.py   # NEW: Credential storage (P2)
└── email/
    ├── __init__.py
    ├── classifier.py    # Existing (unchanged)
    └── fetcher.py       # MODIFIED: Add IMAP email retrieval (P3)

tests/
├── contract/
│   ├── __init__.py
│   └── test_imap_connection.py  # NEW: IMAP protocol tests
├── integration/
│   ├── __init__.py
│   └── test_imap_auth_flow.py   # NEW: End-to-end auth tests
└── unit/
    ├── __init__.py
    ├── test_imap_credentials.py  # NEW: Credential storage tests
    └── test_imap_session.py      # NEW: Session management tests
```

### Files to Modify

```
src/gmail_classifier/cli/main.py  # Add IMAP login commands
pyproject.toml                     # Add imapclient dependency
```

---

## Implementation Order

Follow this sequence to build IMAP support incrementally:

### Phase 1: Core Authentication (P1)

**Files**: `src/gmail_classifier/auth/imap.py`

#### Tasks:
1. ✅ Implement `IMAPAuthInterface` contract
2. ✅ Create `IMAPAuthenticator` class with:
   - `authenticate(email, password)` method
   - Retry logic with exponential backoff (max 5 attempts)
   - Error handling for common failures
3. ✅ Implement session state management
4. ✅ Add keepalive mechanism (NOOP every 10-15 min)

#### Contract Tests First (TDD):
```bash
# Write tests/contract/test_imap_connection.py FIRST
pytest tests/contract/test_imap_connection.py -v

# Tests should FAIL (red phase)
# Then implement auth/imap.py to pass tests (green phase)
```

### Phase 2: Credential Storage (P2)

**Files**: `src/gmail_classifier/storage/credentials.py`

#### Tasks:
1. ✅ Implement `CredentialStorageInterface` contract
2. ✅ Create `CredentialStorage` class with:
   - `store_credentials()` using keyring
   - `retrieve_credentials()` from keyring
   - `delete_credentials()` for logout
3. ✅ Add credential validation (email format, password length)

#### Contract Tests First (TDD):
```bash
# Write tests/unit/test_imap_credentials.py FIRST
pytest tests/unit/test_imap_credentials.py -v

# Tests should FAIL → Implement → Tests PASS
```

### Phase 3: Email Retrieval (P3)

**Files**: `src/gmail_classifier/email/fetcher.py` (modify existing)

#### Tasks:
1. ✅ Implement `FolderInterface` contract
2. ✅ Add IMAP-based email fetching:
   - `list_folders()` - Get Gmail labels as IMAP folders
   - `select_folder()` - Switch to folder (INBOX, Work, etc.)
   - `fetch_emails()` - Retrieve emails from selected folder
3. ✅ Integrate with existing classification pipeline

#### Integration Tests First (TDD):
```bash
# Write tests/integration/test_imap_auth_flow.py FIRST
pytest tests/integration/test_imap_auth_flow.py -v

# Tests should FAIL → Implement → Tests PASS
```

### Phase 4: CLI Integration

**Files**: `src/gmail_classifier/cli/main.py`

#### Tasks:
1. ✅ Add IMAP login command: `gmail-classifier login --imap`
2. ✅ Add logout command: `gmail-classifier logout`
3. ✅ Add credential check: `gmail-classifier auth-status`
4. ✅ Update help documentation

---

## Testing Strategy

### Test-First Development (TDD)

**IMPORTANT**: Follow the Test-First principle from constitution:

1. **Write tests FIRST** based on contracts
2. **Run tests** - they should FAIL (red phase)
3. **Seek user approval** of test design and results
4. **Implement feature** to pass tests (green phase)
5. **Refactor** as needed

### Test Categories

#### 1. Contract Tests (`tests/contract/`)
**Purpose**: Verify IMAP protocol integration

**Example**: `test_imap_connection.py`
```python
def test_imap_connection_contract():
    """Verify IMAP connection follows RFC 3501 protocol."""
    client = IMAPClient('imap.gmail.com', ssl=True)
    # Test successful connection, authentication, folder selection
```

**Ownership**: Agent writes, MUST get user approval after execution

#### 2. Integration Tests (`tests/integration/`)
**Purpose**: End-to-end user journeys

**Example**: `test_imap_auth_flow.py`
```python
def test_complete_imap_auth_flow():
    """Test full flow: authenticate → select folder → fetch emails."""
    # Given: Valid credentials
    # When: Complete auth flow
    # Then: Can retrieve emails
```

**Ownership**: Agent writes, MUST get user approval after execution

#### 3. Unit Tests (`tests/unit/`)
**Purpose**: Test individual components

**Example**: `test_imap_credentials.py`
```python
def test_credential_storage():
    """Test keyring credential storage and retrieval."""
    storage = CredentialStorage()
    # Test store, retrieve, delete operations
```

**Ownership**: Agent MAY write/modify without explicit approval

### Running Tests

```bash
# Run all tests
uv run pytest -v

# Run specific test category
uv run pytest tests/contract/ -v
uv run pytest tests/integration/ -v
uv run pytest tests/unit/ -v

# Run with coverage
uv run pytest --cov=src/gmail_classifier --cov-report=html
```

### Quality Gates (Before Commit)

```bash
# 1. Format code
uv run ruff format .

# 2. Lint code
uv run ruff check .

# 3. Type check
uv run mypy src

# 4. Run tests
uv run pytest -q

# All must pass before committing!
```

---

## Usage Examples

### Example 1: First-Time IMAP Login

```python
from gmail_classifier.auth.imap import IMAPAuthenticator
from gmail_classifier.storage.credentials import CredentialStorage

# Initialize authenticator
auth = IMAPAuthenticator()

# Authenticate
email = "user@gmail.com"
password = "xxxx-xxxx-xxxx-xxxx"  # App password

try:
    session = auth.authenticate(email, password)
    print(f"Connected! Session ID: {session.session_id}")

    # Prompt user to save credentials
    save = input("Save credentials? (y/n): ")
    if save.lower() == 'y':
        storage = CredentialStorage()
        storage.store_credentials(email, password)
        print("Credentials saved securely")

except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except ConnectionError as e:
    print(f"Connection failed: {e}")
finally:
    auth.disconnect(session.session_id)
```

### Example 2: Subsequent Login with Saved Credentials

```python
from gmail_classifier.auth.imap import IMAPAuthenticator
from gmail_classifier.storage.credentials import CredentialStorage

email = "user@gmail.com"

# Check for saved credentials
storage = CredentialStorage()
if storage.has_credentials(email):
    # Retrieve credentials
    creds = storage.retrieve_credentials(email)

    # Auto-authenticate
    auth = IMAPAuthenticator()
    session = auth.authenticate(creds.email, creds.password)
    print(f"Auto-authenticated as {session.email}")

    # Use session...
    auth.disconnect(session.session_id)
else:
    print("No saved credentials found. Please login first.")
```

### Example 3: Email Retrieval via IMAP

```python
from gmail_classifier.auth.imap import IMAPAuthenticator
from gmail_classifier.email.fetcher import FolderManager

# Authenticate
auth = IMAPAuthenticator()
session = auth.authenticate("user@gmail.com", "app-password")

# List folders
folder_mgr = FolderManager()
folders = folder_mgr.list_folders(session.session_id)
print("Available folders:")
for folder in folders:
    print(f"  - {folder['name']} ({folder['message_count']} messages)")

# Select INBOX
inbox = folder_mgr.select_folder(session.session_id, "INBOX")
print(f"INBOX: {inbox['unread_count']} unread messages")

# Fetch recent emails (batch of 10)
# TODO: Implement in fetcher.py
# emails = folder_mgr.fetch_emails(session.session_id, limit=10)

# Cleanup
auth.disconnect(session.session_id)
```

### Example 4: CLI Usage (After Implementation)

```bash
# First-time login with IMAP
gmail-classifier login --imap
# Prompts for email and app password
# Offers to save credentials

# Check authentication status
gmail-classifier auth-status
# Shows: Method: IMAP, Email: user@gmail.com, Status: Connected

# Classify emails using IMAP session
gmail-classifier classify --method imap --batch 10

# Logout (clears saved credentials)
gmail-classifier logout
```

---

## Troubleshooting

### Issue 1: "Authentication Failed" Error

**Symptoms**: `AuthenticationError: Invalid credentials`

**Common Causes:**
1. Using regular Gmail password instead of app password (when 2FA enabled)
2. App password not copied correctly (has spaces/dashes)
3. IMAP not enabled in Gmail settings
4. Account locked due to suspicious activity

**Solutions:**
```bash
# Verify IMAP enabled
# Go to Gmail Settings → Forwarding and POP/IMAP → Enable IMAP

# Regenerate app password
# Google Account → Security → App passwords → Create new

# Test credentials manually
python -c "
from imapclient import IMAPClient
server = IMAPClient('imap.gmail.com', ssl=True)
server.login('your-email@gmail.com', 'your-app-password')
print('Success!')
"
```

### Issue 2: "Connection Timeout" Error

**Symptoms**: `ConnectionError: Connection to imap.gmail.com:993 timed out`

**Common Causes:**
1. Firewall blocking port 993
2. Network connectivity issues
3. Gmail IMAP server temporarily down

**Solutions:**
```bash
# Test network connectivity
telnet imap.gmail.com 993

# Check firewall rules
# (macOS) System Settings → Network → Firewall
# Allow outgoing connections on port 993

# Verify DNS resolution
nslookup imap.gmail.com
```

### Issue 3: "Session Timeout" During Long Operations

**Symptoms**: Connection drops after ~30 minutes of inactivity

**Solution**: Keepalive mechanism should prevent this
```python
# Ensure keepalive is working
auth.keepalive(session.session_id)

# Check last_activity timestamp
info = auth.get_session_info(session.session_id)
print(f"Last activity: {info.last_activity}")
```

### Issue 4: Keyring Storage Fails

**Symptoms**: `keyring.errors.KeyringError: No recommended keyring backend found`

**Platform-Specific Solutions:**

**macOS**:
```bash
# Keychain should work by default
# Verify Keychain Access app is functional
open -a "Keychain Access"
```

**Linux**:
```bash
# Install Secret Service backend
sudo apt-get install gnome-keyring  # Ubuntu/Debian
# or
sudo dnf install gnome-keyring      # Fedora
```

**Windows**:
```bash
# Windows Credential Manager should work by default
# No additional setup needed
```

### Issue 5: "Label Not Found" When Selecting Folder

**Symptoms**: `FolderNotFoundError: Folder 'Work' not found`

**Common Causes:**
1. Label doesn't have "Show in IMAP" enabled
2. Typo in folder name (case-sensitive)
3. Nested label syntax incorrect

**Solutions:**
```python
# List all folders to see exact names
folders = folder_mgr.list_folders(session.session_id)
for folder in folders:
    print(f"'{folder['name']}'")  # Copy exact name

# Enable "Show in IMAP" for label
# Gmail Settings → Labels → [Your Label] → Show in IMAP

# Use correct nested label syntax
# Gmail: "Projects/Q4" → IMAP: "Projects/Q4" (not "Projects\\Q4")
```

---

## Next Steps

### After Implementation
1. ✅ Run full test suite: `uv run pytest -v`
2. ✅ Verify quality gates pass: `ruff`, `mypy`, `pytest`
3. ✅ Test with real Gmail account (use test account!)
4. ✅ Update main README with IMAP authentication docs
5. ✅ Create GitHub issue for GUI support (future enhancement)

### Future Enhancements (Out of Scope for P1-P3)
- GUI for IMAP login (mentioned in spec)
- SMTP support for sending emails
- Multi-account IMAP support
- Non-Gmail IMAP servers (Exchange, iCloud, etc.)
- IMAP IDLE for real-time notifications

---

## Related Documentation

- [Feature Specification](./spec.md) - User stories and requirements
- [Research](./research.md) - Technical decisions and rationale
- [Data Model](./data-model.md) - Entity definitions
- [Contracts](./contracts/) - Interface definitions
- [Constitution](../../.specify/memory/constitution.md) - Development principles

---

## Support

### Getting Help
- Check [Troubleshooting](#troubleshooting) section
- Review Gmail IMAP documentation: https://support.google.com/mail/answer/7126229
- Test with IMAPClient directly: https://imapclient.readthedocs.io/

### Reporting Issues
- Check error logs for specific failure details
- Include Python version, OS, and Gmail account type (personal/Workspace)
- Sanitize credentials before sharing error messages!

---

**Version**: 1.0.0 | **Last Updated**: 2025-11-07
