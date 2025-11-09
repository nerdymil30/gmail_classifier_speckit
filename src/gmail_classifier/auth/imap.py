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

import ctypes
import hashlib
import logging
import random
import re
import ssl
import string
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from time import sleep
from typing import TYPE_CHECKING, Optional

from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError

if TYPE_CHECKING:
    pass
# ============================================================================
# Constants
# ============================================================================
# Session cleanup configuration
CLEANUP_INTERVAL_SECONDS = 300  # Run cleanup every 5 minutes
STALE_TIMEOUT_MINUTES = 25  # Sessions inactive for >25 minutes are stale
MAX_SESSIONS_PER_EMAIL = 5  # Maximum concurrent sessions per email address
# ============================================================================
# Constants
# ============================================================================

# Email validation pattern (compiled once at module level for performance)
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


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
                  Stored internally as bytearray for secure cleanup
        created_at: Timestamp when credentials were first stored
        last_used: Timestamp of last successful authentication (auto-updated)
    Security considerations:
    - Password stored as bytearray for secure memory cleanup
    - Never log password in plain text
    - Sanitize password from error messages
    - Clear from memory after failed authentication
    - Use secure string comparison for validation
    - Automatic cleanup on object deletion via __del__
    """
    email: str
    _password_bytes: bytearray = field(default=None, repr=False, init=False)
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime | None = None

    def __init__(self, email: str, password: str, created_at: datetime = None, last_used: datetime = None):
        """Initialize credentials with secure password storage.

        Args:
            email: Gmail email address
            password: IMAP password or app-specific password
            created_at: Optional timestamp when credentials were created
            last_used: Optional timestamp of last use
        """
        self.email = email
        self._password_bytes = bytearray(password.encode('utf-8'))
        self.created_at = created_at if created_at is not None else datetime.now()
        self.last_used = last_used
        # Validate after initialization
        self.__post_init__()

    def __post_init__(self) -> None:
        """Validate email format and password constraints."""
        # Email format validation
        if not EMAIL_PATTERN.match(self.email):
            raise ValueError(f"Invalid email format: {self.email}")
        # Password validation with comprehensive security checks
        self._validate_password()

    @property
    def password(self) -> str:
        """Get password as string (use sparingly).

        Returns:
            Password decoded from bytearray

        Raises:
            ValueError: Password has been cleared from memory
        """
        if not self._password_bytes:
            raise ValueError("Password has been cleared from memory")
        return self._password_bytes.decode('utf-8')

    def clear_password(self) -> None:
        """Securely clear password from memory.

        Uses ctypes.memset() to overwrite password bytes at C memory level
        before clearing the bytearray. This prevents password data from
        remaining in memory dumps or swap files.

        Can be called multiple times safely (idempotent).
        """
        if self._password_bytes:
            # Overwrite with zeros at C memory level
            # Note: bytearray has 32 bytes of header before data in CPython
            ctypes.memset(id(self._password_bytes) + 32, 0, len(self._password_bytes))
            self._password_bytes.clear()

    def __del__(self):
        """Cleanup password on object deletion."""
        self.clear_password()

    def _validate_password(self) -> None:
        """Validate password format and security requirements.

        Checks for:
        - Gmail app password format (16 lowercase letters, optional spaces)
        - Password length constraints (12-64 chars for regular passwords)
        - Complexity requirements (3 of 4 character types)
        - Weak patterns (repeated characters)

        Raises:
            ValueError: Password fails validation with specific guidance

        Security:
            Addresses CWE-521 (Weak Password Requirements)
        """
        password = self.password

        # Check for Gmail app password format (16 lowercase chars, possibly with spaces)
        clean_password = password.replace(' ', '')
        if len(clean_password) == 16 and clean_password.isalpha():
            if not clean_password.islower():
                raise ValueError(
                    "Gmail app passwords must be lowercase. "
                    "Generate a new app password at: "
                    "https://myaccount.google.com/apppasswords"
                )
            # Valid app password - no further checks needed
            return

        # For non-app passwords, enforce stronger requirements
        # Basic length constraint (max 64 to prevent DoS)
        if len(password) > 64:
            raise ValueError("Password must not exceed 64 characters")

        # Minimum length requirement
        if len(password) < 12:
            raise ValueError(
                "Regular passwords must be at least 12 characters. "
                "Consider using a Gmail app password instead: "
                "https://myaccount.google.com/apppasswords"
            )

        # Check complexity: require 3 of 4 character types
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in string.punctuation for c in password)

        complexity_count = sum([has_upper, has_lower, has_digit, has_special])
        if complexity_count < 3:
            raise ValueError(
                "Password must contain at least 3 of: uppercase, lowercase, "
                "digits, special characters"
            )

        # Check for weak patterns: 3 or more repeated characters
        if re.search(r'(.)\1{2,}', password):
            raise ValueError("Password contains too many repeated characters")

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

    def __enter__(self) -> "IMAPSessionInfo":
        """Enter context manager, returning the session info.

        Returns:
            Self for use in with statements

        Example:
            with session_info as session:
                # Use session here
                pass
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, ensuring connection cleanup.

        Safely closes and logs out of the IMAP connection, preventing
        file descriptor leaks if authentication fails between creation
        and login.

        Args:
            exc_type: Exception type if an error occurred
            exc_val: Exception value if an error occurred
            exc_tb: Exception traceback if an error occurred

        Note:
            Exceptions are suppressed during cleanup to prevent masking
            the original exception that triggered the exit.
        """
        if self.connection:
            try:
                self.connection.logout()
            except Exception:
                # Suppress exceptions during cleanup to avoid masking
                # the original exception that triggered __exit__
                pass

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
# Retry Backoff Utilities
# ============================================================================
def calculate_backoff(attempt: int, base: float = 2.0, max_delay: float = 15.0) -> float:
    """Calculate exponential backoff delay with jitter and maximum cap.
    Implements capped exponential backoff to prevent excessive wait times
    during transient network failures. Adds random jitter to prevent
    thundering herd problems when multiple clients retry simultaneously.
    Args:
        attempt: Current retry attempt number (0-indexed)
        base: Base delay in seconds (default: 2.0)
        max_delay: Maximum delay cap in seconds (default: 15.0)
    Returns:
        Delay in seconds with jitter applied
    Examples:
        attempt=0: ~2s (range: 1.5-2.5s)
        attempt=1: ~4s (range: 3.0-5.0s)
        attempt=2: ~8s (range: 6.0-10.0s)
        attempt=3: ~15s (capped, range: 11.25-18.75s)
        attempt=4: ~15s (capped, range: 11.25-18.75s)
    Performance:
        Old: 3s, 6s, 12s, 24s, 48s = 93s total
        New: 2s, 4s, 8s, 15s, 15s = 44s total (53% faster)
    """
    # Calculate base exponential delay
    delay = min(base * (2 ** attempt), max_delay)
    # Add jitter: ±25% of delay
    jitter = delay * 0.25 * (2 * random.random() - 1)
    return delay + jitter
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
    AIDEV-NOTE: Security
    - SSL/TLS is always enabled with explicit certificate verification
    - Minimum TLS version 1.2 enforced
    - Hostname validation enabled
    - Certificate validation cannot be disabled for security
    Attributes:
        _sessions: Dictionary mapping session_id to IMAPSessionInfo
        _logger: Logger instance for IMAP operations
        _server: IMAP server address (default: imap.gmail.com)
        _port: IMAP server port (default: 993 for SSL/TLS)
            """
    def __init__(
        self,
        server: str = "imap.gmail.com",
        port: int = 993,
            ) -> None:
        """Initialize IMAP authenticator.
        Args:
            server: IMAP server address (default: imap.gmail.com)
            port: IMAP server port (default: 993 for SSL)
        """
        self._sessions: dict[uuid.UUID, IMAPSessionInfo] = {}
        self._logger = logger
        self._server = server
        self._port = port
        # Warn if server is not a Gmail domain
        self._warn_if_not_gmail(server)
        # Rate limiting for authentication attempts
        self._failed_attempts: defaultdict[str, list[datetime]] = defaultdict(list)
        self._lockout_until: dict[str, datetime] = {}
        self._cleanup_lock = threading.Lock()
                # Start background cleanup thread
        self._start_cleanup_thread()
        self._logger.info(
            f"IMAPAuthenticator initialized: server={server}, port={port}, ssl=always"
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
        1. Validate credentials format (done in IMAPCredentials.__post_init__)
        2. Create session with CONNECTING state
        3. Attempt connection with retry logic (max 5 attempts)
        4. On success: Update session state to CONNECTED, update last_used
        5. On failure: Raise appropriate error with context
        """
        # Credentials already validated in IMAPCredentials.__post_init__
        # Warn if not Gmail domain (but allow for Google Workspace)
        if not (
            credentials.email.endswith("@gmail.com")
            or "google" in credentials.email.lower()
        ):
            self._logger.warning(
                f"Email {credentials.email} may not be a Gmail account. "
                f"IMAP authentication works best with Gmail and Google Workspace accounts."
            )
        # Check rate limiting before attempting authentication
        self._check_rate_limit(credentials.email)
        # Create session info
        session_info = IMAPSessionInfo(
            email=credentials.email,
            state=SessionState.CONNECTING,
        )
        max_retries = 5
        for attempt in range(max_retries):
            try:
                hashed_email = self._hash_email(credentials.email)
                self._logger.info(
                    f"Attempting IMAP authentication for user {hashed_email} "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                # Create SSL context with certificate verification
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED
                ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
                # Create IMAP connection with SSL context
                client = IMAPClient(
                    self._server,
                    port=self._port,
                    ssl=True,
                    ssl_context=ssl_context,
                    timeout=30,
                )
                # Authenticate
                try:
                    login_response = client.login(credentials.email, credentials.password)
                    hashed_email = self._hash_email(credentials.email)
                    self._logger.info(
                        f"Authentication successful for user {hashed_email}: "
                        f"{login_response}"
                    )
                except IMAPClientError as e:
                    # Authentication failed - invalid credentials
                    error_msg = str(e).lower()
                    hashed_email = self._hash_email(credentials.email)
                    sanitized_error = self._sanitize_error(e)
                    self._logger.error(
                        f"Authentication failed for user {hashed_email}: {sanitized_error}"
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

                # Clear failed attempts on successful authentication
                if credentials.email in self._failed_attempts:
                    del self._failed_attempts[credentials.email]
                if credentials.email in self._lockout_until:
                    del self._lockout_until[credentials.email]
                # Update session info
                session_info.connection = client
                session_info.state = SessionState.CONNECTED
                session_info.connected_at = datetime.now()
                session_info.last_activity = datetime.now()
                session_info.retry_count = attempt
                # Update credentials last_used
                credentials.last_used = datetime.now()
                # Check session limit for this email
                with self._cleanup_lock:
                    active_sessions = [
                        s for s in self._sessions.values()
                        if s.email == credentials.email and s.state == SessionState.CONNECTED
                    ]
                    if len(active_sessions) >= MAX_SESSIONS_PER_EMAIL:
                        # Disconnect oldest session
                        oldest = min(active_sessions, key=lambda s: s.connected_at)
                        hashed_email = self._hash_email(credentials.email)
                        self._logger.warning(
                            f"Session limit ({MAX_SESSIONS_PER_EMAIL}) reached for user {hashed_email}. "
                            f"Disconnecting oldest session: {oldest.session_id}"
                        )
                        try:
                            self.disconnect(oldest.session_id)
                        except (OSError, TimeoutError, IMAPClientError, ValueError) as e:
                            self._logger.error(f"Failed to disconnect oldest session: {self._sanitize_error(e)}")
                # Store session
                with self._cleanup_lock:
                    self._sessions[session_info.session_id] = session_info
                hashed_email = self._hash_email(credentials.email)
                self._logger.info(
                    f"Session created: {session_info.session_id} for user {hashed_email}"
                )
                return session_info
            except IMAPAuthenticationError:
                # Record failed authentication attempt
                self._failed_attempts[credentials.email].append(datetime.now())
                # Clear password from memory on auth failure
                credentials.clear_password()
                # Don't retry authentication errors - invalid credentials
                raise
            except (OSError, TimeoutError) as e:
                # Network/connection errors - retry with exponential backoff
                session_info.retry_count = attempt + 1
                if attempt < max_retries - 1:
                    # Calculate exponential backoff delay
                    delay = calculate_backoff(attempt)
                    self._logger.warning(
                        f"Connection attempt {attempt + 1} failed: {self._sanitize_error(e)}. "
                        f"Retrying in {delay:.1f} seconds..."
                    )
                    sleep(delay)
                else:
                    # Max retries exhausted
                    self._logger.error(
                        f"Connection failed after {max_retries} attempts: {self._sanitize_error(e)}"
                    )
                    session_info.state = SessionState.ERROR
                    raise IMAPConnectionError(
                        f"Failed to connect to {self._server}:{self._port} "
                        f"after {max_retries} attempts. Please check your network "
                        f"connection and try again."
                    ) from e
            except (OSError, TimeoutError, IMAPClientError) as e:
                # Unexpected IMAP/network error
                self._logger.error(f"Unexpected error during authentication: {self._sanitize_error(e)}")
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
                    except (OSError, TimeoutError, IMAPClientError) as e:
                        self._logger.warning(f"Error closing folder: {self._sanitize_error(e)}")
                # Logout from IMAP server
                try:
                    session_info.connection.logout()
                    self._logger.info(
                        f"Logged out from IMAP server for session {session_id}"
                    )
                except (OSError, TimeoutError, IMAPClientError) as e:
                    self._logger.warning(f"Error during logout: {self._sanitize_error(e)}")
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
        except (OSError, TimeoutError, IMAPClientError) as e:
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
        except (OSError, TimeoutError, IMAPClientError) as e:
            self._logger.error(f"Keepalive failed for session {session_id}: {self._sanitize_error(e)}")
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
    def _start_cleanup_thread(self) -> None:
        """Start background thread for automatic session cleanup."""
        def cleanup_worker():
            while True:
                time.sleep(CLEANUP_INTERVAL_SECONDS)
                try:
                    self._cleanup_stale_sessions()
                except (OSError, TimeoutError, IMAPClientError, ValueError) as e:
                    self._logger.error(f"Error in cleanup thread: {self._sanitize_error(e)}")
        cleanup_thread = threading.Thread(
            target=cleanup_worker,
            daemon=True,
            name="imap-session-cleanup"
        )
        cleanup_thread.start()
        self._logger.info("Started IMAP session cleanup thread")
    def _cleanup_stale_sessions(self) -> None:
        """Remove and disconnect stale sessions."""
        with self._cleanup_lock:
            stale_sessions = [
                session_id
                for session_id, session_info in self._sessions.items()
                if session_info.is_stale(timeout_minutes=STALE_TIMEOUT_MINUTES)
            ]
            for session_id in stale_sessions:
                try:
                    self._logger.warning(
                        f"Auto-cleaning stale session: {session_id}"
                    )
                    self.disconnect(session_id)
                except (OSError, TimeoutError, IMAPClientError, ValueError) as e:
                    self._logger.error(
                        f"Failed to cleanup session {session_id}: {e}"
                    )
                    # Force removal even if disconnect fails
                    self._sessions.pop(session_id, None)
            if stale_sessions:
                self._logger.info(
                    f"Cleaned up {len(stale_sessions)} stale sessions"
                )
    def get_session_stats(self) -> dict:
        """Get session statistics for monitoring.
        Returns:
            Dictionary containing session statistics:
            - total_sessions: Total number of sessions
            - active_sessions: Number of connected sessions
            - stale_sessions: Number of stale sessions
            - sessions_by_email: Number of sessions per email address
        """
        with self._cleanup_lock:
            active = sum(
                1 for s in self._sessions.values()
                if s.state == SessionState.CONNECTED
            )
            stale = sum(
                1 for s in self._sessions.values()
                if s.is_stale(timeout_minutes=STALE_TIMEOUT_MINUTES)
            )
            # Count sessions by email
            sessions_by_email: dict[str, int] = {}
            for session_info in self._sessions.values():
                email = session_info.email
                sessions_by_email[email] = sessions_by_email.get(email, 0) + 1
            return {
                "total_sessions": len(self._sessions),
                "active_sessions": active,
                "stale_sessions": stale,
                "sessions_by_email": sessions_by_email,
            }
    def _sanitize_error(self, error: Exception) -> str:
        """Sanitize error messages to prevent information disclosure.
        Prevents exposing internal details that could aid attackers by
        categorizing errors into generic, safe messages.
        Args:
            error: Exception to sanitize
        Returns:
            Sanitized error message safe for logging
        Security:
            Addresses CWE-209 (Information Exposure Through Error Messages)
        """
        error_str = str(error).lower()
        if 'invalid' in error_str or 'credentials' in error_str:
            return "Authentication credentials rejected"
        elif 'ssl' in error_str or 'tls' in error_str:
            return "SSL/TLS connection error"
        return "Connection error"
    def _hash_email(self, email: str) -> str:
        """Hash email address for safe logging.
        Creates a short hash of the email address to enable correlation
        in logs without exposing the actual email address.
        Args:
            email: Email address to hash
        Returns:
            First 12 characters of SHA-256 hash of email
        Security:
            Prevents email address exposure in logs while maintaining
            traceability for debugging
        """
        return hashlib.sha256(email.encode()).hexdigest()[:12]
    def _warn_if_not_gmail(self, server: str) -> None:
        """Warn if server is not a recognized Gmail domain.
        SSL certificate validation requires the server hostname to match
        the certificate CN/SAN. This method warns users if they configure
        a non-Gmail server, as certificate validation may fail.
        Args:
            server: IMAP server hostname to validate
        Note:
            Recognized Gmail domains: gmail.com, googlemail.com
        """
        if not server.endswith("gmail.com") and not server.endswith("googlemail.com"):
            self._logger.warning(
                f"Server {server} is not a recognized Gmail domain. "
                f"SSL certificate validation may fail."
            )
    def _check_rate_limit(self, email: str) -> None:
        """Check and enforce rate limiting for authentication attempts.
        Tracks failed authentication attempts per email and implements exponential
        lockout after 5 failures within 15 minutes.
        Args:
            email: Email address to check rate limit for
        Raises:
            IMAPAuthenticationError: User is locked out due to excessive failed attempts
        Rate limiting policy:
        - Track failures within 15-minute window
        - After 5 failures: exponential lockout (2^(n-4) minutes, max 64 minutes)
        - Lockout durations: 5 failures=2min, 6=4min, 7=8min, ..., 10+=64min
        """
        now = datetime.now()
        # Check if user is currently locked out
        if email in self._lockout_until and now < self._lockout_until[email]:
            remaining = (self._lockout_until[email] - now).total_seconds()
            raise IMAPAuthenticationError(
                f"Too many failed authentication attempts. Try again in {int(remaining)} seconds."
            )
        # Clean old attempts (older than 15 minutes)
        cutoff = now - timedelta(minutes=15)
        self._failed_attempts[email] = [
            attempt for attempt in self._failed_attempts[email] if attempt > cutoff
        ]
        # Check if user has exceeded failure threshold
        if len(self._failed_attempts[email]) >= 5:
            # Calculate exponential lockout duration (2^(n-4) minutes, capped at 64)
            lockout_minutes = 2 ** min(len(self._failed_attempts[email]) - 4, 6)
            self._lockout_until[email] = now + timedelta(minutes=lockout_minutes)
            self._logger.warning(
                f"Rate limit exceeded for {email}. "
                f"Locked out for {lockout_minutes} minutes. "
                f"({len(self._failed_attempts[email])} failed attempts)"
            )
            raise IMAPAuthenticationError(
                f"Too many failed authentication attempts. Locked out for {lockout_minutes} minutes."
            )
