"""Unit tests for ClassificationSuggestion model."""

import pytest
from datetime import datetime

from gmail_classifier.models.suggestion import ClassificationSuggestion, SuggestedLabel


class TestSuggestedLabel:
    """Test SuggestedLabel model."""

    def test_suggested_label_creation_valid(self):
        """Test creating a valid suggested label."""
        label = SuggestedLabel(
            label_id="Label_123",
            label_name="Finance",
            confidence_score=0.85,
            rank=1,
        )

        assert label.label_id == "Label_123"
        assert label.label_name == "Finance"
        assert label.confidence_score == 0.85
        assert label.rank == 1

    def test_suggested_label_empty_id_raises_error(self):
        """Test that empty label ID raises ValueError."""
        with pytest.raises(ValueError, match="Label ID cannot be empty"):
            SuggestedLabel(label_id="", label_name="Test", confidence_score=0.5, rank=1)

    def test_suggested_label_empty_name_raises_error(self):
        """Test that empty label name raises ValueError."""
        with pytest.raises(ValueError, match="Label name cannot be empty"):
            SuggestedLabel(label_id="Label_123", label_name="", confidence_score=0.5, rank=1)

    def test_suggested_label_invalid_confidence_raises_error(self):
        """Test that confidence score outside 0-1 range raises ValueError."""
        with pytest.raises(ValueError, match="Confidence score must be 0.0-1.0"):
            SuggestedLabel(
                label_id="Label_123", label_name="Test", confidence_score=1.5, rank=1
            )

        with pytest.raises(ValueError, match="Confidence score must be 0.0-1.0"):
            SuggestedLabel(
                label_id="Label_123", label_name="Test", confidence_score=-0.1, rank=1
            )

    def test_suggested_label_invalid_rank_raises_error(self):
        """Test that rank less than 1 raises ValueError."""
        with pytest.raises(ValueError, match="Rank must be >= 1"):
            SuggestedLabel(
                label_id="Label_123", label_name="Test", confidence_score=0.5, rank=0
            )

    def test_suggested_label_to_dict(self):
        """Test converting suggested label to dictionary."""
        label = SuggestedLabel(
            label_id="Label_123",
            label_name="Finance",
            confidence_score=0.85,
            rank=1,
        )

        label_dict = label.to_dict()

        assert label_dict == {
            "label_id": "Label_123",
            "label_name": "Finance",
            "confidence_score": 0.85,
            "rank": 1,
        }

    def test_suggested_label_from_dict(self):
        """Test creating suggested label from dictionary."""
        data = {
            "label_id": "Label_456",
            "label_name": "Work",
            "confidence_score": 0.72,
            "rank": 2,
        }

        label = SuggestedLabel.from_dict(data)

        assert label.label_id == "Label_456"
        assert label.label_name == "Work"
        assert label.confidence_score == 0.72
        assert label.rank == 2


class TestClassificationSuggestion:
    """Test ClassificationSuggestion model."""

    def test_classification_suggestion_creation_valid(self):
        """Test creating a valid classification suggestion."""
        labels = [
            SuggestedLabel("Label_1", "Finance", 0.85, 1),
            SuggestedLabel("Label_2", "Work", 0.72, 2),
        ]

        suggestion = ClassificationSuggestion(
            email_id="msg123",
            suggested_labels=labels,
            confidence_category="high",
            reasoning="Email about invoices",
            created_at=datetime.now(),
            status="pending",
        )

        assert suggestion.email_id == "msg123"
        assert len(suggestion.suggested_labels) == 2
        assert suggestion.confidence_category == "high"
        assert suggestion.status == "pending"

    def test_classification_suggestion_empty_email_id_raises_error(self):
        """Test that empty email ID raises ValueError."""
        with pytest.raises(ValueError, match="Email ID cannot be empty"):
            ClassificationSuggestion(
                email_id="",
                suggested_labels=[],
                confidence_category="no_match",
                reasoning=None,
                created_at=datetime.now(),
            )

    def test_classification_suggestion_invalid_confidence_category_raises_error(self):
        """Test that invalid confidence category raises ValueError."""
        with pytest.raises(ValueError, match="Invalid confidence category"):
            ClassificationSuggestion(
                email_id="msg123",
                suggested_labels=[],
                confidence_category="invalid",
                reasoning=None,
                created_at=datetime.now(),
            )

    def test_classification_suggestion_invalid_status_raises_error(self):
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            ClassificationSuggestion(
                email_id="msg123",
                suggested_labels=[],
                confidence_category="no_match",
                reasoning=None,
                created_at=datetime.now(),
                status="invalid",
            )

    def test_no_match_with_suggested_labels_raises_error(self):
        """Test that no_match category with labels raises ValueError."""
        labels = [SuggestedLabel("Label_1", "Test", 0.5, 1)]

        with pytest.raises(ValueError, match="No-match suggestions should have empty"):
            ClassificationSuggestion(
                email_id="msg123",
                suggested_labels=labels,
                confidence_category="no_match",
                reasoning=None,
                created_at=datetime.now(),
            )

    def test_high_confidence_without_labels_raises_error(self):
        """Test that high confidence without labels raises ValueError."""
        with pytest.raises(ValueError, match="requires suggested_labels"):
            ClassificationSuggestion(
                email_id="msg123",
                suggested_labels=[],
                confidence_category="high",
                reasoning=None,
                created_at=datetime.now(),
            )

    def test_duplicate_ranks_raises_error(self):
        """Test that duplicate ranks in suggested labels raises ValueError."""
        labels = [
            SuggestedLabel("Label_1", "Test1", 0.8, 1),
            SuggestedLabel("Label_2", "Test2", 0.7, 1),  # Duplicate rank
        ]

        with pytest.raises(ValueError, match="unique ranks"):
            ClassificationSuggestion(
                email_id="msg123",
                suggested_labels=labels,
                confidence_category="high",
                reasoning=None,
                created_at=datetime.now(),
            )

    def test_best_suggestion_property(self):
        """Test best_suggestion property returns top-ranked label."""
        labels = [
            SuggestedLabel("Label_1", "Finance", 0.85, 1),
            SuggestedLabel("Label_2", "Work", 0.72, 2),
        ]

        suggestion = ClassificationSuggestion(
            email_id="msg123",
            suggested_labels=labels,
            confidence_category="high",
            reasoning=None,
            created_at=datetime.now(),
        )

        assert suggestion.best_suggestion is not None
        assert suggestion.best_suggestion.label_name == "Finance"
        assert suggestion.best_suggestion.rank == 1

    def test_best_suggestion_property_with_no_labels(self):
        """Test best_suggestion property with no labels."""
        suggestion = ClassificationSuggestion(
            email_id="msg123",
            suggested_labels=[],
            confidence_category="no_match",
            reasoning=None,
            created_at=datetime.now(),
        )

        assert suggestion.best_suggestion is None

    def test_is_high_confidence(self):
        """Test is_high_confidence property."""
        suggestion = ClassificationSuggestion(
            email_id="msg123",
            suggested_labels=[SuggestedLabel("Label_1", "Test", 0.8, 1)],
            confidence_category="high",
            reasoning=None,
            created_at=datetime.now(),
        )

        assert suggestion.is_high_confidence is True

    def test_is_no_match(self):
        """Test is_no_match property."""
        suggestion = ClassificationSuggestion(
            email_id="msg123",
            suggested_labels=[],
            confidence_category="no_match",
            reasoning=None,
            created_at=datetime.now(),
        )

        assert suggestion.is_no_match is True

    def test_approve_method(self):
        """Test approve method changes status."""
        suggestion = ClassificationSuggestion(
            email_id="msg123",
            suggested_labels=[SuggestedLabel("Label_1", "Test", 0.8, 1)],
            confidence_category="high",
            reasoning=None,
            created_at=datetime.now(),
            status="pending",
        )

        suggestion.approve()

        assert suggestion.status == "approved"

    def test_approve_non_pending_raises_error(self):
        """Test that approving non-pending suggestion raises ValueError."""
        suggestion = ClassificationSuggestion(
            email_id="msg123",
            suggested_labels=[SuggestedLabel("Label_1", "Test", 0.8, 1)],
            confidence_category="high",
            reasoning=None,
            created_at=datetime.now(),
            status="approved",
        )

        with pytest.raises(ValueError, match="Can only approve pending suggestions"):
            suggestion.approve()

    def test_reject_method(self):
        """Test reject method changes status."""
        suggestion = ClassificationSuggestion(
            email_id="msg123",
            suggested_labels=[SuggestedLabel("Label_1", "Test", 0.8, 1)],
            confidence_category="high",
            reasoning=None,
            created_at=datetime.now(),
            status="pending",
        )

        suggestion.reject()

        assert suggestion.status == "rejected"

    def test_mark_applied_method(self):
        """Test mark_applied method changes status."""
        suggestion = ClassificationSuggestion(
            email_id="msg123",
            suggested_labels=[SuggestedLabel("Label_1", "Test", 0.8, 1)],
            confidence_category="high",
            reasoning=None,
            created_at=datetime.now(),
            status="pending",
        )

        suggestion.approve()
        suggestion.mark_applied()

        assert suggestion.status == "applied"

    def test_mark_applied_non_approved_raises_error(self):
        """Test that marking non-approved suggestion as applied raises ValueError."""
        suggestion = ClassificationSuggestion(
            email_id="msg123",
            suggested_labels=[SuggestedLabel("Label_1", "Test", 0.8, 1)],
            confidence_category="high",
            reasoning=None,
            created_at=datetime.now(),
            status="pending",
        )

        with pytest.raises(ValueError, match="Can only mark approved suggestions"):
            suggestion.mark_applied()

    def test_create_no_match_factory_method(self):
        """Test create_no_match factory method."""
        suggestion = ClassificationSuggestion.create_no_match(
            email_id="msg123",
            reasoning="No similar emails found",
        )

        assert suggestion.email_id == "msg123"
        assert suggestion.confidence_category == "no_match"
        assert suggestion.suggested_labels == []
        assert suggestion.reasoning == "No similar emails found"
        assert suggestion.status == "pending"

    def test_to_dict(self):
        """Test converting suggestion to dictionary."""
        labels = [SuggestedLabel("Label_1", "Finance", 0.85, 1)]
        created_at = datetime(2025, 1, 1, 12, 0, 0)

        suggestion = ClassificationSuggestion(
            email_id="msg123",
            suggested_labels=labels,
            confidence_category="high",
            reasoning="Test reasoning",
            created_at=created_at,
            status="pending",
        )

        suggestion_dict = suggestion.to_dict()

        assert suggestion_dict["email_id"] == "msg123"
        assert suggestion_dict["confidence_category"] == "high"
        assert suggestion_dict["reasoning"] == "Test reasoning"
        assert suggestion_dict["status"] == "pending"
        assert len(suggestion_dict["suggested_labels"]) == 1

    def test_from_dict(self):
        """Test creating suggestion from dictionary."""
        data = {
            "email_id": "msg456",
            "suggested_labels": [
                {"label_id": "Label_1", "label_name": "Work", "confidence_score": 0.75, "rank": 1}
            ],
            "confidence_category": "medium",
            "reasoning": "Similar emails found",
            "created_at": "2025-01-01T12:00:00",
            "status": "pending",
        }

        suggestion = ClassificationSuggestion.from_dict(data)

        assert suggestion.email_id == "msg456"
        assert suggestion.confidence_category == "medium"
        assert len(suggestion.suggested_labels) == 1
        assert suggestion.suggested_labels[0].label_name == "Work"
