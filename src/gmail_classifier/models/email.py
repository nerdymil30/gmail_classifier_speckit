"""Email entity model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Email:
    """
    Represents a Gmail message.

    Attributes correspond to Gmail API message resource fields.
    """

    id: str
    thread_id: str
    subject: Optional[str]
    sender: str
    sender_name: Optional[str]
    recipients: list[str]
    date: datetime
    snippet: Optional[str]
    body_plain: Optional[str]
    body_html: Optional[str]
    labels: list[str]
    has_attachments: bool
    is_unread: bool

    def __post_init__(self) -> None:
        """Validate email data after initialization."""
        if not self.id:
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
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "subject": self.subject,
            "sender": self.sender,
            "sender_name": self.sender_name,
            "recipients": self.recipients,
            "date": self.date.isoformat(),
            "snippet": self.snippet,
            "labels": self.labels,
            "has_attachments": self.has_attachments,
            "is_unread": self.is_unread,
        }

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

    @staticmethod
    def _parse_email_address(address_str: str) -> tuple[Optional[str], Optional[str]]:
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
    def _parse_email_addresses(addresses_str: str) -> list[tuple[Optional[str], Optional[str]]]:
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
    def _extract_body(payload: dict) -> tuple[Optional[str], Optional[str]]:
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
