---
status: pending
priority: p1
issue_id: "006"
tags: [code-review, data-integrity, critical, race-condition, gmail-api]
dependencies: [003-pending-p1-database-transaction-boundaries]
---

# Fix Race Condition Between Gmail API and Database State

## Problem Statement

There is a critical race condition in `apply_suggestions()` where labels are successfully applied to Gmail but the database update can fail, creating inconsistent state. The system has no rollback mechanism for Gmail operations and no reconciliation process for detecting/fixing inconsistencies.

## Findings

**Discovered by:** data-integrity-guardian agent during workflow analysis

**Location:** `src/gmail_classifier/services/classifier.py:238-267`

**Current Code:**
```python
success = self.gmail_client.add_label_to_message(
    suggestion.email_id,
    suggestion.best_suggestion.label_id,
)  # Label applied to Gmail - COMMITTED

if success:
    suggestion.mark_applied()  # In-memory only
    self.session_db.update_suggestion_status(...)  # Can fail here!
    session.increment_applied()  # Can fail here!
```

**Data Corruption Scenarios:**

**Scenario 1: Database Write Failure**
1. System applies label to email "abc123" via Gmail API (SUCCESS)
2. Disk full error occurs during `update_suggestion_status()`
3. Exception raised, suggestion status remains "pending" in database
4. User re-runs apply command
5. System tries to apply same label again (duplicate operation)
6. Session statistics are incorrect

**Scenario 2: Process Crash**
1. Successfully apply labels to 50 emails via Gmail API
2. Process crashes before database updates complete
3. Gmail has labels, database shows "pending"
4. No audit trail of what was actually applied

**Scenario 3: Partial Batch Failure**
1. Batch of 100 suggestions being applied
2. Gmail API succeeds for emails 1-75
3. Database update fails at email 76
4. Emails 1-75 have inconsistent state (labeled but marked pending)

**Risk Level:** CRITICAL - Data consistency violated, no recovery mechanism

## Proposed Solutions

### Option 1: Compensating Transaction with Audit Log (RECOMMENDED)
**Pros:**
- Records all Gmail operations for reconciliation
- Allows manual recovery from inconsistent state
- Provides audit trail for compliance
- Can detect and report inconsistencies

**Cons:**
- Cannot rollback Gmail operations automatically
- Requires manual reconciliation process

**Effort:** Medium (3-4 hours)
**Risk:** Low

**Implementation:**
```python
# Add audit log table
CREATE TABLE IF NOT EXISTS gmail_operations_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT NOT NULL,
    email_id TEXT NOT NULL,
    label_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    db_synced BOOLEAN DEFAULT 0,
    error_message TEXT
)

def apply_suggestions(self, session_id: str) -> dict[str, int]:
    """Apply suggestions with audit logging."""
    applied = 0
    failed = 0
    inconsistent = []

    session = self.session_db.load_session(session_id)
    suggestions = self.session_db.load_suggestions(session_id, status="approved")

    for suggestion in suggestions:
        try:
            # Apply label to Gmail
            success = self.gmail_client.add_label_to_message(
                suggestion.email_id,
                suggestion.best_suggestion.label_id,
            )

            # Log the operation immediately
            self.session_db.log_gmail_operation(
                operation_type="add_label",
                email_id=suggestion.email_id,
                label_id=suggestion.best_suggestion.label_id,
                success=success,
                timestamp=datetime.now(timezone.utc).isoformat()
            )

            if success:
                try:
                    # Update database with transaction
                    suggestion.mark_applied()
                    self.session_db.update_suggestion_status(
                        session_id, suggestion.email_id, "applied"
                    )
                    session.increment_applied()

                    # Mark as synced in audit log
                    self.session_db.mark_operation_synced(
                        email_id=suggestion.email_id,
                        label_id=suggestion.best_suggestion.label_id
                    )
                    applied += 1

                except Exception as db_error:
                    # CRITICAL: Label applied but DB update failed
                    logger.critical(
                        f"INCONSISTENCY DETECTED: "
                        f"Label applied to Gmail but DB update failed. "
                        f"email_id={suggestion.email_id}, "
                        f"label_id={suggestion.best_suggestion.label_id}, "
                        f"error={db_error}"
                    )
                    inconsistent.append({
                        "email_id": suggestion.email_id,
                        "label_id": suggestion.best_suggestion.label_id,
                        "error": str(db_error)
                    })
                    failed += 1
                    continue
            else:
                failed += 1

        except Exception as gmail_error:
            logger.error(f"Failed to apply label to {suggestion.email_id}: {gmail_error}")
            failed += 1

    # Report inconsistencies
    if inconsistent:
        logger.error(
            f"INCONSISTENT STATE: {len(inconsistent)} labels applied to Gmail "
            f"but not recorded in database. Manual reconciliation required."
        )
        # Write inconsistency report
        with open("gmail_db_inconsistencies.json", "a") as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id,
                "inconsistencies": inconsistent
            }, f)
            f.write("\n")

    return {"applied": applied, "failed": failed, "inconsistent": len(inconsistent)}
```

### Option 2: Two-Phase Commit Pattern
**Pros:**
- Atomic across Gmail and database
- No inconsistent state possible

**Cons:**
- Cannot implement true 2PC with Gmail API (no prepare phase)
- Very complex implementation
- Gmail doesn't support rollback

**Effort:** Large (2-3 days)
**Risk:** High (complex, may not be achievable)

**Not Recommended** - Gmail API doesn't support transaction protocols.

### Option 3: Reconciliation Command
**Pros:**
- Allows detecting and fixing inconsistencies
- Can be run periodically or on-demand

**Cons:**
- Reactive rather than preventive
- Requires Gmail API quota for checking

**Effort:** Medium (2-3 hours)
**Risk:** Low

**Implementation:**
```python
def reconcile_state(self, session_id: str) -> dict:
    """Reconcile database state with Gmail reality."""
    suggestions = self.session_db.load_suggestions(session_id)
    mismatches = []

    for suggestion in suggestions:
        # Check Gmail for label
        gmail_labels = self.gmail_client.get_message_labels(suggestion.email_id)
        has_label = suggestion.best_suggestion.label_id in gmail_labels

        # Check database status
        db_status = suggestion.status

        # Detect mismatches
        if has_label and db_status == "pending":
            # Gmail has label but DB says pending
            self.session_db.update_suggestion_status(
                session_id, suggestion.email_id, "applied"
            )
            mismatches.append(f"Fixed: {suggestion.email_id} was applied but not recorded")

        elif not has_label and db_status == "applied":
            # DB says applied but Gmail doesn't have label
            self.session_db.update_suggestion_status(
                session_id, suggestion.email_id, "pending"
            )
            mismatches.append(f"Fixed: {suggestion.email_id} was not applied but marked as such")

    return {"mismatches_found": len(mismatches), "details": mismatches}
```

## Recommended Action

**Implement Option 1 (Audit Log) + Option 3 (Reconciliation):**
1. Add audit logging for all Gmail operations (immediate)
2. Implement compensating transaction pattern (immediate)
3. Add reconciliation command (next sprint)

## Technical Details

**Affected Files:**
- `src/gmail_classifier/services/classifier.py` (lines 238-267, `apply_suggestions` method)
- `src/gmail_classifier/lib/session_db.py` (add audit log table and methods)
- `src/gmail_classifier/cli/main.py` (add reconcile command)

**Related Components:**
- Label application workflow
- Session state management
- Database operations

**Database Changes:**
- Add `gmail_operations_log` table
- Add methods for audit logging

**Dependencies:**
- Depends on 003-pending-p1-database-transaction-boundaries.md being resolved first

## Resources

- [Compensating Transactions Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction)
- [Saga Pattern for Distributed Transactions](https://microservices.io/patterns/data/saga.html)
- Related findings: 003-pending-p1-database-transaction-boundaries.md

## Acceptance Criteria

- [ ] Gmail operations audit log table created
- [ ] All Gmail API calls logged to audit table
- [ ] Compensating transaction pattern implemented
- [ ] Inconsistencies logged to file for manual review
- [ ] Reconciliation command implemented
- [ ] Unit test: Database failure after Gmail success handled correctly
- [ ] Unit test: Audit log records all operations
- [ ] Integration test: Reconciliation command detects mismatches
- [ ] Manual test: Simulate disk full during apply, verify audit log
- [ ] Documentation: Reconciliation process documented
- [ ] Code reviewed and approved

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (data-integrity-guardian agent)
**Actions:**
- Discovered race condition during workflow analysis
- Identified no rollback mechanism for Gmail operations
- Recognized impossibility of true 2PC with Gmail API
- Categorized as P1 critical data integrity issue

**Learnings:**
- External API operations cannot be rolled back
- Compensating transactions are necessary for distributed state
- Audit logging is critical for detecting inconsistencies
- Reconciliation processes are needed for eventual consistency
