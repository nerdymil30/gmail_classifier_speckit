"""Processing session entity model."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ProcessingSession:
    """
    Represents a single classification run with resume capability.

    Attributes:
        id: Unique session ID (UUID)
        user_email: Gmail account being processed
        start_time: Session start timestamp
        end_time: Session completion timestamp (None if in progress)
        status: Current session status
        total_emails_to_process: Total unlabeled emails found
        emails_processed: Number of emails classified so far
        suggestions_generated: Number of suggestions created
        suggestions_applied: Number of labels successfully applied
        last_processed_email_id: Last email ID processed (for resume)
        error_log: List of error messages encountered
        config: Session configuration (batch size, dry-run mode, etc.)
    """

    id: str
    user_email: str
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    total_emails_to_process: int
    emails_processed: int = 0
    suggestions_generated: int = 0
    suggestions_applied: int = 0
    last_processed_email_id: Optional[str] = None
    error_log: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate session data."""
        valid_statuses = ("in_progress", "paused", "completed", "failed")
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid status: {self.status}. Must be one of {valid_statuses}")

        if self.emails_processed < 0:
            raise ValueError("Emails processed cannot be negative")

        if self.emails_processed > self.total_emails_to_process:
            raise ValueError("Emails processed cannot exceed total emails to process")

        if self.suggestions_applied > self.suggestions_generated:
            raise ValueError("Suggestions applied cannot exceed suggestions generated")

        if self.end_time and self.end_time < self.start_time:
            raise ValueError("End time cannot be before start time")

    @property
    def is_in_progress(self) -> bool:
        """Check if session is currently in progress."""
        return self.status == "in_progress"

    @property
    def is_paused(self) -> bool:
        """Check if session is paused."""
        return self.status == "paused"

    @property
    def is_completed(self) -> bool:
        """Check if session is completed."""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if session has failed."""
        return self.status == "failed"

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage (0.0-100.0)."""
        if self.total_emails_to_process == 0:
            return 100.0
        return (self.emails_processed / self.total_emails_to_process) * 100.0

    @property
    def success_rate(self) -> float:
        """Calculate suggestion application success rate (0.0-1.0)."""
        if self.suggestions_generated == 0:
            return 0.0
        return self.suggestions_applied / self.suggestions_generated

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate session duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def is_dry_run(self) -> bool:
        """Check if session is running in dry-run mode."""
        return self.config.get("dry_run", False)

    def increment_processed(self) -> None:
        """Increment emails processed counter."""
        self.emails_processed += 1

    def increment_generated(self) -> None:
        """Increment suggestions generated counter."""
        self.suggestions_generated += 1

    def increment_applied(self) -> None:
        """Increment suggestions applied counter."""
        self.suggestions_applied += 1

    def add_error(self, error_message: str) -> None:
        """Add error message to error log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.error_log.append(f"[{timestamp}] {error_message}")

    def update_last_processed(self, email_id: str) -> None:
        """Update last processed email ID for resume capability."""
        self.last_processed_email_id = email_id

    def pause(self) -> None:
        """Mark session as paused."""
        if not self.is_in_progress:
            raise ValueError(f"Can only pause in-progress sessions, current status: {self.status}")
        self.status = "paused"

    def resume(self) -> None:
        """Resume paused session."""
        if not self.is_paused:
            raise ValueError(f"Can only resume paused sessions, current status: {self.status}")
        self.status = "in_progress"

    def complete(self) -> None:
        """Mark session as completed."""
        if not self.is_in_progress:
            raise ValueError(
                f"Can only complete in-progress sessions, current status: {self.status}"
            )
        self.status = "completed"
        self.end_time = datetime.now()

    def fail(self, error_message: Optional[str] = None) -> None:
        """Mark session as failed."""
        if error_message:
            self.add_error(error_message)
        self.status = "failed"
        self.end_time = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_email": self.user_email,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "total_emails_to_process": self.total_emails_to_process,
            "emails_processed": self.emails_processed,
            "suggestions_generated": self.suggestions_generated,
            "suggestions_applied": self.suggestions_applied,
            "last_processed_email_id": self.last_processed_email_id,
            "error_log": self.error_log,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProcessingSession":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            user_email=data["user_email"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            status=data["status"],
            total_emails_to_process=data["total_emails_to_process"],
            emails_processed=data.get("emails_processed", 0),
            suggestions_generated=data.get("suggestions_generated", 0),
            suggestions_applied=data.get("suggestions_applied", 0),
            last_processed_email_id=data.get("last_processed_email_id"),
            error_log=data.get("error_log", []),
            config=data.get("config", {}),
        )

    @classmethod
    def create_new(
        cls,
        user_email: str,
        total_emails: int,
        config: Optional[dict] = None,
    ) -> "ProcessingSession":
        """
        Create a new processing session.

        Args:
            user_email: Gmail account email
            total_emails: Total number of emails to process
            config: Optional session configuration

        Returns:
            New ProcessingSession instance
        """
        return cls(
            id=str(uuid.uuid4()),
            user_email=user_email,
            start_time=datetime.now(),
            end_time=None,
            status="in_progress",
            total_emails_to_process=total_emails,
            emails_processed=0,
            suggestions_generated=0,
            suggestions_applied=0,
            last_processed_email_id=None,
            error_log=[],
            config=config or {},
        )

    def __str__(self) -> str:
        """String representation."""
        return (
            f"Session {self.id[:8]}: "
            f"{self.emails_processed}/{self.total_emails_to_process} processed "
            f"({self.progress_percentage:.1f}%) - {self.status}"
        )

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"ProcessingSession("
            f"id={self.id!r}, "
            f"user_email={self.user_email!r}, "
            f"status={self.status!r}, "
            f"progress={self.progress_percentage:.1f}%)"
        )
