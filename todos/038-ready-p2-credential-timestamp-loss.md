---
status: ready
priority: p2
issue_id: "038"
tags: [data-integrity, audit, compliance, high-priority]
dependencies: []
---

# Credential Timestamp Loss - Audit Trail Broken

## Problem Statement

Credential timestamps (`created_at`, `last_used`) are not persisted to keyring storage, losing critical audit trail data. Every time credentials are retrieved, timestamps are reset to current time, making it impossible to determine:
- When credentials were actually created
- When credentials were last used
- If password rotation is needed
- Compliance with GDPR/audit requirements

**Audit Impact:** Cannot track credential age or usage history
**Compliance Risk:** GDPR/SOC2 audit trail requirements violated

## Findings

**Location:** `src/gmail_classifier/storage/credentials.py:129`

**Current Code:**
```python
def retrieve_credentials(self, email: str) -> IMAPCredentials | None:
    """Retrieve credentials from keyring."""
    password = keyring.get_password(self._service_name, email)

    if password:
        credentials = IMAPCredentials(
            email=email,
            password=password,
            created_at=datetime.now(),  # WRONG: Should be original timestamp
            last_used=None,             # LOST: Previous usage data gone
        )
        return credentials
    return None
```

**Problem Scenario:**

**Scenario 1: Lost Creation Time**
```python
# Day 1: User creates credentials
store_credentials(IMAPCredentials(
    email="user@example.com",
    password="secret",
    created_at=datetime(2025, 1, 1)  # Original creation
))

# Day 100: Retrieve credentials
creds = retrieve_credentials("user@example.com")
print(creds.created_at)  # 2025-04-10 - WRONG! Shows today, not Jan 1

# Cannot enforce 90-day password rotation policy
```

**Scenario 2: Lost Usage Tracking**
```python
# Day 1: Use credentials
creds.last_used = datetime(2025, 1, 1)
store_credentials(creds)

# Day 2: Retrieve credentials
creds = retrieve_credentials("user@example.com")
print(creds.last_used)  # None - LOST! Can't track usage

# Cannot identify stale/unused credentials
```

**Scenario 3: Audit Compliance Failure**
```python
# Auditor: "Show me when this credential was created"
creds = retrieve_credentials("user@example.com")
print(creds.created_at)  # Shows retrieval time, not creation time

# Cannot provide accurate audit trail
```

**Impact:**
- Cannot determine actual credential age
- Password rotation policies cannot be enforced
- Cannot identify stale/unused credentials
- GDPR/SOC2 audit compliance broken
- No usage analytics available
- Security best practices violated

## Proposed Solutions

### Option 1: Store Metadata in SQLite Table (RECOMMENDED)
**Pros:**
- Persistent metadata storage
- Easy to query and analyze
- Can add more metadata fields later
- Atomic updates with transactions
- Backup/export friendly

**Cons:**
- Requires additional database table
- Slightly more complex than JSON

**Effort:** Medium (2 hours)
**Risk:** Low (isolated change)

**Implementation:**
```python
# Create metadata table
CREATE TABLE credential_metadata (
    email TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_used TEXT,
    last_updated TEXT,
    notes TEXT
);

# Update storage class
def store_credentials(self, credentials: IMAPCredentials) -> bool:
    """Store credentials with metadata."""
    # Store password in keyring (existing)
    keyring.set_password(
        self._service_name,
        credentials.email,
        credentials.password
    )

    # Store metadata in SQLite
    self.db.execute("""
        INSERT OR REPLACE INTO credential_metadata
        (email, created_at, last_used, last_updated)
        VALUES (?, ?, ?, ?)
    """, (
        credentials.email,
        credentials.created_at.isoformat(),
        credentials.last_used.isoformat() if credentials.last_used else None,
        datetime.now().isoformat()
    ))
    self.db.commit()
    return True

def retrieve_credentials(self, email: str) -> IMAPCredentials | None:
    """Retrieve credentials with metadata."""
    password = keyring.get_password(self._service_name, email)
    if not password:
        return None

    # Retrieve metadata from SQLite
    row = self.db.execute(
        "SELECT created_at, last_used FROM credential_metadata WHERE email = ?",
        (email,)
    ).fetchone()

    if row:
        created_at = datetime.fromisoformat(row[0])
        last_used = datetime.fromisoformat(row[1]) if row[1] else None
    else:
        # Fallback for old credentials without metadata
        created_at = datetime.now()
        last_used = None

    return IMAPCredentials(
        email=email,
        password=password,
        created_at=created_at,
        last_used=last_used
    )
```

### Option 2: Store Metadata as JSON in Keyring
**Pros:**
- No additional database needed
- Simple implementation

**Cons:**
- Keyring value parsing required
- Harder to query/analyze
- No transaction support
- JSON parsing overhead

**Effort:** Small (1 hour)
**Risk:** Low

### Option 3: Ignore Timestamps (Not Recommended)
**Pros:**
- No code changes needed

**Cons:**
- Cannot enforce security policies
- Audit compliance violated
- No usage tracking

**Effort:** Zero
**Risk:** High (compliance/security)

## Recommended Action

**OPTION 1: Store Metadata in SQLite Table**

Create dedicated metadata table for credential tracking:

1. Create migration to add `credential_metadata` table
2. Update `store_credentials()` to save metadata
3. Update `retrieve_credentials()` to load metadata
4. Add migration for existing credentials (backfill with current date)
5. Add method to update `last_used` timestamp
6. Add query methods for credential age analysis

This provides proper audit trail and compliance.

## Technical Details

**Affected Files:**
- `src/gmail_classifier/storage/credentials.py:129` - Update retrieve/store methods
- `src/gmail_classifier/storage/migrations/` - Add metadata table migration
- `tests/` - Add metadata persistence tests

**Related Components:**
- CredentialStorage class
- IMAPAuthenticator (updates last_used)
- CLI commands (reports credential age)

**Database Changes:**
- New table: `credential_metadata`
- Columns: email (PK), created_at, last_used, last_updated, notes

**Migration Strategy:**
1. Create table if not exists
2. Backfill existing credentials with current timestamp
3. Mark backfilled entries for review

## Resources

- SQLite datetime handling: https://www.sqlite.org/lang_datefunc.html
- Python keyring API: https://pypi.org/project/keyring/
- GDPR audit requirements: https://gdpr.eu/article-30-records-of-processing-activities/

## Acceptance Criteria

- [ ] `credential_metadata` table created
- [ ] `store_credentials()` saves metadata to SQLite
- [ ] `retrieve_credentials()` loads metadata from SQLite
- [ ] Timestamps preserved across store/retrieve cycles
- [ ] Migration backfills existing credentials
- [ ] Test: created_at timestamp preserved
- [ ] Test: last_used timestamp preserved
- [ ] Test: fallback for credentials without metadata
- [ ] All existing tests pass

## Work Log

### 2025-11-08 - Discovery
**By:** Claude Multi-Agent Code Review (Data Integrity Guardian)
**Actions:**
- Discovered timestamp loss on credential retrieval
- Identified audit compliance impact
- Categorized as P2 High priority
- Estimated 2 hours to implement properly

**Learnings:**
- Keyring only stores password, not metadata
- Timestamps critical for audit compliance
- SQLite good for queryable metadata
- Need migration strategy for existing credentials

## Notes

**Source:** Code Review - Multi-Agent Analysis (2025-11-08)
**Priority Justification:** Audit compliance and security best practices
**Compliance:** GDPR Article 30, SOC2 requirements
**Security:** Enables password rotation policies
