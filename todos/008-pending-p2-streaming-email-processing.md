---
status: pending
priority: p2
issue_id: "008"
tags: [code-review, performance, high, memory, scalability]
dependencies: [004-pending-p1-gmail-batch-api]
---

# Implement Streaming/Pagination for Email Processing

## Problem Statement

The email classification workflow loads ALL emails into memory before processing, causing unbounded memory growth. At 100,000 emails, memory usage reaches 500MB-1GB, risking OOM crashes and making the application unsuitable for large-scale deployments.

## Findings

**Discovered by:** performance-oracle agent during scalability analysis

**Location:** `src/gmail_classifier/services/classifier.py:93-95`

**Current Code:**
```python
# Fetch unlabeled emails
logger.info("Fetching unlabeled emails")
unlabeled_emails = self.gmail_client.get_unlabeled_emails(max_results=max_emails)
# ALL emails loaded into memory at once!
```

**Memory Analysis:**

| Email Count | Memory Usage | Status |
|-------------|--------------|--------|
| 1,000 | ~5-10 MB | Acceptable |
| 10,000 | ~50-100 MB | Concerning |
| 100,000 | ~500 MB - 1 GB | Unacceptable |
| 1,000,000 | ~5-10 GB | Crash/OOM |

**Additional Memory Issues:**
- Email bodies (plain + HTML) stored in full
- Bodies sent to Claude but kept in memory after processing
- No garbage collection between batches
- Session object grows without bounds

**Risk Level:** HIGH - Application unusable for large email volumes

## Proposed Solutions

### Option 1: Pagination with Incremental Processing (RECOMMENDED)
**Pros:**
- Bounded memory usage (only one page in memory)
- Scalable to millions of emails
- Can resume from interruption
- Minimal architectural changes

**Cons:**
- More complex control flow
- Need to track pagination state

**Effort:** Medium (4-5 hours)
**Risk:** Low

**Implementation:**

```python
def classify_unlabeled_emails(
    self,
    max_emails: int | None = None,
    dry_run: bool = True,
    page_size: int = 100
) -> ProcessingSession:
    """Classify emails using pagination to limit memory usage.

    Args:
        max_emails: Maximum number of emails to process (None = all)
        dry_run: If True, don't apply labels to Gmail
        page_size: Number of emails to fetch per page (default 100)

    Returns:
        Processing session with results
    """
    # Initialize session
    session = self._initialize_session(dry_run)

    # Fetch user labels (cached)
    user_labels = self._get_cached_labels()

    # Get total count for progress tracking
    total_unlabeled = self.gmail_client.count_unlabeled_emails()
    session.total_emails_to_process = min(total_unlabeled, max_emails) if max_emails else total_unlabeled

    processed = 0
    page_token = None

    with Timer("email_classification"):
        while True:
            # Check if we've hit max_emails limit
            if max_emails and processed >= max_emails:
                break

            # Calculate page size for this iteration
            remaining = max_emails - processed if max_emails else page_size
            current_page_size = min(page_size, remaining)

            # Fetch one page of message IDs
            logger.info(f"Fetching page of up to {current_page_size} emails (token: {page_token})")
            message_ids, next_page_token = self.gmail_client.list_unlabeled_messages(
                max_results=current_page_size,
                page_token=page_token
            )

            if not message_ids:
                logger.info("No more unlabeled emails found")
                break

            # Fetch full messages (using batch API)
            emails = self.gmail_client.get_messages_batch(message_ids)
            logger.info(f"Processing {len(emails)} emails")

            # Classify batch with Claude
            suggestions = self.claude_client.classify_batch(emails, user_labels)

            # Save suggestions and update session
            for suggestion in suggestions:
                self.session_db.save_suggestion(session.id, suggestion)
                session.increment_generated()

            session.emails_processed += len(emails)
            session.last_processed_email_id = emails[-1].id if emails else None

            # Free memory before next iteration
            del emails
            del suggestions

            # Auto-save progress
            if session.emails_processed % Config.AUTO_SAVE_FREQUENCY == 0:
                self.session_db.save_session(session)
                logger.info(f"Progress: {session.emails_processed}/{session.total_emails_to_process}")

            processed += len(message_ids)
            page_token = next_page_token

            # Break if no more pages
            if not page_token:
                break

    # Mark session complete
    session.complete()
    self.session_db.save_session(session)

    logger.info(
        f"Classification complete: {session.emails_processed} emails processed, "
        f"{session.suggestions_generated} suggestions generated"
    )

    return session
```

**Gmail Client Changes:**
```python
# In gmail_client.py
@retry_with_exponential_backoff()
def list_unlabeled_messages(
    self,
    max_results: int = 100,
    page_token: str | None = None
) -> tuple[list[str], str | None]:
    """List unlabeled message IDs with pagination.

    Args:
        max_results: Maximum number of message IDs to return
        page_token: Token for next page (from previous call)

    Returns:
        Tuple of (message_ids, next_page_token)
    """
    with Timer("list_unlabeled_messages"):
        results = (
            self.service.users()
            .messages()
            .list(
                userId="me",
                maxResults=max_results,
                pageToken=page_token,
                q="is:unlabeled OR (-in:spam -in:trash -category:*)"
            )
            .execute()
        )

        messages = results.get("messages", [])
        message_ids = [msg["id"] for msg in messages]
        next_page_token = results.get("nextPageToken")

        logger.debug(
            f"Listed {len(message_ids)} message IDs, "
            f"has_more: {next_page_token is not None}"
        )

        return message_ids, next_page_token

@retry_with_exponential_backoff()
def count_unlabeled_emails(self) -> int:
    """Get count of unlabeled emails (for progress tracking)."""
    # Gmail doesn't provide direct count, estimate from first page
    results = self.service.users().messages().list(
        userId="me",
        maxResults=1,
        q="is:unlabeled OR (-in:spam -in:trash -category:*)"
    ).execute()

    return results.get("resultSizeEstimate", 0)
```

### Option 2: Generator-Based Streaming
**Pros:**
- Very memory efficient
- Pythonic pattern
- Can be piped through other generators

**Cons:**
- Requires significant refactoring
- Session management more complex
- Error recovery harder

**Effort:** Large (2-3 days)
**Risk:** Medium

**Not Recommended** - Option 1 provides sufficient improvement with less risk.

### Option 3: Explicit Memory Management with gc
**Pros:**
- Can be added to existing code
- Forces garbage collection

**Cons:**
- Band-aid solution
- Doesn't prevent memory growth
- Performance overhead from forced GC

**Effort:** Small (30 minutes)
**Risk:** Low

**Not Recommended** - Doesn't solve root cause.

## Recommended Action

**Implement Option 1** - Pagination with incremental processing. This provides bounded memory usage while maintaining code clarity.

**Additional Optimizations:**
1. Truncate email bodies after sending to Claude (line 150 in classifier.py)
2. Use `__slots__` in Email dataclass to reduce per-instance memory
3. Add memory usage monitoring

## Technical Details

**Affected Files:**
- `src/gmail_classifier/services/classifier.py` (lines 56-177, `classify_unlabeled_emails`)
- `src/gmail_classifier/services/gmail_client.py` (add pagination methods)

**Related Components:**
- Email fetching workflow
- Session progress tracking
- Auto-save mechanism

**Database Changes:** No schema changes

**Dependencies:**
- Depends on 004-pending-p1-gmail-batch-api.md for efficient fetching

**Memory Target:** < 50 MB peak for any email volume

## Resources

- [Python Memory Management](https://realpython.com/python-memory-management/)
- [Gmail API Pagination](https://developers.google.com/gmail/api/guides/pagination)
- [Memory Profiling in Python](https://docs.python.org/3/library/tracemalloc.html)
- Related findings: 004-pending-p1-gmail-batch-api.md

## Acceptance Criteria

- [ ] `list_unlabeled_messages()` method with pagination implemented
- [ ] `classify_unlabeled_emails()` refactored for page-by-page processing
- [ ] Email objects freed after each batch
- [ ] Session tracking supports resumption from page_token
- [ ] Memory usage benchmark: Process 10,000 emails using < 100 MB peak
- [ ] Unit test: Pagination works correctly across multiple pages
- [ ] Unit test: max_emails limit respected across pages
- [ ] Integration test: Process 1,000 emails, verify memory stays bounded
- [ ] Manual test: Monitor memory with `tracemalloc` during 5,000 email run
- [ ] Progress logging shows X/Y emails processed

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (performance-oracle agent)
**Actions:**
- Discovered unbounded memory growth during scalability analysis
- Calculated memory usage at various email counts
- Identified as blocker for large-scale deployment
- Categorized as P2 high priority

**Learnings:**
- Loading all data into memory is common anti-pattern
- Pagination is standard solution for scalability
- Gmail API supports pagination via pageToken
- Memory profiling essential for understanding usage patterns
