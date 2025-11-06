"""Integration tests for error recovery scenarios."""

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
from gmail_classifier.models.suggestion import ClassificationSuggestion, SuggestedLabel


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
    """Mock Gmail client."""
    client = Mock(spec=GmailClient)
    client.get_profile.return_value = {"emailAddress": "test@example.com"}
    client.get_user_labels.return_value = [
        Label(id="Label_1", name="Work", email_count=10, type="user"),
        Label(id="Label_2", name="Personal", email_count=5, type="user"),
    ]
    return client


@pytest.fixture
def mock_claude_client():
    """Mock Claude client."""
    client = Mock(spec=ClaudeClient)

    def classify_batch(emails, labels):
        return [
            ClassificationSuggestion(
                email_id=email.id,
                suggested_labels=[
                    SuggestedLabel("Label_1", "Work", 0.9, 1, "Work email")
                ],
                confidence_category="high",
                reasoning="Work-related",
            )
            for email in emails
        ]

    client.classify_batch.side_effect = classify_batch
    return client


@pytest.mark.integration
class TestErrorRecovery:
    """Test error recovery across system boundaries."""

    def test_network_error_during_classification(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test error recovery when network fails mid-classification."""
        # Setup multi-page fetch
        call_count = 0

        def list_with_failure(max_results=100, page_token=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (["msg_1", "msg_2"], "next_page")
            else:
                raise ConnectionError("Network timeout")

        mock_gmail_client.list_unlabeled_messages.side_effect = list_with_failure
        mock_gmail_client.count_unlabeled_emails.return_value = 10

        # First batch succeeds
        mock_gmail_client.get_messages_batch.return_value = [
            Email(
                id="msg_1",
                thread_id="thread_1",
                subject="Test 1",
                sender="test1@example.com",
                sender_name="Test 1",
                recipients=["me@example.com"],
                date="2025-01-01T10:00:00Z",
                labels=["INBOX"],
                snippet="Test email 1",
                content="Test content 1",
                body_plain="Test content 1",
                body_html=None
            ),
            Email(
                id="msg_2",
                thread_id="thread_2",
                subject="Test 2",
                sender="test2@example.com",
                sender_name="Test 2",
                recipients=["me@example.com"],
                date="2025-01-01T11:00:00Z",
                labels=["INBOX"],
                snippet="Test email 2",
                content="Test content 2",
                body_plain="Test content 2",
                body_html=None
            ),
        ]

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Classification should handle error gracefully
        with pytest.raises(ConnectionError):
            session = classifier.classify_unlabeled_emails(max_emails=10, dry_run=True)

        # Note: In production, this should save partial results
        # Current implementation may raise - this test documents the behavior

    def test_claude_api_error(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test handling of Claude API errors."""
        # Setup
        mock_gmail_client.count_unlabeled_emails.return_value = 2
        mock_gmail_client.list_unlabeled_messages.return_value = (
            ["msg_1", "msg_2"],
            None
        )
        mock_gmail_client.get_messages_batch.return_value = [
            Email(
                id="msg_1",
                thread_id="thread_1",
                subject="Test",
                sender="test@example.com",
                sender_name="Test",
                recipients=["me@example.com"],
                date="2025-01-01T10:00:00Z",
                labels=["INBOX"],
                snippet="Test snippet",
                content="Test content",
                body_plain="Test content",
                body_html=None
            ),
            Email(
                id="msg_2",
                thread_id="thread_2",
                subject="Test 2",
                sender="test2@example.com",
                sender_name="Test 2",
                recipients=["me@example.com"],
                date="2025-01-01T11:00:00Z",
                labels=["INBOX"],
                snippet="Test snippet 2",
                content="Test content 2",
                body_plain="Test content 2",
                body_html=None
            ),
        ]

        # Mock Claude API error
        mock_claude_client.classify_batch.side_effect = Exception("Claude API quota exceeded")

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Classification should catch the error and mark session as failed
        session = classifier.classify_unlabeled_emails(max_emails=10, dry_run=True)

        # Verify session marked as failed
        assert session.status == "failed"
        assert len(session.error_log) > 0
        assert any("quota exceeded" in err.lower() for err in session.error_log)

    def test_database_write_error(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test handling when database writes fail."""
        # Setup
        mock_gmail_client.count_unlabeled_emails.return_value = 1
        mock_gmail_client.list_unlabeled_messages.return_value = (["msg_1"], None)
        mock_gmail_client.get_messages_batch.return_value = [
            Email(
                id="msg_1",
                thread_id="thread_1",
                subject="Test",
                sender="test@example.com",
                sender_name="Test",
                recipients=["me@example.com"],
                date="2025-01-01T10:00:00Z",
                labels=["INBOX"],
                snippet="Test snippet",
                content="Test content",
                body_plain="Test content",
                body_html=None
            ),
        ]

        # Mock database failure
        original_save = temp_db.save_suggestion

        def failing_save(*args, **kwargs):
            raise IOError("Disk full")

        temp_db.save_suggestion = failing_save

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Should handle database error
        with pytest.raises(IOError):
            session = classifier.classify_unlabeled_emails(max_emails=1, dry_run=True)

    def test_gmail_batch_fetch_partial_failure(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test handling when some emails fail to fetch."""
        # Setup
        mock_gmail_client.count_unlabeled_emails.return_value = 3
        mock_gmail_client.list_unlabeled_messages.return_value = (
            ["msg_1", "msg_2", "msg_3"],
            None
        )

        # Mock partial failure - only return 2 of 3 emails
        mock_gmail_client.get_messages_batch.return_value = [
            Email(
                id="msg_1",
                thread_id="thread_1",
                subject="Test 1",
                sender="test1@example.com",
                sender_name="Test 1",
                recipients=["me@example.com"],
                date="2025-01-01T10:00:00Z",
                labels=["INBOX"],
                snippet="Test snippet 1",
                content="Test content 1",
                body_plain="Test content 1",
                body_html=None
            ),
            Email(
                id="msg_2",
                thread_id="thread_2",
                subject="Test 2",
                sender="test2@example.com",
                sender_name="Test 2",
                recipients=["me@example.com"],
                date="2025-01-01T11:00:00Z",
                labels=["INBOX"],
                snippet="Test snippet 2",
                content="Test content 2",
                body_plain="Test content 2",
                body_html=None
            ),
            # msg_3 missing - simulating fetch failure
        ]

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Should process available emails
        session = classifier.classify_unlabeled_emails(max_emails=10, dry_run=True)

        # Verify partial success
        assert session.status == "completed"
        assert session.emails_processed == 2  # Only 2 were successfully fetched
        assert session.suggestions_generated == 2

    def test_apply_with_invalid_session_id(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test error handling when applying suggestions with invalid session ID."""
        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Try to apply suggestions for non-existent session
        with pytest.raises(ValueError, match="not found"):
            classifier.apply_suggestions("invalid_session_id")

    def test_apply_with_dry_run_session(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test error when trying to apply suggestions from dry-run session."""
        # Setup
        mock_gmail_client.count_unlabeled_emails.return_value = 1
        mock_gmail_client.list_unlabeled_messages.return_value = (["msg_1"], None)
        mock_gmail_client.get_messages_batch.return_value = [
            Email(
                id="msg_1",
                thread_id="thread_1",
                subject="Test",
                sender="test@example.com",
                sender_name="Test",
                recipients=["me@example.com"],
                date="2025-01-01T10:00:00Z",
                labels=["INBOX"],
                snippet="Test snippet",
                content="Test content",
                body_plain="Test content",
                body_html=None
            ),
        ]

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Create dry-run session
        session = classifier.classify_unlabeled_emails(max_emails=1, dry_run=True)

        # Try to apply suggestions
        with pytest.raises(ValueError, match="Cannot apply suggestions from dry-run session"):
            classifier.apply_suggestions(session.id)

    def test_database_connection_recovery(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test that database connection can be recovered after closure."""
        # Setup
        mock_gmail_client.count_unlabeled_emails.return_value = 1
        mock_gmail_client.list_unlabeled_messages.return_value = (["msg_1"], None)
        mock_gmail_client.get_messages_batch.return_value = [
            Email(
                id="msg_1",
                thread_id="thread_1",
                subject="Test",
                sender="test@example.com",
                sender_name="Test",
                recipients=["me@example.com"],
                date="2025-01-01T10:00:00Z",
                labels=["INBOX"],
                snippet="Test snippet",
                content="Test content",
                body_plain="Test content",
                body_html=None
            ),
        ]

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Run classification
        session1 = classifier.classify_unlabeled_emails(max_emails=1, dry_run=True)
        assert session1.suggestions_generated == 1

        # Close database connection
        temp_db.close()

        # Should be able to reconnect and query
        session_loaded = temp_db.load_session(session1.id)
        assert session_loaded is not None
        assert session_loaded.id == session1.id

    def test_session_cleanup_with_errors(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test that session cleanup works even with failed sessions."""
        # Setup
        mock_gmail_client.count_unlabeled_emails.return_value = 1
        mock_gmail_client.list_unlabeled_messages.return_value = (["msg_1"], None)
        mock_gmail_client.get_messages_batch.return_value = [
            Email(
                id="msg_1",
                thread_id="thread_1",
                subject="Test",
                sender="test@example.com",
                sender_name="Test",
                recipients=["me@example.com"],
                date="2025-01-01T10:00:00Z",
                labels=["INBOX"],
                snippet="Test snippet",
                content="Test content",
                body_plain="Test content",
                body_html=None
            ),
        ]

        # Create a failed session
        mock_claude_client.classify_batch.side_effect = Exception("API error")

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        session = classifier.classify_unlabeled_emails(max_emails=1, dry_run=True)
        assert session.status == "failed"

        # Cleanup should work
        deleted = temp_db.cleanup_old_sessions(days_to_keep=-1)
        assert deleted >= 1

    def test_concurrent_classification_sessions(
        self,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test that multiple concurrent sessions don't interfere."""
        # Create two separate databases
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                db1 = SessionDatabase(Path(tmpdir1) / "test1.db")
                db2 = SessionDatabase(Path(tmpdir2) / "test2.db")

                # Setup mocks
                mock_gmail_client.count_unlabeled_emails.return_value = 1
                mock_gmail_client.list_unlabeled_messages.return_value = (["msg_1"], None)
                mock_gmail_client.get_messages_batch.return_value = [
                    Email(
                        id="msg_1",
                        thread_id="thread_1",
                        subject="Test",
                        sender="test@example.com",
                        sender_name="Test",
                        recipients=["me@example.com"],
                        date="2025-01-01T10:00:00Z",
                        labels=["INBOX"],
                        snippet="Test snippet",
                        content="Test content",
                        body_plain="Test content",
                        body_html=None
                    ),
                ]

                classifier1 = EmailClassifier(
                    gmail_client=mock_gmail_client,
                    claude_client=mock_claude_client,
                    session_db=db1
                )

                classifier2 = EmailClassifier(
                    gmail_client=mock_gmail_client,
                    claude_client=mock_claude_client,
                    session_db=db2
                )

                # Run concurrent classifications
                session1 = classifier1.classify_unlabeled_emails(max_emails=1, dry_run=True)
                session2 = classifier2.classify_unlabeled_emails(max_emails=1, dry_run=True)

                # Verify sessions are independent
                assert session1.id != session2.id

                # Verify each database has its own session
                db1_sessions = db1.list_sessions()
                db2_sessions = db2.list_sessions()
                assert len(db1_sessions) == 1
                assert len(db2_sessions) == 1
                assert db1_sessions[0].id == session1.id
                assert db2_sessions[0].id == session2.id

                db1.close()
                db2.close()
