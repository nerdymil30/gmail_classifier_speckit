"""Integration tests for Gmail/Database consistency."""

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
    client.count_unlabeled_emails.return_value = 1
    client.list_unlabeled_messages.return_value = (["msg_1"], None)
    client.get_messages_batch.return_value = [
        Email(
            id="msg_1",
            thread_id="thread_1",
            subject="Test Email",
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
    return client


@pytest.fixture
def mock_claude_client():
    """Mock Claude client."""
    client = Mock(spec=ClaudeClient)

    def classify_batch(emails, labels):
        return [
            ClassificationSuggestion(
                email_id=emails[0].id,
                suggested_labels=[
                    SuggestedLabel("Label_1", "Work", 0.9, 1, "Work email")
                ],
                confidence_category="high",
                reasoning="Work-related",
            ),
        ]

    client.classify_batch.side_effect = classify_batch
    return client


@pytest.mark.integration
class TestGmailDatabaseConsistency:
    """Test Gmail API and database stay consistent."""

    def test_label_applied_but_db_update_fails(
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

        session = classifier.classify_unlabeled_emails(max_emails=1, dry_run=False)

        # Mock successful label application
        mock_gmail_client.add_label_to_message.return_value = True

        # Mock database failure
        original_update = temp_db.update_suggestion_status

        def failing_update(*args, **kwargs):
            raise IOError("Disk full")

        temp_db.update_suggestion_status = failing_update

        # Apply suggestions should raise but log the inconsistency
        try:
            results = classifier.apply_suggestions(session.id)
            # If it doesn't raise, check that failed count is incremented
            assert results["failed"] > 0 or results["inconsistent"] > 0
        except IOError:
            # This is expected - the operation failed
            pass

        # Restore original method
        temp_db.update_suggestion_status = original_update

        # Verify that Gmail operation was logged
        operations = temp_db.get_operation_log(session_id=session.id)
        assert len(operations) > 0

        # Verify unsynced operations exist
        unsynced = temp_db.get_unsynced_operations(session_id=session.id)
        assert len(unsynced) > 0, "Inconsistent operations should be tracked"

    def test_gmail_operation_audit_log(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test that Gmail operations are logged for audit trail."""
        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=1, dry_run=False)

        # Apply suggestions
        mock_gmail_client.add_label_to_message.return_value = True
        results = classifier.apply_suggestions(session.id)

        # Verify operations logged
        operations = temp_db.get_operation_log(session_id=session.id)
        assert len(operations) == results["applied"]

        # Verify all successful operations marked as synced
        for op in operations:
            if op["success"]:
                assert op["db_synced"] is True

    def test_failed_gmail_operation_logged(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test that failed Gmail operations are logged."""
        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=1, dry_run=False)

        # Mock Gmail failure
        mock_gmail_client.add_label_to_message.return_value = False

        # Apply suggestions
        results = classifier.apply_suggestions(session.id)

        assert results["failed"] == 1

        # Verify failed operation logged
        operations = temp_db.get_operation_log(session_id=session.id)
        assert len(operations) == 1
        assert operations[0]["success"] is False

    def test_gmail_exception_logged(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test that Gmail exceptions are logged."""
        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=1, dry_run=False)

        # Mock Gmail exception
        mock_gmail_client.add_label_to_message.side_effect = Exception("API error")

        # Apply suggestions
        results = classifier.apply_suggestions(session.id)

        assert results["failed"] == 1

        # Verify exception logged
        operations = temp_db.get_operation_log(session_id=session.id)
        assert len(operations) == 1
        assert operations[0]["success"] is False
        assert operations[0]["error_message"] == "API error"

    def test_partial_application_tracked(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test that partial label application is tracked correctly."""
        # Mock multiple emails
        mock_gmail_client.list_unlabeled_messages.return_value = (
            ["msg_1", "msg_2", "msg_3"],
            None
        )
        mock_gmail_client.count_unlabeled_emails.return_value = 3
        mock_gmail_client.get_messages_batch.return_value = [
            Email(
                id=f"msg_{i}",
                thread_id=f"thread_{i}",
                subject=f"Test Email {i}",
                sender=f"test{i}@example.com",
                sender_name=f"Test {i}",
                recipients=["me@example.com"],
                date="2025-01-01T10:00:00Z",
                labels=["INBOX"],
                snippet=f"Test snippet {i}",
                content=f"Test content {i}",
                body_plain=f"Test content {i}",
                body_html=None
            )
            for i in range(1, 4)
        ]

        # Mock Claude to return suggestions for all emails
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

        mock_claude_client.classify_batch.side_effect = classify_batch

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=3, dry_run=False)

        # Mock partial success: first succeeds, second fails, third succeeds
        call_count = 0

        def partial_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return False  # Second call fails
            return True

        mock_gmail_client.add_label_to_message.side_effect = partial_success

        # Apply suggestions
        results = classifier.apply_suggestions(session.id)

        # Verify results
        assert results["applied"] == 2
        assert results["failed"] == 1

        # Verify database reflects partial application
        suggestions = temp_db.load_suggestions(session.id, status="applied")
        assert len(suggestions) == 2

        pending_suggestions = temp_db.load_suggestions(session.id, status="pending")
        assert len(pending_suggestions) == 1

    def test_session_persistence_after_error(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test that session state is persisted even when errors occur."""
        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Mock Claude to fail
        mock_claude_client.classify_batch.side_effect = Exception("Claude API error")

        # Run classification - should handle error gracefully
        try:
            session = classifier.classify_unlabeled_emails(max_emails=1, dry_run=True)
            # Session should be marked as failed
            assert session.status == "failed"
        except Exception:
            # Even if exception propagates, session should be saved
            pass

        # Verify session was saved despite error
        sessions = temp_db.list_sessions()
        assert len(sessions) > 0

    def test_inconsistency_file_created(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test that inconsistency file is created when mismatches occur."""
        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=1, dry_run=False)

        # Mock successful label application
        mock_gmail_client.add_label_to_message.return_value = True

        # Mock database failure
        def failing_update(*args, **kwargs):
            raise IOError("Disk full")

        temp_db.update_suggestion_status = failing_update

        # Apply suggestions
        try:
            results = classifier.apply_suggestions(session.id)
        except IOError:
            pass

        # Verify inconsistency tracked
        unsynced = temp_db.get_unsynced_operations(session_id=session.id)
        assert len(unsynced) > 0

    def test_operation_log_filtering(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test filtering operation logs by email and session."""
        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Run classification
        session1 = classifier.classify_unlabeled_emails(max_emails=1, dry_run=False)

        # Apply suggestions
        mock_gmail_client.add_label_to_message.return_value = True
        classifier.apply_suggestions(session1.id)

        # Get operations for this session
        session_ops = temp_db.get_operation_log(session_id=session1.id)
        assert len(session_ops) == 1

        # Get operations for specific email
        email_ops = temp_db.get_operation_log(email_id="msg_1")
        assert len(email_ops) == 1
        assert email_ops[0]["email_id"] == "msg_1"
