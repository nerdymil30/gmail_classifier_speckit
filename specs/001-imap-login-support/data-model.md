# Data Model: IMAP Login Support

**Feature**: 001-imap-login-support
**Date**: 2025-11-07

This document defines the data entities, relationships, and state transitions for IMAP authentication support.

---

## Entity: IMAPCredentials

**Description**: Represents user's Gmail IMAP login credentials (email and password/app-specific password) for authentication.

### Fields

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| email | string | Yes | Valid email format, @gmail.com or Google Workspace domain | User's Gmail email address |
| password | string | Yes | Min 16 chars for app passwords | IMAP password or app-specific password |
| created_at | datetime | Yes | Auto-generated | Timestamp when credentials were first stored |
| last_used | datetime | No | Auto-updated on successful auth | Timestamp of last successful authentication |

### Validation Rules

1. **Email format**: Must be valid email address (regex: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)
2. **Password length**: App passwords typically 16 characters; allow 8-64 characters range
3. **Domain validation**: Warn if not @gmail.com or Google Workspace domain
4. **Created timestamp**: Automatically set on first save
5. **Last used**: Updated only on successful authentication (not on retrieval from storage)

### Storage

- **Location**: Operating system credential manager via `keyring` library
- **Service name**: `gmail_classifier_imap`
- **Username key**: User's email address
- **Password value**: Encrypted by OS credential manager
- **Persistence**: Until explicitly deleted by user logout action

### Security Considerations

- Never log password in plain text
- Sanitize password from error messages
- No in-memory persistence beyond active session
- Clear from memory after failed authentication attempts
- Use secure string comparison for password validation

---

## Entity: IMAPSession

**Description**: Represents an active authenticated IMAP connection to Gmail's IMAP server, including connection state and session metadata.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| session_id | UUID | Yes | Unique identifier for this session |
| email | string | Yes | Email address associated with session |
| connection | IMAPClient | Yes | Active imapclient connection object |
| selected_folder | string | No | Currently selected IMAP folder (e.g., "INBOX") |
| connected_at | datetime | Yes | Timestamp when connection established |
| last_activity | datetime | Yes | Last IMAP command timestamp (for keepalive) |
| state | enum | Yes | Session state: CONNECTING, CONNECTED, DISCONNECTED, ERROR |
| retry_count | integer | Yes | Number of reconnection attempts (default: 0) |

### State Transitions

```
CONNECTING → CONNECTED (on successful login)
CONNECTING → ERROR (on auth failure)
CONNECTED → DISCONNECTED (on explicit logout)
CONNECTED → ERROR (on connection loss)
ERROR → CONNECTING (on retry attempt)
DISCONNECTED → CONNECTING (on reconnect request)
```

### State Transition Rules

1. **CONNECTING → CONNECTED**:
   - Trigger: Successful `IMAPClient.login()` call
   - Action: Set `connected_at`, reset `retry_count` to 0
   - Validation: Connection must respond to NOOP command

2. **CONNECTING → ERROR**:
   - Trigger: Auth failure, network error, timeout
   - Action: Increment `retry_count`, log error details
   - Validation: Max 5 retry attempts before giving up

3. **CONNECTED → DISCONNECTED**:
   - Trigger: User logout, application shutdown
   - Action: Call `IMAPClient.logout()`, clear connection
   - Validation: Ensure mailbox closed before logout

4. **CONNECTED → ERROR**:
   - Trigger: Network interruption, IMAP4.abort exception, timeout
   - Action: Mark state as ERROR, attempt auto-reconnect
   - Validation: Check if connection still alive before state change

5. **ERROR → CONNECTING**:
   - Trigger: Retry logic with exponential backoff
   - Action: Wait (initial_delay * 2^retry_count) seconds, attempt reconnect
   - Validation: retry_count < max_retries (5)

### Lifecycle Management

- **Keepalive**: Send NOOP command every 10-15 minutes (managed by `last_activity` check)
- **Timeout**: Detect stale connections via `last_activity` > 25 minutes
- **Auto-reconnect**: On connection loss, auto-retry up to 5 times with exponential backoff
- **Cleanup**: On session end, ensure `close()` and `logout()` called

### Operations

1. **connect()**: Establish new IMAP connection with credentials
2. **disconnect()**: Gracefully close connection and cleanup
3. **keepalive()**: Send NOOP to prevent timeout
4. **reconnect()**: Reestablish connection after interruption
5. **select_folder(folder_name)**: Change active IMAP folder
6. **is_alive()**: Check if connection still valid

---

## Entity: EmailFolder

**Description**: Represents IMAP mailbox folders (Gmail labels) that can be accessed and queried for messages.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| folder_name | string | Yes | IMAP folder name (e.g., "INBOX", "[Gmail]/Sent Mail", "Work") |
| display_name | string | Yes | Human-readable folder name |
| folder_type | enum | Yes | INBOX, SENT, DRAFTS, TRASH, LABEL, SYSTEM |
| message_count | integer | No | Total messages in folder (from SELECT response) |
| unread_count | integer | No | Unread message count (from SELECT response) |
| selectable | boolean | Yes | Whether folder can be selected (default: true) |
| delimiter | string | Yes | IMAP hierarchy delimiter (usually "/") |

### Folder Type Classification

| Type | Examples | Selectable | Description |
|------|----------|------------|-------------|
| INBOX | "INBOX" | Yes | Primary inbox |
| SENT | "[Gmail]/Sent Mail" | Yes | Sent messages |
| DRAFTS | "[Gmail]/Drafts" | Yes | Draft messages |
| TRASH | "[Gmail]/Trash" | Yes | Deleted messages |
| LABEL | "Work", "Finance", "Projects/Q4" | Yes | User-created labels |
| SYSTEM | "[Gmail]" | No | System folder (non-selectable) |

### Gmail Label Mapping

Gmail labels appear as IMAP folders with specific patterns:

```
Gmail Label          →  IMAP Folder Name
─────────────────────────────────────────
(no label)           →  INBOX
Sent                 →  [Gmail]/Sent Mail
Drafts               →  [Gmail]/Drafts
Trash                →  [Gmail]/Trash
All Mail             →  [Gmail]/All Mail
Spam                 →  [Gmail]/Spam
Custom Label "Work"  →  Work
Nested "Projects/Q4" →  Projects/Q4
```

### Validation Rules

1. **Folder name format**: Follow IMAP naming conventions (UTF-7 encoded for non-ASCII)
2. **System folders**: "[Gmail]/*" folders cannot be renamed or deleted
3. **Nested folders**: Use "/" delimiter for hierarchy (e.g., "Projects/Q4")
4. **Name restrictions**: No leading/trailing spaces, avoid special chars (*, %, \)
5. **Selectability**: System folders like "[Gmail]" are non-selectable (NoSelect attribute)

### Operations

1. **list_folders()**: Retrieve all folders from server
2. **select_folder(name)**: Make folder active for message operations
3. **get_folder_status(name)**: Get message counts without selecting
4. **create_folder(name)**: Create new label (if supported)
5. **delete_folder(name)**: Delete custom label (Gmail labels only)

---

## Entity: AuthenticationMethod

**Description**: Represents the chosen authentication approach (OAuth2 or IMAP) for the current session, allowing users to select preferred login method.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| method_type | enum | Yes | OAUTH2, IMAP |
| email | string | Yes | Associated email address |
| is_default | boolean | Yes | Whether this is the default method for this email |
| last_selected | datetime | No | When method was last used |
| config | JSON | No | Method-specific configuration |

### Method Types

#### OAUTH2
- **Description**: Browser-based OAuth2 flow with Google consent screen
- **Requirements**: OAuth2 client credentials, token storage
- **Advantages**: More secure, no app passwords needed, broader API access
- **Disadvantages**: Complex flow, requires browser, tokens expire

#### IMAP
- **Description**: Direct credential-based authentication with email + app password
- **Requirements**: IMAP enabled in Gmail, app password generated
- **Advantages**: Simple, desktop-client-like experience, no browser needed
- **Disadvantages**: Requires app password setup, limited to IMAP operations

### Configuration Schema

#### OAuth2 Config
```json
{
  "token_file": "path/to/token.json",
  "scopes": ["gmail.readonly", "gmail.modify"],
  "client_id": "...",
  "client_secret": "..."
}
```

#### IMAP Config
```json
{
  "server": "imap.gmail.com",
  "port": 993,
  "use_ssl": true,
  "credentials_stored": true
}
```

### Validation Rules

1. **Method selection**: User must explicitly choose method (no automatic selection)
2. **Credentials required**: OAuth2 requires token file, IMAP requires stored credentials
3. **Fallback**: If preferred method fails, prompt user to try alternative
4. **Default method**: Only one method can be default per email address

### State Machine

```
[Initial] → User selects method → Method-specific auth flow
    ↓
[OAUTH2] → OAuth flow → Token acquired → Connected
    ↓
[IMAP] → Credential prompt → IMAP login → Connected
    ↓
[Connected] → Session active → Can switch methods on next login
```

---

## Relationships

### IMAPCredentials ← → IMAPSession (1:N)
- One set of credentials can be used for multiple sessions (across time)
- Each session is associated with exactly one set of credentials
- **Cascade**: Deleting credentials does not delete historical session records

### IMAPSession ← → EmailFolder (1:N)
- One session can access multiple folders
- Each folder access is within the context of a session
- **Lifecycle**: Selected folder is session-specific state

### AuthenticationMethod ← → IMAPCredentials (1:1)
- IMAP authentication method requires IMAPCredentials
- OAuth2 method does not use IMAPCredentials (uses token file)
- **Association**: Method type determines credential storage location

---

## Persistence Strategy

| Entity | Storage | Format | Encryption |
|--------|---------|--------|------------|
| IMAPCredentials | OS Keyring | Key-value | OS-managed |
| IMAPSession | In-memory only | Python object | N/A |
| EmailFolder | Cached in-memory | List/dict | N/A |
| AuthenticationMethod | sqlite3 | Relational | Config JSON only |

### Storage Locations

- **Keyring**: `keyring.get_password("gmail_classifier_imap", email)`
- **SQLite**: `~/.gmail_classifier/session.db` (existing)
- **Cache**: In-memory dictionaries, cleared on disconnect

---

## Data Flow Examples

### Example 1: First-Time IMAP Login

```
1. User provides email + password
2. Validate email format and password length
3. Attempt IMAP connection with credentials
4. On success:
   - Create IMAPSession (state: CONNECTED)
   - Prompt user: "Save credentials?"
   - If yes: Store in keyring as IMAPCredentials
   - List folders → populate EmailFolder entities
   - Mark AuthenticationMethod as IMAP (is_default: true)
5. On failure:
   - IMAPSession state: ERROR
   - Display error (invalid creds, IMAP disabled, 2FA issue)
   - Retry or fallback to OAuth2
```

### Example 2: Subsequent Login with Saved Credentials

```
1. Application starts
2. Check AuthenticationMethod for email → finds IMAP as default
3. Retrieve IMAPCredentials from keyring
4. Create IMAPSession (state: CONNECTING)
5. Attempt login with stored credentials
6. On success:
   - Update IMAPCredentials.last_used
   - IMAPSession state: CONNECTED
   - Auto-select INBOX folder
7. On failure (e.g., password revoked):
   - IMAPSession state: ERROR
   - Prompt user to re-enter credentials or switch to OAuth2
```

### Example 3: Switching Folders During Active Session

```
1. IMAPSession is CONNECTED with folder="INBOX"
2. User requests folder switch to "Work"
3. Validate "Work" exists in EmailFolder cache
4. Call session.select_folder("Work")
5. On success:
   - Update IMAPSession.selected_folder to "Work"
   - Update IMAPSession.last_activity timestamp
   - Retrieve EmailFolder.message_count for "Work"
6. No reconnection needed (folder switch within same session)
```

---

## Integration with Existing Classification System

### Existing Entities (Unchanged)
- **Email**: Existing email entity from classification system
- **Label**: Existing Gmail label entity
- **Classification Suggestion**: Existing entity from classification logic
- **Processing Session**: Existing batch processing entity

### New Relationships
- **IMAPSession** → **Email** retrieval (replaces Gmail API fetch)
- **EmailFolder** → **Label** mapping (IMAP folders map to Gmail labels)
- **AuthenticationMethod** determines retrieval mechanism

### Authentication-Agnostic Design
The existing classification logic remains **unchanged** and authentication-agnostic:
- Emails retrieved via IMAP or Gmail API have same structure
- Labels applied via IMAP X-GM-LABELS or Gmail API have same effect
- Classification engine doesn't know or care about auth method

---

## Summary

This data model supports:
- ✅ IMAP credential storage with OS-level encryption
- ✅ Session lifecycle management with auto-reconnect
- ✅ Gmail folder/label mapping via IMAP
- ✅ Multiple authentication methods (OAuth2 + IMAP)
- ✅ Integration with existing classification system
- ✅ Security best practices (no plain-text credentials, sanitized logs)
