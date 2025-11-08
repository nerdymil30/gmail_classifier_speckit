---
status: ready
priority: p2
issue_id: "039"
tags: [performance, bug, high-priority, regression]
dependencies: []
---

# Double-Fetch Performance Regression in Adaptive Batching

## Problem Statement

Adaptive batching has a critical bug that doubles network round-trips for large emails. The code fetches RFC822.SIZE first, then fetches the actual email data separately. This means large email batches do 2× round-trips instead of 1×, potentially making the "optimization" SLOWER than the old code.

**Performance Bug:** 2× network round-trips instead of 1×
**Impact:** Adaptive batching may be slower than non-adaptive batching

## Findings

**Location:** `src/gmail_classifier/email/fetcher.py:391-422`

**Current Code:**
```python
def _fetch_emails_adaptive(
    self,
    connection: IMAPClient,
    message_ids: list[int],
    batch_size: int
) -> list[Email]:
    """Fetch emails with adaptive batching."""

    # Round-trip 1: Fetch sizes
    size_data = connection.fetch(batch_ids, ["RFC822.SIZE"])

    # Analyze sizes and split batch
    small_ids = []
    large_ids = []
    for msg_id, data in size_data.items():
        size = data[b"RFC822.SIZE"]
        if size > self.LARGE_EMAIL_THRESHOLD:
            large_ids.append(msg_id)
        else:
            small_ids.append(msg_id)

    # Round-trip 2: Fetch actual data
    self._fetch_and_parse_batch(connection, small_ids)

    # Round-trip 3: Fetch large emails one by one
    for large_id in large_ids:
        self._fetch_and_parse_batch(connection, [large_id])
```

**Problem Scenario:**

**Scenario 1: Normal Batch (All Small Emails)**
```python
# Old code: 1 round-trip
connection.fetch([1,2,3,4,5], ["BODY[]", "ENVELOPE"])  # 1 RT

# New code: 2 round-trips
connection.fetch([1,2,3,4,5], ["RFC822.SIZE"])  # RT 1
connection.fetch([1,2,3,4,5], ["BODY[]", "ENVELOPE"])  # RT 2

# Result: 100% MORE round-trips!
```

**Scenario 2: Batch with 1 Large Email**
```python
# 100 emails, 1 is large (>5MB)

# Old code: 1 round-trip
connection.fetch([1..100], ["BODY[]"])  # 1 RT, may timeout on large

# New code: 3 round-trips
connection.fetch([1..100], ["RFC822.SIZE"])  # RT 1
connection.fetch([1..99], ["BODY[]"])         # RT 2 (small emails)
connection.fetch([100], ["BODY[]"])           # RT 3 (large email)

# Result: 200% MORE round-trips!
```

**Impact:**
- Network latency multiplied by 2× or 3×
- Adaptive batching slower than naive batching
- High-latency connections severely affected
- Regression in performance "optimization"
- More chances for network errors

**Performance Analysis:**
```
Scenario: 100 emails, 200ms network latency

Old code:
- 1 fetch: 200ms
- Total: 200ms

New code (all small):
- Size fetch: 200ms
- Data fetch: 200ms
- Total: 400ms (100% SLOWER!)

New code (with 10 large):
- Size fetch: 200ms
- Small batch fetch: 200ms
- 10 individual fetches: 2000ms
- Total: 2400ms (1100% SLOWER!)
```

## Proposed Solutions

### Option 1: Fetch Size AND Data in Single Round-Trip (RECOMMENDED)
**Pros:**
- Eliminates double-fetch bug
- Same 1× round-trip as old code
- Still gets size information for metrics
- No performance regression

**Cons:**
- Cannot split batch before fetching
- Must handle large emails after fetching

**Effort:** Small (1 hour)
**Risk:** Low (improves performance)

**Implementation:**
```python
def _fetch_emails_adaptive(
    self,
    connection: IMAPClient,
    message_ids: list[int],
    batch_size: int
) -> list[Email]:
    """Fetch emails with adaptive batching."""

    # Single round-trip: get size AND data
    data = connection.fetch(
        batch_ids,
        ["RFC822.SIZE", "BODY[]", "ENVELOPE", "INTERNALDATE"]
    )

    # Process results and identify large emails
    emails = []
    for msg_id, msg_data in data.items():
        size = msg_data[b"RFC822.SIZE"]

        if size > self.LARGE_EMAIL_THRESHOLD:
            # Large email: handle with care (streaming, etc.)
            logger.warning(f"Large email {msg_id}: {size} bytes")

        # Parse email (already fetched)
        email = self._parse_fetch_response(msg_id, msg_data)
        emails.append(email)

    return emails
```

### Option 2: Remove Adaptive Batching Entirely
**Pros:**
- Simplest solution
- Removes premature optimization
- Eliminates bug completely

**Cons:**
- Loses size-based batching logic
- May timeout on very large emails

**Effort:** Small (30 minutes)
**Risk:** Low

### Option 3: Make Size Fetch Optional (Feature Flag)
**Pros:**
- Can compare performance
- Allows A/B testing

**Cons:**
- Added complexity
- Doesn't fix the bug

**Effort:** Medium (2 hours)
**Risk:** Medium

## Recommended Action

**OPTION 1: Fetch Size AND Data in Single Round-Trip**

Modify adaptive batching to fetch everything at once:

1. Change `connection.fetch()` to include RFC822.SIZE in initial fetch
2. Remove separate size fetch round-trip
3. Process size information after fetch (for logging/metrics)
4. Handle large emails appropriately after identifying them
5. Add performance metrics to verify improvement

This fixes the regression while keeping size-based logic.

## Technical Details

**Affected Files:**
- `src/gmail_classifier/email/fetcher.py:391-422` - Fix double-fetch bug
- `tests/` - Update/add performance tests

**Related Components:**
- IMAPEmailFetcher._fetch_emails_adaptive()
- IMAPClient.fetch() calls
- Batch processing logic

**Database Changes:** No

**Performance Impact:**
- Before fix: 2-3× round-trips
- After fix: 1× round-trip (same as naive)
- Improvement: 50-66% fewer network calls

## Resources

- IMAPClient fetch documentation: https://imapclient.readthedocs.io/en/master/#imapclient.IMAPClient.fetch
- IMAP FETCH command: https://www.rfc-editor.org/rfc/rfc3501#section-6.4.5
- Network latency impact: https://www.igvita.com/2012/07/19/latency-the-new-web-performance-bottleneck/

## Acceptance Criteria

- [ ] Single fetch call includes RFC822.SIZE and email data
- [ ] No separate size-only fetch round-trip
- [ ] Size information still available for large email handling
- [ ] Performance test: verify 1× round-trip for normal batch
- [ ] Performance test: verify improvement over current code
- [ ] Large emails still handled correctly
- [ ] All existing tests pass
- [ ] Benchmarks show improvement

## Work Log

### 2025-11-08 - Critical Discovery
**By:** Claude Multi-Agent Code Review (Performance Oracle)
**Actions:**
- Discovered double-fetch performance bug
- Analyzed round-trip multiplication
- Calculated 100-1100% performance regression
- Categorized as P2 High priority
- Estimated 1 hour to fix

**Learnings:**
- Separate size fetch doubles network round-trips
- Network latency is cumulative
- "Optimizations" can cause regressions
- Should fetch all needed data in single round-trip
- Size information can be extracted from fetched data

## Notes

**Source:** Code Review - Multi-Agent Analysis (2025-11-08)
**Priority Justification:** Performance regression in optimization code
**Irony:** Adaptive batching optimization is slower than naive approach
**Fix Simplicity:** Very simple fix with significant impact
