---
status: ready
priority: p1
issue_id: "037"
tags: [data-integrity, critical, bug, data-corruption]
dependencies: []
---

# Email ID Type Inconsistency Causes Data Corruption

## Problem Statement

The Email dataclass accepts both `str | int` for the `id` field without validation or normalization. This creates data corruption risks where the same email appears as duplicate, database foreign keys fail, and deduplication logic breaks.

**Data Corruption Risk:** "123" != 123 in Python (different hash, comparison)
**Impact:** Email deduplication will fail, classification processes same email twice

## Findings

**Location:** `src/gmail_classifier/models/email.py:37`

**Current Code:**
```python
@dataclass
class Email:
    id: str | int  # Gmail API: string, IMAP: integer
    subject: str
    sender: str
    # ... other fields
```

**Problem Scenario:**

**Scenario 1: Deduplication Failure**
```python
# Gmail API returns string ID
email1 = Email(id="123", subject="Test", ...)

# IMAP returns integer ID
email2 = Email(id=123, subject="Test", ...)

# Deduplication check:
if email1.id in seen_ids:  # False! "123" != 123
    skip()
else:
    process()  # Processes same email twice!
```

**Scenario 2: Database Corruption**
```python
# Database with email_id foreign key
db.execute("INSERT INTO emails VALUES (?)", email.id)  # "123"
db.execute("INSERT INTO classifications VALUES (?, ?)", email.id, label)  # 123

# Foreign key constraint fails: "123" != 123
# Or worse: creates orphaned records
```

**Scenario 3: Set/Dict Lookup**
```python
seen_ids = {"123", "456", "789"}  # String IDs from Gmail

# IMAP email check
if 123 in seen_ids:  # False! Type mismatch
    skip()
else:
    classify()  # Duplicate classification!
```

**Impact:**
- Same email classified multiple times
- Database foreign key violations
- Wasted API quota on duplicates
- Set/dict lookups fail silently
- Comparison operators behave unexpectedly
- Hash collisions possible

## Proposed Solutions

### Option 1: Normalize to String in __post_init__ (RECOMMENDED)
**Pros:**
- Simple and automatic
- Works with both Gmail and IMAP sources
- No caller changes needed
- Consistent type throughout codebase
- String is more flexible (handles UUIDs, etc.)

**Cons:**
- Slight conversion overhead (negligible)

**Effort:** Small (15 minutes)
**Risk:** Low (backward compatible)

**Implementation:**
```python
from dataclasses import dataclass

@dataclass
class Email:
    id: str  # Always normalized to string
    subject: str
    sender: str
    body: str
    date: datetime
    labels: list[str]

    def __post_init__(self):
        """Normalize ID to string for consistency."""
        # Handle both Gmail (str) and IMAP (int) sources
        self.id = str(self.id)

        # Validate not empty
        if not self.id or self.id == "None":
            raise ValueError("Email ID cannot be empty or None")
```

### Option 2: Normalize to Integer
**Pros:**
- Smaller in memory
- Matches IMAP native type

**Cons:**
- Gmail API uses string IDs (may not be integers)
- Cannot handle UUID-style IDs
- Less flexible for future ID formats

**Effort:** Small (15 minutes)
**Risk:** Medium (may break Gmail API IDs)

### Option 3: Require Caller to Normalize
**Pros:**
- No dataclass logic needed

**Cons:**
- Error-prone (easy to forget)
- Pushes responsibility to all callers
- Doesn't prevent mistakes

**Effort:** Medium (must update all creation sites)
**Risk:** High (likely to miss some locations)

## Recommended Action

**OPTION 1: Normalize to String in __post_init__**

Add `__post_init__` method to Email dataclass:

1. Change type annotation to `id: str`
2. Add `__post_init__` method that calls `self.id = str(self.id)`
3. Add validation that ID is not empty
4. Update tests to verify normalization works
5. Test with both Gmail (string) and IMAP (integer) sources

This ensures consistency automatically with zero caller changes.

## Technical Details

**Affected Files:**
- `src/gmail_classifier/models/email.py:37` - Add __post_init__ normalization
- `tests/` - Add tests for ID normalization

**Related Components:**
- Gmail API email fetching (returns string IDs)
- IMAP email fetching (returns integer IDs)
- Email deduplication logic
- Database storage/retrieval
- Classification processing

**Database Changes:** No (unless DB schema expects integer - verify first)

**Migration Notes:**
- If database stores email_id as INTEGER, may need to change to TEXT
- Or use integer normalization instead (less recommended)

## Resources

- Python dataclass __post_init__: https://docs.python.org/3/library/dataclasses.html#post-init-processing
- Gmail API Message ID format: https://developers.google.com/gmail/api/reference/rest/v1/users.messages
- IMAP UID documentation: https://www.rfc-editor.org/rfc/rfc3501#section-2.3.1.1

## Acceptance Criteria

- [ ] Email.id type annotation changed to `str`
- [ ] `__post_init__` method implemented with normalization
- [ ] ID validation added (not empty, not "None")
- [ ] Test: Gmail string ID ("123") normalizes correctly
- [ ] Test: IMAP integer ID (123) converts to "123"
- [ ] Test: Empty ID raises ValueError
- [ ] Deduplication logic tested with mixed ID types
- [ ] Database operations work correctly
- [ ] All existing tests pass

## Work Log

### 2025-11-08 - Critical Discovery
**By:** Claude Multi-Agent Code Review (Data Integrity Guardian)
**Actions:**
- Discovered str | int union type without normalization
- Identified data corruption scenarios
- Categorized as P1 Critical data integrity issue
- Estimated 15 minutes to fix

**Learnings:**
- Python comparison: "123" != 123 (different types)
- Set/dict lookups fail with type mismatch
- Deduplication requires consistent ID types
- Database FKs fail with mixed types
- __post_init__ is perfect for normalization

## Notes

**Source:** Code Review - Multi-Agent Analysis (2025-11-08)
**Priority Justification:** Data corruption leading to duplicate processing
**Root Cause:** Type union without normalization
**Prevention:** Always normalize mixed-type identifiers immediately
