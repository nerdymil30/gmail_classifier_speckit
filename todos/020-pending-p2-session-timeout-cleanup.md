---
status: resolved
priority: p2
issue_id: "020"
tags: [security, performance, memory-leak, resource-management, imap]
dependencies: []
---

# Session Timeout Without Automatic Cleanup

## Problem Statement

The `IMAPSessionInfo.is_stale()` method detects sessions inactive for >25 minutes, but there's **no automatic cleanup mechanism**. Stale sessions accumulate in the `_sessions` dictionary, consuming memory and leaving connections open indefinitely. This creates both a memory leak and a security vulnerability (connection pool exhaustion DoS).

**Impact:** Memory leaks, resource exhaustion, potential denial of service
**CWE:** CWE-400 (Uncontrolled Resource Consumption)

## Findings

**Location:** `src/gmail_classifier/auth/imap.py:178-188`

**Current Implementation:**
```python
def is_stale(self, timeout_minutes: int = 25) -> bool:
    """Check if session is stale (no activity beyond timeout)."""
    from datetime import timedelta
    return (datetime.now() - self.last_activity) > timedelta(minutes=timeout_minutes)

# Sessions are DETECTED as stale but NEVER automatically cleaned up
# Manual cleanup required via explicit disconnect() calls
```

**Attack/Failure Scenario:**
1. User creates 100 IMAP sessions (legitimate or attack)
2. Sessions become stale after 25 minutes of inactivity
3. No automatic cleanup runs
4. Sessions accumulate in `_sessions` dict consuming memory
5. IMAP server maintains 100 open connections
6. Eventually: Out of memory OR connection pool exhausted

**Memory Leak Calculation:**
- Each session: ~10KB (connection object, metadata, buffers)
- 1000 stale sessions: ~10MB leaked
- Long-running CLI process: Unlimited accumulation

## Proposed Solutions

### Option 1: Background Cleanup Thread (RECOMMENDED)

**Pros:**
- Automatic, no manual intervention
- Runs independently of main operations
- Session limits prevent abuse
- Standard pattern for long-running processes

**Cons:**
- Adds threading complexity
- Daemon thread stops on process exit (acceptable)

**Effort:** Medium (2 hours)
**Risk:** Low (daemon thread, safe cleanup)

**Implementation:**
```python
import threading
import time
from collections import defaultdict

class IMAPAuthenticator:
    def __init__(
        self,
        server: str = "imap.gmail.com",
        port: int = 993,
    ) -> None:
        self._sessions: dict[uuid.UUID, IMAPSessionInfo] = {}
        self._logger = logger
        self._server = server
        self._port = port
        self._cleanup_lock = threading.Lock()

        # Start background cleanup thread
        self._start_cleanup_thread()

    def _start_cleanup_thread(self) -> None:
        """Start background thread for automatic session cleanup."""
        def cleanup_worker():
            while True:
                time.sleep(300)  # Check every 5 minutes
                self._cleanup_stale_sessions()

        cleanup_thread = threading.Thread(
            target=cleanup_worker,
            daemon=True,
            name="imap-session-cleanup"
        )
        cleanup_thread.start()
        self._logger.info("Started IMAP session cleanup thread")

    def _cleanup_stale_sessions(self) -> None:
        """Remove and disconnect stale sessions."""
        with self._cleanup_lock:
            stale_sessions = [
                session_id
                for session_id, session_info in self._sessions.items()
                if session_info.is_stale(timeout_minutes=25)
            ]

            for session_id in stale_sessions:
                try:
                    self._logger.warning(
                        f"Auto-cleaning stale session: {session_id}"
                    )
                    self.disconnect(session_id)
                except Exception as e:
                    self._logger.error(
                        f"Failed to cleanup session {session_id}: {e}"
                    )
                    # Force removal even if disconnect fails
                    self._sessions.pop(session_id, None)

            if stale_sessions:
                self._logger.info(
                    f"Cleaned up {len(stale_sessions)} stale sessions"
                )
```

### Option 2: Session Limit per Email (Additional Protection)

Prevent session accumulation attacks:

```python
MAX_SESSIONS_PER_EMAIL = 5

def authenticate(self, credentials: IMAPCredentials) -> IMAPSessionInfo:
    # Check session count for this email
    active_sessions = [
        s for s in self._sessions.values()
        if s.email == credentials.email and s.state == SessionState.CONNECTED
    ]

    if len(active_sessions) >= MAX_SESSIONS_PER_EMAIL:
        # Disconnect oldest session
        oldest = min(active_sessions, key=lambda s: s.connected_at)
        self._logger.warning(
            f"Session limit ({MAX_SESSIONS_PER_EMAIL}) reached for {credentials.email}. "
            f"Disconnecting oldest session: {oldest.session_id}"
        )
        self.disconnect(oldest.session_id)

    # Continue with authentication...
```

## Recommended Action

1. **Implement background cleanup thread** (Option 1)
2. **Add session limit per email** (Option 2)
3. **Add cleanup metrics** for monitoring
4. **Test cleanup runs correctly**

## Technical Details

**Affected Files:**
- `src/gmail_classifier/auth/imap.py` - IMAPAuthenticator class

**Related Components:**
- All IMAP session management
- disconnect() method
- is_stale() method

**Database Changes:** No

**Configuration:**
```python
# Add to IMAPConfig (if implemented)
cleanup_interval_seconds: int = 300  # 5 minutes
stale_timeout_minutes: int = 25
max_sessions_per_email: int = 5
```

**Monitoring:**
```python
def get_session_stats(self) -> dict:
    """Get session statistics for monitoring."""
    active = sum(1 for s in self._sessions.values() if s.state == SessionState.CONNECTED)
    stale = sum(1 for s in self._sessions.values() if s.is_stale())

    return {
        "total_sessions": len(self._sessions),
        "active_sessions": active,
        "stale_sessions": stale,
    }
```

## Resources

- **CWE-400:** https://cwe.mitre.org/data/definitions/400.html
- **Python Threading:** https://docs.python.org/3/library/threading.html
- **Daemon Threads:** https://docs.python.org/3/library/threading.html#thread-objects

## Acceptance Criteria

- [ ] Background cleanup thread implemented
- [ ] Thread runs as daemon (stops on process exit)
- [ ] Cleanup runs every 5 minutes
- [ ] Stale sessions (>25 min) automatically cleaned
- [ ] Session limit (5 per email) enforced
- [ ] Lock protects concurrent access to _sessions dict
- [ ] Cleanup failures don't crash thread
- [ ] Force removal if disconnect fails
- [ ] Test: Stale sessions cleaned after timeout
- [ ] Test: Cleanup thread runs in background
- [ ] Test: Session limit prevents accumulation
- [ ] All existing tests pass

## Work Log

### 2025-11-08 - Initial Discovery
**By:** Claude Multi-Agent Review System
**Actions:**
- Issue discovered during security and performance audit
- Categorized as P2 High (security + performance)
- Estimated effort: 2 hours

**Learnings:**
- is_stale() detects but doesn't clean
- Long-running processes accumulate sessions
- Memory leaks in CLI if user runs for days
- Connection pool exhaustion possible
- Standard pattern: background cleanup thread
- Daemon threads perfect for this (auto-stop on exit)

### 2025-11-08 - Implementation Complete
**By:** Claude Code
**Actions:**
- Implemented background cleanup thread (daemon, runs every 5 minutes)
- Added session limit enforcement (5 per email, disconnects oldest)
- Added get_session_stats() monitoring method
- Created comprehensive test suite (13 tests, all passing)
- All acceptance criteria met

**Changes Made:**
- `/home/user/gmail_classifier_speckit/src/gmail_classifier/auth/imap.py`:
  - Added constants: CLEANUP_INTERVAL_SECONDS, STALE_TIMEOUT_MINUTES, MAX_SESSIONS_PER_EMAIL
  - Added imports: threading, time
  - Added _cleanup_lock to __init__ for thread safety
  - Added _start_cleanup_thread() method
  - Added _cleanup_stale_sessions() method
  - Added get_session_stats() monitoring method
  - Updated authenticate() to enforce session limits

- `/home/user/gmail_classifier_speckit/tests/unit/test_imap_cleanup.py`: Created comprehensive test suite

**Learnings:**
- Daemon threads automatically stop when main process exits
- Lock-based thread safety essential for shared data structures
- Session limits prevent resource exhaustion attacks
- Monitoring metrics critical for production observability

## Notes

**Source:** IMAP Implementation Security & Performance Review - 2025-11-08
**Review Agents:** Security-Sentinel, Performance-Oracle
**Priority Justification:** Prevents memory leaks and DoS attacks
**Production Blocker:** NO - but important for production stability
