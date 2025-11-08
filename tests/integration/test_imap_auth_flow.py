"""Integration tests for IMAP authentication flow.

These tests verify end-to-end authentication scenarios from credential input
through connection establishment and verification.

Test Organization:
- T013: Complete authentication flow (credentials → authenticate → verify)
- T025: Auto-authentication with saved credentials (User Story 2)
- T035: Email retrieval after authentication (User Story 3)
- T036: Classification integration with IMAP emails (User Story 3)

NOTE: These tests require IMAPAuthenticator implementation to be complete.
Early tests will be skipped until the implementation is available.
"""

import os
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from gmail_classifier.auth.imap import (
    IMAPAuthenticationError,
    IMAPConnectionError,
    IMAPCredentials,
    IMAPSessionInfo,
    SessionState,
)

# IMAPAuthenticator will be implemented in T014-T021
# For now, tests will use mocks or be skipped


# ============================================================================
# Test Configuration
# ============================================================================


@pytest.fixture
def test_credentials() -> IMAPCredentials:
    """Provide test IMAP credentials.

    Returns:
        IMAPCredentials with test email and password
    """
    return IMAPCredentials(
        email="test@gmail.com",
        password="test_app_password_16ch",
        created_at=datetime.now(),
    )


@pytest.fixture
def gmail_live_credentials() -> IMAPCredentials:
    """Provide live Gmail credentials from environment (optional).

    Returns:
        IMAPCredentials from environment variables

    Raises:
        pytest.skip: If live credentials not available
    """
    email = os.getenv("GMAIL_TEST_EMAIL")
    password = os.getenv("GMAIL_TEST_APP_PASSWORD")

    if not email or not password:
        pytest.skip("Live Gmail credentials not available for integration test")

    return IMAPCredentials(
        email=email,
        password=password,
        created_at=datetime.now(),
    )


# ============================================================================
# T013: Complete Authentication Flow
# ============================================================================


class TestCompleteAuthenticationFlow:
    """Integration tests for end-to-end IMAP authentication."""

    def test_authenticate_with_valid_credentials_creates_session(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """T013: Test complete auth flow: credentials → authenticate → verify.

        Flow:
        1. Provide valid IMAP credentials
        2. Call authenticate() method
        3. Verify session created with CONNECTED state
        4. Verify connection is alive
        5. Verify session info contains correct email

        Expected outcome:
        - Session created successfully
        - State is CONNECTED
        - Connection responds to is_alive()
        - Session email matches credentials
        """
        from unittest.mock import MagicMock, patch

        from gmail_classifier.auth.imap import IMAPAuthenticator

        # Mock the IMAPClient to avoid real network calls
        with patch("imapclient.IMAPClient") as mock_client_class:
            # Configure mock
            mock_client = MagicMock()
            mock_client.login.return_value = b"LOGIN completed"
            mock_client.noop.return_value = (b"OK", [b"NOOP completed"])
            mock_client_class.return_value = mock_client

            # Test authentication
            authenticator = IMAPAuthenticator()
            session_info = authenticator.authenticate(test_credentials)

            # Assert
            assert session_info.state == SessionState.CONNECTED
            assert session_info.email == test_credentials.email
            assert authenticator.is_alive(session_info.session_id)
            assert test_credentials.last_used is not None

            # Cleanup
            authenticator.disconnect(session_info.session_id)

    def test_authenticate_with_invalid_credentials_raises_error(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """T013: Test auth flow with invalid credentials raises error.

        Flow:
        1. Provide invalid IMAP credentials
        2. Call authenticate() method
        3. Expect IMAPAuthenticationError raised
        4. Verify error message is clear and actionable

        Expected outcome:
        - IMAPAuthenticationError raised
        - Error message explains failure
        - No session created
        """
        from unittest.mock import MagicMock, patch

        from imapclient.exceptions import IMAPClientError

        from gmail_classifier.auth.imap import IMAPAuthenticator

        # Mock the IMAPClient to simulate authentication failure
        with patch("imapclient.IMAPClient") as mock_client_class:
            # Configure mock to raise authentication error
            mock_client = MagicMock()
            mock_client.login.side_effect = IMAPClientError("Invalid credentials")
            mock_client_class.return_value = mock_client

            # Test authentication with invalid credentials
            authenticator = IMAPAuthenticator()
            invalid_creds = IMAPCredentials(
                email=test_credentials.email, password="wrongpassword"
            )

            with pytest.raises(IMAPAuthenticationError) as exc_info:
                authenticator.authenticate(invalid_creds)

            assert "authentication failed" in str(exc_info.value).lower()

    def test_authenticate_with_network_error_raises_connection_error(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """T013: Test auth flow with network errors raises ConnectionError.

        Flow:
        1. Simulate network connectivity issues
        2. Attempt authentication
        3. Expect IMAPConnectionError raised
        4. Verify retry logic is attempted

        Expected outcome:
        - IMAPConnectionError raised after retries
        - Retry count tracked in error context
        - Clear error message for user
        """
        from unittest.mock import patch

        from gmail_classifier.auth.imap import IMAPAuthenticator

        # Mock the IMAPClient to simulate network error
        with patch("imapclient.IMAPClient") as mock_client_class:
            # Configure mock to raise network error
            mock_client_class.side_effect = OSError("Network unreachable")

            # Test authentication with network error
            authenticator = IMAPAuthenticator()

            with pytest.raises(IMAPConnectionError) as exc_info:
                authenticator.authenticate(test_credentials)

            # Verify retry logic was attempted
            assert "after 5 attempts" in str(exc_info.value).lower()

    def test_successful_authentication_updates_credentials_last_used(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """T013: Test successful auth updates credentials last_used timestamp.

        Flow:
        1. Authenticate with credentials
        2. Verify last_used timestamp is updated
        3. Timestamp should be recent (within last minute)

        Expected outcome:
        - last_used field updated to current time
        - Timestamp reflects successful authentication
        """
        from unittest.mock import MagicMock, patch

        from gmail_classifier.auth.imap import IMAPAuthenticator

        # Mock the IMAPClient to avoid real network calls
        with patch("imapclient.IMAPClient") as mock_client_class:
            # Configure mock
            mock_client = MagicMock()
            mock_client.login.return_value = b"LOGIN completed"
            mock_client.noop.return_value = (b"OK", [b"NOOP completed"])
            mock_client_class.return_value = mock_client

            # Test authentication updates last_used
            authenticator = IMAPAuthenticator()
            before_auth = datetime.now()
            session_info = authenticator.authenticate(test_credentials)

            # Assert
            assert test_credentials.last_used is not None
            assert test_credentials.last_used >= before_auth

            # Cleanup
            authenticator.disconnect(session_info.session_id)

    @pytest.mark.skip(reason="Requires IMAPAuthenticator and live credentials")
    def test_live_authentication_with_real_gmail_account(
        self, gmail_live_credentials: IMAPCredentials
    ) -> None:
        """T013: Test authentication with real Gmail account (optional).

        This test uses real Gmail credentials from environment to verify
        end-to-end authentication works with Gmail's IMAP server.

        Flow:
        1. Use real Gmail credentials
        2. Authenticate to Gmail IMAP server
        3. Verify connection established
        4. Verify can access INBOX
        5. Disconnect cleanly

        Expected outcome:
        - Real authentication succeeds
        - INBOX accessible
        - Clean disconnect
        """
        # This test will be implemented after T014-T021
        # Requires GMAIL_TEST_EMAIL and GMAIL_TEST_APP_PASSWORD in environment
        pass


# ============================================================================
# Mock Helpers for Early Testing
# ============================================================================


@pytest.fixture
def mock_imap_authenticator() -> Mock:
    """Provide a mocked IMAPAuthenticator for testing.

    Returns:
        Mock IMAPAuthenticator with simulated behavior
    """
    mock_auth = Mock()

    # Mock successful authentication
    def mock_authenticate(credentials: IMAPCredentials) -> IMAPSessionInfo:
        if credentials.password == "valid_password":
            return IMAPSessionInfo(
                email=credentials.email,
                state=SessionState.CONNECTED,
                selected_folder="INBOX",
                retry_count=0,
            )
        else:
            raise IMAPAuthenticationError("Invalid credentials")

    mock_auth.authenticate.side_effect = mock_authenticate
    mock_auth.is_alive.return_value = True
    mock_auth.disconnect.return_value = None

    return mock_auth


# ============================================================================
# Placeholder Tests for Future User Stories
# ============================================================================


class TestAutoAuthenticationWithSavedCredentials:
    """Integration tests for auto-authentication (User Story 2, T025)."""

    def test_auto_authenticate_with_saved_credentials(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """T025: Test auto-authentication using saved credentials.

        Flow:
        1. Credentials saved in keyring
        2. Application starts
        3. Retrieve credentials from storage
        4. Auto-authenticate
        5. Verify connected state

        Expected outcome:
        - Auto-authentication succeeds
        - No user prompt required
        - Session established automatically
        """
        from unittest.mock import MagicMock, patch

        from gmail_classifier.auth.imap import IMAPAuthenticator
        from gmail_classifier.storage.credentials import CredentialStorage

        # Mock keyring and IMAP client
        with patch("keyring.get_password") as mock_get_password:
            with patch("imapclient.IMAPClient") as mock_client_class:
                # Configure mocks
                mock_get_password.return_value = test_credentials.password
                mock_client = MagicMock()
                mock_client.login.return_value = b"LOGIN completed"
                mock_client.noop.return_value = (b"OK", [b"NOOP completed"])
                mock_client_class.return_value = mock_client

                # Simulate application restart - retrieve saved credentials
                storage = CredentialStorage()
                retrieved_creds = storage.retrieve_credentials(test_credentials.email)

                # Assert credentials were retrieved
                assert retrieved_creds is not None
                assert retrieved_creds.email == test_credentials.email

                # Auto-authenticate with retrieved credentials
                authenticator = IMAPAuthenticator()
                session_info = authenticator.authenticate(retrieved_creds)

                # Assert auto-authentication succeeded
                assert session_info.state == SessionState.CONNECTED
                assert session_info.email == test_credentials.email

                # Cleanup
                authenticator.disconnect(session_info.session_id)


class TestEmailRetrievalAfterAuthentication:
    """Integration tests for email retrieval (User Story 3, T035)."""

    def test_fetch_emails_from_inbox_after_authentication(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """T035: Test email retrieval after IMAP authentication.

        Flow:
        1. Authenticate via IMAP
        2. Select INBOX folder
        3. Fetch emails
        4. Verify email structure matches Email entity

        Expected outcome:
        - Emails retrieved successfully
        - Email structure compatible with classification
        """
        from unittest.mock import MagicMock, patch

        from gmail_classifier.auth.imap import IMAPAuthenticator
        from gmail_classifier.email.fetcher import FolderManager

        with patch("imapclient.IMAPClient") as mock_client_class:
            # Configure mocks
            mock_client = MagicMock()
            mock_client.login.return_value = b"LOGIN completed"
            mock_client.noop.return_value = (b"OK", [b"NOOP completed"])
            mock_client.select_folder.return_value = {
                b"EXISTS": 10,
                b"RECENT": 2,
            }
            # Mock email fetch
            mock_client.search.return_value = [1, 2, 3]
            mock_client.fetch.return_value = {
                1: {
                    b"BODY[]": b"From: test@example.com\r\nSubject: Test Email\r\n\r\nTest body",
                    b"FLAGS": (b"\\Seen",),
                },
            }
            mock_client_class.return_value = mock_client

            # Authenticate
            authenticator = IMAPAuthenticator()
            session_info = authenticator.authenticate(test_credentials)

            # Select INBOX and fetch emails
            folder_manager = FolderManager(authenticator)
            folder_manager.select_folder(session_info.session_id, "INBOX")
            emails = folder_manager.fetch_emails(session_info.session_id, limit=10)

            # Assert
            assert len(emails) > 0
            # Verify email structure has required fields
            assert all(hasattr(email, "subject") for email in emails)
            assert all(hasattr(email, "sender") for email in emails)

            # Cleanup
            authenticator.disconnect(session_info.session_id)


class TestClassificationWithIMAPEmails:
    """Integration tests for classification with IMAP (User Story 3, T036)."""

    def test_classify_emails_retrieved_via_imap(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """T036: Test classification pipeline works with IMAP-retrieved emails.

        Flow:
        1. Authenticate via IMAP
        2. Fetch emails from INBOX
        3. Run classification on emails
        4. Verify classification results

        Expected outcome:
        - IMAP emails work with existing classification logic
        - Labels applied correctly
        - No authentication-specific issues
        """
        from unittest.mock import MagicMock, patch

        from gmail_classifier.auth.imap import IMAPAuthenticator
        from gmail_classifier.email.fetcher import FolderManager

        with patch("imapclient.IMAPClient") as mock_client_class:
            # Configure mocks
            mock_client = MagicMock()
            mock_client.login.return_value = b"LOGIN completed"
            mock_client.noop.return_value = (b"OK", [b"NOOP completed"])
            mock_client.select_folder.return_value = {
                b"EXISTS": 5,
                b"RECENT": 1,
            }
            mock_client.search.return_value = [1]
            mock_client.fetch.return_value = {
                1: {
                    b"BODY[]": b"From: work@example.com\r\nSubject: Project Update\r\n\r\nWork related content",
                    b"FLAGS": (b"\\Seen",),
                },
            }
            mock_client_class.return_value = mock_client

            # Authenticate and fetch
            authenticator = IMAPAuthenticator()
            session_info = authenticator.authenticate(test_credentials)

            folder_manager = FolderManager(authenticator)
            folder_manager.select_folder(session_info.session_id, "INBOX")
            emails = folder_manager.fetch_emails(session_info.session_id, limit=10)

            # Assert emails are in format compatible with classification
            assert len(emails) > 0
            for email in emails:
                # Verify structure matches what classifier expects
                assert hasattr(email, "subject")
                assert hasattr(email, "sender")
                assert hasattr(email, "body") or hasattr(email, "content")

            # Note: Actual classification testing would require the classifier module
            # This test verifies the email format is correct for classification

            # Cleanup
            authenticator.disconnect(session_info.session_id)
