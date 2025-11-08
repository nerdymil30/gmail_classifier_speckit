"""Protocol definitions for IMAP authentication and client operations.

This module defines Protocol-based interfaces for dependency injection,
enabling testable code without concrete dependencies on imapclient and keyring.

Protocols use structural subtyping (PEP 544), meaning any class implementing
the required methods satisfies the protocol without explicit inheritance.

Benefits:
- Easy mocking in tests
- Testable without network/OS keyring
- Swappable implementations
- Follows Dependency Inversion Principle
"""

import uuid
from typing import Protocol, runtime_checkable

from gmail_classifier.auth.imap import IMAPCredentials, IMAPSessionInfo

# ============================================================================
# IMAP Authentication Protocol
# ============================================================================


@runtime_checkable
class IMAPAuthProtocol(Protocol):
    """Protocol for IMAP authentication operations.

    This protocol defines the interface for authenticating with IMAP servers
    and managing session lifecycle. Any class implementing these methods can
    be used as an authenticator dependency.

    Methods:
        authenticate: Authenticate with IMAP credentials and create session
        disconnect: Close IMAP session and cleanup resources
        get_session: Retrieve session information by session ID
        is_alive: Check if session is active and responsive
        keepalive: Send keepalive command to prevent timeout

    Example:
        >>> # IMAPAuthenticator implicitly satisfies this protocol
        >>> auth: IMAPAuthProtocol = IMAPAuthenticator()
        >>> session = auth.authenticate(credentials)
        >>> assert auth.is_alive(session.session_id)
        >>> auth.disconnect(session.session_id)

        >>> # Mock for testing
        >>> class MockAuth:
        ...     def authenticate(self, creds): ...
        ...     def disconnect(self, session_id): ...
        ...     def get_session(self, session_id): ...
        ...     def is_alive(self, session_id): ...
        ...     def keepalive(self, session_id): ...
        >>> mock_auth: IMAPAuthProtocol = MockAuth()
    """

    def authenticate(self, credentials: IMAPCredentials) -> IMAPSessionInfo:
        """Authenticate with IMAP server and create session.

        Args:
            credentials: IMAP credentials containing email and password

        Returns:
            IMAPSessionInfo with active connection and session details

        Raises:
            IMAPAuthenticationError: Authentication failed
            IMAPConnectionError: Connection failed
        """
        ...

    def disconnect(self, session_id: uuid.UUID) -> None:
        """Disconnect IMAP session and cleanup resources.

        Args:
            session_id: UUID of session to disconnect

        Raises:
            ValueError: Session not found
        """
        ...

    def get_session(self, session_id: uuid.UUID) -> IMAPSessionInfo | None:
        """Retrieve session information by session ID.

        Args:
            session_id: UUID of session to retrieve

        Returns:
            IMAPSessionInfo if session exists, None otherwise
        """
        ...

    def is_alive(self, session_id: uuid.UUID) -> bool:
        """Check if session is alive and responsive.

        Args:
            session_id: UUID of session to check

        Returns:
            True if session is alive, False otherwise
        """
        ...

    def keepalive(self, session_id: uuid.UUID) -> None:
        """Send keepalive command to prevent session timeout.

        Args:
            session_id: UUID of session to keep alive

        Raises:
            ValueError: Session not found
            IMAPSessionError: Keepalive failed
        """
        ...


# ============================================================================
# IMAP Client Adapter Protocol
# ============================================================================


@runtime_checkable
class IMAPClientProtocol(Protocol):
    """Protocol for IMAP client connection operations.

    This protocol defines the low-level IMAP client interface for connecting
    to IMAP servers. It abstracts the underlying imapclient library, allowing
    for mock implementations in tests.

    Methods:
        login: Authenticate with username and password
        logout: Close IMAP connection
        noop: Send NOOP keepalive command
        list_folders: List available IMAP folders
        select_folder: Select a folder for operations
        folder_status: Get folder status without selecting
        search: Search for messages matching criteria
        fetch: Fetch message data
        close_folder: Close currently selected folder

    Example:
        >>> # IMAPClient from imapclient library satisfies this protocol
        >>> from imapclient import IMAPClient
        >>> client: IMAPClientProtocol = IMAPClient("imap.gmail.com")

        >>> # Mock for testing
        >>> class MockIMAPClient:
        ...     def login(self, username, password): ...
        ...     def logout(self): ...
        ...     def noop(self): ...
        >>> mock_client: IMAPClientProtocol = MockIMAPClient()
    """

    def login(self, username: str, password: str) -> bytes:
        """Authenticate with IMAP server.

        Args:
            username: Email address
            password: IMAP password or app-specific password

        Returns:
            Login response from server

        Raises:
            IMAPClientError: Authentication failed
        """
        ...

    def logout(self) -> bytes:
        """Logout from IMAP server.

        Returns:
            Logout response from server
        """
        ...

    def noop(self) -> tuple[bytes, list[bytes]]:
        """Send NOOP command for keepalive.

        Returns:
            NOOP response from server
        """
        ...

    def list_folders(
        self, directory: str = "", pattern: str = "*"
    ) -> list[tuple[tuple[bytes, ...], bytes, str]]:
        """List available IMAP folders.

        Args:
            directory: Directory to list (default: root)
            pattern: Pattern to match (default: all folders)

        Returns:
            List of (flags, delimiter, folder_name) tuples
        """
        ...

    def select_folder(
        self, folder: str, readonly: bool = False
    ) -> dict[bytes, int]:
        """Select an IMAP folder for operations.

        Args:
            folder: Folder name to select
            readonly: Open in read-only mode

        Returns:
            Folder metadata (EXISTS, RECENT, UNSEEN counts)
        """
        ...

    def folder_status(
        self, folder: str, what: list[str]
    ) -> dict[bytes, int]:
        """Get folder status without selecting.

        Args:
            folder: Folder name
            what: Status items to retrieve (e.g., ["MESSAGES", "UNSEEN"])

        Returns:
            Folder status dictionary
        """
        ...

    def search(self, criteria: str | list[str] = "ALL") -> list[int]:
        """Search for messages matching criteria.

        Args:
            criteria: IMAP search criteria

        Returns:
            List of message IDs
        """
        ...

    def fetch(
        self, messages: list[int] | int, data: list[str]
    ) -> dict[int, dict]:
        """Fetch message data.

        Args:
            messages: Message ID or list of message IDs
            data: Data items to fetch (e.g., ["BODY[]", "FLAGS"])

        Returns:
            Dictionary mapping message ID to fetched data
        """
        ...

    def close_folder(self) -> bytes:
        """Close currently selected folder.

        Returns:
            Close response from server
        """
        ...
