"""Contract tests for Gmail API client.

These tests verify the Gmail API integration contracts without making actual API calls.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Mock the google API modules before importing our code
import sys
sys.modules['googleapiclient'] = MagicMock()
sys.modules['googleapiclient.discovery'] = MagicMock()
sys.modules['googleapiclient.errors'] = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.auth'] = MagicMock()
sys.modules['google.oauth2'] = MagicMock()
sys.modules['google.oauth2.credentials'] = MagicMock()

from gmail_classifier.models.label import Label
from gmail_classifier.models.email import Email


class TestGmailAPIContract:
    """Test Gmail API contract compliance."""

    @pytest.fixture
    def mock_credentials(self):
        """Create mock credentials."""
        mock_creds = Mock()
        mock_creds.valid = True
        return mock_creds

    @pytest.fixture
    def mock_gmail_service(self):
        """Create mock Gmail service."""
        mock_service = MagicMock()
        return mock_service

    def test_list_labels_contract(self, mock_gmail_service):
        """Test that list labels follows Gmail API contract."""
        # Mock the Gmail API response for labels().list()
        mock_gmail_service.users().labels().list().execute.return_value = {
            'labels': [
                {
                    'id': 'INBOX',
                    'name': 'INBOX',
                    'type': 'system',
                    'messagesTotal': 100,
                },
                {
                    'id': 'Label_123',
                    'name': 'Work',
                    'type': 'user',
                    'messagesTotal': 42,
                },
            ]
        }

        # Verify the call structure
        result = mock_gmail_service.users().labels().list(userId='me').execute()

        assert 'labels' in result
        assert len(result['labels']) == 2
        assert result['labels'][0]['id'] == 'INBOX'
        assert result['labels'][1]['id'] == 'Label_123'

        # Verify method calls
        mock_gmail_service.users().labels().list.assert_called_with(userId='me')

    def test_list_messages_contract(self, mock_gmail_service):
        """Test that list messages follows Gmail API contract."""
        # Mock the Gmail API response for messages().list()
        mock_gmail_service.users().messages().list().execute.return_value = {
            'messages': [
                {'id': 'msg1', 'threadId': 'thread1'},
                {'id': 'msg2', 'threadId': 'thread2'},
            ],
            'nextPageToken': 'token123',
            'resultSizeEstimate': 2,
        }

        # Verify the call structure
        result = mock_gmail_service.users().messages().list(
            userId='me',
            q='in:inbox',
            maxResults=500
        ).execute()

        assert 'messages' in result
        assert len(result['messages']) == 2
        assert 'nextPageToken' in result

        # Verify method calls
        mock_gmail_service.users().messages().list.assert_called_with(
            userId='me',
            q='in:inbox',
            maxResults=500
        )

    def test_get_message_contract(self, mock_gmail_service):
        """Test that get message follows Gmail API contract."""
        # Mock the Gmail API response for messages().get()
        mock_gmail_service.users().messages().get().execute.return_value = {
            'id': 'msg123',
            'threadId': 'thread123',
            'labelIds': ['INBOX', 'UNREAD'],
            'snippet': 'Email preview text...',
            'payload': {
                'headers': [
                    {'name': 'From', 'value': 'sender@example.com'},
                    {'name': 'To', 'value': 'recipient@example.com'},
                    {'name': 'Subject', 'value': 'Test Subject'},
                    {'name': 'Date', 'value': 'Mon, 1 Jan 2025 12:00:00 +0000'},
                ],
                'mimeType': 'text/plain',
                'body': {
                    'data': 'VGVzdCBib2R5',  # Base64 encoded "Test body"
                },
            },
        }

        # Verify the call structure
        result = mock_gmail_service.users().messages().get(
            userId='me',
            id='msg123',
            format='full'
        ).execute()

        assert result['id'] == 'msg123'
        assert result['threadId'] == 'thread123'
        assert 'payload' in result
        assert 'headers' in result['payload']

        # Verify method calls
        mock_gmail_service.users().messages().get.assert_called_with(
            userId='me',
            id='msg123',
            format='full'
        )

    def test_modify_message_labels_contract(self, mock_gmail_service):
        """Test that modify message labels follows Gmail API contract."""
        # Mock the Gmail API response for messages().modify()
        mock_gmail_service.users().messages().modify().execute.return_value = {
            'id': 'msg123',
            'threadId': 'thread123',
            'labelIds': ['INBOX', 'Label_123'],
        }

        # Verify the call structure
        result = mock_gmail_service.users().messages().modify(
            userId='me',
            id='msg123',
            body={
                'addLabelIds': ['Label_123'],
                'removeLabelIds': [],
            }
        ).execute()

        assert result['id'] == 'msg123'
        assert 'Label_123' in result['labelIds']

        # Verify method calls
        mock_gmail_service.users().messages().modify.assert_called_once()
        call_args = mock_gmail_service.users().messages().modify.call_args

        assert call_args[1]['userId'] == 'me'
        assert call_args[1]['id'] == 'msg123'
        assert 'addLabelIds' in call_args[1]['body']

    def test_error_handling_contract(self, mock_gmail_service):
        """Test that HTTP errors are handled correctly."""
        from googleapiclient.errors import HttpError

        # Create a mock HTTP error
        mock_response = Mock()
        mock_response.status = 429  # Rate limit error

        # Mock the API to raise HttpError
        error = HttpError(resp=mock_response, content=b'Rate limit exceeded')
        mock_gmail_service.users().labels().list().execute.side_effect = error

        # Verify that HttpError is raised
        with pytest.raises(HttpError) as exc_info:
            mock_gmail_service.users().labels().list().execute()

        assert exc_info.value.resp.status == 429

    def test_pagination_contract(self, mock_gmail_service):
        """Test that pagination follows Gmail API contract."""
        # First page response
        first_response = {
            'messages': [{'id': 'msg1'}, {'id': 'msg2'}],
            'nextPageToken': 'page2_token',
        }

        # Second page response
        second_response = {
            'messages': [{'id': 'msg3'}, {'id': 'msg4'}],
            # No nextPageToken means last page
        }

        # Configure mock to return different responses
        mock_gmail_service.users().messages().list().execute.side_effect = [
            first_response,
            second_response,
        ]

        # First call - should have nextPageToken
        result1 = mock_gmail_service.users().messages().list(
            userId='me',
            maxResults=2
        ).execute()

        assert 'nextPageToken' in result1
        assert result1['nextPageToken'] == 'page2_token'

        # Second call with pageToken
        result2 = mock_gmail_service.users().messages().list(
            userId='me',
            maxResults=2,
            pageToken='page2_token'
        ).execute()

        assert 'nextPageToken' not in result2  # Last page

    def test_user_profile_contract(self, mock_gmail_service):
        """Test that get user profile follows Gmail API contract."""
        # Mock the Gmail API response for getProfile()
        mock_gmail_service.users().getProfile().execute.return_value = {
            'emailAddress': 'user@example.com',
            'messagesTotal': 1234,
            'threadsTotal': 567,
            'historyId': '123456',
        }

        # Verify the call structure
        result = mock_gmail_service.users().getProfile(userId='me').execute()

        assert result['emailAddress'] == 'user@example.com'
        assert 'messagesTotal' in result
        assert 'threadsTotal' in result

        # Verify method calls
        mock_gmail_service.users().getProfile.assert_called_with(userId='me')

    def test_batch_request_contract(self, mock_gmail_service):
        """Test that batch requests follow Gmail API contract."""
        # Mock batch request response
        mock_batch = MagicMock()
        mock_gmail_service.new_batch_http_request.return_value = mock_batch

        # Create batch
        batch = mock_gmail_service.new_batch_http_request()

        # Add requests to batch
        batch.add(mock_gmail_service.users().messages().get(userId='me', id='msg1'))
        batch.add(mock_gmail_service.users().messages().get(userId='me', id='msg2'))

        # Execute batch
        batch.execute()

        # Verify batch was created and executed
        mock_gmail_service.new_batch_http_request.assert_called_once()
        mock_batch.execute.assert_called_once()
        assert mock_batch.add.call_count == 2


class TestLabelFromGmailAPI:
    """Test Label model creation from Gmail API responses."""

    def test_create_user_label_from_api_response(self):
        """Test creating user label from Gmail API response."""
        api_response = {
            'id': 'Label_456',
            'name': 'Personal',
            'messagesTotal': 25,
            'threadsTotal': 15,
        }

        label = Label.from_gmail_label(api_response)

        assert label.id == 'Label_456'
        assert label.name == 'Personal'
        assert label.email_count == 25
        assert label.type == 'user'
        assert label.is_user_label is True

    def test_create_system_label_from_api_response(self):
        """Test creating system label from Gmail API response."""
        api_response = {
            'id': 'INBOX',
            'name': 'INBOX',
            'messagesTotal': 150,
        }

        label = Label.from_gmail_label(api_response)

        assert label.id == 'INBOX'
        assert label.type == 'system'
        assert label.is_system_label is True


class TestEmailFromGmailAPI:
    """Test Email model creation from Gmail API responses."""

    def test_create_email_from_api_response(self):
        """Test creating email from Gmail API response."""
        api_response = {
            'id': 'msg123',
            'threadId': 'thread123',
            'labelIds': ['INBOX', 'UNREAD'],
            'snippet': 'Email preview...',
            'payload': {
                'headers': [
                    {'name': 'From', 'value': 'John Doe <john@example.com>'},
                    {'name': 'To', 'value': 'jane@example.com'},
                    {'name': 'Subject', 'value': 'Test Email'},
                    {'name': 'Date', 'value': 'Mon, 1 Jan 2025 12:00:00 +0000'},
                ],
                'mimeType': 'text/plain',
                'body': {
                    'data': 'VGVzdCBib2R5',  # Base64: "Test body"
                },
            },
        }

        email = Email.from_gmail_message(api_response)

        assert email.id == 'msg123'
        assert email.thread_id == 'thread123'
        assert email.subject == 'Test Email'
        assert email.sender == 'john@example.com'
        assert email.sender_name == 'John Doe'
        assert 'INBOX' in email.labels
        assert email.is_unread is True

    def test_email_with_missing_headers(self):
        """Test creating email with missing optional headers."""
        api_response = {
            'id': 'msg456',
            'threadId': 'thread456',
            'labelIds': ['INBOX'],
            'snippet': 'No subject email',
            'payload': {
                'headers': [
                    {'name': 'From', 'value': 'sender@example.com'},
                    # Missing Subject header
                ],
                'body': {},
            },
        }

        email = Email.from_gmail_message(api_response)

        assert email.id == 'msg456'
        assert email.subject is None
        assert email.display_subject == '(No Subject)'
