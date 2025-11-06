"""Unit tests for utility functions."""

import pytest
from gmail_classifier.lib.utils import (
    batch_items,
    format_confidence,
    get_confidence_category,
    sanitize_email_content,
    safe_int,
    safe_float,
    truncate_string,
    validate_email_address,
)


class TestBatchItems:
    """Test batch_items function."""

    def test_batch_items_evenly_divisible(self):
        """Test batching with evenly divisible items."""
        items = [1, 2, 3, 4, 5, 6]
        batches = batch_items(items, 2)

        assert batches == [[1, 2], [3, 4], [5, 6]]

    def test_batch_items_with_remainder(self):
        """Test batching with remainder items."""
        items = [1, 2, 3, 4, 5]
        batches = batch_items(items, 2)

        assert batches == [[1, 2], [3, 4], [5]]

    def test_batch_items_single_batch(self):
        """Test batching where batch size equals list size."""
        items = [1, 2, 3]
        batches = batch_items(items, 3)

        assert batches == [[1, 2, 3]]

    def test_batch_items_larger_batch_size(self):
        """Test batching with batch size larger than list."""
        items = [1, 2, 3]
        batches = batch_items(items, 10)

        assert batches == [[1, 2, 3]]

    def test_batch_items_empty_list(self):
        """Test batching empty list."""
        batches = batch_items([], 5)

        assert batches == []


class TestFormatConfidence:
    """Test format_confidence function."""

    def test_format_confidence_high(self):
        """Test formatting high confidence score."""
        assert format_confidence(0.875) == "87.5%"

    def test_format_confidence_low(self):
        """Test formatting low confidence score."""
        assert format_confidence(0.123) == "12.3%"

    def test_format_confidence_perfect(self):
        """Test formatting perfect confidence."""
        assert format_confidence(1.0) == "100.0%"

    def test_format_confidence_zero(self):
        """Test formatting zero confidence."""
        assert format_confidence(0.0) == "0.0%"


class TestGetConfidenceCategory:
    """Test get_confidence_category function."""

    def test_confidence_category_high(self):
        """Test high confidence categorization."""
        assert get_confidence_category(0.85) == "high"
        assert get_confidence_category(0.7) == "high"

    def test_confidence_category_medium(self):
        """Test medium confidence categorization."""
        assert get_confidence_category(0.65) == "medium"
        assert get_confidence_category(0.5) == "medium"

    def test_confidence_category_low(self):
        """Test low confidence categorization."""
        assert get_confidence_category(0.45) == "low"
        assert get_confidence_category(0.3) == "low"

    def test_confidence_category_no_match(self):
        """Test no match categorization."""
        assert get_confidence_category(0.25) == "no_match"
        assert get_confidence_category(0.0) == "no_match"


class TestSanitizeEmailContent:
    """Test sanitize_email_content function."""

    def test_sanitize_email_content_within_limit(self):
        """Test sanitizing content within max length."""
        content = "This is a short email"
        result = sanitize_email_content(content, max_length=100)

        assert result == "This is a short email"

    def test_sanitize_email_content_exceeds_limit(self):
        """Test sanitizing content exceeding max length."""
        content = "a" * 600
        result = sanitize_email_content(content, max_length=500)

        assert len(result) == 503  # 500 + "..."
        assert result.endswith("...")

    def test_sanitize_email_content_empty(self):
        """Test sanitizing empty content."""
        result = sanitize_email_content("", max_length=100)

        assert result == ""

    def test_sanitize_email_content_none(self):
        """Test sanitizing None content."""
        result = sanitize_email_content(None, max_length=100)

        assert result == ""


class TestTruncateString:
    """Test truncate_string function."""

    def test_truncate_string_within_limit(self):
        """Test truncating string within max length."""
        text = "Short text"
        result = truncate_string(text, max_length=20)

        assert result == "Short text"

    def test_truncate_string_exceeds_limit(self):
        """Test truncating string exceeding max length."""
        text = "This is a very long text that needs truncation"
        result = truncate_string(text, max_length=20)

        assert len(result) == 20
        assert result.endswith("...")

    def test_truncate_string_custom_suffix(self):
        """Test truncating with custom suffix."""
        text = "This is a long text"
        result = truncate_string(text, max_length=15, suffix=" [...]")

        assert result.endswith(" [...]")
        assert len(result) == 15


class TestValidateEmailAddress:
    """Test validate_email_address function."""

    def test_validate_email_address_valid(self):
        """Test validating valid email addresses."""
        assert validate_email_address("user@example.com") is True
        assert validate_email_address("test.user+tag@domain.co.uk") is True
        assert validate_email_address("name123@test-domain.com") is True

    def test_validate_email_address_invalid(self):
        """Test validating invalid email addresses."""
        assert validate_email_address("invalid") is False
        assert validate_email_address("@example.com") is False
        assert validate_email_address("user@") is False
        assert validate_email_address("user @example.com") is False
        assert validate_email_address("") is False


class TestSafeInt:
    """Test safe_int function."""

    def test_safe_int_valid_string(self):
        """Test converting valid string to int."""
        assert safe_int("42") == 42
        assert safe_int("-10") == -10

    def test_safe_int_valid_number(self):
        """Test converting valid number to int."""
        assert safe_int(42) == 42
        assert safe_int(3.7) == 3

    def test_safe_int_invalid_value(self):
        """Test converting invalid value returns default."""
        assert safe_int("invalid") == 0
        assert safe_int("invalid", default=99) == 99
        assert safe_int(None) == 0

    def test_safe_int_empty_string(self):
        """Test converting empty string returns default."""
        assert safe_int("") == 0


class TestSafeFloat:
    """Test safe_float function."""

    def test_safe_float_valid_string(self):
        """Test converting valid string to float."""
        assert safe_float("3.14") == 3.14
        assert safe_float("-2.5") == -2.5

    def test_safe_float_valid_number(self):
        """Test converting valid number to float."""
        assert safe_float(42) == 42.0
        assert safe_float(3.7) == 3.7

    def test_safe_float_invalid_value(self):
        """Test converting invalid value returns default."""
        assert safe_float("invalid") == 0.0
        assert safe_float("invalid", default=99.9) == 99.9
        assert safe_float(None) == 0.0

    def test_safe_float_empty_string(self):
        """Test converting empty string returns default."""
        assert safe_float("") == 0.0
