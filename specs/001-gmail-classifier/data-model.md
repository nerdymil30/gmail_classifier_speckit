# Data Model: Gmail Classifier & Organizer

**Feature**: Gmail Classifier & Organizer
**Created**: 2025-11-05
**Purpose**: Define entities and their relationships for email classification system

## Core Entities

### 1. Email

Represents a Gmail message retrieved via API.

**Fields**:
- `id` (string, required): Gmail message ID (unique identifier from API)
- `thread_id` (string, required): Gmail thread ID (for grouping conversations)
- `subject` (string, optional): Email subject line
- `sender` (string, required): Email address of sender (from "From" header)
- `sender_name` (string, optional): Display name of sender
- `recipients` (list[string], required): Email addresses of recipients (To, Cc)
- `date` (datetime, required): Email sent date/time
- `snippet` (string, optional): Gmail API snippet (preview text, ~200 chars)
- `body_plain` (string, optional): Plain text body content
- `body_html` (string, optional): HTML body content
- `labels` (list[string], required): Current Gmail label IDs applied to email
- `has_attachments` (boolean, required): Whether email has attachments
- `is_unread` (boolean, required): Read/unread status

**Relationships**:
- Has zero or more `Label` associations (many-to-many)
- Generates one or more `ClassificationSuggestion` entries
- May be included in a `SummaryBrief` group

**Validation Rules**:
- `id` must be non-empty string
- `sender` must be valid email format
- `date` must be valid ISO 8601 datetime
- `labels` list can be empty (indicates unlabeled email)

**Privacy Constraints**:
- Do NOT persist `body_plain` or `body_html` beyond classification session
- Sanitize PII from logs (only log email IDs and metadata, not content)

---

### 2. Label

Represents a Gmail label (user-created category).

**Fields**:
- `id` (string, required): Gmail label ID (from API)
- `name` (string, required): Label display name (e.g., "Finance", "Personal")
- `email_count` (integer, required): Number of emails currently with this label
- `type` (string, required): Label type - "user" (user-created) or "system" (Gmail built-in like INBOX)

**Relationships**:
- Associated with multiple `Email` entities (many-to-many)
- Referenced by `ClassificationSuggestion` as suggested label

**Validation Rules**:
- `name` must be non-empty string
- `email_count` must be >= 0
- `type` must be one of: "user", "system"
- Only `type="user"` labels are used for classification

**Pattern Analysis**:
- System provides complete label list to Claude API for each classification request
- Claude API uses semantic understanding to match email content to appropriate labels
- No local embeddings or pattern storage needed

---

### 3. ClassificationSuggestion

Represents a proposed label assignment for an unlabeled email.

**Fields**:
- `email_id` (string, required): Reference to `Email.id`
- `suggested_labels` (list[SuggestedLabel], required): Ordered list of label suggestions with scores
- `confidence_category` (string, required): Overall confidence - "high" (>0.7), "medium" (0.5-0.7), "low" (0.3-0.5), "no_match" (<0.3)
- `reasoning` (string, optional): Human-readable explanation of classification (e.g., "Similar to 3 emails in Finance label")
- `created_at` (datetime, required): When suggestion was generated
- `status` (string, required): "pending", "approved", "rejected", "applied"

**Nested Type: SuggestedLabel**:
- `label_id` (string, required): Reference to `Label.id`
- `label_name` (string, required): Label display name (denormalized for convenience)
- `confidence_score` (float, required): Similarity score 0.0-1.0
- `rank` (integer, required): 1-based ranking (1 = best match)

**Relationships**:
- Belongs to one `Email`
- References one or more `Label` entities
- Part of a `ProcessingSession`

**Validation Rules**:
- `suggested_labels` list can be empty only if `confidence_category="no_match"`
- `confidence_score` must be between 0.0 and 1.0
- `rank` must be unique within `suggested_labels` list
- `status` must be one of: "pending", "approved", "rejected", "applied"

**State Transitions**:
1. Created as "pending"
2. User reviews → "approved" or "rejected"
3. If "approved" → attempt to apply label → "applied" (success) or back to "approved" (API failure, can retry)

---

### 4. SummaryBrief

Represents a consolidated report of emails that don't match existing labels.

**Fields**:
- `id` (string, required): Unique ID for this brief
- `group_type` (string, required): Grouping strategy - "sender", "topic", "domain"
- `group_key` (string, required): The grouping value (e.g., sender email, detected topic keyword, domain name)
- `email_ids` (list[string], required): List of `Email.id` values in this group
- `email_count` (integer, required): Number of emails in group
- `earliest_date` (datetime, required): Date of oldest email in group
- `latest_date` (datetime, required): Date of newest email in group
- `summary` (string, required): 2-3 sentence summary of email group content
- `suggested_action` (string, required): Recommended action - "create_new_label", "assign_to_existing", "delete_all", "archive", "manual_review"
- `created_at` (datetime, required): When brief was generated

**Relationships**:
- References multiple `Email` entities
- Part of a `ProcessingSession`

**Validation Rules**:
- `email_count` must equal length of `email_ids` list
- `earliest_date` must be <= `latest_date`
- `group_type` must be one of: "sender", "topic", "domain"
- `suggested_action` must be one of listed values

**Aggregation Logic**:
- **Sender grouping**: All emails from same sender address
- **Topic grouping**: Emails with similar semantic content (using embeddings)
- **Domain grouping**: All emails from same domain (@company.com)

---

### 5. ProcessingSession

Represents a single classification run with resume capability.

**Fields**:
- `id` (string, required): Unique session ID (UUID)
- `user_email` (string, required): Gmail account being processed
- `start_time` (datetime, required): Session start timestamp
- `end_time` (datetime, optional): Session completion timestamp (null if in progress)
- `status` (string, required): "in_progress", "paused", "completed", "failed"
- `total_emails_to_process` (integer, required): Total unlabeled emails found
- `emails_processed` (integer, required): Number of emails classified so far
- `suggestions_generated` (integer, required): Number of suggestions created
- `suggestions_applied` (integer, required): Number of labels successfully applied
- `last_processed_email_id` (string, optional): Last email ID processed (for resume)
- `error_log` (list[string], optional): List of error messages encountered
- `config` (dict, optional): Session configuration (e.g., batch size, dry-run mode)

**Relationships**:
- Contains multiple `ClassificationSuggestion` entities
- Contains multiple `SummaryBrief` entities

**Validation Rules**:
- `emails_processed` must be <= `total_emails_to_process`
- `suggestions_applied` must be <= `suggestions_generated`
- `status` must be one of: "in_progress", "paused", "completed", "failed"
- `end_time` must be >= `start_time` (if set)

**State Transitions**:
1. Created as "in_progress" when session starts
2. → "paused" if user interrupts or quota exceeded
3. → "completed" when all emails processed
4. → "failed" if unrecoverable error occurs
5. Can resume from "paused" back to "in_progress"

**Resume Capability**:
- Persist to SQLite after each batch (e.g., every 50 emails)
- On resume, read `last_processed_email_id` and continue from next email
- Validate that email list hasn't changed significantly (warn user if so)

---

## Entity Relationships Diagram

```
┌─────────────────┐      has labels      ┌──────────────┐
│     Email       │◄────────────────────►│    Label     │
└────────┬────────┘                      └──────┬───────┘
         │                                      │
         │ generates                  referenced by
         │                                      │
         ▼                                      │
┌─────────────────────────┐                    │
│ ClassificationSuggestion│◄───────────────────┘
└───────────┬─────────────┘
            │
            │ part of
            │
            ▼
┌─────────────────────┐
│ ProcessingSession   │
└──────────┬──────────┘
           │ contains
           │
           ▼
┌─────────────────┐      groups
│  SummaryBrief   │◄─────────── Email (no match)
└─────────────────┘
```

---

## Storage Considerations

### Transient Data (In-Memory Only)
- Email body content (`body_plain`, `body_html`)
- Claude API request/response objects
- Classification prompts and responses

### Persistent Data (SQLite)
- `ProcessingSession` (for resume capability)
- `ClassificationSuggestion` with status (for review/approval)
- Processing logs (email IDs, timestamps, actions)

### Never Persist
- Raw email content beyond session lifetime
- OAuth2 access tokens (only refresh tokens in system keyring)
- PII in logs (sanitize before logging)

---

## Privacy & Security Notes

1. **Minimal Data Retention**: Only persist email IDs and metadata, never raw content
2. **Secure Credentials**: OAuth2 refresh tokens and Claude API key stored in system keyring (not files)
3. **Log Sanitization**: Logs contain email IDs and aggregate stats only, no email content
4. **Cloud Processing**: Email content sent to Anthropic Claude API for classification (requires user consent)
5. **User Consent**: Explicit consent required before first use acknowledging cloud processing
6. **Session Cleanup**: Provide command to purge old sessions and suggestion data
7. **API Key Protection**: Claude API key never logged or included in error messages

---

## Example Data

### Email
```json
{
  "id": "18c2a3b4f5e6d7c8",
  "thread_id": "18c2a3b4f5e6d7c8",
  "subject": "Your monthly bank statement is ready",
  "sender": "statements@bank.com",
  "sender_name": "First National Bank",
  "recipients": ["user@example.com"],
  "date": "2025-11-01T09:30:00Z",
  "snippet": "Your statement for October is now available...",
  "labels": [],
  "has_attachments": true,
  "is_unread": true
}
```

### ClassificationSuggestion
```json
{
  "email_id": "18c2a3b4f5e6d7c8",
  "suggested_labels": [
    {
      "label_id": "Label_1234",
      "label_name": "Finance",
      "confidence_score": 0.87,
      "rank": 1
    },
    {
      "label_id": "Label_5678",
      "label_name": "Banking",
      "confidence_score": 0.72,
      "rank": 2
    }
  ],
  "confidence_category": "high",
  "reasoning": "Similar to 12 emails in Finance label (bank statements, invoices)",
  "created_at": "2025-11-05T10:00:00Z",
  "status": "pending"
}
```

### SummaryBrief
```json
{
  "id": "brief_001",
  "group_type": "sender",
  "group_key": "newsletters@company.com",
  "email_ids": ["18c2...", "29d3...", "3ae4..."],
  "email_count": 3,
  "earliest_date": "2025-10-15T08:00:00Z",
  "latest_date": "2025-11-01T08:00:00Z",
  "summary": "Marketing newsletters from Company XYZ about product updates and promotions. All sent bi-weekly.",
  "suggested_action": "create_new_label",
  "created_at": "2025-11-05T10:05:00Z"
}
```
