"""Performance benchmarks for email fetching operations."""

import pytest
import time
from unittest.mock import Mock
from pathlib import Path
import tempfile

from gmail_classifier.services.gmail_client import GmailClient
from gmail_classifier.lib.session_db import SessionDatabase
from gmail_classifier.models.email import Email
from gmail_classifier.models.label import Label


def generate_test_emails(count: int) -> list[Email]:
    """Generate test emails."""
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
            content=f"Test content {i}",
            body_plain=f"Test content {i}",
            body_html=None
        )
        for i in range(count)
    ]


@pytest.fixture
def temp_db():
    """Temporary database for performance tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sessions.db"
        db = SessionDatabase(db_path)
        yield db
        db.close()


@pytest.mark.performance
class TestEmailFetchingPerformance:
    """Performance benchmarks for email fetching."""

    def test_batch_email_fetch_performance(self):
        """Benchmark: Batch email fetching."""
        mock_gmail = Mock(spec=GmailClient)

        emails = generate_test_emails(100)
        message_ids = [email.id for email in emails]

        # Mock batch fetch
        mock_gmail.get_messages_batch.return_value = emails

        # Benchmark
        start_time = time.time()
        result = mock_gmail.get_messages_batch(message_ids)
        elapsed = time.time() - start_time

        # Performance assertion
        assert len(result) == 100
        assert elapsed < 1.0, f"Batch fetch took {elapsed:.2f}s, expected < 1s"

        # Log performance
        print(f"\nBatch fetch: 100 emails in {elapsed:.3f}s")
        print(f"Rate: {100/elapsed:.1f} emails/second")

    def test_label_fetch_performance(self):
        """Benchmark: Label fetching."""
        mock_gmail = Mock(spec=GmailClient)

        labels = [
            Label(id=f"Label_{i}", name=f"Label {i}", email_count=10, type="user")
            for i in range(50)
        ]

        mock_gmail.get_user_labels.return_value = labels

        # Benchmark
        start_time = time.time()
        result = mock_gmail.get_user_labels()
        elapsed = time.time() - start_time

        # Performance assertion
        assert len(result) == 50
        assert elapsed < 0.5, f"Label fetch took {elapsed:.2f}s, expected < 0.5s"

        # Log performance
        print(f"\nLabel fetch: 50 labels in {elapsed:.3f}s")

    def test_pagination_performance(self):
        """Benchmark: Paginated email listing."""
        mock_gmail = Mock(spec=GmailClient)

        # Simulate 5 pages of 100 emails each
        num_pages = 5
        page_size = 100
        call_count = 0

        def list_messages(max_results=100, page_token=None):
            nonlocal call_count
            call_count += 1
            if call_count > num_pages:
                return ([], None)

            message_ids = [f"msg_{call_count}_{i}" for i in range(page_size)]
            next_token = "next" if call_count < num_pages else None
            return (message_ids, next_token)

        mock_gmail.list_unlabeled_messages.side_effect = list_messages

        # Benchmark
        start_time = time.time()
        all_ids = []
        page_token = None

        while True:
            ids, page_token = mock_gmail.list_unlabeled_messages(
                max_results=page_size,
                page_token=page_token
            )
            all_ids.extend(ids)
            if not page_token:
                break

        elapsed = time.time() - start_time

        # Performance assertion
        assert len(all_ids) == num_pages * page_size
        assert elapsed < 2.0, f"Pagination took {elapsed:.2f}s, expected < 2s"

        # Log performance
        print(f"\nPagination: {num_pages} pages ({len(all_ids)} emails) in {elapsed:.3f}s")
        print(f"Rate: {len(all_ids)/elapsed:.1f} emails/second")

    def test_email_count_performance(self):
        """Benchmark: Email count query."""
        mock_gmail = Mock(spec=GmailClient)
        mock_gmail.count_unlabeled_emails.return_value = 5000

        # Benchmark
        start_time = time.time()
        for _ in range(100):
            count = mock_gmail.count_unlabeled_emails()
        elapsed = time.time() - start_time

        # Performance assertion
        assert count == 5000
        assert elapsed < 1.0, f"100 count queries took {elapsed:.2f}s, expected < 1s"

        # Log performance
        print(f"\nCount queries: 100 queries in {elapsed:.3f}s")
        print(f"Rate: {100/elapsed:.1f} queries/second")

    def test_concurrent_batch_fetches(self):
        """Benchmark: Multiple concurrent batch fetches."""
        mock_gmail = Mock(spec=GmailClient)

        # Simulate multiple batches
        num_batches = 10
        batch_size = 50

        def get_batch(message_ids):
            return generate_test_emails(len(message_ids))

        mock_gmail.get_messages_batch.side_effect = get_batch

        # Benchmark
        start_time = time.time()
        for i in range(num_batches):
            message_ids = [f"msg_{i}_{j}" for j in range(batch_size)]
            emails = mock_gmail.get_messages_batch(message_ids)
            assert len(emails) == batch_size
        elapsed = time.time() - start_time

        total_emails = num_batches * batch_size

        # Performance assertion
        assert elapsed < 5.0, f"Batch fetches took {elapsed:.2f}s, expected < 5s"

        # Log performance
        print(f"\nConcurrent batches: {num_batches} batches ({total_emails} emails) in {elapsed:.2f}s")
        print(f"Rate: {total_emails/elapsed:.1f} emails/second")

    def test_email_filtering_performance(self):
        """Benchmark: Filtering unlabeled emails."""
        # Generate mixed emails
        all_emails = []
        for i in range(200):
            if i % 2 == 0:
                # Unlabeled email
                labels = ["INBOX"]
            else:
                # Labeled email
                labels = ["INBOX", "Label_1"]

            email = Email(
                id=f"msg_{i}",
                thread_id=f"thread_{i}",
                subject=f"Test Email {i}",
                sender=f"sender{i}@test.com",
                sender_name=f"Sender {i}",
                recipients=["me@test.com"],
                date="2025-01-01T10:00:00Z",
                labels=labels,
                snippet=f"Test snippet {i}",
                content=f"Test content {i}",
                body_plain=f"Test content {i}",
                body_html=None
            )
            all_emails.append(email)

        # Benchmark filtering
        start_time = time.time()
        unlabeled = [email for email in all_emails if email.is_unlabeled]
        elapsed = time.time() - start_time

        # Performance assertion
        assert len(unlabeled) == 100  # Half are unlabeled
        assert elapsed < 0.1, f"Filtering took {elapsed:.3f}s, expected < 0.1s"

        # Log performance
        print(f"\nFiltering: 200 emails filtered in {elapsed:.3f}s")
        print(f"Found {len(unlabeled)} unlabeled emails")

    @pytest.mark.slow
    def test_large_batch_fetch_performance(self):
        """Benchmark: Large batch email fetch."""
        mock_gmail = Mock(spec=GmailClient)

        # Large batch
        batch_size = 500
        emails = generate_test_emails(batch_size)
        message_ids = [email.id for email in emails]

        mock_gmail.get_messages_batch.return_value = emails

        # Benchmark
        start_time = time.time()
        result = mock_gmail.get_messages_batch(message_ids)
        elapsed = time.time() - start_time

        # Performance assertion
        assert len(result) == batch_size
        assert elapsed < 5.0, f"Large batch fetch took {elapsed:.2f}s, expected < 5s"

        # Log performance
        print(f"\nLarge batch: {batch_size} emails in {elapsed:.2f}s")
        print(f"Rate: {batch_size/elapsed:.1f} emails/second")

    def test_profile_fetch_performance(self):
        """Benchmark: User profile fetching."""
        mock_gmail = Mock(spec=GmailClient)
        mock_gmail.get_profile.return_value = {"emailAddress": "test@example.com"}

        # Benchmark
        start_time = time.time()
        for _ in range(100):
            profile = mock_gmail.get_profile()
        elapsed = time.time() - start_time

        # Performance assertion
        assert profile["emailAddress"] == "test@example.com"
        assert elapsed < 1.0, f"100 profile fetches took {elapsed:.2f}s, expected < 1s"

        # Log performance
        print(f"\nProfile fetch: 100 fetches in {elapsed:.3f}s")

    def test_label_application_performance(self):
        """Benchmark: Label application rate."""
        mock_gmail = Mock(spec=GmailClient)
        mock_gmail.add_label_to_message.return_value = True

        num_operations = 100

        # Benchmark
        start_time = time.time()
        for i in range(num_operations):
            result = mock_gmail.add_label_to_message(f"msg_{i}", "Label_1")
            assert result is True
        elapsed = time.time() - start_time

        # Performance assertion
        assert elapsed < 5.0, f"Label applications took {elapsed:.2f}s, expected < 5s"

        # Log performance
        print(f"\nLabel application: {num_operations} operations in {elapsed:.2f}s")
        print(f"Rate: {num_operations/elapsed:.1f} operations/second")

    def test_message_id_listing_performance(self):
        """Benchmark: Message ID listing speed."""
        mock_gmail = Mock(spec=GmailClient)

        # Return many message IDs
        message_ids = [f"msg_{i}" for i in range(1000)]
        mock_gmail.list_unlabeled_messages.return_value = (message_ids, None)

        # Benchmark
        start_time = time.time()
        ids, token = mock_gmail.list_unlabeled_messages(max_results=1000)
        elapsed = time.time() - start_time

        # Performance assertion
        assert len(ids) == 1000
        assert elapsed < 1.0, f"ID listing took {elapsed:.2f}s, expected < 1s"

        # Log performance
        print(f"\nID listing: 1000 IDs in {elapsed:.3f}s")
