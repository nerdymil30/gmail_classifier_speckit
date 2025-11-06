"""Performance benchmarks for classification."""

import pytest
import time
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


@pytest.fixture
def temp_db():
    """Temporary database for performance tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sessions.db"
        db = SessionDatabase(db_path)
        yield db
        db.close()


def generate_test_emails(count: int) -> list[Email]:
    """Generate test emails for performance testing."""
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
            content=f"Test content for email {i}",
            body_plain=f"Test content for email {i}",
            body_html=None
        )
        for i in range(count)
    ]


@pytest.mark.performance
class TestClassificationPerformance:
    """Performance benchmarks for email classification."""

    def test_classification_speed_10_emails(self, temp_db):
        """Benchmark: Classify 10 emails."""
        # Setup mocks
        mock_gmail = Mock(spec=GmailClient)
        mock_gmail.get_profile.return_value = {"emailAddress": "test@example.com"}
        mock_gmail.get_user_labels.return_value = [
            Label(id="Label_1", name="Work", email_count=10, type="user"),
            Label(id="Label_2", name="Personal", email_count=5, type="user"),
        ]

        emails = generate_test_emails(10)
        mock_gmail.count_unlabeled_emails.return_value = 10
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

        classifier = EmailClassifier(
            gmail_client=mock_gmail,
            claude_client=mock_claude,
            session_db=temp_db
        )

        # Benchmark
        start_time = time.time()
        session = classifier.classify_unlabeled_emails(max_emails=10, dry_run=True)
        elapsed = time.time() - start_time

        # Performance assertions
        assert session.emails_processed == 10
        assert elapsed < 5.0, f"Classification took {elapsed:.2f}s, expected < 5s"

        # Log performance
        print(f"\nPerformance: Classified 10 emails in {elapsed:.2f}s")
        print(f"Throughput: {10/elapsed:.1f} emails/second")

    def test_classification_speed_100_emails(self, temp_db):
        """Benchmark: Classify 100 emails."""
        # Setup mocks
        mock_gmail = Mock(spec=GmailClient)
        mock_gmail.get_profile.return_value = {"emailAddress": "test@example.com"}
        mock_gmail.get_user_labels.return_value = [
            Label(id="Label_1", name="Work", email_count=10, type="user"),
            Label(id="Label_2", name="Personal", email_count=5, type="user"),
        ]

        emails = generate_test_emails(100)
        mock_gmail.count_unlabeled_emails.return_value = 100

        # Simulate pagination
        page_size = 50
        pages = [emails[i:i+page_size] for i in range(0, len(emails), page_size)]
        call_count = 0

        def list_messages(max_results=100, page_token=None):
            nonlocal call_count
            if call_count >= len(pages):
                return ([], None)
            page = pages[call_count]
            call_count += 1
            next_token = "next" if call_count < len(pages) else None
            return ([email.id for email in page], next_token)

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
                        SuggestedLabel("Label_1", "Work", 0.85, 1, "Work email")
                    ],
                    confidence_category="high",
                    reasoning="Classified as work",
                )
                for email in emails
            ]

        mock_claude.classify_batch.side_effect = classify_batch

        classifier = EmailClassifier(
            gmail_client=mock_gmail,
            claude_client=mock_claude,
            session_db=temp_db
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
    def test_database_write_performance(self, temp_db):
        """Benchmark: Database write performance for suggestions."""
        # Generate test suggestions
        suggestions = [
            ClassificationSuggestion(
                email_id=f"msg_{i}",
                suggested_labels=[
                    SuggestedLabel("Label_1", "Work", 0.85, 1, "Work email")
                ],
                confidence_category="high",
                reasoning="Test reasoning",
            )
            for i in range(100)
        ]

        session_id = "test_session_123"

        # Benchmark
        start_time = time.time()
        for suggestion in suggestions:
            temp_db.save_suggestion(session_id, suggestion)
        elapsed = time.time() - start_time

        # Performance assertions
        assert elapsed < 5.0, f"DB writes took {elapsed:.2f}s, expected < 5s"

        # Log performance
        print(f"\nDatabase: Saved 100 suggestions in {elapsed:.2f}s")
        print(f"Write rate: {100/elapsed:.1f} suggestions/second")

        # Verify all saved
        loaded_suggestions = temp_db.load_suggestions(session_id)
        assert len(loaded_suggestions) == 100

    @pytest.mark.slow
    def test_database_read_performance(self, temp_db):
        """Benchmark: Database read performance for suggestions."""
        # Setup: Create session and suggestions
        session_id = "test_session_456"

        for i in range(100):
            suggestion = ClassificationSuggestion(
                email_id=f"msg_{i}",
                suggested_labels=[
                    SuggestedLabel("Label_1", "Work", 0.85, 1, "Work email")
                ],
                confidence_category="high",
                reasoning="Test reasoning",
            )
            temp_db.save_suggestion(session_id, suggestion)

        # Benchmark
        start_time = time.time()
        suggestions = temp_db.load_suggestions(session_id)
        elapsed = time.time() - start_time

        # Performance assertions
        assert len(suggestions) == 100
        assert elapsed < 1.0, f"DB reads took {elapsed:.2f}s, expected < 1s"

        # Log performance
        print(f"\nDatabase: Loaded 100 suggestions in {elapsed:.3f}s")
        print(f"Read rate: {100/elapsed:.1f} suggestions/second")

    def test_session_save_performance(self, temp_db):
        """Benchmark: Session save/load performance."""
        from gmail_classifier.models.session import ProcessingSession

        # Create test session
        session = ProcessingSession.create_new(
            user_email="test@example.com",
            total_emails=1000,
            config={"dry_run": True}
        )

        # Simulate processing
        for i in range(100):
            session.emails_processed += 1
            session.suggestions_generated += 1

        session.complete()

        # Benchmark save
        save_start = time.time()
        for _ in range(10):
            temp_db.save_session(session)
        save_elapsed = time.time() - save_start

        # Benchmark load
        load_start = time.time()
        for _ in range(10):
            loaded = temp_db.load_session(session.id)
        load_elapsed = time.time() - load_start

        # Performance assertions
        assert save_elapsed < 1.0, f"Session saves took {save_elapsed:.2f}s for 10 ops"
        assert load_elapsed < 1.0, f"Session loads took {load_elapsed:.2f}s for 10 ops"

        # Log performance
        print(f"\nSession save: {save_elapsed/10*1000:.1f}ms per save")
        print(f"Session load: {load_elapsed/10*1000:.1f}ms per load")

    def test_batch_processing_scalability(self, temp_db):
        """Test that batch processing scales linearly."""
        mock_gmail = Mock(spec=GmailClient)
        mock_gmail.get_profile.return_value = {"emailAddress": "test@example.com"}
        mock_gmail.get_user_labels.return_value = [
            Label(id="Label_1", name="Work", email_count=10, type="user"),
        ]

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

        # Test with different batch sizes
        times = {}
        for count in [10, 20, 40]:
            emails = generate_test_emails(count)
            mock_gmail.count_unlabeled_emails.return_value = count
            mock_gmail.list_unlabeled_messages.return_value = (
                [email.id for email in emails],
                None
            )
            mock_gmail.get_messages_batch.return_value = emails

            classifier = EmailClassifier(
                gmail_client=mock_gmail,
                claude_client=mock_claude,
                session_db=temp_db
            )

            start = time.time()
            classifier.classify_unlabeled_emails(max_emails=count, dry_run=True)
            elapsed = time.time() - start

            times[count] = elapsed
            print(f"\n{count} emails: {elapsed:.2f}s ({count/elapsed:.1f} emails/s)")

        # Check for reasonable scaling
        # 40 emails should take less than 5x the time of 10 emails
        assert times[40] < times[10] * 5
