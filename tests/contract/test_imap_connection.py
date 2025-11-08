"""Contract tests for IMAP connection to Gmail.

These tests verify that the imapclient library works correctly with Gmail's
IMAP server and validates the basic connection and authentication protocol.

Test Organization:
- T010: Basic SSL connection to Gmail IMAP server
- T011: Successful authentication with valid credentials
- T012: Authentication failure scenarios (invalid credentials, network errors, timeouts)

NOTE: These tests require:
1. Gmail account with IMAP enabled
2. App password generated (2FA enabled accounts)
3. Environment variables: GMAIL_TEST_EMAIL, GMAIL_TEST_APP_PASSWORD
"""

import os
import socket
from unittest.mock import MagicMock, patch

import pytest
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError


# ============================================================================
# Test Configuration
# ============================================================================


@pytest.fixture
def gmail_test_credentials() -> tuple[str, str]:
    """Provide test Gmail credentials from environment.

    Returns:
        Tuple of (email, app_password)

    Raises:
        pytest.skip: If credentials not available in environment
    """
    email = os.getenv("GMAIL_TEST_EMAIL")
    password = os.getenv("GMAIL_TEST_APP_PASSWORD")

    if not email or not password:
        pytest.skip("Gmail test credentials not available in environment")

    return email, password


# ============================================================================
# T010: Test Basic IMAP Connection
# ============================================================================


class TestIMAPConnection:
    """Contract tests for basic IMAP connection to Gmail."""

    def test_connect_to_gmail_imap_server_with_ssl(self) -> None:
        """T010: Test basic SSL connection to imap.gmail.com:993.

        Validates:
        - Can connect to Gmail IMAP server
        - SSL/TLS connection established successfully
        - Server responds to basic commands (CAPABILITY)

        Expected outcome: Connection established, capabilities returned
        """
        # Arrange
        server = "imap.gmail.com"
        port = 993

        # Act
        with IMAPClient(server, port=port, ssl=True) as client:
            # Assert - connection established
            assert client is not None
            assert client._imap is not None

            # Verify server capabilities
            capabilities = client.capabilities()
            assert b"IMAP4REV1" in capabilities
            assert b"STARTTLS" not in capabilities  # Should use SSL, not STARTTLS

    def test_connect_fails_with_invalid_server(self) -> None:
        """T010: Test connection failure with invalid server address.

        Validates:
        - Connection errors are properly raised
        - Network issues are detectable

        Expected outcome: Connection error raised
        """
        # Arrange
        invalid_server = "invalid.gmail.com"
        port = 993

        # Act & Assert
        with pytest.raises((socket.gaierror, OSError)):
            with IMAPClient(invalid_server, port=port, ssl=True, timeout=5):
                pass

    def test_connect_fails_with_timeout(self) -> None:
        """T010: Test connection timeout handling.

        Validates:
        - Timeout errors are properly handled
        - Connection respects timeout parameter

        Expected outcome: Timeout error raised
        """
        # Arrange - use non-routable IP to force timeout
        non_routable_server = "10.255.255.1"
        port = 993

        # Act & Assert
        with pytest.raises((socket.timeout, OSError)):
            with IMAPClient(non_routable_server, port=port, ssl=True, timeout=1):
                pass


# ============================================================================
# T011: Test Authentication Success
# ============================================================================


class TestIMAPAuthentication:
    """Contract tests for IMAP authentication with Gmail."""

    def test_authenticate_with_valid_credentials(
        self, gmail_test_credentials: tuple[str, str]
    ) -> None:
        """T011: Test successful authentication with valid Gmail credentials.

        Validates:
        - Can login with email + app password
        - Connection remains open after authentication
        - Can execute basic IMAP commands (SELECT INBOX)

        Expected outcome: Authentication successful, INBOX accessible
        """
        # Arrange
        email, password = gmail_test_credentials
        server = "imap.gmail.com"
        port = 993

        # Act
        with IMAPClient(server, port=port, ssl=True) as client:
            # Authenticate
            response = client.login(email, password)

            # Assert - authentication successful
            assert response is not None
            assert isinstance(response, bytes)
            assert b"success" in response.lower() or email.encode() in response

            # Verify post-authentication operations
            select_response = client.select_folder("INBOX")
            assert b"EXISTS" in select_response
            assert select_response[b"EXISTS"] >= 0  # May have 0 emails

    def test_authenticated_connection_supports_noop(
        self, gmail_test_credentials: tuple[str, str]
    ) -> None:
        """T011: Test NOOP command on authenticated connection (for keepalive).

        Validates:
        - NOOP command works after authentication
        - Connection stays alive with NOOP

        Expected outcome: NOOP returns success response
        """
        # Arrange
        email, password = gmail_test_credentials

        # Act
        with IMAPClient("imap.gmail.com", ssl=True) as client:
            client.login(email, password)

            # Send NOOP (keepalive)
            noop_response = client.noop()

            # Assert - NOOP successful
            assert noop_response is not None
            assert isinstance(noop_response, (bytes, tuple))


# ============================================================================
# T012: Test Authentication Failures
# ============================================================================


class TestIMAPAuthenticationFailures:
    """Contract tests for IMAP authentication failure scenarios."""

    def test_authentication_fails_with_invalid_password(
        self, gmail_test_credentials: tuple[str, str]
    ) -> None:
        """T012: Test authentication failure with invalid password.

        Validates:
        - Invalid credentials are rejected
        - Appropriate exception is raised
        - Error message indicates authentication failure

        Expected outcome: IMAPClientError raised with auth failure message
        """
        # Arrange
        email, _ = gmail_test_credentials
        invalid_password = "invalid_password_12345"

        # Act & Assert
        with IMAPClient("imap.gmail.com", ssl=True) as client:
            with pytest.raises(IMAPClientError) as exc_info:
                client.login(email, invalid_password)

            # Verify error message indicates authentication failure
            error_message = str(exc_info.value).lower()
            assert any(
                keyword in error_message
                for keyword in ["invalid", "authentication", "failed", "credentials"]
            )

    def test_authentication_fails_with_invalid_email(self) -> None:
        """T012: Test authentication failure with invalid email address.

        Validates:
        - Invalid email format is rejected
        - Server responds with appropriate error

        Expected outcome: IMAPClientError raised
        """
        # Arrange
        invalid_email = "notarealemail@invaliddomain12345.com"
        invalid_password = "invalid_password"

        # Act & Assert
        with IMAPClient("imap.gmail.com", ssl=True) as client:
            with pytest.raises(IMAPClientError):
                client.login(invalid_email, invalid_password)

    @patch("imapclient.IMAPClient.login")
    def test_authentication_handles_network_interruption(
        self, mock_login: MagicMock
    ) -> None:
        """T012: Test authentication handles network errors gracefully.

        Validates:
        - Network errors during auth are caught
        - Connection errors are properly raised

        Expected outcome: Exception raised for network issues
        """
        # Arrange
        mock_login.side_effect = OSError("Network connection lost")

        # Act & Assert
        with IMAPClient("imap.gmail.com", ssl=True) as client:
            with pytest.raises(OSError) as exc_info:
                client.login("test@gmail.com", "password")

            assert "Network connection lost" in str(exc_info.value)

    @patch("imapclient.IMAPClient.login")
    def test_authentication_handles_timeout(self, mock_login: MagicMock) -> None:
        """T012: Test authentication handles timeout scenarios.

        Validates:
        - Timeout during authentication is handled
        - Appropriate timeout exception is raised

        Expected outcome: Timeout exception raised
        """
        # Arrange
        mock_login.side_effect = socket.timeout("Operation timed out")

        # Act & Assert
        with IMAPClient("imap.gmail.com", ssl=True) as client:
            with pytest.raises(socket.timeout) as exc_info:
                client.login("test@gmail.com", "password")

            assert "timed out" in str(exc_info.value).lower()


# ============================================================================
# Test Fixtures and Helpers
# ============================================================================


@pytest.fixture
def mock_imap_client() -> MagicMock:
    """Provide a mocked IMAPClient for unit tests.

    Returns:
        MagicMock configured to simulate IMAPClient behavior
    """
    mock_client = MagicMock(spec=IMAPClient)
    mock_client.capabilities.return_value = {b"IMAP4REV1", b"IDLE", b"NAMESPACE"}
    mock_client.login.return_value = b"LOGIN completed"
    mock_client.select_folder.return_value = {b"EXISTS": 42, b"RECENT": 5}
    mock_client.noop.return_value = (b"OK", [b"NOOP completed"])
    return mock_client
