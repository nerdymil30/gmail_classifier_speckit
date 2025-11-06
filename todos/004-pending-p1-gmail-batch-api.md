---
status: pending
priority: p1
issue_id: "004"
tags: [code-review, performance, critical, gmail-api, n+1-query]
dependencies: []
---

# Implement Gmail Batch API for Message Fetching

## Problem Statement

The `get_messages_batch()` method uses sequential API calls instead of Gmail's batch API, creating an N+1 query pattern. This results in 50-100x slower performance at scale and will hit rate limits with larger email volumes.

## Findings

**Discovered by:** performance-oracle agent during API analysis

**Location:** `src/gmail_classifier/services/gmail_client.py:169-190`

**Current Code:**
```python
def get_messages_batch(self, message_ids: List[str]) -> List[Email]:
    emails = []
    for message_id in message_ids:  # O(n) API calls - CRITICAL BOTTLENECK
        try:
            email = self.get_message(message_id)
            emails.append(email)
        except Exception as e:
            logger.error(f"Failed to fetch message {message_id}: {e}")
    return emails
```

**Performance Impact:**

| Email Count | Current Time | API Calls | Optimized Time | Speedup |
|-------------|--------------|-----------|----------------|---------|
| 100 | 30-50 sec | 100 | 1-2 sec | 25-50x |
| 1,000 | 5-8 min | 1,000 | 10-20 sec | 25-50x |
| 10,000 | 50-80 min | 10,000 | 2-3 min | 25-40x |

**Additional Issues:**
- Each call has ~50-100ms latency overhead
- Rate limiting becomes severe bottleneck
- Gmail API quota (250 units/second) quickly exhausted
- User experience severely degraded at scale

**Risk Level:** CRITICAL - Performance blocker for production use

## Proposed Solutions

### Option 1: Gmail Batch API with BatchHttpRequest (RECOMMENDED)
**Pros:**
- 50-100x performance improvement
- Reduces API quota consumption by ~99%
- Supports up to 100 requests per batch
- Built into google-api-python-client
- Industry standard approach

**Cons:**
- Slightly more complex code
- Need to handle batch callbacks

**Effort:** Medium (3-4 hours including testing)
**Risk:** Low

**Implementation:**
```python
from googleapiclient.http import BatchHttpRequest
from gmail_classifier.lib.utils import batch_items

@retry_with_exponential_backoff()
def get_messages_batch(self, message_ids: list[str]) -> list[Email]:
    """Fetch multiple messages using Gmail Batch API.

    Args:
        message_ids: List of Gmail message IDs to fetch

    Returns:
        List of Email objects

    Note:
        Gmail Batch API supports up to 100 requests per batch.
        This method automatically chunks larger requests.
    """
    with Timer("get_messages_batch"):
        emails = []
        failed_ids = []

        # Process in chunks of 100 (Gmail batch API limit)
        for chunk in batch_items(message_ids, 100):
            batch = self.service.new_batch_http_request()

            # Closure to capture results
            def callback(request_id, response, exception):
                if exception:
                    logger.error(f"Batch request failed for message {request_id}: {exception}")
                    failed_ids.append(request_id)
                else:
                    try:
                        email = Email.from_gmail_message(response)
                        emails.append(email)
                    except Exception as e:
                        logger.error(f"Failed to parse email {request_id}: {e}")
                        failed_ids.append(request_id)

            # Add all messages in chunk to batch
            for msg_id in chunk:
                batch.add(
                    self.service.users().messages().get(
                        userId="me",
                        id=msg_id,
                        format="full"
                    ),
                    callback=callback,
                    request_id=msg_id
                )

            # Execute batch request
            batch.execute()

        if failed_ids:
            logger.warning(f"Failed to fetch {len(failed_ids)} messages: {failed_ids}")

        logger.info(f"Fetched {len(emails)} messages using batch API")
        return emails
```

### Option 2: Concurrent Requests with Threading
**Pros:**
- Parallelizes requests
- Simpler than batch API
- Can control concurrency level

**Cons:**
- Still makes N individual API calls
- Thread management complexity
- May hit rate limits faster
- Only 5-10x improvement vs 50-100x with batch API

**Effort:** Medium (2-3 hours)
**Risk:** Medium (rate limiting, thread safety)

**Not Recommended** - Batch API is superior solution.

## Recommended Action

**Implement Option 1** - Gmail Batch API. This is the industry standard and provides maximum performance improvement.

## Technical Details

**Affected Files:**
- `src/gmail_classifier/services/gmail_client.py` (lines 169-190, `get_messages_batch` method)

**Related Components:**
- Email classification workflow
- All email fetching operations

**Database Changes:** No

**Dependencies:**
- `googleapiclient.http.BatchHttpRequest` (already available)
- Existing `batch_items` utility function (in `lib/utils.py`)

**Testing Requirements:**
- Unit test with mocked batch API
- Integration test with real Gmail API (small batch)
- Performance benchmark comparing old vs new implementation
- Error handling test (partial batch failures)

## Resources

- [Gmail Batch API Documentation](https://developers.google.com/gmail/api/guides/batch)
- [google-api-python-client Batch Requests](https://github.com/googleapis/google-api-python-client/blob/main/docs/batch.md)
- Related findings: 007-pending-p2-batch-label-application.md (similar pattern for label operations)

## Acceptance Criteria

- [ ] Batch API implementation using `BatchHttpRequest`
- [ ] Automatic chunking for message_ids > 100
- [ ] Callback function handles success and error cases
- [ ] Failed message IDs logged and tracked
- [ ] Performance benchmark: 100 emails fetched in < 5 seconds
- [ ] Unit test: Batch processing with mock API
- [ ] Unit test: Chunking works correctly for 250 message IDs
- [ ] Integration test: Real API call with 10 messages succeeds
- [ ] Error handling test: Partial batch failure handled gracefully
- [ ] Code reviewed and approved

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (performance-oracle agent)
**Actions:**
- Discovered N+1 query pattern during API analysis
- Calculated performance impact at various scales
- Identified as critical performance bottleneck
- Categorized as P1 priority

**Learnings:**
- N+1 patterns are critical performance anti-patterns
- Gmail Batch API can process 100 requests in single call
- Current implementation would take 80+ minutes for 10k emails
- Batch API implementation is straightforward with google-api-python-client
