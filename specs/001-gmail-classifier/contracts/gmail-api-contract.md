# Gmail API Contract: Gmail Classifier & Organizer

**Feature**: Gmail Classifier & Organizer
**Created**: 2025-11-05
**Purpose**: Define Gmail API integration contracts and expectations

## Authentication Flow

### OAuth2 Setup

**Endpoint**: Google OAuth2 Authorization Server
**Library**: `google-auth-oauthlib`

**Required Scopes**:
```python
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',  # Read emails and labels
    'https://www.googleapis.com/auth/gmail.modify'     # Modify labels (P3 feature)
]
```

**Flow**:
1. User initiates authentication via CLI command
2. System opens browser to Google OAuth consent screen
3. User authorizes application access
4. System receives authorization code
5. Exchange code for access token + refresh token
6. Store refresh token in system keyring (secure)
7. Access token used for API calls (expires in 1 hour)
8. Refresh token used to obtain new access tokens

**Credential Storage**:
- Refresh token: System keyring (`keyring` library)
- Access token: In-memory only (ephemeral)
- Client ID/Secret: Environment variables or `.env` file

**Error Handling**:
- Invalid/expired credentials → Prompt re-authentication
- User denies consent → Clear error message, exit gracefully
- Network errors during auth → Retry with exponential backoff

---

## API Endpoints

### 1. List User Labels

**Purpose**: Retrieve all Gmail labels for classification reference

**Endpoint**: `GET https://gmail.googleapis.com/gmail/v1/users/{userId}/labels`

**Parameters**:
- `userId`: "me" (authenticated user)

**Request Example**:
```python
service = build('gmail', 'v1', credentials=creds)
results = service.users().labels().list(userId='me').execute()
labels = results.get('labels', [])
```

**Response Structure**:
```json
{
  "labels": [
    {
      "id": "Label_1234",
      "name": "Finance",
      "type": "user",
      "messageListVisibility": "show",
      "labelListVisibility": "labelShow"
    },
    {
      "id": "INBOX",
      "name": "INBOX",
      "type": "system"
    }
  ]
}
```

**Filtering Logic**:
- Only process labels with `type="user"` (exclude Gmail built-ins like INBOX, SENT)
- Skip labels with no emails (`messageListVisibility="hide"`)

**Rate Limits**:
- Quota cost: 1 unit per request
- Limit: 250 units/user/second

**Error Responses**:
- 401 Unauthorized → Re-authenticate
- 403 Forbidden → Check scopes
- 429 Rate Limit → Exponential backoff (start 1s, max 32s)
- 500 Internal Error → Retry up to 3 times

---

### 2. List Unlabeled Emails

**Purpose**: Fetch emails without user-created labels for classification

**Endpoint**: `GET https://gmail.googleapis.com/gmail/v1/users/{userId}/messages`

**Parameters**:
- `userId`: "me"
- `q`: Query string to filter unlabeled emails
- `maxResults`: Batch size (default 100, max 500)
- `pageToken`: For pagination

**Query String Construction**:
```python
# Fetch emails with NO user labels (only system labels allowed)
query = "-label:* has:nouserlabels"

# Optional filters
query += " -in:trash -in:spam"  # Exclude trash/spam
```

**Request Example**:
```python
results = service.users().messages().list(
    userId='me',
    q='-label:* has:nouserlabels -in:trash -in:spam',
    maxResults=100
).execute()
messages = results.get('messages', [])
nextPageToken = results.get('nextPageToken')
```

**Response Structure**:
```json
{
  "messages": [
    {
      "id": "18c2a3b4f5e6d7c8",
      "threadId": "18c2a3b4f5e6d7c8"
    }
  ],
  "nextPageToken": "12345abcde",
  "resultSizeEstimate": 247
}
```

**Pagination**:
- Use `nextPageToken` for subsequent requests
- Continue until `nextPageToken` is null/absent
- Track `resultSizeEstimate` for progress indicators

**Rate Limits**:
- Quota cost: 5 units per request
- Limit: 250 units/user/second (50 requests/second)
- **Processing Rate**: ~20 emails/minute accounting for get + classify

**Error Responses**:
- 400 Bad Request → Invalid query syntax
- 401/403 → Authentication/authorization issue
- 429 Rate Limit → Exponential backoff
- 500 Internal Error → Retry with backoff

---

### 3. Get Email Content

**Purpose**: Retrieve full email details for classification

**Endpoint**: `GET https://gmail.googleapis.com/gmail/v1/users/{userId}/messages/{messageId}`

**Parameters**:
- `userId`: "me"
- `id`: Message ID from list response
- `format`: "full" (include headers and body) or "metadata" (headers only)

**Request Example**:
```python
message = service.users().messages().get(
    userId='me',
    id='18c2a3b4f5e6d7c8',
    format='full'
).execute()
```

**Response Structure**:
```json
{
  "id": "18c2a3b4f5e6d7c8",
  "threadId": "18c2a3b4f5e6d7c8",
  "labelIds": ["INBOX", "UNREAD"],
  "snippet": "Your monthly bank statement...",
  "payload": {
    "headers": [
      {"name": "From", "value": "statements@bank.com"},
      {"name": "To", "value": "user@example.com"},
      {"name": "Subject", "value": "Your monthly statement"},
      {"name": "Date", "value": "Mon, 1 Nov 2025 09:30:00 -0700"}
    ],
    "body": {
      "size": 1234,
      "data": "BASE64_ENCODED_CONTENT"
    }
  },
  "internalDate": "1730476200000"
}
```

**Content Extraction**:
```python
def extract_email_content(message):
    """Extract relevant fields from Gmail API message"""
    headers = {h['name']: h['value'] for h in message['payload']['headers']}

    # Decode body (base64url encoded)
    body_data = message['payload']['body'].get('data', '')
    body_text = base64.urlsafe_b64decode(body_data).decode('utf-8')

    return {
        'id': message['id'],
        'thread_id': message['threadId'],
        'subject': headers.get('Subject', ''),
        'sender': headers.get('From', ''),
        'recipients': headers.get('To', '').split(','),
        'date': headers.get('Date', ''),
        'snippet': message.get('snippet', ''),
        'body': body_text,
        'labels': message.get('labelIds', [])
    }
```

**Rate Limits**:
- Quota cost: 5 units per request
- Limit: 250 units/user/second
- **Batch Optimization**: Use `batchGet` for multiple emails (reduces quota)

**Error Responses**:
- 404 Not Found → Email deleted/moved, skip
- 401/403 → Auth issue
- 429 Rate Limit → Backoff
- 500 Internal Error → Retry

---

### 4. Modify Email Labels (P3 Feature)

**Purpose**: Apply approved label suggestions to emails

**Endpoint**: `POST https://gmail.googleapis.com/gmail/v1/users/{userId}/messages/{messageId}/modify`

**Parameters**:
- `userId`: "me"
- `id`: Message ID
- `addLabelIds`: List of label IDs to add
- `removeLabelIds`: List of label IDs to remove (usually empty for our use case)

**Request Example**:
```python
service.users().messages().modify(
    userId='me',
    id='18c2a3b4f5e6d7c8',
    body={
        'addLabelIds': ['Label_1234', 'Label_5678'],
        'removeLabelIds': []
    }
).execute()
```

**Response Structure**:
```json
{
  "id": "18c2a3b4f5e6d7c8",
  "threadId": "18c2a3b4f5e6d7c8",
  "labelIds": ["INBOX", "Label_1234", "Label_5678"]
}
```

**Batch Modification**:
- Use `batchModify` endpoint for bulk operations (more efficient)
- Max 1000 messages per batch request

**Rate Limits**:
- Quota cost: 5 units per request
- Limit: 250 units/user/second
- **Important**: User approval required before ANY label modifications

**Error Responses**:
- 400 Bad Request → Invalid label ID
- 404 Not Found → Email deleted
- 403 Forbidden → Insufficient permissions (check `gmail.modify` scope)
- 429 Rate Limit → Backoff
- 500 Internal Error → Mark as failed, allow retry

**Failure Handling**:
- Track failures in processing log
- Report to user which emails succeeded/failed
- Provide retry mechanism for failed applications

---

## Rate Limiting Strategy

### Quota Management

**Gmail API Quotas** (per project per day):
- Total quota: 1,000,000,000 units/day (effectively unlimited for single user)
- Per-user-per-second: 250 units/second
- **Critical**: Per-second limit is the bottleneck

**Quota Costs**:
- List labels: 1 unit
- List messages: 5 units
- Get message: 5 units
- Modify message: 5 units

**Processing Rate Calculation**:
```
For classifying 100 emails:
- List unlabeled: 5 units (1 request for 100 emails)
- Get content: 5 × 100 = 500 units (100 individual requests)
- Total: 505 units

At 250 units/sec limit:
- Time: 505 / 250 = ~2 seconds for API calls
- Plus ~3 minutes for classification (ML processing)
- Total: ~3 minutes for 100 emails ✅ Meets <5 min requirement
```

### Exponential Backoff

```python
import time
import random

def exponential_backoff(attempt, max_attempts=5):
    """Calculate backoff delay with jitter"""
    if attempt >= max_attempts:
        raise Exception("Max retry attempts exceeded")

    # Exponential backoff: 1s, 2s, 4s, 8s, 16s
    delay = min(2 ** attempt, 32)

    # Add jitter to prevent thundering herd
    jitter = random.uniform(0, delay * 0.1)

    time.sleep(delay + jitter)
```

**Apply backoff for**:
- 429 Rate Limit Exceeded
- 500/502/503 Server errors
- Network timeouts

---

## Error Handling Matrix

| Error Code | Meaning | Action | Retry? |
|------------|---------|--------|--------|
| 400 | Bad Request | Log error, skip item | No |
| 401 | Unauthorized | Re-authenticate | No (prompt user) |
| 403 | Forbidden | Check scopes/permissions | No (prompt user) |
| 404 | Not Found | Email deleted, skip | No |
| 429 | Rate Limit | Exponential backoff | Yes (5 attempts) |
| 500 | Internal Error | Exponential backoff | Yes (3 attempts) |
| 502/503 | Server Error | Exponential backoff | Yes (3 attempts) |
| Network | Timeout/Connection | Exponential backoff | Yes (3 attempts) |

---

## Testing Strategy

### Mock Responses

**For Contract Tests**:
```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_gmail_service():
    """Mock Gmail API service"""
    service = Mock()

    # Mock labels list
    service.users().labels().list().execute.return_value = {
        'labels': [
            {'id': 'Label_1', 'name': 'Finance', 'type': 'user'},
            {'id': 'Label_2', 'name': 'Personal', 'type': 'user'},
            {'id': 'INBOX', 'name': 'INBOX', 'type': 'system'}
        ]
    }

    # Mock messages list
    service.users().messages().list().execute.return_value = {
        'messages': [
            {'id': 'msg_1', 'threadId': 'thread_1'}
        ],
        'resultSizeEstimate': 1
    }

    # Mock message get
    service.users().messages().get().execute.return_value = {
        'id': 'msg_1',
        'snippet': 'Test email content',
        'payload': {
            'headers': [
                {'name': 'Subject', 'value': 'Test'},
                {'name': 'From', 'value': 'test@example.com'}
            ],
            'body': {'data': 'VGVzdCBib2R5'}  # "Test body" in base64
        }
    }

    return service
```

**Offline Mode**:
- Use mocked service for all tests
- Save sample API responses as JSON fixtures
- Load fixtures instead of making real API calls
- Enables development without Gmail account

---

## Security Considerations

1. **OAuth2 Scopes**: Request minimum necessary scopes
   - Start with `gmail.readonly` for P1/P2
   - Add `gmail.modify` only when implementing P3

2. **Credential Storage**: Never store credentials in code/files
   - Use system keyring for refresh tokens
   - Environment variables for client ID/secret
   - Provide `.env.example` template (not tracked in git)

3. **API Key Protection**:
   - Client secret should be in `.env` (gitignored)
   - Rotate keys if accidentally exposed

4. **Data Privacy**:
   - Never log email content (only IDs and metadata)
   - Don't persist email bodies beyond classification session
   - Clear sensitive data from memory after use

5. **Rate Limiting**:
   - Implement exponential backoff to avoid abuse
   - Monitor quota usage, warn user if approaching limits
   - Graceful degradation if quota exceeded

---

## Example Integration Code

```python
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

class GmailClient:
    def __init__(self, credentials):
        self.service = build('gmail', 'v1', credentials=credentials)

    def get_user_labels(self):
        """Fetch all user-created labels"""
        results = self.service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])

        # Filter to user-created labels only
        return [l for l in labels if l.get('type') == 'user']

    def list_unlabeled_emails(self, max_results=100):
        """Fetch emails without user labels"""
        query = '-label:* has:nouserlabels -in:trash -in:spam'

        results = self.service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()

        return results.get('messages', [])

    def get_email_content(self, message_id):
        """Retrieve full email details"""
        message = self.service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()

        return self._parse_message(message)

    def apply_labels(self, message_id, label_ids):
        """Apply labels to email (P3 feature)"""
        return self.service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'addLabelIds': label_ids}
        ).execute()
```

---

## References

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [OAuth2 for Installed Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [API Quotas & Limits](https://developers.google.com/gmail/api/reference/quota)
- [Error Codes Reference](https://developers.google.com/gmail/api/guides/handle-errors)
