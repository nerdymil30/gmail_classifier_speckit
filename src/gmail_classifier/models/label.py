"""Label entity model."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Label:
    """
    Represents a Gmail label (user-created category).

    Attributes:
        id: Gmail label ID from API
        name: Label display name
        email_count: Number of emails with this label
        type: Label type ("user" or "system")
    """

    id: str
    name: str
    email_count: int
    type: str

    def __post_init__(self) -> None:
        """Validate label data after initialization."""
        if not self.id:
            raise ValueError("Label ID cannot be empty")
        if not self.name:
            raise ValueError("Label name cannot be empty")
        if self.email_count < 0:
            raise ValueError("Email count cannot be negative")
        if self.type not in ("user", "system"):
            raise ValueError(f"Invalid label type: {self.type}. Must be 'user' or 'system'")

    @property
    def is_user_label(self) -> bool:
        """Check if this is a user-created label."""
        return self.type == "user"

    @property
    def is_system_label(self) -> bool:
        """Check if this is a Gmail system label."""
        return self.type == "system"

    def to_dict(self) -> dict:
        """Convert label to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "email_count": self.email_count,
            "type": self.type,
        }

    @classmethod
    def from_gmail_label(cls, label: dict, email_count: Optional[int] = None) -> "Label":
        """
        Create Label instance from Gmail API label response.

        Args:
            label: Gmail API label resource
            email_count: Optional email count (defaults to messagesTotal if available)

        Returns:
            Label instance
        """
        label_id = label["id"]
        label_name = label["name"]

        # Determine label type based on ID
        # User labels have custom IDs, system labels have predefined IDs
        system_labels = {
            "INBOX",
            "SPAM",
            "TRASH",
            "UNREAD",
            "STARRED",
            "IMPORTANT",
            "SENT",
            "DRAFT",
            "CHAT",
            "CATEGORY_PERSONAL",
            "CATEGORY_SOCIAL",
            "CATEGORY_PROMOTIONS",
            "CATEGORY_UPDATES",
            "CATEGORY_FORUMS",
        }

        is_system = label_id in system_labels or label_id.startswith("CATEGORY_")
        label_type = "system" if is_system else "user"

        # Get email count from label resource or use provided value
        count = email_count if email_count is not None else label.get("messagesTotal", 0)

        return cls(
            id=label_id,
            name=label_name,
            email_count=count,
            type=label_type,
        )

    def __str__(self) -> str:
        """String representation of label."""
        return f"{self.name} ({self.email_count} emails)"

    def __repr__(self) -> str:
        """Detailed representation of label."""
        return f"Label(id={self.id!r}, name={self.name!r}, email_count={self.email_count}, type={self.type!r})"
