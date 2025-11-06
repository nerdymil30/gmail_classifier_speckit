"""Pytest configuration and shared fixtures."""

import pytest
import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_email_data():
    """Sample email data for testing."""
    return {
        "id": "msg123",
        "threadId": "thread123",
        "subject": "Test Email Subject",
        "sender": "sender@example.com",
        "sender_name": "Test Sender",
        "recipients": ["recipient@example.com"],
        "snippet": "This is a test email snippet",
        "labels": ["INBOX", "UNREAD"],
        "has_attachments": False,
        "is_unread": True,
    }


@pytest.fixture
def sample_label_data():
    """Sample label data for testing."""
    return {
        "id": "Label_123",
        "name": "Work",
        "email_count": 42,
        "type": "user",
    }


@pytest.fixture
def sample_gmail_message_response():
    """Sample Gmail API message response."""
    return {
        "id": "msg123",
        "threadId": "thread123",
        "labelIds": ["INBOX", "UNREAD"],
        "snippet": "Test email content...",
        "payload": {
            "headers": [
                {"name": "From", "value": "John Doe <john@example.com>"},
                {"name": "To", "value": "jane@example.com"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "Mon, 1 Jan 2025 12:00:00 +0000"},
            ],
            "mimeType": "text/plain",
            "body": {
                "data": "VGVzdCBib2R5",  # Base64 encoded "Test body"
            },
        },
    }


@pytest.fixture
def sample_gmail_labels_response():
    """Sample Gmail API labels list response."""
    return {
        "labels": [
            {
                "id": "INBOX",
                "name": "INBOX",
                "type": "system",
                "messagesTotal": 100,
            },
            {
                "id": "Label_123",
                "name": "Work",
                "type": "user",
                "messagesTotal": 42,
            },
            {
                "id": "Label_456",
                "name": "Personal",
                "type": "user",
                "messagesTotal": 25,
            },
        ]
    }


# Configure pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast, no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "contract: marks tests as contract tests (API mocking)"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (slower, may use real APIs)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
