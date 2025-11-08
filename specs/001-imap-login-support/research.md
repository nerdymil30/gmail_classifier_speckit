# Research: IMAP Login Support

**Feature**: 001-imap-login-support
**Date**: 2025-11-07
**Status**: Complete

This document consolidates research findings that inform the technical approach for implementing IMAP authentication support in the Gmail classifier.

---

## Research Item 1: Python IMAP Library Selection

### Decision
**Use `imapclient` (third-party library)** for Gmail IMAP integration

### Rationale
1. **Higher-level abstraction**: Provides Pythonic interface with fully parsed return values using natural Python types
2. **Better error handling**: Uses proper Python exceptions instead of requiring manual response code checking
3. **Production-ready**: Heavily tested against Gmail, Fastmail, Office365, and Yahoo
4. **Gmail-specific features**: Supports Gmail search extensions (X-GM-RAW, gmail_search)
5. **Built on imaplib**: Uses standard library internally, providing stability with better API
6. **Active maintenance**: Currently v3.0.1, supports Python 3.7-3.11+

### Alternatives Considered
- **imaplib (standard library)**: Rejected due to very low-level API requiring extensive manual parsing, poor error handling, and more boilerplate code. Consider only for zero-dependency requirements.
- **aioimaplib**: Rejected as async/await not needed for CLI single-user application

### Best Practices

#### Gmail IMAP Configuration
```python
HOST = 'imap.gmail.com'
PORT = 993  # SSL/TLS required
USE_SSL = True
```

#### Authentication
- Use **App Passwords** (not regular Gmail password) when 2FA enabled
- Store credentials in keyring (never hardcode)
- Consider OAuth2 for production multi-user systems

#### Error Handling Pattern
```python
def connect_with_retry(host, email, password, max_retries=5, initial_delay=3):
    """Connect with exponential backoff retry logic."""
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            server = IMAPClient(host, ssl=True, use_uid=True)
            server.login(email, password)
            return server
        except IMAPClientError as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(delay)
            delay *= 2  # Exponential backoff
```

#### Connection Lifecycle
- Use context managers for automatic cleanup
- Implement reconnection logic for long-running sessions
- Select folder explicitly after connection

### Installation
```bash
pip install imapclient  # Requires user approval per CLAUDE.md policy
```

---

## Research Item 2: IMAP Connection Pooling Strategy

### Decision
**Single persistent connection** (no connection pooling needed)

### Rationale
1. **Single-user CLI**: Connection pooling designed for multi-user web applications with concurrent requests
2. **Gmail connection limits**: 15 max connections per account; single connection avoids conflicts with other clients
3. **IMAP protocol design**: Stateful, long-lived connections are the norm; pooling adds unnecessary complexity
4. **Performance**: Single connection sufficient for batch processing (10-100 emails at a time)

### Alternatives Considered
- **Connection pool**: Rejected; adds complexity without benefits for single-user CLI
- **Connection per operation**: Rejected; high overhead, risks hitting rate limits, inefficient

### Gmail IMAP Limits
- **Max connections**: 15 simultaneous per account
- **Session timeout**: ~30 minutes of inactivity
- **OAuth session**: ~1 hour token validity
- **Bandwidth limit**: 2.5 GB/day download
- **Best practice**: Poll no more frequently than every 10 minutes

### Implementation Guidance

#### Connection Manager Pattern
```python
class GmailIMAPConnection:
    def __init__(self, email, password):
        self.server = None
        self.email = email
        self.password = password
        self.last_noop = time.time()

    def connect(self):
        """Establish connection with retry logic."""
        self.server = IMAPClient('imap.gmail.com', ssl=True, use_uid=True)
        self.server.login(self.email, self.password)

    def keepalive(self):
        """Send NOOP every 10-15 minutes to prevent timeout."""
        if time.time() - self.last_noop > 600:  # 10 minutes
            self.server.noop()
            self.last_noop = time.time()

    def reconnect(self):
        """Handle connection loss with exponential backoff."""
        # Implementation with retry logic
```

#### Key Practices
1. **Keepalive**: Send NOOP command every 10-15 minutes
2. **Auto-reconnect**: Catch connection errors and recreate connection with exponential backoff
3. **Folder switching**: Use SELECT command; no reconnection needed
4. **Batch operations**: Fetch 50-100 emails per batch for optimal performance
5. **Cleanup**: Always close() mailbox and logout() when done

---

## Research Item 3: Gmail IMAP vs API for Label Operations

### Decision
**IMAP-only approach** using X-GM-LABELS extension for label operations

### Rationale
1. **Technical feasibility**: Gmail's X-GM-LABELS IMAP extension provides complete label CRUD operations
2. **Performance**: IMAP is 40x faster than Gmail API for bulk operations (130 vs 3.3 messages/sec)
3. **Authentication clarity**: IMAP credentials (App Password) **cannot** be converted to Gmail API OAuth tokens - completely separate auth mechanisms
4. **User experience**: Simple App Password auth vs complex OAuth consent flow
5. **Consistency**: Single authentication method reduces complexity

### Gmail IMAP Label Support
- Gmail labels map to IMAP folders bidirectionally
- X-GM-LABELS extension allows direct label manipulation
- Supports: nested labels, multiple labels per message, all CRUD operations
- **Requirement**: Labels must have "Show in IMAP" enabled in Gmail settings

### Hybrid Feasibility Analysis
**Conclusion: Not technically feasible for IMAP auth + Gmail API labels**

#### Why Hybrid Doesn't Work:
1. App Passwords authenticate to IMAP server only, not Gmail REST API
2. No mechanism to convert IMAP credentials to OAuth tokens
3. "Hybrid" typically means OAuth + IMAP protocol (not IMAP auth + API operations)
4. If OAuth needed anyway, better to use Gmail API exclusively

### Alternatives Considered
1. **Gmail API only**: Rejected (40x slower, requires OAuth, more complex)
2. **IMAP COPY/MOVE only**: Rejected (less precise than X-GM-LABELS)
3. **Dual authentication** (IMAP + OAuth separately): Rejected (can't convert credentials, adds complexity)
4. **Service accounts**: Rejected (Google Workspace only, overkill for personal Gmail)

### Recommended Implementation

#### X-GM-LABELS IMAP Extension
```python
# Reading labels
response = server.fetch([msg_id], ['X-GM-LABELS'])
labels = response[msg_id][b'X-GM-LABELS']  # Returns list of label names

# Applying labels
server.add_gmail_labels([msg_id], ['Finance', 'Important'])

# Removing labels
server.remove_gmail_labels([msg_id], ['Spam'])

# Setting labels (replaces all)
server.set_gmail_labels([msg_id], ['Work', 'Projects'])
```

#### Label Operations via Folder Mapping
```python
# List all Gmail labels as folders
folders = server.list_folders()
# Returns: [Gmail]/All Mail, [Gmail]/Sent Mail, custom labels

# Select label folder
server.select_folder('Work')

# Copy message to label (applies label)
server.copy([msg_id], 'Finance')

# Handle nested labels
server.select_folder('Projects/Q4-2025')
```

#### Edge Cases to Handle
1. **Labels with spaces**: Encode properly in IMAP folder names
2. **Nested labels**: Use "/" separator (e.g., "Parent/Child")
3. **UTF-7 encoding**: Gmail uses modified UTF-7 for non-ASCII label names
4. **Hidden labels**: System labels like [Gmail]/Trash, [Gmail]/Spam
5. **Label limits**: 5000 labels per account max

### Performance Characteristics
- **Read labels**: ~130 messages/sec via X-GM-LABELS
- **Apply labels**: Batch operations recommended (50-100 at a time)
- **List folders**: Cached, fast operation
- **Label creation**: Via folder creation (IMAP CREATE command)

### Important Timeline Notes (2025)
- **January 2025**: IMAP enabled by default for all Gmail accounts
- **March 2025**: Third-party apps must use OAuth (personal Gmail still supports App Passwords)
- **May 2025**: Google Workspace no longer supports "less secure apps"

---

## Summary of Technical Decisions

| Aspect | Decision | Key Reason |
|--------|----------|------------|
| IMAP Library | imapclient | Better API, Gmail-tested, production-ready |
| Connection Strategy | Single persistent | CLI single-user, no pooling needed |
| Keepalive | NOOP every 10-15 min | Prevent session timeout |
| Label Operations | IMAP X-GM-LABELS | 40x faster, no OAuth needed |
| Authentication | App Passwords | Simple, secure, no OAuth complexity |
| Credential Storage | keyring | OS-level encrypted storage |

---

## Implementation Priorities (Aligned with User Stories)

### P1: IMAP Authentication
- Use imapclient library
- Implement retry logic with exponential backoff
- Error handling for invalid credentials, IMAP disabled, 2FA issues

### P2: Credential Storage
- Use keyring for secure OS-level storage
- Implement optional save credentials flow
- Auto-authentication on subsequent launches

### P3: Email Retrieval
- Single persistent connection with keepalive
- Batch retrieval (10 emails at a time per spec)
- Folder selection support (INBOX, Sent, Archive)
- Integration with existing classification logic (authentication-agnostic)

### Label Operations (Future Enhancement)
- Use X-GM-LABELS extension for reading/writing labels
- Maintain compatibility with existing OAuth-based label ops
- Support both IMAP and Gmail API label sources

---

## Dependencies to Add

```toml
# Add to pyproject.toml dependencies
dependencies = [
    "imapclient>=3.0.0",  # IMAP client library
    # ... existing dependencies
]
```

**Note**: Requires user approval before installation per CLAUDE.md policy.

---

## Sources Referenced

1. IMAPClient Documentation: https://imapclient.readthedocs.io/
2. Gmail IMAP Documentation: https://developers.google.com/workspace/gmail/imap/imap-smtp
3. Python imaplib: https://docs.python.org/3/library/imaplib.html
4. Gmail X-GM-LABELS: https://developers.google.com/gmail/imap/imap-extensions
5. Gmail Security Updates 2025: https://support.google.com/accounts/answer/6010255
