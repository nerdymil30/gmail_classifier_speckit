---
status: resolved
priority: p2
issue_id: "022"
tags: [performance, imap, optimization]
dependencies: []
---

# Email Batch Fetching Too Conservative

## Problem Statement

Default `limit=10` is too small for production use, causing 100 network round-trips to fetch 1000 emails. Each round-trip adds 200-500ms overhead, resulting in 40+ seconds of pure network latency.

**Impact:** Fetching 1000 emails takes 40 seconds (pure overhead) - 5x slower than necessary

## Findings

**Location:** `src/gmail_classifier/email/fetcher.py:315-385`

**Current Code:**
```python
def fetch_emails(
    self,
    session_id: uuid.UUID,
    limit: int = 10,  # TOO SMALL
    criteria: str = "ALL",
) -> list[Email]:
```

**Performance Impact:**
- 100 emails: 10 batches × 400ms = 4 seconds overhead
- 1000 emails: 100 batches × 400ms = 40 seconds overhead
- 10,000 emails: 1000 batches × 400ms = 6.6 minutes overhead

## Proposed Solution

```python
def fetch_emails(
    self,
    session_id: uuid.UUID,
    limit: int = 100,  # Increased from 10
    batch_size: int = 50,  # New parameter
    criteria: str = "ALL",
) -> list[Email]:
    # Fetch in batches
    for i in range(0, len(message_ids), batch_size):
        batch_ids = message_ids[i:i + batch_size]

        # Adaptive batching based on email size
        if len(batch_ids) > 20:
            headers = connection.fetch(batch_ids, ["RFC822.SIZE"])
            avg_size = sum(h.get(b'RFC822.SIZE', 0) for h in headers.values()) / len(headers)

            # Large emails: fetch individually
            if avg_size > 100_000:
                for msg_id in batch_ids:
                    # Individual fetch for large emails
```

**Performance Gain:**
- 1000 emails: 40s → 8s (5x faster)
- Adaptive batching prevents timeouts

## Acceptance Criteria

- [ ] Increase default limit to 100
- [ ] Add batch_size parameter (default 50)
- [ ] Implement adaptive batching for large emails
- [ ] Test: 100 emails fetched in <5 seconds
- [ ] Test: Large emails don't timeout
- [ ] Test: Batch size adapts to email size

**Effort:** 2 hours

