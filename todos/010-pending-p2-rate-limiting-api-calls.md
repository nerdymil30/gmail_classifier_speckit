---
status: pending
priority: p2
issue_id: "010"
tags: [code-review, performance, high, rate-limiting, api]
dependencies: []
---

# Implement Rate Limiting on Gmail API Calls

## Problem Statement

Gmail API methods lack rate limiting despite having a rate limit decorator available in the codebase. Gmail API has a quota of 250 units/user/second, and batch operations can quickly exhaust this quota, causing 429 errors and temporary service blocks. The Claude API also lacks rate limiting, risking quota exhaustion and increased costs.

## Findings

**Discovered by:** performance-oracle agent during API usage analysis

**Location:** `src/gmail_classifier/services/gmail_client.py` (all API methods)

**Current State:**

**Rate Limit Decorator Exists But Unused:**
```python
# In lib/utils.py - decorator exists
@rate_limit(calls_per_second: float | None = None)
def rate_limited_function():
    ...

# But in gmail_client.py - not applied!
@retry_with_exponential_backoff()  # Has retry
def get_labels(self) -> list[Label]:  # Missing @rate_limit
    ...
```

**Gmail API Quotas:**
- 250 quota units per user per second
- 1 billion quota units per day
- Methods consume 1-5 units each
- Batch requests count as multiple units

**Risk Scenarios:**

1. **Rapid Batch Operations:**
   - Fetch 500 emails in quick succession
   - 500 API calls × 1 unit = 500 units
   - Exceeds 250 units/second quota
   - Result: 429 errors, backoff, slowdown

2. **Concurrent Sessions:**
   - Multiple classification runs
   - All hitting API simultaneously
   - Quota exhausted quickly

3. **Claude API:**
   - No rate limiting at all
   - Potential cost explosion
   - API throttling possible

**Risk Level:** HIGH - Service disruption from quota exhaustion

## Proposed Solutions

### Option 1: Apply Existing Rate Limit Decorator (RECOMMENDED)
**Pros:**
- Decorator already implemented and tested
- Simple application to methods
- Configurable rate limits
- Prevents quota exhaustion

**Cons:**
- May slow down operations slightly
- Need to tune rate limits

**Effort:** Small (1 hour)
**Risk:** Low

**Implementation:**

```python
# In gmail_client.py
from gmail_classifier.lib.utils import rate_limit

class GmailClient:
    """Client for interacting with Gmail API."""

    @rate_limit(calls_per_second=10)  # Conservative: 10 calls/sec = 600/min
    @retry_with_exponential_backoff()
    def get_labels(self) -> list[Label]:
        """Get user's Gmail labels with rate limiting."""
        with Timer("get_labels"):
            results = self.service.users().labels().list(userId="me").execute()
            ...

    @rate_limit(calls_per_second=10)
    @retry_with_exponential_backoff()
    def get_message(self, message_id: str) -> Email:
        """Get single message with rate limiting."""
        with Timer("get_message"):
            result = self.service.users().messages().get(...).execute()
            ...

    @rate_limit(calls_per_second=5)  # Lower for batch operations
    @retry_with_exponential_backoff()
    def get_messages_batch(self, message_ids: list[str]) -> list[Email]:
        """Get messages in batch with rate limiting."""
        # Batch API already efficient, rate limit the batch calls themselves
        ...

    @rate_limit(calls_per_second=10)
    @retry_with_exponential_backoff()
    def add_label_to_message(self, message_id: str, label_id: str) -> bool:
        """Add label to message with rate limiting."""
        ...

    @rate_limit(calls_per_second=5)
    @retry_with_exponential_backoff()
    def batch_add_labels(self, email_label_pairs: list[tuple[str, str]]) -> dict[str, bool]:
        """Batch add labels with rate limiting."""
        ...

# In claude_client.py
from gmail_classifier.lib.utils import rate_limit

class ClaudeClient:
    """Client for Claude API interactions."""

    @rate_limit(calls_per_second=2)  # Conservative for Claude API
    @retry_with_exponential_backoff()
    def classify_batch(self, emails: list[Email], available_labels: list[Label]):
        """Classify emails with rate limiting."""
        ...
```

**Rate Limit Configuration:**
```python
# In config.py
GMAIL_API_RATE_LIMIT: float = float(os.getenv("GMAIL_API_RATE_LIMIT", "10.0"))
CLAUDE_API_RATE_LIMIT: float = float(os.getenv("CLAUDE_API_RATE_LIMIT", "2.0"))

# Usage
@rate_limit(calls_per_second=Config.GMAIL_API_RATE_LIMIT)
```

### Option 2: Token Bucket Algorithm with Quota Tracking
**Pros:**
- More sophisticated rate limiting
- Tracks actual quota usage
- Can burst when quota available
- Professional implementation

**Cons:**
- More complex
- Need to track quota across methods
- Overkill for current needs

**Effort:** Medium (4-5 hours)
**Risk:** Low

**Implementation:**
```python
import time
from threading import Lock

class QuotaManager:
    """Manage API quota with token bucket algorithm."""

    def __init__(self, quota_per_second: float):
        self.quota_per_second = quota_per_second
        self.bucket_size = quota_per_second * 2  # Allow 2 seconds of burst
        self.tokens = self.bucket_size
        self.last_update = time.time()
        self.lock = Lock()

    def acquire(self, cost: int = 1) -> None:
        """Acquire quota tokens, block if insufficient."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update

            # Refill bucket
            self.tokens = min(
                self.bucket_size,
                self.tokens + (elapsed * self.quota_per_second)
            )
            self.last_update = now

            # Wait if insufficient tokens
            if self.tokens < cost:
                wait_time = (cost - self.tokens) / self.quota_per_second
                time.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= cost

# Usage
gmail_quota = QuotaManager(quota_per_second=250)

def get_message(self, message_id: str) -> Email:
    gmail_quota.acquire(cost=1)  # 1 quota unit
    result = self.service.users().messages().get(...).execute()
```

**Not Recommended** - Option 1 is sufficient and much simpler.

### Option 3: Reactive Rate Limiting (Backoff on 429)
**Pros:**
- No upfront rate limiting
- Full speed when quota available
- Simple implementation

**Cons:**
- Only reacts after quota exceeded
- Causes user-visible delays
- Less predictable performance

**Effort:** Small (30 minutes)
**Risk:** Medium

**Not Recommended** - Proactive rate limiting is better UX.

## Recommended Action

**Implement Option 1** - Apply existing `@rate_limit` decorator to all API methods with conservative defaults.

**Configuration Strategy:**
- Gmail API: 10 calls/second (40% of quota, safe margin)
- Claude API: 2 calls/second (conservative, adjust based on tier)
- Allow override via environment variables

## Technical Details

**Affected Files:**
- `src/gmail_classifier/services/gmail_client.py` (all API methods)
- `src/gmail_classifier/services/claude_client.py` (classification methods)
- `src/gmail_classifier/lib/config.py` (add rate limit configs)

**Related Components:**
- Email fetching
- Label operations
- Classification operations
- All external API calls

**Database Changes:** No

**Methods to Rate Limit:**

**Gmail API (10 calls/second):**
- `get_labels()`
- `get_message()`
- `get_user_labels()`
- `add_label_to_message()`
- `remove_label_from_message()`
- `modify_message_labels()`

**Gmail API (5 calls/second - batch operations):**
- `get_messages_batch()`
- `batch_add_labels()`

**Claude API (2 calls/second):**
- `classify_batch()`

## Resources

- [Gmail API Quotas](https://developers.google.com/gmail/api/reference/quota)
- [Rate Limiting Patterns](https://www.cloudflare.com/learning/bots/what-is-rate-limiting/)
- [Token Bucket Algorithm](https://en.wikipedia.org/wiki/Token_bucket)
- [Claude API Rate Limits](https://docs.anthropic.com/claude/reference/rate-limits)
- Related findings: 004-pending-p1-gmail-batch-api.md

## Acceptance Criteria

- [ ] `@rate_limit` decorator applied to all Gmail API methods
- [ ] `@rate_limit` decorator applied to Claude API methods
- [ ] Rate limits configurable via environment variables
- [ ] Conservative defaults set (Gmail: 10/sec, Claude: 2/sec)
- [ ] Configuration added to config.py
- [ ] Unit test: Rate limiting enforced (multiple calls delayed)
- [ ] Unit test: Rate limit configurable via env var
- [ ] Integration test: 100 API calls complete without 429 errors
- [ ] Manual test: Monitor API call timing with logging
- [ ] Documentation: Rate limit configuration in README

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (performance-oracle agent)
**Actions:**
- Discovered rate limit decorator exists but unused
- Analyzed Gmail API quota limits
- Identified risk of quota exhaustion in batch operations
- Categorized as P2 high priority

**Learnings:**
- Gmail API has 250 units/user/second quota
- Batch operations can quickly exhaust quota
- Proactive rate limiting prevents 429 errors
- Existing decorator infrastructure makes fix simple
- Conservative defaults better than aggressive tuning
