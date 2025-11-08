# IMAP Authentication Contracts

**Feature**: 001-imap-login-support
**Date**: 2025-11-07

This directory contains interface contracts for IMAP authentication support in the Gmail classifier.

## Purpose

These contracts define the expected interfaces and behaviors for IMAP authentication implementations. They serve as:

1. **Design Specification**: Clear definition of required operations and data structures
2. **Contract Tests**: Basis for writing contract tests that verify implementations
3. **Documentation**: Reference for developers implementing or extending IMAP features
4. **Type Safety**: Type hints and abstract base classes for static analysis

## Files

### `imap_auth_interface.py`

Defines three primary interfaces:

#### 1. **IMAPAuthInterface**
Core authentication and session management interface.

**Key Methods:**
- `authenticate(email, password)`: Authenticate with Gmail IMAP
- `disconnect(session_id)`: Close session and cleanup
- `reconnect(session_id)`: Reestablish connection after loss
- `keepalive(session_id)`: Send NOOP to prevent timeout
- `get_session_info(session_id)`: Get session state
- `is_alive(session_id)`: Check if session active

**Implementation Location**: `src/gmail_classifier/auth/imap.py`

#### 2. **CredentialStorageInterface**
Secure credential storage using OS credential manager.

**Key Methods:**
- `store_credentials(email, password)`: Save to keyring
- `retrieve_credentials(email)`: Load from keyring
- `delete_credentials(email)`: Remove from keyring
- `has_credentials(email)`: Check if credentials exist

**Implementation Location**: `src/gmail_classifier/storage/credentials.py`

#### 3. **FolderInterface**
IMAP folder (Gmail label) operations.

**Key Methods:**
- `list_folders(session_id)`: Get all folders/labels
- `select_folder(session_id, folder_name)`: Select folder for operations
- `get_folder_status(session_id, folder_name)`: Get folder metadata

**Implementation Location**: `src/gmail_classifier/email/fetcher.py` (folder operations)

## Data Structures

### IMAPCredentials
```python
@dataclass
class IMAPCredentials:
    email: str
    password: str  # App-specific password
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
```

### IMAPSessionInfo
```python
@dataclass
class IMAPSessionInfo:
    session_id: UUID
    email: str
    selected_folder: Optional[str]
    connected_at: datetime
    last_activity: datetime
    state: SessionState
    retry_count: int
```

### SessionState (Enum)
```python
class SessionState(Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
```

## Error Handling

### Exception Hierarchy
```
Exception
├── AuthenticationError     # Invalid credentials, auth failure
├── ConnectionError         # Cannot connect to IMAP server
└── SessionError           # Session-related errors (timeout, invalid state)
```

All interface methods document which exceptions they may raise. Implementations MUST raise these specific exceptions for proper error handling.

## Usage Examples

### Example 1: Basic Authentication
```python
from contracts.imap_auth_interface import IMAPAuthInterface

auth: IMAPAuthInterface = IMAPAuthenticator()

try:
    session = auth.authenticate("user@gmail.com", "app-password")
    print(f"Connected: {session.state}")
finally:
    auth.disconnect(session.session_id)
```

### Example 2: Credential Storage
```python
from contracts.imap_auth_interface import CredentialStorageInterface

storage: CredentialStorageInterface = CredentialStorage()

# Store
storage.store_credentials("user@gmail.com", "app-password")

# Retrieve and use
if storage.has_credentials("user@gmail.com"):
    creds = storage.retrieve_credentials("user@gmail.com")
    session = auth.authenticate(creds.email, creds.password)
```

### Example 3: Folder Operations
```python
from contracts.imap_auth_interface import FolderInterface

folders: FolderInterface = FolderManager()

# List folders
all_folders = folders.list_folders(session.session_id)
for folder in all_folders:
    print(f"{folder['name']}: {folder['message_count']} messages")

# Select folder
inbox = folders.select_folder(session.session_id, "INBOX")
print(f"INBOX: {inbox['unread_count']} unread")
```

## Contract Testing

When implementing these interfaces, create contract tests that verify:

1. **Happy Path**: Normal operations succeed as expected
2. **Error Handling**: Appropriate exceptions raised for error conditions
3. **State Transitions**: Session states change correctly (CONNECTING → CONNECTED → DISCONNECTED)
4. **Idempotency**: Operations like disconnect can be called multiple times safely
5. **Resource Cleanup**: Connections are properly closed, no resource leaks

### Example Contract Test Structure
```python
import pytest
from contracts.imap_auth_interface import IMAPAuthInterface, SessionState

def test_authentication_contract(auth_implementation: IMAPAuthInterface):
    """Verify implementation adheres to authentication contract."""

    # Setup
    email = "test@gmail.com"
    password = "test-password"

    # Test: Successful authentication
    session = auth_implementation.authenticate(email, password)
    assert session.state == SessionState.CONNECTED
    assert session.email == email
    assert session.retry_count == 0

    # Test: Session is alive
    assert auth_implementation.is_alive(session.session_id)

    # Test: Keepalive doesn't error
    auth_implementation.keepalive(session.session_id)

    # Test: Disconnect succeeds
    auth_implementation.disconnect(session.session_id)
    assert not auth_implementation.is_alive(session.session_id)

    # Test: Invalid credentials raise AuthenticationError
    with pytest.raises(AuthenticationError):
        auth_implementation.authenticate(email, "wrong-password")
```

## Implementation Guidelines

### 1. Type Hints
All implementations MUST use type hints matching the interface definitions.

### 2. Docstrings
Implement methods SHOULD include docstrings with:
- Brief description
- Args documentation
- Returns documentation
- Raises documentation
- Example usage

### 3. Logging
Implementations SHOULD include structured logging:
- INFO: Successful operations (connect, disconnect, select folder)
- WARNING: Recoverable errors (retry attempts)
- ERROR: Unrecoverable errors (auth failure, max retries exceeded)

### 4. Security
- Never log passwords in plain text
- Sanitize credentials from error messages
- Use secure string comparison for password validation
- Clear sensitive data from memory after use

### 5. Testing
- Unit tests for each interface method
- Contract tests verifying interface adherence
- Integration tests for end-to-end workflows

## Dependencies

Implementations will require:

```toml
dependencies = [
    "imapclient>=3.0.0",  # IMAP client library
    "keyring>=24.0.0",    # Credential storage (existing)
]
```

## Related Documentation

- [Feature Specification](../spec.md) - User stories and requirements
- [Data Model](../data-model.md) - Entity definitions and relationships
- [Research](../research.md) - Technical decisions and rationale
- [Quickstart](../quickstart.md) - Developer setup and usage guide

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-07 | Initial contract definitions for P1 (IMAP auth), P2 (credential storage), P3 (folder operations) |

---

**Note**: These contracts are design artifacts generated during Phase 1 of the `/speckit.plan` workflow. They inform implementation but are not executable code until implemented in `src/`.
