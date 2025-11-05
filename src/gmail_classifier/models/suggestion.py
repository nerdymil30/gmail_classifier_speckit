"""Classification suggestion entity model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SuggestedLabel:
    """
    Represents a single label suggestion with confidence.

    Attributes:
        label_id: Gmail label ID
        label_name: Label display name (denormalized for convenience)
        confidence_score: Similarity score 0.0-1.0
        rank: 1-based ranking (1 = best match)
    """

    label_id: str
    label_name: str
    confidence_score: float
    rank: int

    def __post_init__(self) -> None:
        """Validate suggested label data."""
        if not self.label_id:
            raise ValueError("Label ID cannot be empty")
        if not self.label_name:
            raise ValueError("Label name cannot be empty")
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(f"Confidence score must be 0.0-1.0, got {self.confidence_score}")
        if self.rank < 1:
            raise ValueError(f"Rank must be >= 1, got {self.rank}")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "label_id": self.label_id,
            "label_name": self.label_name,
            "confidence_score": self.confidence_score,
            "rank": self.rank,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SuggestedLabel":
        """Create from dictionary."""
        return cls(
            label_id=data["label_id"],
            label_name=data["label_name"],
            confidence_score=data["confidence_score"],
            rank=data["rank"],
        )


@dataclass
class ClassificationSuggestion:
    """
    Represents a proposed label assignment for an email.

    Attributes:
        email_id: Reference to Email.id
        suggested_labels: Ordered list of label suggestions with scores
        confidence_category: Overall confidence level
        reasoning: Human-readable explanation
        created_at: When suggestion was generated
        status: Current status of suggestion
    """

    email_id: str
    suggested_labels: list[SuggestedLabel]
    confidence_category: str
    reasoning: Optional[str]
    created_at: datetime
    status: str = "pending"

    def __post_init__(self) -> None:
        """Validate classification suggestion data."""
        if not self.email_id:
            raise ValueError("Email ID cannot be empty")

        valid_categories = ("high", "medium", "low", "no_match")
        if self.confidence_category not in valid_categories:
            raise ValueError(
                f"Invalid confidence category: {self.confidence_category}. "
                f"Must be one of {valid_categories}"
            )

        valid_statuses = ("pending", "approved", "rejected", "applied")
        if self.status not in valid_statuses:
            raise ValueError(
                f"Invalid status: {self.status}. Must be one of {valid_statuses}"
            )

        # Validate suggested_labels consistency
        if self.confidence_category == "no_match":
            if self.suggested_labels:
                raise ValueError("No-match suggestions should have empty suggested_labels list")
        else:
            if not self.suggested_labels:
                raise ValueError(
                    f"Confidence category {self.confidence_category} requires suggested_labels"
                )

        # Validate rank uniqueness
        if self.suggested_labels:
            ranks = [label.rank for label in self.suggested_labels]
            if len(ranks) != len(set(ranks)):
                raise ValueError("Suggested labels must have unique ranks")

    @property
    def best_suggestion(self) -> Optional[SuggestedLabel]:
        """Get the top-ranked label suggestion."""
        if not self.suggested_labels:
            return None
        return min(self.suggested_labels, key=lambda x: x.rank)

    @property
    def is_high_confidence(self) -> bool:
        """Check if suggestion is high confidence."""
        return self.confidence_category == "high"

    @property
    def is_no_match(self) -> bool:
        """Check if email has no matching labels."""
        return self.confidence_category == "no_match"

    @property
    def is_pending(self) -> bool:
        """Check if suggestion is pending review."""
        return self.status == "pending"

    @property
    def is_approved(self) -> bool:
        """Check if suggestion has been approved."""
        return self.status == "approved"

    @property
    def is_applied(self) -> bool:
        """Check if suggestion has been applied to Gmail."""
        return self.status == "applied"

    def approve(self) -> None:
        """Mark suggestion as approved."""
        if self.status != "pending":
            raise ValueError(f"Can only approve pending suggestions, current status: {self.status}")
        self.status = "approved"

    def reject(self) -> None:
        """Mark suggestion as rejected."""
        if self.status != "pending":
            raise ValueError(f"Can only reject pending suggestions, current status: {self.status}")
        self.status = "rejected"

    def mark_applied(self) -> None:
        """Mark suggestion as successfully applied."""
        if self.status != "approved":
            raise ValueError(
                f"Can only mark approved suggestions as applied, current status: {self.status}"
            )
        self.status = "applied"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "email_id": self.email_id,
            "suggested_labels": [label.to_dict() for label in self.suggested_labels],
            "confidence_category": self.confidence_category,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ClassificationSuggestion":
        """Create from dictionary."""
        return cls(
            email_id=data["email_id"],
            suggested_labels=[
                SuggestedLabel.from_dict(label) for label in data["suggested_labels"]
            ],
            confidence_category=data["confidence_category"],
            reasoning=data.get("reasoning"),
            created_at=datetime.fromisoformat(data["created_at"]),
            status=data.get("status", "pending"),
        )

    @classmethod
    def create_no_match(
        cls,
        email_id: str,
        reasoning: Optional[str] = None,
    ) -> "ClassificationSuggestion":
        """
        Create a no-match suggestion for an email.

        Args:
            email_id: Email ID
            reasoning: Optional explanation for no match

        Returns:
            ClassificationSuggestion with no_match category
        """
        return cls(
            email_id=email_id,
            suggested_labels=[],
            confidence_category="no_match",
            reasoning=reasoning or "No matching labels found",
            created_at=datetime.now(),
            status="pending",
        )

    def __str__(self) -> str:
        """String representation."""
        if self.best_suggestion:
            return (
                f"Suggestion for {self.email_id}: "
                f"{self.best_suggestion.label_name} "
                f"({self.best_suggestion.confidence_score:.2%})"
            )
        return f"Suggestion for {self.email_id}: No match"

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"ClassificationSuggestion("
            f"email_id={self.email_id!r}, "
            f"confidence_category={self.confidence_category!r}, "
            f"status={self.status!r}, "
            f"suggestions={len(self.suggested_labels)})"
        )
