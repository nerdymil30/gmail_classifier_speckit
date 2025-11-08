---
status: pending
priority: p1
issue_id: "018"
tags: [architecture, data-model, integration, imap, critical]
dependencies: []
---

# Email Entity Duplication - Broken Classification Integration

## Problem Statement

Two different `Email` entities exist in the codebase:
1. **OAuth2 Email** (`src/gmail_classifier/models/email.py`) - Used by Gmail API and classification logic
2. **IMAP Email** (`src/gmail_classifier/email/fetcher.py`) - Created by IMAP implementation

These are incompatible, violating Single Source of Truth principle. The classification logic expects the OAuth2 Email structure but will receive IMAP Email objects, causing **immediate integration failure**.

**Impact:** Classification completely broken for IMAP-fetched emails
**Category:** Critical Architecture Flaw

## Findings

**Locations:**
- Existing: `src/gmail_classifier/models/email.py` (OAuth2 Email)
- New: `src/gmail_classifier/email/fetcher.py:102-140` (IMAP Email)

**OAuth2 Email Structure:**
```python
@dataclass
class Email:
    id: str  # Gmail message ID (string)
    thread_id: str
    subject: str
    sender: str
    sender_name: str
    recipients: list[str]
    date: datetime
    snippet: str
    body_plain: str
    body_html: str
    labels: list[str]
    has_attachments: bool
    is_unread: bool

    @classmethod
    def from_gmail_message(cls, message: dict) -> "Email":
        """Create from Gmail API response."""
```

**IMAP Email Structure:**
```python
@dataclass
class Email:
    message_id: int  # IMAP message ID (integer)
    subject: str
    sender: str
    recipients: list[str]
    body: str  # Single body field
    received_date: datetime | None
    labels: list[str]
    flags: tuple  # IMAP-specific
```

**Incompatibilities:**
- Different ID types (string vs int)
- Different field names (`date` vs `received_date`, `body_plain` vs `body`)
- Missing fields (no `thread_id`, `snippet`, `is_unread` in IMAP version)
- IMAP-specific fields (`flags`) not in OAuth2 version

**Integration Failure:**
```python
# Classification expects:
email.body_plain  # AttributeError: 'Email' object has no attribute 'body_plain'
email.thread_id   # AttributeError: 'Email' object has no attribute 'thread_id'
email.is_unread   # AttributeError: 'Email' object has no attribute 'is_unread'
```

## Proposed Solutions

### Option 1: Unified Email Entity with Dual Constructors (RECOMMENDED)

**Pros:**
- Single source of truth
- Backward compatible via class methods
- Both Gmail API and IMAP work with classification
- Clean separation of concerns

**Cons:**
- Some fields optional (Gmail-specific or IMAP-specific)
- Requires refactoring existing code

**Effort:** Medium (3 hours)
**Risk:** Low (isolated to data model)

**Implementation:**
```python
# Consolidate into src/gmail_classifier/models/email.py
@dataclass
class Email:
    """Unified email representation for both Gmail API and IMAP."""

    # Core fields (common to both sources)
    id: str | int  # Gmail API: string, IMAP: int
    subject: str
    sender: str
    recipients: list[str]
    body_plain: str  # Primary body content
    date: datetime
    labels: list[str]

    # Gmail API specific fields (optional)
    thread_id: str | None = None
    sender_name: str | None = None
    snippet: str | None = None
    body_html: str | None = None
    has_attachments: bool = False
    is_unread: bool = False

    # IMAP specific fields (optional)
    flags: tuple | None = None

    @classmethod
    def from_gmail_message(cls, message: dict) -> "Email":
        """Create from Gmail API response."""
        # Existing implementation
        return cls(
            id=message['id'],
            thread_id=message['threadId'],
            subject=...,
            sender=...,
            sender_name=...,
            recipients=...,
            date=...,
            snippet=...,
            body_plain=...,
            body_html=...,
            labels=...,
            has_attachments=...,
            is_unread=...,
            flags=None,  # Not applicable
        )

    @classmethod
    def from_imap_message(cls, msg_id: int, data: dict) -> "Email":
        """Create from IMAP fetch response."""
        # Parse IMAP data
        raw_email = data[b"BODY[]"]
        parser = BytesParser(policy=default)
        msg = parser.parsebytes(raw_email)

        # Extract fields
        subject = msg.get("Subject", "")
        sender = msg.get("From", "")
        to = msg.get("To", "")
        recipients = [addr.strip() for addr in to.split(",") if addr.strip()]

        # Extract body (prefer plain text)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_content()
                    break
        else:
            body = msg.get_content()

        # Get flags and determine if unread
        flags = data.get(b"FLAGS", ())
        is_unread = b'\\Seen' not in flags

        return cls(
            id=msg_id,
            subject=subject,
            sender=sender,
            recipients=recipients,
            body_plain=body,
            date=datetime.now(),  # From INTERNALDATE if available
            labels=[],  # Can extract from X-GM-LABELS if needed
            thread_id=None,  # Not available in IMAP
            sender_name=None,  # Could parse from sender field
            snippet=body[:100] if body else "",  # First 100 chars
            body_html=None,  # Not extracted for IMAP
            has_attachments=False,  # Could detect from multipart
            is_unread=is_unread,
            flags=flags,
        )
```

## Recommended Action

1. **Consolidate Email entities** into `src/gmail_classifier/models/email.py`
2. **Add `from_imap_message()` class method** to unified Email
3. **Update IMAP fetcher** to use unified Email entity
4. **Remove duplicate Email** from `email/fetcher.py`
5. **Update imports** across codebase

## Technical Details

**Affected Files:**
- `src/gmail_classifier/models/email.py` - Add `from_imap_message()` method
- `src/gmail_classifier/email/fetcher.py` - Remove Email dataclass, use models.email
- `src/gmail_classifier/email/fetcher.py:_parse_email()` - Update to use `Email.from_imap_message()`

**Related Components:**
- EmailClassifier (consumer of Email entities)
- GmailClient (creates OAuth2 emails)
- FolderManager (creates IMAP emails)

**Database Changes:** No

**Migration Steps:**
1. Extend `models/email.py` Email with optional IMAP fields
2. Add `from_imap_message()` class method
3. Update `email/fetcher.py` to import and use `models.Email`
4. Remove duplicate Email dataclass from `fetcher.py`
5. Update `_parse_email()` to call `Email.from_imap_message()`
6. Run all tests to verify classification works

## Resources

- **Single Source of Truth:** https://en.wikipedia.org/wiki/Single_source_of_truth
- **Python Dataclass Inheritance:** https://docs.python.org/3/library/dataclasses.html

## Acceptance Criteria

- [ ] Single Email entity in `src/gmail_classifier/models/email.py`
- [ ] Email has all OAuth2 fields (some optional)
- [ ] Email has IMAP-specific fields (optional)
- [ ] `from_gmail_message()` class method works
- [ ] `from_imap_message()` class method implemented
- [ ] Duplicate Email removed from `email/fetcher.py`
- [ ] FolderManager uses unified Email entity
- [ ] Test: IMAP emails work with EmailClassifier
- [ ] Test: OAuth2 emails still work
- [ ] Test: Field compatibility verified
- [ ] All existing tests pass

## Work Log

### 2025-11-08 - Initial Discovery
**By:** Claude Multi-Agent Review System
**Actions:**
- Issue discovered during architectural analysis
- Categorized as P1 Critical
- Estimated effort: 3 hours

**Learnings:**
- Two Email entities discovered during code review
- Classification logic tightly coupled to OAuth2 Email structure
- IMAP emails would cause AttributeError crashes
- Common pattern is unified entity with multiple constructors
- Class methods (from_X) provide clean separation

## Notes

**Source:** IMAP Implementation Architecture Review - 2025-11-08
**Review Agent:** Architecture-Strategist
**Priority Justification:** Breaks core classification functionality
**Production Blocker:** YES - Classification completely non-functional for IMAP
