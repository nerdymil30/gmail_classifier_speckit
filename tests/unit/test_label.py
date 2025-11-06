"""Unit tests for Label model."""

import pytest

from gmail_classifier.models.label import Label


class TestLabelModel:
    """Test Label model validation and methods."""

    def test_label_creation_valid(self):
        """Test creating a valid label."""
        label = Label(
            id="Label_123",
            name="Work",
            email_count=42,
            type="user",
        )

        assert label.id == "Label_123"
        assert label.name == "Work"
        assert label.email_count == 42
        assert label.type == "user"

    def test_label_missing_id_raises_error(self):
        """Test that empty ID raises ValueError."""
        with pytest.raises(ValueError, match="Label ID cannot be empty"):
            Label(id="", name="Test", email_count=0, type="user")

    def test_label_missing_name_raises_error(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Label name cannot be empty"):
            Label(id="Label_123", name="", email_count=0, type="user")

    def test_label_negative_email_count_raises_error(self):
        """Test that negative email count raises ValueError."""
        with pytest.raises(ValueError, match="Email count cannot be negative"):
            Label(id="Label_123", name="Test", email_count=-1, type="user")

    def test_label_invalid_type_raises_error(self):
        """Test that invalid type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid label type"):
            Label(id="Label_123", name="Test", email_count=0, type="invalid")

    def test_is_user_label(self):
        """Test is_user_label property."""
        user_label = Label(id="Label_123", name="Work", email_count=5, type="user")
        system_label = Label(id="INBOX", name="Inbox", email_count=100, type="system")

        assert user_label.is_user_label is True
        assert system_label.is_user_label is False

    def test_is_system_label(self):
        """Test is_system_label property."""
        user_label = Label(id="Label_123", name="Work", email_count=5, type="user")
        system_label = Label(id="INBOX", name="Inbox", email_count=100, type="system")

        assert user_label.is_system_label is False
        assert system_label.is_system_label is True

    def test_to_dict(self):
        """Test label conversion to dictionary."""
        label = Label(id="Label_123", name="Finance", email_count=10, type="user")
        label_dict = label.to_dict()

        assert label_dict == {
            "id": "Label_123",
            "name": "Finance",
            "email_count": 10,
            "type": "user",
        }

    def test_from_gmail_label_user_label(self):
        """Test creating Label from Gmail API response for user label."""
        gmail_label = {
            "id": "Label_456",
            "name": "Personal",
            "messagesTotal": 25,
        }

        label = Label.from_gmail_label(gmail_label)

        assert label.id == "Label_456"
        assert label.name == "Personal"
        assert label.email_count == 25
        assert label.type == "user"
        assert label.is_user_label is True

    def test_from_gmail_label_system_label(self):
        """Test creating Label from Gmail API response for system label."""
        gmail_label = {
            "id": "INBOX",
            "name": "INBOX",
            "messagesTotal": 150,
        }

        label = Label.from_gmail_label(gmail_label)

        assert label.id == "INBOX"
        assert label.name == "INBOX"
        assert label.email_count == 150
        assert label.type == "system"
        assert label.is_system_label is True

    def test_from_gmail_label_category_label(self):
        """Test creating Label from Gmail API response for category label."""
        gmail_label = {
            "id": "CATEGORY_PERSONAL",
            "name": "Personal",
            "messagesTotal": 50,
        }

        label = Label.from_gmail_label(gmail_label)

        assert label.id == "CATEGORY_PERSONAL"
        assert label.type == "system"  # Categories are system labels

    def test_from_gmail_label_with_custom_email_count(self):
        """Test creating Label with custom email count override."""
        gmail_label = {
            "id": "Label_789",
            "name": "Custom",
            "messagesTotal": 10,
        }

        label = Label.from_gmail_label(gmail_label, email_count=99)

        assert label.email_count == 99  # Custom count overrides messagesTotal

    def test_str_representation(self):
        """Test string representation of label."""
        label = Label(id="Label_123", name="Work", email_count=42, type="user")
        assert str(label) == "Work (42 emails)"

    def test_repr_representation(self):
        """Test detailed representation of label."""
        label = Label(id="Label_123", name="Work", email_count=42, type="user")
        repr_str = repr(label)

        assert "Label(" in repr_str
        assert "id='Label_123'" in repr_str
        assert "name='Work'" in repr_str
        assert "email_count=42" in repr_str
        assert "type='user'" in repr_str
