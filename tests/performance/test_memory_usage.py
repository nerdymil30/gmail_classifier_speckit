"""Memory usage benchmarks for Gmail Classifier."""

import pytest
import tracemalloc
from unittest.mock import Mock
from pathlib import Path
import tempfile

from gmail_classifier.services.classifier import EmailClassifier
from gmail_classifier.services.gmail_client import GmailClient
from gmail_classifier.services.claude_client import ClaudeClient
from gmail_classifier.lib.session_db import SessionDatabase
from gmail_classifier.models.email import Email
from gmail_classifier.models.label import Label
from gmail_classifier.models.suggestion import ClassificationSuggestion, SuggestedLabel


def generate_test_emails(count: int, content_size: int = 100) -> list[Email]:
    """Generate test emails with specified content size."""
    return [
        Email(
            id=f"msg_{i}",
            thread_id=f"thread_{i}",
            subject=f"Test Email {i}",
            sender=f"sender{i}@test.com",
            sender_name=f"Sender {i}",
            recipients=["me@test.com"],
            date="2025-01-01T10:00:00Z",
            labels=["INBOX"],
            snippet=f"Test snippet {i}",
            content="x" * content_size,  # Variable content size
            body_plain="x" * content_size,
            body_html=None
        )
        for i in range(count)
    ]


@pytest.fixture
def temp_db():
    """Temporary database for memory tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sessions.db"
        db = SessionDatabase(db_path)
        yield db
        db.close()


@pytest.mark.performance
class TestMemoryUsage:
    """Memory usage benchmarks."""

    def test_memory_usage_100_emails(self, temp_db):
        """Benchmark: Memory usage for 100 emails."""
        # Setup mocks
        mock_gmail = Mock(spec=GmailClient)
        mock_gmail.get_profile.return_value = {"emailAddress": "test@example.com"}
        mock_gmail.get_user_labels.return_value = [
            Label(id="Label_1", name="Work", email_count=10, type="user"),
            Label(id="Label_2", name="Personal", email_count=5, type="user"),
        ]

        emails = generate_test_emails(100, content_size=1000)
        mock_gmail.count_unlabeled_emails.return_value = 100
        mock_gmail.list_unlabeled_messages.return_value = (
            [email.id for email in emails],
            None
        )
        mock_gmail.get_messages_batch.return_value = emails

        # Mock Claude
        mock_claude = Mock(spec=ClaudeClient)

        def classify_batch(emails, labels):
            return [
                ClassificationSuggestion(
                    email_id=email.id,
                    suggested_labels=[
                        SuggestedLabel("Label_1", "Work", 0.85, 1, "Work email")
                    ],
                    confidence_category="high",
                    reasoning="Classified as work",
                )
                for email in emails
            ]

        mock_claude.classify_batch.side_effect = classify_batch

        # Start memory tracking
        tracemalloc.start()

        classifier = EmailClassifier(
            gmail_client=mock_gmail,
            claude_client=mock_claude,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=100, dry_run=True)

        # Get memory stats
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Memory assertions
        peak_mb = peak / 1024 / 1024
        current_mb = current / 1024 / 1024

        assert peak_mb < 50, f"Peak memory {peak_mb:.1f} MB exceeded 50 MB limit"
        assert session.emails_processed == 100

        # Log memory usage
        print(f"\nMemory: Peak usage {peak_mb:.1f} MB for 100 emails")
        print(f"Memory: Current usage {current_mb:.1f} MB after processing")

    @pytest.mark.slow
    def test_memory_usage_500_emails(self, temp_db):
        """Benchmark: Memory usage for 500 emails."""
        # Setup mocks
        mock_gmail = Mock(spec=GmailClient)
        mock_gmail.get_profile.return_value = {"emailAddress": "test@example.com"}
        mock_gmail.get_user_labels.return_value = [
            Label(id="Label_1", name="Work", email_count=10, type="user"),
        ]

        # Simulate pagination
        all_emails = generate_test_emails(500, content_size=500)
        page_size = 100
        pages = [all_emails[i:i+page_size] for i in range(0, len(all_emails), page_size)]
        call_count = 0

        def list_messages(max_results=100, page_token=None):
            nonlocal call_count
            if call_count >= len(pages):
                return ([], None)
            page = pages[call_count]
            call_count += 1
            next_token = "next" if call_count < len(pages) else None
            return ([email.id for email in page], next_token)

        mock_gmail.count_unlabeled_emails.return_value = 500
        mock_gmail.list_unlabeled_messages.side_effect = list_messages

        batch_call_count = 0

        def get_batch(message_ids):
            nonlocal batch_call_count
            page = pages[batch_call_count] if batch_call_count < len(pages) else []
            batch_call_count += 1
            return page

        mock_gmail.get_messages_batch.side_effect = get_batch

        # Mock Claude
        mock_claude = Mock(spec=ClaudeClient)

        def classify_batch(emails, labels):
            return [
                ClassificationSuggestion(
                    email_id=email.id,
                    suggested_labels=[
                        SuggestedLabel("Label_1", "Work", 0.85, 1, "Work")
                    ],
                    confidence_category="high",
                    reasoning="Test",
                )
                for email in emails
            ]

        mock_claude.classify_batch.side_effect = classify_batch

        # Start memory tracking
        tracemalloc.start()

        classifier = EmailClassifier(
            gmail_client=mock_gmail,
            claude_client=mock_claude,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=500, dry_run=True)

        # Get memory stats
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Memory assertions
        peak_mb = peak / 1024 / 1024
        current_mb = current / 1024 / 1024

        assert peak_mb < 100, f"Peak memory {peak_mb:.1f} MB exceeded 100 MB limit"
        assert session.emails_processed == 500

        # Log memory usage
        print(f"\nMemory: Peak usage {peak_mb:.1f} MB for 500 emails")
        print(f"Memory: Current usage {current_mb:.1f} MB after processing")
        print(f"Memory: {peak_mb/500*1000:.2f} KB per email (peak)")

    def test_memory_cleanup_between_batches(self, temp_db):
        """Test that memory is properly cleaned up between batches."""
        # Setup mocks
        mock_gmail = Mock(spec=GmailClient)
        mock_gmail.get_profile.return_value = {"emailAddress": "test@example.com"}
        mock_gmail.get_user_labels.return_value = [
            Label(id="Label_1", name="Work", email_count=10, type="user"),
        ]

        # Create multiple small batches
        batch_size = 10
        num_batches = 5
        all_emails = generate_test_emails(batch_size * num_batches, content_size=1000)

        pages = [all_emails[i:i+batch_size] for i in range(0, len(all_emails), batch_size)]
        call_count = 0

        def list_messages(max_results=100, page_token=None):
            nonlocal call_count
            if call_count >= len(pages):
                return ([], None)
            page = pages[call_count]
            call_count += 1
            next_token = "next" if call_count < len(pages) else None
            return ([email.id for email in page], next_token)

        mock_gmail.count_unlabeled_emails.return_value = len(all_emails)
        mock_gmail.list_unlabeled_messages.side_effect = list_messages

        batch_call_count = 0
        memory_per_batch = []

        def get_batch(message_ids):
            nonlocal batch_call_count
            page = pages[batch_call_count] if batch_call_count < len(pages) else []
            batch_call_count += 1

            # Track memory after each batch
            current, _ = tracemalloc.get_traced_memory()
            memory_per_batch.append(current / 1024 / 1024)

            return page

        mock_gmail.get_messages_batch.side_effect = get_batch

        # Mock Claude
        mock_claude = Mock(spec=ClaudeClient)

        def classify_batch(emails, labels):
            return [
                ClassificationSuggestion(
                    email_id=email.id,
                    suggested_labels=[
                        SuggestedLabel("Label_1", "Work", 0.85, 1, "Work")
                    ],
                    confidence_category="high",
                    reasoning="Test",
                )
                for email in emails
            ]

        mock_claude.classify_batch.side_effect = classify_batch

        # Start memory tracking
        tracemalloc.start()

        classifier = EmailClassifier(
            gmail_client=mock_gmail,
            claude_client=mock_claude,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=len(all_emails), dry_run=True)

        tracemalloc.stop()

        # Memory should not continuously grow
        # Check that memory doesn't double between first and last batch
        if len(memory_per_batch) >= 2:
            first_batch_mem = memory_per_batch[0]
            last_batch_mem = memory_per_batch[-1]

            print(f"\nMemory per batch: {[f'{m:.1f} MB' for m in memory_per_batch]}")
            print(f"First batch: {first_batch_mem:.1f} MB")
            print(f"Last batch: {last_batch_mem:.1f} MB")

            # Memory growth should be reasonable (not unbounded)
            assert last_batch_mem < first_batch_mem * 3, "Memory growth indicates memory leak"

    def test_database_connection_memory(self, temp_db):
        """Test memory usage of database connections."""
        tracemalloc.start()

        # Perform multiple database operations
        from gmail_classifier.models.session import ProcessingSession

        sessions = []
        for i in range(10):
            session = ProcessingSession.create_new(
                user_email=f"test{i}@example.com",
                total_emails=100,
                config={"dry_run": True}
            )
            session.complete()
            temp_db.save_session(session)
            sessions.append(session)

        # Save many suggestions
        for session in sessions:
            for j in range(10):
                suggestion = ClassificationSuggestion(
                    email_id=f"msg_{j}",
                    suggested_labels=[
                        SuggestedLabel("Label_1", "Work", 0.85, 1, "Work")
                    ],
                    confidence_category="high",
                    reasoning="Test",
                )
                temp_db.save_suggestion(session.id, suggestion)

        # Load data back
        for session in sessions:
            loaded_session = temp_db.load_session(session.id)
            suggestions = temp_db.load_suggestions(session.id)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024

        print(f"\nDatabase operations memory: {peak_mb:.1f} MB")

        # Database operations should be memory-efficient
        assert peak_mb < 20, f"Database memory {peak_mb:.1f} MB exceeded 20 MB limit"

    def test_large_email_content_memory(self, temp_db):
        """Test memory usage with large email content."""
        # Setup mocks with large email content (10KB per email)
        mock_gmail = Mock(spec=GmailClient)
        mock_gmail.get_profile.return_value = {"emailAddress": "test@example.com"}
        mock_gmail.get_user_labels.return_value = [
            Label(id="Label_1", name="Work", email_count=10, type="user"),
        ]

        # Generate emails with large content
        emails = generate_test_emails(50, content_size=10000)
        mock_gmail.count_unlabeled_emails.return_value = 50
        mock_gmail.list_unlabeled_messages.return_value = (
            [email.id for email in emails],
            None
        )
        mock_gmail.get_messages_batch.return_value = emails

        # Mock Claude
        mock_claude = Mock(spec=ClaudeClient)

        def classify_batch(emails, labels):
            return [
                ClassificationSuggestion(
                    email_id=email.id,
                    suggested_labels=[
                        SuggestedLabel("Label_1", "Work", 0.85, 1, "Work")
                    ],
                    confidence_category="high",
                    reasoning="Test" * 100,  # Large reasoning text
                )
                for email in emails
            ]

        mock_claude.classify_batch.side_effect = classify_batch

        # Start memory tracking
        tracemalloc.start()

        classifier = EmailClassifier(
            gmail_client=mock_gmail,
            claude_client=mock_claude,
            session_db=temp_db
        )

        # Run classification
        session = classifier.classify_unlabeled_emails(max_emails=50, dry_run=True)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024

        print(f"\nLarge content memory: {peak_mb:.1f} MB for 50 emails @ 10KB each")

        # Should handle large content efficiently
        assert peak_mb < 50, f"Memory {peak_mb:.1f} MB exceeded limit for large content"
        assert session.emails_processed == 50
