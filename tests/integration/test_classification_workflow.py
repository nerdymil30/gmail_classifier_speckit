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
    """Mock Gmail client with realistic data."""
    client = Mock(spec=GmailClient)

    # Mock profile
    client.get_profile.return_value = {"emailAddress": "test@example.com"}

    # Mock labels
    client.get_user_labels.return_value = [
        Label(id="Label_1", name="Work", email_count=10, type="user"),
        Label(id="Label_2", name="Personal", email_count=5, type="user"),
        Label(id="Label_3", name="Important", email_count=8, type="user"),
    ]

    # Mock email count
    client.count_unlabeled_emails.return_value = 2

    # Mock unlabeled messages listing
    client.list_unlabeled_messages.return_value = (
        ["msg_1", "msg_2"],
        None  # No next page token
    )

    # Mock emails
    client.get_messages_batch.return_value = [
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


@pytest.mark.integration
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
        mock_gmail_client.list_unlabeled_messages.assert_called_once()
        mock_gmail_client.get_messages_batch.assert_called_once()

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

        # Override dry_run config for this test
        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Non-dry run
        session = classifier.classify_unlabeled_emails(
            max_emails=10,
            dry_run=False
        )

        assert session.is_dry_run is False
        assert session.suggestions_generated == 2

        # Apply suggestions
        results = classifier.apply_suggestions(session.id)

        assert results["applied"] == 2
        assert results["failed"] == 0

        # Verify labels were applied via Gmail API
        assert mock_gmail_client.add_label_to_message.call_count == 2

        # Verify suggestions marked as applied in database
        suggestions = temp_db.load_suggestions(session.id, status="applied")
        assert len(suggestions) == 2

    def test_classification_with_no_labels(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test error when no user labels exist."""
        # Mock no labels
        mock_gmail_client.get_user_labels.return_value = []

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="No user-created labels found"):
            classifier.classify_unlabeled_emails(max_emails=10, dry_run=True)

    def test_classification_with_no_unlabeled_emails(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test handling when no unlabeled emails exist."""
        # Mock no unlabeled emails
        mock_gmail_client.count_unlabeled_emails.return_value = 0

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=10, dry_run=True)

        # Verify empty session
        assert session.status == "completed"
        assert session.emails_processed == 0
        assert session.suggestions_generated == 0

    def test_classification_pagination(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test classification with paginated email fetching."""
        # Mock pagination
        call_count = 0

        def list_with_pagination(max_results=100, page_token=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First page
                return (["msg_1", "msg_2"], "next_page_token")
            elif call_count == 2:
                # Second page
                return (["msg_3", "msg_4"], None)
            return ([], None)

        mock_gmail_client.list_unlabeled_messages.side_effect = list_with_pagination

        # Mock batch email retrieval
        batch_count = 0

        def get_batch(message_ids):
            nonlocal batch_count
            batch_count += 1
            if batch_count == 1:
                return [
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
            else:
                return [
                    Email(
                        id="msg_3",
                        thread_id="thread_3",
                        subject="Test 3",
                        sender="test3@example.com",
                        sender_name="Test 3",
                        recipients=["me@example.com"],
                        date="2025-01-01T12:00:00Z",
                        labels=["INBOX"],
                        snippet="Test email 3",
                        content="Test content 3",
                        body_plain="Test content 3",
                        body_html=None
                    ),
                    Email(
                        id="msg_4",
                        thread_id="thread_4",
                        subject="Test 4",
                        sender="test4@example.com",
                        sender_name="Test 4",
                        recipients=["me@example.com"],
                        date="2025-01-01T13:00:00Z",
                        labels=["INBOX"],
                        snippet="Test email 4",
                        content="Test content 4",
                        body_plain="Test content 4",
                        body_html=None
                    ),
                ]

        mock_gmail_client.get_messages_batch.side_effect = get_batch
        mock_gmail_client.count_unlabeled_emails.return_value = 4

        # Mock Claude classification
        def classify_batch_dynamic(emails, labels):
            return [
                ClassificationSuggestion(
                    email_id=email.id,
                    suggested_labels=[
                        SuggestedLabel("Label_1", "Work", 0.8, 1, "Work email")
                    ],
                    confidence_category="high",
                    reasoning="Classified as work",
                )
                for email in emails
            ]

        mock_claude_client.classify_batch.side_effect = classify_batch_dynamic

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=10, dry_run=True)

        # Verify pagination worked
        assert session.emails_processed == 4
        assert session.suggestions_generated == 4
        assert mock_gmail_client.list_unlabeled_messages.call_count == 2

    def test_get_session_summary(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test getting session summary."""
        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=10, dry_run=True)

        # Get summary
        summary = classifier.get_session_summary(session.id)

        # Verify summary structure
        assert summary["session_id"] == session.id
        assert summary["user_email"] == "test@example.com"
        assert summary["status"] == "completed"
        assert summary["emails_processed"] == 2
        assert summary["suggestions_generated"] == 2
        assert summary["high_confidence_count"] == 2
        assert summary["no_match_count"] == 0
        assert summary["dry_run"] is True

    def test_classification_with_mixed_confidence_levels(
        self,
        temp_db,
        mock_gmail_client,
        mock_claude_client
    ):
        """Test classification with varying confidence levels."""
        # Mock Claude with mixed confidence
        def classify_mixed(emails, labels):
            return [
                ClassificationSuggestion(
                    email_id=emails[0].id,
                    suggested_labels=[
                        SuggestedLabel("Label_1", "Work", 0.95, 1, "High confidence")
                    ],
                    confidence_category="high",
                    reasoning="Clearly work-related",
                ),
                ClassificationSuggestion(
                    email_id=emails[1].id,
                    suggested_labels=[
                        SuggestedLabel("Label_2", "Personal", 0.55, 1, "Low confidence")
                    ],
                    confidence_category="medium",
                    reasoning="Might be personal",
                ),
            ]

        mock_claude_client.classify_batch.side_effect = classify_mixed

        classifier = EmailClassifier(
            gmail_client=mock_gmail_client,
            claude_client=mock_claude_client,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=10, dry_run=False)

        # Apply only high confidence suggestions
        mock_gmail_client.add_label_to_message.return_value = True
        results = classifier.apply_suggestions(session.id, min_confidence=0.75)

        # Only high confidence suggestion should be applied
        assert results["applied"] == 1
        assert results["total"] == 2
