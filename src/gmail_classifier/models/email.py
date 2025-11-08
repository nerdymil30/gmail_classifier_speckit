"""Email entity model."""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from gmail_classifier.email.fetcher import IMAPFetchData


@dataclass
class Email:
    """
    Unified email representation for both Gmail API and IMAP sources.

    Core fields are required for both sources. Gmail API-specific and
    IMAP-specific fields are optional to support both authentication methods.

    Attributes:
        id: Message identifier (Gmail API: string, IMAP: integer)
        subject: Email subject line
        sender: From address
        recipients: To addresses
        body_plain: Plain text body content
        date: Email date/time
        labels: Gmail labels or IMAP folder names
        is_unread: Whether email is unread
        thread_id: Gmail thread ID (OAuth2 only)
        sender_name: Parsed sender name (OAuth2 only)
        snippet: Email preview text (OAuth2 only)
        body_html: HTML body content (OAuth2 only)
        has_attachments: Whether email has attachments
        flags: IMAP flags (IMAP only)
    """

    # Core fields (common to both sources)
    id: str | int
    subject: str | None
    sender: str
    recipients: list[str]
    body_plain: str | None
    date: datetime
    labels: list[str]
    is_unread: bool

    # Gmail API specific fields (optional)
    thread_id: str | None = None
    sender_name: str | None = None
    snippet: str | None = None
    body_html: str | None = None
    has_attachments: bool = False

    # IMAP specific fields (optional)
    flags: tuple | None = None

    def __post_init__(self) -> None:
        """Validate email data after initialization."""
        # Validate ID (handle both string and int)
        if self.id is None or (isinstance(self.id, str) and not self.id):
            raise ValueError("Email ID cannot be empty")
        if not self.sender:
            raise ValueError("Email sender cannot be empty")
        if not self.recipients:
            self.recipients = []
        if not self.labels:
            self.labels = []

    @property
    def is_unlabeled(self) -> bool:
        """Check if email has no user-created labels."""
        # System labels start with specific prefixes
        system_label_prefixes = ("INBOX", "SPAM", "TRASH", "UNREAD", "STARRED", "IMPORTANT",
                                   "SENT", "DRAFT", "CATEGORY_")
        return all(
            any(label.startswith(prefix) for prefix in system_label_prefixes)
            for label in self.labels
        ) if self.labels else True

    @property
    def content(self) -> str:
        """Get email content (prefer plain text, fallback to snippet)."""
        if self.body_plain:
            return self.body_plain
        elif self.snippet:
            return self.snippet
        return ""

    @property
    def display_subject(self) -> str:
        """Get display-safe subject line."""
        return self.subject or "(No Subject)"

    @property
    def display_sender(self) -> str:
        """Get display-safe sender (name or email)."""
        return self.sender_name or self.sender

    def to_dict(self) -> dict:
        """Convert email to dictionary (without body content for privacy)."""
        result = {
            "id": str(self.id),  # Convert to string for consistency
            "subject": self.subject,
            "sender": self.sender,
            "recipients": self.recipients,
            "date": self.date.isoformat(),
            "labels": self.labels,
            "is_unread": self.is_unread,
            "has_attachments": self.has_attachments,
        }

        # Add optional fields only if present
        if self.thread_id is not None:
            result["thread_id"] = self.thread_id
        if self.sender_name is not None:
            result["sender_name"] = self.sender_name
        if self.snippet is not None:
            result["snippet"] = self.snippet
        if self.flags is not None:
            result["flags"] = self.flags

        return result

    @classmethod
    def from_gmail_message(cls, message: dict) -> "Email":
        """
        Create Email instance from Gmail API message response.

        Args:
            message: Gmail API message resource

        Returns:
            Email instance
        """
        # Extract headers
        headers = {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}

        # Parse date
        date_str = headers.get("date", "")
        try:
            from email.utils import parsedate_to_datetime
            email_date = parsedate_to_datetime(date_str)
        except Exception:
            email_date = datetime.now()

        # Extract sender info
        sender_raw = headers.get("from", "")
        sender_name, sender_email = cls._parse_email_address(sender_raw)

        # Extract recipients
        to_header = headers.get("to", "")
        recipients = [addr[1] for addr in cls._parse_email_addresses(to_header)]

        # Extract body
        body_plain, body_html = cls._extract_body(message.get("payload", {}))

        return cls(
            id=message["id"],
            thread_id=message.get("threadId", message["id"]),
            subject=headers.get("subject"),
            sender=sender_email or sender_raw,
            sender_name=sender_name,
            recipients=recipients,
            date=email_date,
            snippet=message.get("snippet"),
            body_plain=body_plain,
            body_html=body_html,
            labels=message.get("labelIds", []),
            has_attachments=cls._has_attachments(message.get("payload", {})),
            is_unread="UNREAD" in message.get("labelIds", []),
        )

    @classmethod
    def from_imap_message(cls, msg_id: int, data: "IMAPFetchData") -> "Email":
        """
        Create Email instance from IMAP fetch response.

        Args:
            msg_id: IMAP message ID
            data: Raw email data from IMAP fetch (includes BODY[], FLAGS, INTERNALDATE)
                  Runtime keys are bytes (e.g., b"BODY[]")

        Returns:
            Email instance

        Note:
            - Uses email.parser to parse RFC 822 message format
            - Prefers plain text body over HTML
            - Extracts is_unread from IMAP \\Seen flag
            - IMAP-specific fields (flags) are preserved
        """
        from email.parser import BytesParser
        from email.policy import default

        # Note: Runtime uses bytes keys, but TypedDict requires string keys.
        # We use cast(Any, data) to access bytes keys while maintaining type hints.
        data_any = cast(Any, data)

        # Parse email message
        raw_email = data_any[b"BODY[]"]
        parser = BytesParser(policy=default)
        msg = parser.parsebytes(raw_email)

        # Extract headers
        subject = msg.get("Subject", "")
        sender = msg.get("From", "")
        to = msg.get("To", "")
        recipients = [addr.strip() for addr in to.split(",") if addr.strip()]

        # Extract sender name using existing parser
        sender_name, sender_email = cls._parse_email_address(sender)

        # Extract body (prefer plain text)
        body = ""
        body_html = None
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain" and not body:
                    try:
                        body = part.get_content()
                    except Exception:
                        pass
                elif content_type == "text/html" and not body_html:
                    try:
                        body_html = part.get_content()
                    except Exception:
                        pass
            # Fallback to HTML if no plain text
            if not body and body_html:
                body = body_html
        else:
            try:
                content = msg.get_content()
                if msg.get_content_type() == "text/html":
                    body_html = content
                body = content
            except Exception:
                body = ""

        # Parse date from INTERNALDATE or Date header
        try:
            from email.utils import parsedate_to_datetime
            date_str = msg.get("Date", "")
            if date_str:
                email_date = parsedate_to_datetime(date_str)
            else:
                email_date = datetime.now()
        except Exception:
            email_date = datetime.now()

        # Get flags and determine if unread
        flags = data_any.get(b"FLAGS", ())
        is_unread = b'\\Seen' not in flags

        # Check for attachments
        has_attachments = False
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_filename():
                    has_attachments = True
                    break

        return cls(
            id=msg_id,
            subject=subject,
            sender=sender_email or sender,
            sender_name=sender_name,
            recipients=recipients,
            body_plain=body,
            body_html=body_html,
            date=email_date,
            labels=[],  # IMAP labels can be added via X-GM-LABELS if needed
            is_unread=is_unread,
            thread_id=None,  # Not available in IMAP
            snippet=body[:100] if body else "",  # First 100 chars as snippet
            has_attachments=has_attachments,
            flags=flags,
        )

    @staticmethod
    def _parse_email_address(address_str: str) -> tuple[str | None, str | None]:
        """
        Parse email address from header format.

        Args:
            address_str: Email header (e.g., "John Doe <john@example.com>")

        Returns:
            Tuple of (name, email)
        """
        from email.utils import parseaddr
        name, email = parseaddr(address_str)
        return name or None, email or None

    @staticmethod
    def _parse_email_addresses(addresses_str: str) -> list[tuple[str | None, str | None]]:
        """
        Parse multiple email addresses from header.

        Args:
            addresses_str: Comma-separated email addresses

        Returns:
            List of (name, email) tuples
        """
        from email.utils import getaddresses
        return [(name or None, email or None) for name, email in getaddresses([addresses_str])]

    @staticmethod
    def _extract_body(payload: dict) -> tuple[str | None, str | None]:
        """
        Extract plain text and HTML body from message payload.

        Args:
            payload: Gmail API message payload

        Returns:
            Tuple of (plain_text, html)
        """
        import base64

        plain_text = None
        html = None

        def decode_data(data: str) -> str:
            """Decode base64url-encoded data."""
            try:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            except Exception:
                return ""

        def extract_from_parts(parts: list) -> None:
            """Recursively extract body from message parts."""
            nonlocal plain_text, html

            for part in parts:
                mime_type = part.get("mimeType", "")
                body_data = part.get("body", {}).get("data")

                if mime_type == "text/plain" and body_data and not plain_text:
                    plain_text = decode_data(body_data)
                elif mime_type == "text/html" and body_data and not html:
                    html = decode_data(body_data)
                elif "parts" in part:
                    extract_from_parts(part["parts"])

        # Check if single-part message
        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data")

        if mime_type == "text/plain" and body_data:
            plain_text = decode_data(body_data)
        elif mime_type == "text/html" and body_data:
            html = decode_data(body_data)
        elif "parts" in payload:
            extract_from_parts(payload["parts"])

        return plain_text, html

    @staticmethod
    def _has_attachments(payload: dict) -> bool:
        """
        Check if message has attachments.

        Args:
            payload: Gmail API message payload

        Returns:
            True if message has attachments
        """
        def check_parts(parts: list) -> bool:
            """Recursively check parts for attachments."""
            for part in parts:
                if part.get("filename"):
                    return True
                if "parts" in part:
                    if check_parts(part["parts"]):
                        return True
            return False

        if "parts" in payload:
            return check_parts(payload["parts"])

        return False
