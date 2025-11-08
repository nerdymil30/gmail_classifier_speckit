"""Unit tests for IMAP password validation (TODO 021).

Tests verify comprehensive password validation including:
- Gmail app password format (16 lowercase letters)
- Password length constraints (12-64 chars for regular passwords)
- Complexity requirements (3 of 4 character types)
- Weak pattern detection (repeated characters)
- Helpful error messages

Test Coverage:
- T021-01: Gmail app password validation
- T021-02: Regular password length requirements
- T021-03: Password complexity requirements
- T021-04: Weak pattern detection
- T021-05: Error message guidance
"""

import pytest

from gmail_classifier.auth.imap import IMAPCredentials


class TestGmailAppPasswordValidation:
    """Tests for Gmail app password format validation (16 lowercase letters)."""

    def test_valid_app_password_16_lowercase_letters(self) -> None:
        """T021-01: Valid 16-char lowercase app password is accepted."""
        # Valid app password format
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="abcdefghijklmnop"  # 16 lowercase letters
        )
        assert credentials.password == "abcdefghijklmnop"

    def test_valid_app_password_with_spaces(self) -> None:
        """T021-01: Valid app password with spaces is accepted."""
        # Gmail app passwords can have spaces (e.g., "abcd efgh ijkl mnop")
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="abcd efgh ijkl mnop"  # 16 letters with spaces
        )
        assert credentials.password == "abcd efgh ijkl mnop"

    def test_app_password_uppercase_rejected(self) -> None:
        """T021-01: App password with uppercase letters is rejected."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="ABCDEFGHIJKLMNOP"  # Uppercase
            )
        assert "lowercase" in str(exc_info.value).lower()
        assert "myaccount.google.com/apppasswords" in str(exc_info.value)

    def test_app_password_mixed_case_rejected(self) -> None:
        """T021-01: App password with mixed case is rejected."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="AbCdEfGhIjKlMnOp"  # Mixed case
            )
        assert "lowercase" in str(exc_info.value).lower()

    def test_app_password_with_digits_not_app_password(self) -> None:
        """T021-01: 16-char password with digits is not treated as app password."""
        # 16 characters but contains digits - should be treated as regular password
        # and fail complexity requirements (only lowercase and digits = 2 types)
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="abcdefghijklm123"  # 16 chars with digits
            )
        assert "at least 3 of" in str(exc_info.value).lower()


class TestRegularPasswordValidation:
    """Tests for regular password length and complexity requirements."""

    def test_valid_password_12_chars_complex(self) -> None:
        """T021-02: Valid 12-char password with complexity is accepted."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="Test1234567!"  # 12 chars: upper, lower, digit, special
        )
        assert credentials.password == "Test1234567!"

    def test_valid_password_long_complex(self) -> None:
        """T021-02: Valid long password with complexity is accepted."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="ThisIsAVerySecurePassword123!"  # Long and complex
        )
        assert credentials.password == "ThisIsAVerySecurePassword123!"

    def test_password_too_short_rejected(self) -> None:
        """T021-02: Password shorter than 12 chars is rejected."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="Short1!"  # Only 7 chars
            )
        assert "at least 12 characters" in str(exc_info.value)
        assert "myaccount.google.com/apppasswords" in str(exc_info.value)

    def test_password_11_chars_rejected(self) -> None:
        """T021-02: Password with 11 chars is rejected (just under minimum)."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="Password1!"  # 11 chars
            )
        assert "at least 12 characters" in str(exc_info.value)

    def test_password_too_long_rejected(self) -> None:
        """T021-02: Password longer than 64 chars is rejected."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="A" * 65 + "bc1!"  # 69 chars
            )
        assert "must not exceed 64 characters" in str(exc_info.value)

    def test_password_64_chars_accepted(self) -> None:
        """T021-02: Password with exactly 64 chars is accepted."""
        # 64 chars with complexity (avoid repeated chars)
        password = "AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz0123456789!@"
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password=password
        )
        assert len(credentials.password) == 64


class TestPasswordComplexity:
    """Tests for password complexity requirements (3 of 4 character types)."""

    def test_complexity_upper_lower_digit(self) -> None:
        """T021-03: Password with uppercase, lowercase, and digits is valid."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="Password1234"  # Upper, lower, digits (3 types)
        )
        assert credentials.password == "Password1234"

    def test_complexity_upper_lower_special(self) -> None:
        """T021-03: Password with uppercase, lowercase, and special is valid."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="Password!@#$"  # Upper, lower, special (3 types)
        )
        assert credentials.password == "Password!@#$"

    def test_complexity_upper_digit_special(self) -> None:
        """T021-03: Password with uppercase, digits, and special is valid."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="PASSWORD123!"  # Upper, digits, special (3 types)
        )
        assert credentials.password == "PASSWORD123!"

    def test_complexity_lower_digit_special(self) -> None:
        """T021-03: Password with lowercase, digits, and special is valid."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="password123!"  # Lower, digits, special (3 types)
        )
        assert credentials.password == "password123!"

    def test_complexity_all_four_types(self) -> None:
        """T021-03: Password with all 4 character types is valid."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="Password123!"  # Upper, lower, digits, special (4 types)
        )
        assert credentials.password == "Password123!"

    def test_complexity_only_lowercase_rejected(self) -> None:
        """T021-03: Password with only lowercase is rejected."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="passwordpasswordlong"  # Only lowercase (1 type), 20 chars
            )
        assert "at least 3 of" in str(exc_info.value)

    def test_complexity_only_two_types_rejected(self) -> None:
        """T021-03: Password with only 2 character types is rejected."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="password1234"  # Lower and digits only (2 types)
            )
        assert "at least 3 of" in str(exc_info.value)
        assert "uppercase, lowercase, digits, special characters" in str(exc_info.value)


class TestWeakPatternDetection:
    """Tests for weak password pattern detection."""

    def test_repeated_chars_3_in_row_rejected(self) -> None:
        """T021-04: Password with 3 repeated characters is rejected."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="Passsword123!"  # 'sss' repeated
            )
        assert "repeated characters" in str(exc_info.value).lower()

    def test_repeated_chars_4_in_row_rejected(self) -> None:
        """T021-04: Password with 4 repeated characters is rejected."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="Passsssword1!"  # Multiple 's' repeated
            )
        assert "repeated characters" in str(exc_info.value).lower()

    def test_repeated_digits_rejected(self) -> None:
        """T021-04: Password with repeated digits is rejected."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="Password111!"  # '111' repeated
            )
        assert "repeated characters" in str(exc_info.value).lower()

    def test_repeated_special_chars_rejected(self) -> None:
        """T021-04: Password with repeated special characters is rejected."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="Password123!!!"  # '!!!' repeated
            )
        assert "repeated characters" in str(exc_info.value).lower()

    def test_two_repeated_chars_allowed(self) -> None:
        """T021-04: Password with 2 repeated characters (not 3) is allowed."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="Passw0rd!123"  # 'ss' is OK (only 2 in a row)
        )
        assert credentials.password == "Passw0rd!123"


class TestErrorMessages:
    """Tests for helpful error messages with guidance."""

    def test_short_password_shows_app_password_link(self) -> None:
        """T021-05: Short password error suggests using app password."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="Short1!"
            )
        error_msg = str(exc_info.value)
        assert "at least 12 characters" in error_msg
        assert "Gmail app password" in error_msg
        assert "https://myaccount.google.com/apppasswords" in error_msg

    def test_uppercase_app_password_shows_link(self) -> None:
        """T021-05: Uppercase app password error shows generation link."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="ABCDEFGHIJKLMNOP"
            )
        error_msg = str(exc_info.value)
        assert "lowercase" in error_msg.lower()
        assert "https://myaccount.google.com/apppasswords" in error_msg

    def test_complexity_error_shows_requirements(self) -> None:
        """T021-05: Complexity error clearly states requirements."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="passwordonly"
            )
        error_msg = str(exc_info.value)
        assert "at least 3 of" in error_msg
        assert "uppercase" in error_msg
        assert "lowercase" in error_msg
        assert "digits" in error_msg
        assert "special characters" in error_msg

    def test_repeated_chars_error_is_clear(self) -> None:
        """T021-05: Repeated character error is clear."""
        with pytest.raises(ValueError) as exc_info:
            IMAPCredentials(
                email="test@gmail.com",
                password="Passsword123!"
            )
        assert "repeated characters" in str(exc_info.value).lower()


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_password_with_special_punctuation(self) -> None:
        """Test password with various special characters is accepted."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="P@ssw0rd#$%^&*()"  # Various special chars
        )
        assert credentials.password == "P@ssw0rd#$%^&*()"

    def test_password_with_unicode_special_chars(self) -> None:
        """Test password with unicode characters and complexity is accepted."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="Пароль123!Test"  # Unicode with complexity
        )
        assert credentials.password == "Пароль123!Test"

    def test_exactly_12_chars_complex(self) -> None:
        """Test exactly 12-char password at minimum threshold."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="Password12!x"  # Exactly 12 chars
        )
        assert len(credentials.password) == 12

    def test_app_password_exactly_16_no_spaces(self) -> None:
        """Test app password with exactly 16 chars and no spaces."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="qwertyuiopasdfgh"  # Exactly 16 lowercase
        )
        assert credentials.password == "qwertyuiopasdfgh"

    def test_app_password_16_chars_with_multiple_spaces(self) -> None:
        """Test app password with multiple space variations."""
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="qwer tyui opas dfgh"  # 16 letters with spaces
        )
        assert credentials.password == "qwer tyui opas dfgh"
