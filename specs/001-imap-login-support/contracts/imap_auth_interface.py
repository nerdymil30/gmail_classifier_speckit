"""
IMAP Authentication Interface Contract

This contract defines the interface for IMAP authentication operations.
Implementations must adhere to this interface to ensure compatibility
with the Gmail classifier system.

Feature: 001-imap-login-support
Date: 2025-11-07
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID


class SessionState(Enum):
    """IMAP session state enumeration."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class AuthenticationError(Exception):
    """Raised when IMAP authentication fails."""
    pass


class ConnectionError(Exception):
    """Raised when IMAP connection cannot be established."""
    pass


class SessionError(Exception):
    """Raised when IMAP session encounters an error."""
    pass


@dataclass
class IMAPCredentials:
    """IMAP login credentials."""
    email: str
    password: str  # App-specific password for 2FA accounts
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None


@dataclass
class IMAPSessionInfo:
    """IMAP session information."""
    session_id: UUID
    email: str
    selected_folder: Optional[str]
    connected_at: datetime
    last_activity: datetime
    state: SessionState
    retry_count: int


class IMAPAuthInterface(ABC):
    """
    Interface for IMAP authentication operations.

    This interface defines the contract for:
    - Authenticating with Gmail via IMAP
    - Managing IMAP sessions
    - Handling connection lifecycle
    """

    @abstractmethod
    def authenticate(self, email: str, password: str) -> IMAPSessionInfo:
        """
        Authenticate with Gmail IMAP server.

        Args:
            email: Gmail email address
            password: IMAP password or app-specific password

        Returns:
            IMAPSessionInfo: Session information for authenticated connection

        Raises:
            AuthenticationError: If credentials are invalid
            ConnectionError: If connection to IMAP server fails

        Example:
            >>> auth = IMAPAuthenticator()
            >>> session = auth.authenticate("user@gmail.com", "app-password")
            >>> assert session.state == SessionState.CONNECTED
        """
        pass

    @abstractmethod
    def disconnect(self, session_id: UUID) -> None:
        """
        Disconnect from IMAP server and cleanup session.

        Args:
            session_id: Session identifier to disconnect

        Raises:
            SessionError: If session does not exist or disconnect fails

        Example:
            >>> auth.disconnect(session.session_id)
        """
        pass

    @abstractmethod
    def reconnect(self, session_id: UUID) -> IMAPSessionInfo:
        """
        Reconnect to IMAP server after connection loss.

        Implements exponential backoff retry logic (max 5 attempts).

        Args:
            session_id: Session identifier to reconnect

        Returns:
            IMAPSessionInfo: Updated session information

        Raises:
            ConnectionError: If reconnection fails after max retries

        Example:
            >>> session = auth.reconnect(session.session_id)
            >>> assert session.state == SessionState.CONNECTED
        """
        pass

    @abstractmethod
    def keepalive(self, session_id: UUID) -> None:
        """
        Send NOOP command to prevent session timeout.

        Should be called every 10-15 minutes for active sessions.

        Args:
            session_id: Session identifier to keep alive

        Raises:
            SessionError: If session does not exist or keepalive fails

        Example:
            >>> auth.keepalive(session.session_id)
        """
        pass

    @abstractmethod
    def get_session_info(self, session_id: UUID) -> IMAPSessionInfo:
        """
        Get current session information.

        Args:
            session_id: Session identifier

        Returns:
            IMAPSessionInfo: Current session state and metadata

        Raises:
            SessionError: If session does not exist

        Example:
            >>> info = auth.get_session_info(session.session_id)
            >>> print(f"Session state: {info.state}")
        """
        pass

    @abstractmethod
    def is_alive(self, session_id: UUID) -> bool:
        """
        Check if session is still alive.

        Args:
            session_id: Session identifier

        Returns:
            bool: True if session is active and connected

        Example:
            >>> if auth.is_alive(session.session_id):
            ...     print("Session is active")
        """
        pass


class CredentialStorageInterface(ABC):
    """
    Interface for secure credential storage operations.

    This interface defines the contract for:
    - Storing IMAP credentials securely
    - Retrieving stored credentials
    - Managing credential lifecycle
    """

    @abstractmethod
    def store_credentials(self, email: str, password: str) -> None:
        """
        Store IMAP credentials securely in OS credential manager.

        Args:
            email: Gmail email address (used as key)
            password: IMAP password or app-specific password

        Raises:
            StorageError: If credential storage fails

        Example:
            >>> storage = CredentialStorage()
            >>> storage.store_credentials("user@gmail.com", "app-password")
        """
        pass

    @abstractmethod
    def retrieve_credentials(self, email: str) -> Optional[IMAPCredentials]:
        """
        Retrieve stored IMAP credentials from OS credential manager.

        Args:
            email: Gmail email address

        Returns:
            IMAPCredentials if found, None otherwise

        Example:
            >>> creds = storage.retrieve_credentials("user@gmail.com")
            >>> if creds:
            ...     print(f"Found credentials for {creds.email}")
        """
        pass

    @abstractmethod
    def delete_credentials(self, email: str) -> bool:
        """
        Delete stored IMAP credentials from OS credential manager.

        Args:
            email: Gmail email address

        Returns:
            bool: True if credentials were deleted, False if not found

        Example:
            >>> if storage.delete_credentials("user@gmail.com"):
            ...     print("Credentials deleted")
        """
        pass

    @abstractmethod
    def has_credentials(self, email: str) -> bool:
        """
        Check if credentials are stored for email address.

        Args:
            email: Gmail email address

        Returns:
            bool: True if credentials exist

        Example:
            >>> if storage.has_credentials("user@gmail.com"):
            ...     print("Credentials found")
        """
        pass


class FolderInterface(ABC):
    """
    Interface for IMAP folder operations.

    This interface defines the contract for:
    - Listing Gmail folders/labels
    - Selecting folders
    - Getting folder metadata
    """

    @abstractmethod
    def list_folders(self, session_id: UUID) -> List[dict]:
        """
        List all IMAP folders (Gmail labels) for authenticated session.

        Args:
            session_id: Active session identifier

        Returns:
            List of folder dictionaries with keys:
                - name: Folder name (e.g., "INBOX", "Work")
                - display_name: Human-readable name
                - type: Folder type (INBOX, SENT, LABEL, etc.)
                - selectable: Whether folder can be selected
                - message_count: Total messages (if available)

        Raises:
            SessionError: If session is not connected

        Example:
            >>> folders = folder_mgr.list_folders(session.session_id)
            >>> for folder in folders:
            ...     print(f"{folder['name']}: {folder['message_count']} messages")
        """
        pass

    @abstractmethod
    def select_folder(self, session_id: UUID, folder_name: str) -> dict:
        """
        Select IMAP folder for message operations.

        Args:
            session_id: Active session identifier
            folder_name: Folder name to select (e.g., "INBOX", "Work")

        Returns:
            Dictionary with folder metadata:
                - name: Selected folder name
                - message_count: Total messages
                - unread_count: Unread messages
                - recent_count: Recent messages

        Raises:
            SessionError: If session is not connected
            FolderNotFoundError: If folder does not exist

        Example:
            >>> info = folder_mgr.select_folder(session.session_id, "INBOX")
            >>> print(f"INBOX has {info['message_count']} messages")
        """
        pass

    @abstractmethod
    def get_folder_status(self, session_id: UUID, folder_name: str) -> dict:
        """
        Get folder status without selecting it.

        Args:
            session_id: Active session identifier
            folder_name: Folder name

        Returns:
            Dictionary with folder metadata (same structure as select_folder)

        Raises:
            SessionError: If session is not connected
            FolderNotFoundError: If folder does not exist

        Example:
            >>> status = folder_mgr.get_folder_status(session.session_id, "Work")
            >>> print(f"Work folder: {status['unread_count']} unread")
        """
        pass


# Example usage and testing patterns
if __name__ == "__main__":
    """
    Example test patterns for implementing the interface.

    These examples demonstrate expected behavior and can be used
    as a basis for contract tests.
    """

    # Example 1: Authentication flow
    def test_authentication_flow():
        # Given
        auth = IMAPAuthenticator()  # type: ignore # Implementation
        email = "user@gmail.com"
        password = "app-specific-password"

        # When
        session = auth.authenticate(email, password)

        # Then
        assert session.state == SessionState.CONNECTED
        assert session.email == email
        assert session.retry_count == 0

        # Cleanup
        auth.disconnect(session.session_id)

    # Example 2: Credential storage flow
    def test_credential_storage_flow():
        # Given
        storage = CredentialStorage()  # type: ignore # Implementation
        email = "user@gmail.com"
        password = "app-password"

        # When - Store
        storage.store_credentials(email, password)

        # Then - Retrieve
        creds = storage.retrieve_credentials(email)
        assert creds is not None
        assert creds.email == email
        assert creds.password == password

        # Cleanup
        storage.delete_credentials(email)
        assert not storage.has_credentials(email)

    # Example 3: Session lifecycle
    def test_session_lifecycle():
        # Given
        auth = IMAPAuthenticator()  # type: ignore
        session = auth.authenticate("user@gmail.com", "password")

        # When - Active session
        assert auth.is_alive(session.session_id)
        auth.keepalive(session.session_id)

        # When - Disconnect
        auth.disconnect(session.session_id)

        # Then
        assert not auth.is_alive(session.session_id)
