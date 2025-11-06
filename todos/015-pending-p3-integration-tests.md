---
status: pending
priority: p3
issue_id: "015"
tags: [code-review, testing, medium, quality-assurance]
dependencies: []
---

# Add Comprehensive Integration Tests

## Problem Statement

The test suite contains 85+ unit tests and contract tests, but lacks integration tests that verify end-to-end workflows. Critical gaps include: no tests for complete classification workflows, no tests for Gmail/database consistency, no tests for error recovery across system boundaries, and no performance benchmarks.

## Findings

**Discovered by:** Testing analysis during code review

**Current Test Coverage:**
- **Unit tests:** 85+ tests (email.py, label.py, suggestion.py, utils.py)
- **Contract tests:** 9 tests (test_gmail_api.py)
- **Integration tests:** 0 tests ❌
- **Performance tests:** 0 tests ❌

**Missing Test Coverage:**

1. **End-to-End Classification Workflow**
   - Auth → Fetch emails → Classify → Save → Apply
   - No test verifies complete flow

2. **Gmail/Database Consistency**
   - No test for race condition scenarios
   - No test for compensating transactions
   - No test for state reconciliation

3. **Error Recovery**
   - No test for network failures mid-classification
   - No test for disk full during save
   - No test for API quota exhaustion

4. **Performance Benchmarks**
   - No test measuring actual classification speed
   - No test measuring memory usage
   - No test measuring database query performance

5. **Configuration Integration**
   - No test that environment variables work correctly
   - No test that invalid config prevents startup

**Risk Level:** MEDIUM - Incomplete test coverage, integration bugs not caught

## Proposed Solutions

### Option 1: pytest Integration Test Suite (RECOMMENDED)
**Pros:**
- Uses existing pytest infrastructure
- Can use fixtures from conftest.py
- Easy to run with `pytest tests/integration/`
- Standard Python approach

**Cons:**
- Need to mock external APIs carefully
- Integration tests slower than unit tests

**Effort:** Large (1-2 days to create comprehensive suite)
**Risk:** Low

**Implementation:**

**Directory Structure:**
```
tests/
├── unit/              # Existing
├── contract/          # Existing
├── integration/       # NEW
│   ├── __init__.py
│   ├── test_classification_workflow.py
│   ├── test_gmail_db_consistency.py
│   ├── test_error_recovery.py
│   ├── test_configuration.py
│   └── test_cli_commands.py
└── performance/       # NEW
    ├── __init__.py
    ├── test_email_fetching_performance.py
    ├── test_classification_performance.py
    └── test_memory_usage.py
```

**Example: `tests/integration/test_classification_workflow.py`**
```python
"""Integration tests for complete classification workflow."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile

from gmail_classifier.services.classifier import EmailClassifier
from gmail_classifier.services.gmail_client import GmailClient
from gmail_classifier.services.claude_client import ClaudeClient
from gmail_classifier.lib.session_db import SessionDatabase
from gmail_classifier.models.email import Email
from gmail_classifier.models.label import Label


@pytest.fixture
def temp_db():
    """Temporary database for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sessions.db"
        db = SessionDatabase(db_path)
        yield db
        db.close()


@pytest.fixture
def mock_gmail_client():
    """Mock Gmail client with realistic data."""
    client = Mock(spec=GmailClient)

    # Mock labels
    client.get_user_labels.return_value = [
        Label(id="Label_1", name="Work", email_count=10, type="user"),
        Label(id="Label_2", name="Personal", email_count=5, type="user"),
    ]

    # Mock emails
    client.get_unlabeled_emails.return_value = [
        Email(
            id="msg_1",
            thread_id="thread_1",
            subject="Project Update",
            sender="boss@company.com",
            sender_name="Boss",
            recipients=["me@company.com"],
            date="2025-01-01T10:00:00Z",
            labels=["INBOX"],
            snippet="Quick project status...",
            content="Let me know about the project status.",
            body_plain="Let me know about the project status.",
            body_html=None
        ),
        Email(
            id="msg_2",
            thread_id="thread_2",
            subject="Weekend Plans",
            sender="friend@personal.com",
            sender_name="Friend",
            recipients=["me@personal.com"],
            date="2025-01-01T11:00:00Z",
            labels=["INBOX"],
            snippet="Hey, want to hang out...",
            content="Hey, want to hang out this weekend?",
            body_plain="Hey, want to hang out this weekend?",
            body_html=None
        ),
    ]

    return client


@pytest.fixture
def mock_claude_client():
    """Mock Claude client with realistic classifications."""
    from gmail_classifier.models.suggestion import ClassificationSuggestion, SuggestedLabel

    client = Mock(spec=ClaudeClient)

    def classify_batch(emails, labels):
        """Return realistic suggestions."""
        return [
            ClassificationSuggestion(
                email_id=emails[0].id,
                suggested_labels=[
                    SuggestedLabel("Label_1", "Work", 0.9, 1, "Work-related email from boss")
                ],
                confidence_category="high",
                reasoning="Email from boss about project",
            ),
            ClassificationSuggestion(
                email_id=emails[1].id,
                suggested_labels=[
                    SuggestedLabel("Label_2", "Personal", 0.85, 1, "Personal conversation")
                ],
                confidence_category="high",
                reasoning="Personal email from friend",
            ),
        ]

    client.classify_batch.side_effect = classify_batch
    return client


class TestCompleteClassificationWorkflow:
    """Test complete end-to-end classification workflow."""

    def test_full_classification_dry_run(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test complete dry-run classification workflow."""
        # Create classifier with mocked dependencies
        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(
            max_emails=10,
            dry_run=True
        )

        # Verify workflow steps
        assert session.status == "completed"
        assert session.emails_processed == 2
        assert session.suggestions_generated == 2
        assert session.is_dry_run is True

        # Verify labels were fetched
        mock_gmail_client.get_user_labels.assert_called_once()

        # Verify emails were fetched
        mock_gmail_client.get_unlabeled_emails.assert_called_once()

        # Verify Claude was called
        mock_claude_client.classify_batch.assert_called_once()

        # Verify session saved to database
        loaded_session = temp_db.load_session(session.id)
        assert loaded_session is not None
        assert loaded_session.id == session.id

        # Verify suggestions saved
        suggestions = temp_db.load_suggestions(session.id)
        assert len(suggestions) == 2

    def test_full_classification_with_apply(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test classification with label application."""
        # Mock label application
        mock_gmail_client.add_label_to_message.return_value = True

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Dry run
        session = classifier.classify_unlabeled_emails(
            max_emails=10,
            dry_run=True
        )

        # Apply suggestions
        results = classifier.apply_suggestions(session.id)

        assert results["applied"] == 2
        assert results["failed"] == 0

        # Verify labels were applied via Gmail API
        assert mock_gmail_client.add_label_to_message.call_count == 2

        # Verify suggestions marked as applied in database
        suggestions = temp_db.load_suggestions(session.id, status="applied")
        assert len(suggestions) == 2

    def test_classification_with_network_error(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test error recovery when network fails mid-classification."""
        # Simulate network error on second batch
        call_count = 0

        def classify_with_failure(emails, labels):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ConnectionError("Network timeout")
            # First call succeeds
            return [
                ClassificationSuggestion(...) for email in emails
            ]

        mock_claude_client.classify_batch.side_effect = classify_with_failure

        # Mock paginated email fetching
        mock_gmail_client.get_unlabeled_emails.side_effect = [
            [Email(...)],  # First batch
            [Email(...)],  # Second batch (will fail)
        ]

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Classification should handle error gracefully
        session = classifier.classify_unlabeled_emails(max_emails=10, dry_run=True)

        # Verify partial success
        assert session.status == "failed"
        assert session.emails_processed >= 1  # At least first batch processed
        assert len(session.error_log) > 0

        # Verify session saved with error state
        loaded_session = temp_db.load_session(session.id)
        assert loaded_session.status == "failed"


class TestGmailDatabaseConsistency:
    """Test Gmail API and database stay consistent."""

    def test_label_applied_but_db_fails(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test handling when label applied to Gmail but DB update fails."""
        # Setup: Create session with suggestions
        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        session = classifier.classify_unlabeled_emails(max_emails=1, dry_run=True)

        # Mock successful label application
        mock_gmail_client.add_label_to_message.return_value = True

        # Mock database failure
        original_update = temp_db.update_suggestion_status

        def failing_update(*args, **kwargs):
            raise IOError("Disk full")

        temp_db.update_suggestion_status = failing_update

        # Apply suggestions should handle DB failure
        with pytest.raises(IOError):
            classifier.apply_suggestions(session.id)

        # Verify inconsistency logged
        # (Check audit log in real implementation)

    def test_reconciliation_detects_mismatches(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test state reconciliation detects Gmail/DB mismatches."""
        # This test validates the reconciliation command from todo #006
        # Implementation depends on that todo being completed
        pytest.skip("Requires reconciliation feature from todo #006")
```

**Example: `tests/performance/test_classification_performance.py`**
```python
"""Performance benchmarks for classification."""

import pytest
import time
from unittest.mock import Mock

from gmail_classifier.services.classifier import EmailClassifier
from gmail_classifier.models.email import Email


@pytest.mark.performance
class TestClassificationPerformance:
    """Performance benchmarks."""

    def test_classification_speed_100_emails(self, mock_gmail_client, mock_claude_client):
        """Benchmark: Classify 100 emails in reasonable time."""
        # Generate 100 test emails
        emails = [
            Email(
                id=f"msg_{i}",
                thread_id=f"thread_{i}",
                subject=f"Test Email {i}",
                sender=f"sender{i}@test.com",
                sender_name=f"Sender {i}",
                recipients=["me@test.com"],
                date="2025-01-01T10:00:00Z",
                labels=["INBOX"],
                snippet="Test snippet",
                content=f"Test content {i}",
                body_plain=f"Test content {i}",
                body_html=None
            )
            for i in range(100)
        ]

        mock_gmail_client.get_unlabeled_emails.return_value = emails

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client
        )

        # Benchmark
        start_time = time.time()
        session = classifier.classify_unlabeled_emails(max_emails=100, dry_run=True)
        elapsed = time.time() - start_time

        # Performance assertions
        assert session.emails_processed == 100
        assert elapsed < 30.0, f"Classification took {elapsed:.2f}s, expected < 30s"

        # Log performance
        print(f"\nPerformance: Classified 100 emails in {elapsed:.2f}s")
        print(f"Throughput: {100/elapsed:.1f} emails/second")

    @pytest.mark.slow
    def test_memory_usage_1000_emails(self):
        """Benchmark: Memory usage stays bounded with 1000 emails."""
        import tracemalloc

        tracemalloc.start()

        # Run classification with 1000 emails
        # ... implementation ...

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Memory assertions
        peak_mb = peak / 1024 / 1024
        assert peak_mb < 100, f"Peak memory {peak_mb:.1f} MB exceeded limit"

        print(f"\nMemory: Peak usage {peak_mb:.1f} MB for 1000 emails")
```

**Running Integration Tests:**
```bash
# Run only integration tests
pytest tests/integration/ -v

# Run performance tests (marked @pytest.mark.performance)
pytest -m performance

# Run integration tests with coverage
pytest tests/integration/ --cov=gmail_classifier --cov-report=html
```

### Option 2: Docker-Based Integration Tests
**Pros:**
- Real database instances
- Can test with actual Gmail API (sandbox)
- Isolated test environment

**Cons:**
- Requires Docker
- More complex setup
- Slower to run

**Effort:** Large (2-3 days)
**Risk:** Medium

**Not Recommended** - Option 1 sufficient for current needs.

## Recommended Action

**Implement Option 1** - pytest integration test suite with comprehensive coverage.

**Test Priority:**
1. Complete classification workflow (P1)
2. Error recovery scenarios (P1)
3. Gmail/DB consistency (P1)
4. Performance benchmarks (P2)
5. Configuration integration (P2)

## Technical Details

**Affected Files:**
- `tests/integration/` (NEW DIRECTORY)
- `tests/performance/` (NEW DIRECTORY)
- `tests/conftest.py` (add integration test fixtures)
- `pytest.ini` or `pyproject.toml` (add performance markers)

**Related Components:**
- All services
- Database operations
- CLI commands
- Configuration

**Database Changes:** No

**New Dependencies:**
```toml
[project.optional-dependencies]
dev = [
    # ... existing ...
    "pytest-benchmark>=4.0.0",  # For performance tests
]
```

## Resources

- [pytest Integration Testing](https://docs.pytest.org/en/stable/how-to/usage.html)
- [pytest Markers](https://docs.pytest.org/en/stable/how-to/mark.html)
- [Python Testing Best Practices](https://realpython.com/python-testing/)
- Related findings: Testing gaps in detailed review

## Acceptance Criteria

- [ ] `tests/integration/` directory created
- [ ] `tests/performance/` directory created
- [ ] `test_classification_workflow.py` with 5+ integration tests
- [ ] `test_gmail_db_consistency.py` with consistency tests
- [ ] `test_error_recovery.py` with failure scenarios
- [ ] `test_configuration.py` with config validation tests
- [ ] `test_cli_commands.py` with CLI integration tests
- [ ] Performance benchmark for 100 emails
- [ ] Memory usage benchmark for 1000 emails
- [ ] All integration tests pass
- [ ] pytest markers configured (@pytest.mark.integration, @pytest.mark.performance)
- [ ] CI/CD runs integration tests
- [ ] Documentation: How to run integration tests

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (testing analysis)
**Actions:**
- Discovered missing integration test coverage
- Identified critical workflow gaps in test suite
- Noted lack of performance benchmarks
- Categorized as P3 medium priority (quality assurance)

**Learnings:**
- Unit tests alone insufficient for complex workflows
- Integration tests catch system boundary issues
- Performance tests prevent regressions
- End-to-end tests provide confidence for production
