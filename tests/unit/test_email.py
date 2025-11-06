"""Unit tests for Email model."""

import pytest
from datetime import datetime

from gmail_classifier.models.email import Email


class TestEmailModel:
    """Test Email model validation and methods."""

    def test_email_creation_valid(self):
        """Test creating a valid email."""
        email = Email(
            id="msg123",
            thread_id="thread123",
            subject="Test Subject",
            sender="sender@example.com",
            sender_name="Test Sender",
            recipients=["recipient@example.com"],
            date=datetime(2025, 1, 1, 12, 0, 0),
            snippet="Test snippet",
            body_plain="Test body",
            body_html="<p>Test body</p>",
            labels=["INBOX", "UNREAD"],
            has_attachments=False,
            is_unread=True,
        )

        assert email.id == "msg123"
        assert email.subject == "Test Subject"
        assert email.sender == "sender@example.com"

    def test_email_missing_id_raises_error(self):
        """Test that empty ID raises ValueError."""
        with pytest.raises(ValueError, match="Email ID cannot be empty"):
            Email(
                id="",
                thread_id="thread123",
                subject="Test",
                sender="sender@example.com",
                sender_name=None,
                recipients=[],
                date=datetime.now(),
                snippet=None,
                body_plain=None,
                body_html=None,
                labels=[],
                has_attachments=False,
                is_unread=False,
            )

    def test_email_missing_sender_raises_error(self):
        """Test that empty sender raises ValueError."""
        with pytest.raises(ValueError, match="Email sender cannot be empty"):
            Email(
                id="msg123",
                thread_id="thread123",
                subject="Test",
                sender="",
                sender_name=None,
                recipients=[],
                date=datetime.now(),
                snippet=None,
                body_plain=None,
                body_html=None,
                labels=[],
                has_attachments=False,
                is_unread=False,
            )

    def test_is_unlabeled_with_only_system_labels(self):
        """Test that emails with only system labels are considered unlabeled."""
        email = Email(
            id="msg123",
            thread_id="thread123",
            subject="Test",
            sender="sender@example.com",
            sender_name=None,
            recipients=[],
            date=datetime.now(),
            snippet=None,
            body_plain=None,
            body_html=None,
            labels=["INBOX", "UNREAD", "STARRED"],
            has_attachments=False,
            is_unread=True,
        )

        assert email.is_unlabeled is True

    def test_is_unlabeled_with_user_labels(self):
        """Test that emails with user labels are not unlabeled."""
        email = Email(
            id="msg123",
            thread_id="thread123",
            subject="Test",
            sender="sender@example.com",
            sender_name=None,
            recipients=[],
            date=datetime.now(),
            snippet=None,
            body_plain=None,
            body_html=None,
            labels=["INBOX", "Label_123"],  # Label_123 is a user label
            has_attachments=False,
            is_unread=True,
        )

        assert email.is_unlabeled is False

    def test_is_unlabeled_with_no_labels(self):
        """Test that emails with no labels are unlabeled."""
        email = Email(
            id="msg123",
            thread_id="thread123",
            subject="Test",
            sender="sender@example.com",
            sender_name=None,
            recipients=[],
            date=datetime.now(),
            snippet=None,
            body_plain=None,
            body_html=None,
            labels=[],
            has_attachments=False,
            is_unread=True,
        )

        assert email.is_unlabeled is True

    def test_content_property_returns_plain_body(self):
        """Test that content property prefers plain text body."""
        email = Email(
            id="msg123",
            thread_id="thread123",
            subject="Test",
            sender="sender@example.com",
            sender_name=None,
            recipients=[],
            date=datetime.now(),
            snippet="Snippet text",
            body_plain="Plain text body",
            body_html="<p>HTML body</p>",
            labels=[],
            has_attachments=False,
            is_unread=False,
        )

        assert email.content == "Plain text body"

    def test_content_property_fallback_to_snippet(self):
        """Test that content property falls back to snippet."""
        email = Email(
            id="msg123",
            thread_id="thread123",
            subject="Test",
            sender="sender@example.com",
            sender_name=None,
            recipients=[],
            date=datetime.now(),
            snippet="Snippet text",
            body_plain=None,
            body_html=None,
            labels=[],
            has_attachments=False,
            is_unread=False,
        )

        assert email.content == "Snippet text"

    def test_display_subject_with_subject(self):
        """Test display_subject with actual subject."""
        email = Email(
            id="msg123",
            thread_id="thread123",
            subject="Test Subject",
            sender="sender@example.com",
            sender_name=None,
            recipients=[],
            date=datetime.now(),
            snippet=None,
            body_plain=None,
            body_html=None,
            labels=[],
            has_attachments=False,
            is_unread=False,
        )

        assert email.display_subject == "Test Subject"

    def test_display_subject_without_subject(self):
        """Test display_subject fallback for missing subject."""
        email = Email(
            id="msg123",
            thread_id="thread123",
            subject=None,
            sender="sender@example.com",
            sender_name=None,
            recipients=[],
            date=datetime.now(),
            snippet=None,
            body_plain=None,
            body_html=None,
            labels=[],
            has_attachments=False,
            is_unread=False,
        )

        assert email.display_subject == "(No Subject)"

    def test_display_sender_prefers_name(self):
        """Test display_sender prefers sender name over email."""
        email = Email(
            id="msg123",
            thread_id="thread123",
            subject="Test",
            sender="sender@example.com",
            sender_name="John Doe",
            recipients=[],
            date=datetime.now(),
            snippet=None,
            body_plain=None,
            body_html=None,
            labels=[],
            has_attachments=False,
            is_unread=False,
        )

        assert email.display_sender == "John Doe"

    def test_display_sender_fallback_to_email(self):
        """Test display_sender falls back to email address."""
        email = Email(
            id="msg123",
            thread_id="thread123",
            subject="Test",
            sender="sender@example.com",
            sender_name=None,
            recipients=[],
            date=datetime.now(),
            snippet=None,
            body_plain=None,
            body_html=None,
            labels=[],
            has_attachments=False,
            is_unread=False,
        )

        assert email.display_sender == "sender@example.com"

    def test_to_dict_excludes_body_content(self):
        """Test that to_dict excludes body content for privacy."""
        email = Email(
            id="msg123",
            thread_id="thread123",
            subject="Test Subject",
            sender="sender@example.com",
            sender_name="Test Sender",
            recipients=["recipient@example.com"],
            date=datetime(2025, 1, 1, 12, 0, 0),
            snippet="Test snippet",
            body_plain="Secret content",
            body_html="<p>Secret HTML</p>",
            labels=["INBOX"],
            has_attachments=True,
            is_unread=True,
        )

        email_dict = email.to_dict()

        assert "body_plain" not in email_dict
        assert "body_html" not in email_dict
        assert email_dict["id"] == "msg123"
        assert email_dict["subject"] == "Test Subject"
        assert email_dict["snippet"] == "Test snippet"
