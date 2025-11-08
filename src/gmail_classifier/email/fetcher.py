r"""Email fetching module for IMAP operations.

This module provides folder management and email retrieval functionality
for IMAP connections. It integrates with the IMAPAuthenticator to access
Gmail mailboxes and retrieve emails for classification.

AIDEV-NOTE: X-GM-LABELS extension
- Gmail labels are accessible via IMAP using the X-GM-LABELS extension
- X-GM-LABELS provides label names for messages
- Can be used to apply/remove labels without Gmail API
- Format: X-GM-LABELS (\Inbox \Sent "Custom Label")
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from email.parser import BytesParser
from email.policy import default
from typing import Any

from gmail_classifier.auth.imap import IMAPAuthenticator, IMAPSessionError

# ============================================================================
# Logging Configuration
# ============================================================================

logger = logging.getLogger("gmail_classifier.email.fetcher")


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class EmailFolder:
    """Represents an IMAP mailbox folder (Gmail label).

    Attributes:
        folder_name: IMAP folder name (e.g., "INBOX", "[Gmail]/Sent Mail")
        display_name: Human-readable folder name
        folder_type: Type classification (INBOX, SENT, DRAFTS, TRASH, LABEL, SYSTEM)
        message_count: Total messages in folder (optional)
        unread_count: Unread message count (optional)
        selectable: Whether folder can be selected (default: True)
        delimiter: IMAP hierarchy delimiter (usually "/")
    """

    folder_name: str
    display_name: str
    folder_type: str = "LABEL"
    message_count: int | None = None
    unread_count: int | None = None
    selectable: bool = True
    delimiter: str = "/"

    @staticmethod
    def from_imap_response(flags: tuple, delimiter: bytes, name: str) -> "EmailFolder":
        """Create EmailFolder from IMAP LIST response.

        Args:
            flags: IMAP flags tuple (e.g., (b'\\HasNoChildren', b'\\Sent'))
            delimiter: Hierarchy delimiter
            name: Folder name

        Returns:
            EmailFolder instance
        """
        # Determine folder type
        flags_bytes = b"".join(flags)
        if name == "INBOX":
            folder_type = "INBOX"
        elif b"\\Sent" in flags_bytes:
            folder_type = "SENT"
        elif b"\\Drafts" in flags_bytes:
            folder_type = "DRAFTS"
        elif b"\\Trash" in flags_bytes:
            folder_type = "TRASH"
        elif name.startswith("[Gmail]"):
            folder_type = "SYSTEM"
        else:
            folder_type = "LABEL"

        # Check if selectable
        selectable = b"\\Noselect" not in flags_bytes

        # Create display name (clean up Gmail system folders)
        display_name = name
        if name.startswith("[Gmail]/"):
            display_name = name.replace("[Gmail]/", "")

        return EmailFolder(
            folder_name=name,
            display_name=display_name,
            folder_type=folder_type,
            selectable=selectable,
            delimiter=delimiter.decode() if isinstance(delimiter, bytes) else delimiter,
        )


@dataclass
class Email:
    """Simplified email representation for classification.

    Compatible with existing classification logic.

    Attributes:
        message_id: Unique message identifier
        subject: Email subject line
        sender: From address
        recipients: To addresses
        body: Email body text
        content: Alias for body (for compatibility)
        received_date: When email was received
        labels: Gmail labels/IMAP folders
        flags: IMAP flags (\\Seen, \\Flagged, etc.)
    """

    message_id: int
    subject: str
    sender: str
    recipients: list[str] | None = None
    body: str = ""
    received_date: datetime | None = None
    labels: list[str] | None = None
    flags: tuple = ()

    def __post_init__(self) -> None:
        """Initialize optional fields."""
        if self.recipients is None:
            self.recipients = []
        if self.labels is None:
            self.labels = []

    @property
    def content(self) -> str:
        """Alias for body (for compatibility with classification logic)."""
        return self.body


# ============================================================================
# FolderManager Class
# ============================================================================


class FolderManager:
    """Manages IMAP folder operations and email retrieval.

    Provides high-level folder listing, selection, and email fetching
    operations on top of IMAPAuthenticator sessions.

    Attributes:
        _authenticator: IMAPAuthenticator instance
        _folder_cache: Cached folder listings by session_id
        _logger: Logger instance
    """

    def __init__(self, authenticator: IMAPAuthenticator) -> None:
        """Initialize FolderManager.

        Args:
            authenticator: IMAPAuthenticator instance with active sessions
        """
        self._authenticator = authenticator
        self._folder_cache: dict[uuid.UUID, list[EmailFolder]] = {}
        self._logger = logger

        self._logger.info("FolderManager initialized")

    def list_folders(self, session_id: uuid.UUID) -> list[EmailFolder]:
        """List all IMAP folders (Gmail labels) for the session.

        Retrieves and parses folder list from IMAP server. Results are cached
        for subsequent calls.

        Args:
            session_id: UUID of active IMAP session

        Returns:
            List of EmailFolder objects

        Raises:
            ValueError: Session not found
            IMAPSessionError: IMAP operation failed
        """
        # Check cache first
        if session_id in self._folder_cache:
            self._logger.debug(f"Returning cached folders for session {session_id}")
            return self._folder_cache[session_id]

        # Get session
        session_info = self._authenticator.get_session(session_id)
        if not session_info or not session_info.connection:
            raise ValueError(f"No active connection for session {session_id}")

        try:
            # List folders using IMAP
            raw_folders = session_info.connection.list_folders()

            # Parse into EmailFolder objects
            folders = []
            for flags, delimiter, name in raw_folders:
                folder = EmailFolder.from_imap_response(flags, delimiter, name)
                folders.append(folder)

            # Cache results
            self._folder_cache[session_id] = folders

            self._logger.info(
                f"Listed {len(folders)} folders for session {session_id}"
            )
            return folders

        except Exception as e:
            self._logger.error(f"Failed to list folders: {e}")
            raise IMAPSessionError(f"Failed to list folders: {e}") from e

    def select_folder(
        self, session_id: uuid.UUID, folder_name: str, readonly: bool = False
    ) -> dict[str, Any]:
        """Select an IMAP folder for operations.

        Args:
            session_id: UUID of active IMAP session
            folder_name: Folder name to select (e.g., "INBOX")
            readonly: Open folder in read-only mode (default: False)

        Returns:
            Dict with folder metadata:
                - message_count: Total messages in folder
                - recent_count: Recent messages
                - unread_count: Unseen messages

        Raises:
            ValueError: Session not found
            IMAPSessionError: Folder selection failed
        """
        # Get session
        session_info = self._authenticator.get_session(session_id)
        if not session_info or not session_info.connection:
            raise ValueError(f"No active connection for session {session_id}")

        try:
            # Select folder
            response = session_info.connection.select_folder(folder_name, readonly=readonly)

            # Update session state
            session_info.selected_folder = folder_name
            session_info.update_activity()

            # Parse response
            metadata = {
                "message_count": response.get(b"EXISTS", 0),
                "recent_count": response.get(b"RECENT", 0),
                "unread_count": response.get(b"UNSEEN", 0),
            }

            self._logger.info(
                f"Selected folder '{folder_name}' for session {session_id}: "
                f"{metadata['message_count']} messages"
            )
            return metadata

        except Exception as e:
            self._logger.error(f"Failed to select folder '{folder_name}': {e}")
            raise IMAPSessionError(f"Failed to select folder: {e}") from e

    def get_folder_status(
        self, session_id: uuid.UUID, folder_name: str
    ) -> dict[str, Any]:
        """Get folder status without selecting it.

        Uses IMAP STATUS command to get folder info without changing
        the currently selected folder.

        Args:
            session_id: UUID of active IMAP session
            folder_name: Folder name to query

        Returns:
            Dict with folder status:
                - message_count: Total messages
                - unread_count: Unseen messages

        Raises:
            ValueError: Session not found
            IMAPSessionError: STATUS command failed
        """
        # Get session
        session_info = self._authenticator.get_session(session_id)
        if not session_info or not session_info.connection:
            raise ValueError(f"No active connection for session {session_id}")

        try:
            # Get folder status (doesn't change selected folder)
            response = session_info.connection.folder_status(
                folder_name, ["MESSAGES", "UNSEEN"]
            )

            session_info.update_activity()

            metadata = {
                "message_count": response.get(b"MESSAGES", 0),
                "unread_count": response.get(b"UNSEEN", 0),
            }

            self._logger.debug(f"Folder status for '{folder_name}': {metadata}")
            return metadata

        except Exception as e:
            self._logger.error(f"Failed to get folder status for '{folder_name}': {e}")
            raise IMAPSessionError(f"Failed to get folder status: {e}") from e

    def fetch_emails(
        self,
        session_id: uuid.UUID,
        limit: int = 10,
        criteria: str = "ALL",
    ) -> list[Email]:
        """Fetch emails from currently selected folder.

        Retrieves emails in batches from the selected folder and parses
        them into Email objects compatible with classification logic.

        Args:
            session_id: UUID of active IMAP session
            limit: Maximum number of emails to fetch (default: 10)
            criteria: IMAP search criteria (default: "ALL")

        Returns:
            List of Email objects

        Raises:
            ValueError: Session not found or no folder selected
            IMAPSessionError: Email fetch failed

        Note:
        - Folder must be selected first using select_folder()
        - Emails are fetched in reverse order (newest first)
        - Batch size limited to prevent memory issues
        """
        # Get session
        session_info = self._authenticator.get_session(session_id)
        if not session_info or not session_info.connection:
            raise ValueError(f"No active connection for session {session_id}")

        if not session_info.selected_folder:
            raise ValueError("No folder selected. Call select_folder() first.")

        try:
            # Search for messages matching criteria
            message_ids = session_info.connection.search(criteria)

            # Limit results (take most recent)
            if len(message_ids) > limit:
                message_ids = message_ids[-limit:]

            # Fetch email data
            emails = []
            if message_ids:
                # Fetch in batches to avoid overwhelming the server
                fetch_data = session_info.connection.fetch(
                    message_ids, ["BODY[]", "FLAGS", "INTERNALDATE"]
                )

                # Parse each email
                for msg_id, data in fetch_data.items():
                    try:
                        email_obj = self._parse_email(msg_id, data)
                        emails.append(email_obj)
                    except Exception as e:
                        self._logger.warning(f"Failed to parse email {msg_id}: {e}")
                        continue

            session_info.update_activity()

            self._logger.info(
                f"Fetched {len(emails)} emails from '{session_info.selected_folder}'"
            )
            return emails

        except Exception as e:
            self._logger.error(f"Failed to fetch emails: {e}")
            raise IMAPSessionError(f"Failed to fetch emails: {e}") from e

    def _parse_email(self, msg_id: int, data: dict) -> Email:
        """Parse raw IMAP email data into Email object.

        Args:
            msg_id: IMAP message ID
            data: Raw email data from IMAP fetch

        Returns:
            Email object

        Raises:
            Exception: Email parsing failed
        """
        # Parse email message
        raw_email = data[b"BODY[]"]
        parser = BytesParser(policy=default)
        msg = parser.parsebytes(raw_email)

        # Extract fields
        subject = msg.get("Subject", "")
        sender = msg.get("From", "")
        to = msg.get("To", "")
        recipients = [addr.strip() for addr in to.split(",") if addr.strip()]

        # Extract body (prefer plain text)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    body = part.get_content()
                    break
            # Fallback to HTML if no plain text
            if not body:
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        body = part.get_content()
                        break
        else:
            body = msg.get_content()

        # Get flags
        flags = data.get(b"FLAGS", ())

        # Create Email object
        return Email(
            message_id=msg_id,
            subject=subject,
            sender=sender,
            recipients=recipients,
            body=body,
            flags=flags,
        )
