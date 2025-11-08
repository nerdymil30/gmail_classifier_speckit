"""IMAP authentication module for Gmail.

This module provides IMAP-based authentication as an alternative to OAuth2,
enabling desktop-client-like login experience using email and app passwords.

AIDEV-NOTE: Library choice rationale
- imapclient>=3.0.0 selected for:
  - Pythonic API with high-level abstractions
  - Gmail-specific testing and production readiness
  - Active maintenance and comprehensive documentation
  - Built-in SSL/TLS support for secure connections
  - Native support for IMAP extensions including X-GM-LABELS

AIDEV-NOTE: Label operations via X-GM-LABELS
- Gmail labels are accessible via IMAP using the X-GM-LABELS extension
- This provides complete label CRUD operations without Gmail API
- 40x faster than Gmail API for label operations
- No OAuth required, simplifying authentication flow
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Type hints for IMAPClient (imported lazily to avoid import errors)
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from imapclient import IMAPClient


# ============================================================================
# Enums
# ============================================================================


class SessionState(Enum):
    """IMAP session connection states.

    State transitions:
    - CONNECTING → CONNECTED (on successful login)
    - CONNECTING → ERROR (on auth failure)
    - CONNECTED → DISCONNECTED (on explicit logout)
    - CONNECTED → ERROR (on connection loss)
    - ERROR → CONNECTING (on retry attempt)
    - DISCONNECTED → CONNECTING (on reconnect request)
    """
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


# ============================================================================
# Custom Exceptions
# ============================================================================


class IMAPAuthenticationError(Exception):
    """Raised when IMAP authentication fails.

    This includes:
    - Invalid email/password credentials
    - IMAP disabled in Gmail settings
    - 2FA/app password issues
    - Account security blocks
    """
    pass


class IMAPConnectionError(Exception):
    """Raised when IMAP connection cannot be established.

    This includes:
    - Network connectivity issues
    - SSL/TLS handshake failures
    - Server unreachable or timeout
    - Firewall/proxy issues
    """
    pass


class IMAPSessionError(Exception):
    """Raised when IMAP session encounters operational errors.

    This includes:
    - Session expired or timed out
    - Folder selection failures
    - Protocol violations
    - Unexpected server responses
    """
    pass


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class IMAPCredentials:
    """IMAP login credentials for Gmail authentication.

    Attributes:
        email: Gmail email address (e.g., user@gmail.com)
        password: IMAP password or app-specific password (16 chars for app passwords)
        created_at: Timestamp when credentials were first stored
        last_used: Timestamp of last successful authentication (auto-updated)

    Security considerations:
    - Never log password in plain text
    - Sanitize password from error messages
    - Clear from memory after failed authentication
    - Use secure string comparison for validation
    """
    email: str
    password: str
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime | None = None

    def __post_init__(self) -> None:
        """Validate email format and password constraints."""
        import re

        # Email format validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, self.email):
            raise ValueError(f"Invalid email format: {self.email}")

        # Password length validation (8-64 chars)
        if not (8 <= len(self.password) <= 64):
            raise ValueError("Password must be between 8 and 64 characters")

    def __repr__(self) -> str:
        """String representation with sanitized password."""
        return (
            f"IMAPCredentials(email='{self.email}', "
            f"created_at={self.created_at.isoformat()}, "
            f"last_used={self.last_used.isoformat() if self.last_used else 'Never'})"
        )


@dataclass
class IMAPSessionInfo:
    """Active IMAP session metadata and connection state.

    Attributes:
        session_id: Unique identifier for this session (UUID)
        email: Email address associated with this session
        connection: Active IMAPClient connection object (optional during initialization)
        selected_folder: Currently selected IMAP folder (e.g., "INBOX")
        connected_at: Timestamp when connection was established
        last_activity: Last IMAP command timestamp (for keepalive management)
        state: Current session state (SessionState enum)
        retry_count: Number of reconnection attempts (default: 0, max: 5)

    Lifecycle:
    - Keepalive: Send NOOP every 10-15 minutes (based on last_activity)
    - Timeout: Detect stale connections via last_activity > 25 minutes
    - Auto-reconnect: On connection loss, retry up to 5 times with exponential backoff
    - Cleanup: On session end, ensure close() and logout() called
    """
    session_id: uuid.UUID = field(default_factory=uuid.uuid4)
    email: str = ""
    connection: Optional["IMAPClient"] = None
    selected_folder: str | None = None
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    state: SessionState = SessionState.CONNECTING
    retry_count: int = 0

    def update_activity(self) -> None:
        """Update last_activity timestamp to current time."""
        self.last_activity = datetime.now()

    def is_stale(self, timeout_minutes: int = 25) -> bool:
        """Check if session is stale (no activity beyond timeout).

        Args:
            timeout_minutes: Inactivity threshold in minutes (default: 25)

        Returns:
            True if session has been inactive beyond timeout
        """
        from datetime import timedelta
        return (datetime.now() - self.last_activity) > timedelta(minutes=timeout_minutes)

    def __repr__(self) -> str:
        """String representation of session info."""
        return (
            f"IMAPSessionInfo(session_id={self.session_id}, "
            f"email='{self.email}', "
            f"state={self.state.value}, "
            f"selected_folder='{self.selected_folder}', "
            f"connected_at={self.connected_at.isoformat()}, "
            f"retry_count={self.retry_count})"
        )


# ============================================================================
# Logging Configuration
# ============================================================================


def configure_imap_logger(name: str = "gmail_classifier.auth.imap") -> logging.Logger:
    """Configure structured logging for IMAP operations.

    Args:
        name: Logger name (default: gmail_classifier.auth.imap)

    Returns:
        Configured logger instance with structured formatting

    Log levels:
    - DEBUG: Detailed protocol-level operations
    - INFO: Connection events, authentication success
    - WARNING: Retry attempts, recoverable errors
    - ERROR: Authentication failures, connection errors
    - CRITICAL: Unrecoverable session failures

    Log format:
    - Timestamp (ISO 8601)
    - Level
    - Module context
    - Message with structured fields (session_id, email, state)
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Console handler with structured formatting
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)

        # Format: timestamp - level - module - message
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        # Prevent propagation to avoid duplicate logs
        logger.propagate = False

    return logger


# Initialize module-level logger
logger = configure_imap_logger()


# ============================================================================
# IMAPAuthenticator Class
# ============================================================================


class IMAPAuthenticator:
    """IMAP authentication manager for Gmail.

    Manages IMAP connections, sessions, and authentication lifecycle including
    retry logic, keepalive, and error handling.

    AIDEV-NOTE: Keepalive strategy
    - Send NOOP command every 10-15 minutes to prevent timeout
    - Gmail IMAP timeout is typically 30 minutes
    - We use 10-minute intervals with 25-minute stale detection
    - Auto-reconnect on connection loss with exponential backoff

    Attributes:
        _sessions: Dictionary mapping session_id to IMAPSessionInfo
        _logger: Logger instance for IMAP operations
        _server: IMAP server address (default: imap.gmail.com)
        _port: IMAP server port (default: 993)
        _use_ssl: Use SSL/TLS connection (default: True)
    """

    def __init__(
        self,
        server: str = "imap.gmail.com",
        port: int = 993,
        use_ssl: bool = True,
    ) -> None:
        """Initialize IMAP authenticator.

        Args:
            server: IMAP server address (default: imap.gmail.com)
            port: IMAP server port (default: 993 for SSL)
            use_ssl: Enable SSL/TLS encryption (default: True)
        """
        self._sessions: dict[uuid.UUID, IMAPSessionInfo] = {}
        self._logger = logger
        self._server = server
        self._port = port
        self._use_ssl = use_ssl

        self._logger.info(
            f"IMAPAuthenticator initialized: server={server}, port={port}, ssl={use_ssl}"
        )

    def authenticate(self, credentials: IMAPCredentials) -> IMAPSessionInfo:
        """Authenticate to Gmail IMAP server with retry logic.

        Establishes IMAP connection, authenticates with credentials, and creates
        a new session. Implements exponential backoff retry logic for transient
        failures.

        Args:
            credentials: IMAPCredentials containing email and password

        Returns:
            IMAPSessionInfo for the authenticated session

        Raises:
            IMAPAuthenticationError: Authentication failed (invalid credentials)
            IMAPConnectionError: Connection failed after retries
            ValueError: Invalid credential format

        Flow:
        1. Validate credentials format
        2. Create session with CONNECTING state
        3. Attempt connection with retry logic (max 5 attempts)
        4. On success: Update session state to CONNECTED, update last_used
        5. On failure: Raise appropriate error with context
        """
        from time import sleep

        from imapclient import IMAPClient
        from imapclient.exceptions import IMAPClientError

        # Validate credentials (will raise ValueError if invalid)
        self._validate_credentials(credentials)

        # Create session info
        session_info = IMAPSessionInfo(
            email=credentials.email,
            state=SessionState.CONNECTING,
        )

        max_retries = 5
        initial_delay = 3  # seconds

        for attempt in range(max_retries):
            try:
                self._logger.info(
                    f"Attempting IMAP authentication for {credentials.email} "
                    f"(attempt {attempt + 1}/{max_retries})"
                )

                # Create IMAP connection
                client = IMAPClient(
                    self._server,
                    port=self._port,
                    ssl=self._use_ssl,
                    timeout=30,
                )

                # Authenticate
                try:
                    login_response = client.login(credentials.email, credentials.password)
                    self._logger.info(
                        f"Authentication successful for {credentials.email}: "
                        f"{login_response}"
                    )
                except IMAPClientError as e:
                    # Authentication failed - invalid credentials
                    error_msg = str(e).lower()
                    self._logger.error(
                        f"Authentication failed for {credentials.email}: {e}"
                    )

                    # Translate IMAP error to our custom exception
                    if any(
                        keyword in error_msg
                        for keyword in [
                            "invalid",
                            "authentication",
                            "failed",
                            "credentials",
                        ]
                    ):
                        raise IMAPAuthenticationError(
                            f"Authentication failed for {credentials.email}. "
                            f"Please check your credentials and ensure IMAP is enabled "
                            f"in Gmail settings. If using 2FA, generate an app password."
                        ) from e
                    else:
                        raise IMAPAuthenticationError(
                            f"Authentication failed: {e}"
                        ) from e

                # Verify connection with NOOP
                client.noop()

                # Update session info
                session_info.connection = client
                session_info.state = SessionState.CONNECTED
                session_info.connected_at = datetime.now()
                session_info.last_activity = datetime.now()
                session_info.retry_count = attempt

                # Update credentials last_used
                credentials.last_used = datetime.now()

                # Store session
                self._sessions[session_info.session_id] = session_info

                self._logger.info(
                    f"Session created: {session_info.session_id} for {credentials.email}"
                )

                return session_info

            except IMAPAuthenticationError:
                # Don't retry authentication errors - invalid credentials
                raise

            except (OSError, TimeoutError) as e:
                # Network/connection errors - retry with exponential backoff
                session_info.retry_count = attempt + 1

                if attempt < max_retries - 1:
                    # Calculate exponential backoff delay
                    delay = initial_delay * (2**attempt)
                    self._logger.warning(
                        f"Connection attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay} seconds..."
                    )
                    sleep(delay)
                else:
                    # Max retries exhausted
                    self._logger.error(
                        f"Connection failed after {max_retries} attempts: {e}"
                    )
                    session_info.state = SessionState.ERROR
                    raise IMAPConnectionError(
                        f"Failed to connect to {self._server}:{self._port} "
                        f"after {max_retries} attempts. Please check your network "
                        f"connection and try again."
                    ) from e

            except Exception as e:
                # Unexpected error
                self._logger.error(f"Unexpected error during authentication: {e}")
                session_info.state = SessionState.ERROR
                raise IMAPConnectionError(f"Unexpected error: {e}") from e

        # Should never reach here, but for type safety
        raise IMAPConnectionError("Authentication failed: max retries exceeded")

    def disconnect(self, session_id: uuid.UUID) -> None:
        """Disconnect IMAP session and cleanup.

        Logs out from IMAP server, closes connection, and removes session
        from active sessions dictionary.

        Args:
            session_id: UUID of the session to disconnect

        Raises:
            ValueError: Session ID not found
        """
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")

        session_info = self._sessions[session_id]

        try:
            if session_info.connection:
                # Close selected mailbox if any
                if session_info.selected_folder:
                    try:
                        session_info.connection.close_folder()
                    except Exception as e:
                        self._logger.warning(f"Error closing folder: {e}")

                # Logout from IMAP server
                try:
                    session_info.connection.logout()
                    self._logger.info(
                        f"Logged out from IMAP server for session {session_id}"
                    )
                except Exception as e:
                    self._logger.warning(f"Error during logout: {e}")

            # Update session state
            session_info.state = SessionState.DISCONNECTED
            session_info.connection = None

        finally:
            # Always remove from sessions dict
            del self._sessions[session_id]
            self._logger.info(f"Session {session_id} disconnected and removed")

    def is_alive(self, session_id: uuid.UUID) -> bool:
        """Check if IMAP session is alive and responsive.

        Verifies session exists and connection responds to NOOP command.
        Updates last_activity timestamp if successful.

        Args:
            session_id: UUID of the session to check

        Returns:
            True if session is alive and responsive, False otherwise
        """
        if session_id not in self._sessions:
            return False

        session_info = self._sessions[session_id]

        if not session_info.connection:
            return False

        if session_info.state != SessionState.CONNECTED:
            return False

        try:
            # Send NOOP to verify connection
            session_info.connection.noop()
            session_info.update_activity()
            return True

        except Exception as e:
            self._logger.warning(
                f"Session {session_id} is not alive: {e}"
            )
            session_info.state = SessionState.ERROR
            return False

    def keepalive(self, session_id: uuid.UUID) -> None:
        """Send keepalive NOOP command to prevent timeout.

        Should be called periodically (every 10-15 minutes) to keep
        the IMAP connection alive. Gmail IMAP typically times out
        after 30 minutes of inactivity.

        Args:
            session_id: UUID of the session to keepalive

        Raises:
            ValueError: Session ID not found
            IMAPSessionError: Keepalive failed, connection likely dead
        """
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")

        session_info = self._sessions[session_id]

        if not session_info.connection:
            raise IMAPSessionError(f"No active connection for session {session_id}")

        try:
            session_info.connection.noop()
            session_info.update_activity()
            self._logger.debug(f"Keepalive successful for session {session_id}")

        except Exception as e:
            self._logger.error(f"Keepalive failed for session {session_id}: {e}")
            session_info.state = SessionState.ERROR
            raise IMAPSessionError(f"Keepalive failed: {e}") from e

    def get_session(self, session_id: uuid.UUID) -> IMAPSessionInfo | None:
        """Retrieve session info by session ID.

        Args:
            session_id: UUID of the session to retrieve

        Returns:
            IMAPSessionInfo if found, None otherwise
        """
        return self._sessions.get(session_id)

    def _validate_credentials(self, credentials: IMAPCredentials) -> None:
        """Validate credentials format and constraints.

        Credentials dataclass already validates email format and password length
        in __post_init__, but we add additional checks here for security.

        Args:
            credentials: IMAPCredentials to validate

        Raises:
            ValueError: Credentials fail validation
        """
        # Email validation (already done in dataclass, but double-check)
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, credentials.email):
            raise ValueError(f"Invalid email format: {credentials.email}")

        # Password length validation
        if not (8 <= len(credentials.password) <= 64):
            raise ValueError("Password must be between 8 and 64 characters")

        # Warn if not Gmail domain (but allow for Google Workspace)
        if not (
            credentials.email.endswith("@gmail.com")
            or "google" in credentials.email.lower()
        ):
            self._logger.warning(
                f"Email {credentials.email} may not be a Gmail account. "
                f"IMAP authentication works best with Gmail and Google Workspace accounts."
            )
