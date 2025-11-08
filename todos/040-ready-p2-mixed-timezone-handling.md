---
status: ready
priority: p2
issue_id: "040"
tags: [data-integrity, bug, high-priority, datetime]
dependencies: []
---

# Mixed Timezone Handling Causes Runtime Errors

## Problem Statement

Inconsistent timezone handling throughout the codebase causes comparison failures and runtime errors. Some datetimes are naive (no timezone), others are aware (with timezone). Python cannot compare naive and aware datetimes, causing `TypeError` exceptions.

**Bug:** Cannot compare naive and aware datetimes
**Impact:** Runtime errors in time-based logic, incorrect comparisons

## Findings

**Locations:** Multiple files throughout codebase

**Problem Pattern:**
```python
# Some places: naive datetime (no timezone)
@dataclass
class Email:
    date: datetime  # No timezone info

@dataclass
class IMAPCredentials:
    created_at: datetime = field(default_factory=datetime.now)  # Naive

# Other places: aware datetime (with timezone)
cutoff = datetime.now(timezone.utc)  # Timezone-aware

# Comparison fails:
if session.start_time < cutoff:  # TypeError!
    cleanup()
```

**Problem Scenario:**

**Scenario 1: Session Cleanup Crash**
```python
# Session created with naive datetime
session = IMAPSessionInfo(
    start_time=datetime.now(),  # Naive: 2025-11-08 10:00:00
    ...
)

# Cleanup checks with aware datetime
cutoff = datetime.now(timezone.utc)  # Aware: 2025-11-08 10:00:00+00:00

# Comparison crashes
if session.start_time < cutoff:
    # TypeError: can't compare offset-naive and offset-aware datetimes
    cleanup_session()
```

**Scenario 2: Email Date Comparison**
```python
# Email with naive datetime
email = Email(
    date=datetime(2025, 11, 1),  # Naive
    ...
)

# Filter by date range
start_date = datetime.now(timezone.utc) - timedelta(days=30)  # Aware

# Comparison crashes
if email.date >= start_date:
    # TypeError: can't compare offset-naive and offset-aware datetimes
    process(email)
```

**Scenario 3: Credential Age Check**
```python
# Credential created with naive datetime
cred = IMAPCredentials(
    created_at=datetime.now(),  # Naive
    ...
)

# Check if credential is old
age_threshold = datetime.now(timezone.utc) - timedelta(days=90)  # Aware

# Comparison crashes
if cred.created_at < age_threshold:
    # TypeError!
    rotate_password()
```

**Impact:**
- Runtime TypeError exceptions
- Comparisons silently fail in some cases
- Time-based logic broken
- Cleanup operations crash
- Age calculations incorrect
- Hard to debug timezone issues

## Proposed Solutions

### Option 1: Standardize on UTC Timezone-Aware (RECOMMENDED)
**Pros:**
- Explicit timezone handling
- No ambiguity about local vs UTC
- Industry best practice
- Handles daylight saving time correctly
- Easy to convert to user's local time

**Cons:**
- Must update all datetime creation sites
- More verbose than naive datetimes

**Effort:** Medium (3 hours)
**Risk:** Low (improves correctness)

**Implementation:**
```python
from datetime import datetime, timezone
from dataclasses import dataclass, field

# Helper function
def utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)

# Update Email dataclass
@dataclass
class Email:
    id: str
    subject: str
    sender: str
    body: str
    date: datetime  # Must be timezone-aware
    labels: list[str]

    def __post_init__(self):
        """Ensure date is timezone-aware."""
        if self.date.tzinfo is None:
            # Assume UTC if naive
            self.date = self.date.replace(tzinfo=timezone.utc)

# Update IMAPCredentials
@dataclass
class IMAPCredentials:
    email: str
    password: str
    created_at: datetime = field(default_factory=utc_now)  # UTC aware
    last_used: datetime | None = None

# Update IMAPSessionInfo
@dataclass
class IMAPSessionInfo:
    connection: IMAPClient
    folder: str
    start_time: datetime = field(default_factory=utc_now)  # UTC aware
    last_activity: datetime = field(default_factory=utc_now)

# Update all comparisons
cutoff = utc_now() - timedelta(minutes=30)
if session.start_time < cutoff:  # Works! Both aware
    cleanup_session()
```

### Option 2: Standardize on Naive Datetimes (All UTC)
**Pros:**
- Simpler (less verbose)
- All datetimes comparable

**Cons:**
- No explicit timezone information
- Assumes all times are UTC (risky)
- Cannot handle local time properly
- Bad practice for production code

**Effort:** Medium (2 hours)
**Risk:** Medium (implicit timezone assumptions)

### Option 3: Convert at Comparison Points
**Pros:**
- No dataclass changes needed

**Cons:**
- Error-prone (easy to forget)
- Doesn't prevent mistakes
- Must remember at every comparison

**Effort:** Small (1 hour)
**Risk:** High (likely to miss locations)

## Recommended Action

**OPTION 1: Standardize on UTC Timezone-Aware**

Make all datetimes timezone-aware with UTC:

1. Create `utc_now()` helper function
2. Update all dataclasses to use timezone-aware defaults
3. Add `__post_init__` validation to ensure timezone-aware
4. Update all `datetime.now()` calls to `utc_now()`
5. Update all datetime literals to include `timezone.utc`
6. Add tests to verify all datetimes are timezone-aware
7. Update serialization/deserialization to preserve timezone

This eliminates comparison errors and follows best practices.

## Technical Details

**Affected Files:**
- `src/gmail_classifier/models/email.py` - Email.date validation
- `src/gmail_classifier/auth/imap.py` - IMAPCredentials, IMAPSessionInfo
- `src/gmail_classifier/storage/credentials.py` - Datetime storage/retrieval
- `src/gmail_classifier/email/fetcher.py` - Session cleanup comparisons
- All files using `datetime.now()` - Replace with `utc_now()`

**Related Components:**
- All dataclasses with datetime fields
- Session management
- Cleanup operations
- Age calculations
- Database datetime storage

**Database Changes:**
- May need to update datetime format in database
- SQLite: Store as ISO 8601 with timezone: `2025-11-08T10:00:00+00:00`

## Resources

- Python datetime documentation: https://docs.python.org/3/library/datetime.html
- Timezone best practices: https://pypi.org/project/python-dateutil/
- ISO 8601 format: https://en.wikipedia.org/wiki/ISO_8601

## Acceptance Criteria

- [ ] `utc_now()` helper function created
- [ ] All dataclass datetime fields use timezone-aware defaults
- [ ] `__post_init__` validation ensures timezone-aware datetimes
- [ ] All `datetime.now()` replaced with `utc_now()`
- [ ] All datetime literals include `timezone.utc`
- [ ] Test: naive datetime converted to aware in __post_init__
- [ ] Test: all datetime comparisons work without TypeError
- [ ] Test: session cleanup doesn't crash
- [ ] All existing tests pass

## Work Log

### 2025-11-08 - Critical Discovery
**By:** Claude Multi-Agent Code Review (Data Integrity Guardian)
**Actions:**
- Discovered mixed naive/aware datetime usage
- Identified TypeError crash scenarios
- Categorized as P2 High priority
- Estimated 3 hours to standardize

**Learnings:**
- Python cannot compare naive and aware datetimes
- Timezone-aware is best practice
- UTC is standard for backend systems
- __post_init__ can enforce timezone-aware
- Need helper function for consistency

## Notes

**Source:** Code Review - Multi-Agent Analysis (2025-11-08)
**Priority Justification:** Runtime errors in production code
**Best Practice:** Always use timezone-aware datetimes in production
**Standard:** UTC for storage, convert to local for display
