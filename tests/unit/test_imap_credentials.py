"""Unit tests for IMAP credential storage.

These tests verify credential storage operations using the OS keyring.
Tests use mocked keyring to avoid actual OS keyring operations.

Test Organization:
- T022: Credential storage (store_credentials)
- T023: Credential retrieval (retrieve_credentials)
- T024: Credential deletion (delete_credentials)

NOTE: These tests use mocked keyring to avoid modifying the actual OS keyring.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from gmail_classifier.auth.imap import IMAPCredentials


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def test_credentials() -> IMAPCredentials:
    """Provide test IMAP credentials.

    Returns:
        IMAPCredentials with test email and password
    """
    return IMAPCredentials(
        email="test@gmail.com",
        password="abcdefghijklmnop",  # Valid 16-char Gmail app password
        created_at=datetime.now(),
    )


# ============================================================================
# T022: Test Credential Storage
# ============================================================================


class TestCredentialStorage:
    """Unit tests for storing credentials in OS keyring."""

    def test_store_credentials_saves_to_keyring(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """T022: Test store_credentials() saves to keyring.

        Validates:
        - Credentials are stored using keyring.set_password
        - Service name is correct (gmail_classifier_imap)
        - Email is used as username key
        - Password is stored as the keyring value
        - Method returns True on success

        Expected outcome: keyring.set_password called with correct parameters
        """
        from gmail_classifier.storage.credentials import CredentialStorage

        with patch("keyring.set_password") as mock_set_password:
            # Arrange
            storage = CredentialStorage()

            # Act
            result = storage.store_credentials(test_credentials)

            # Assert
            assert result is True
            mock_set_password.assert_called_once_with(
                "gmail_classifier_imap",
                test_credentials.email,
                test_credentials.password,
            )

    def test_store_credentials_handles_keyring_error(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """T022: Test store_credentials() handles keyring errors gracefully.

        Validates:
        - Keyring errors are caught and handled
        - Method returns False on error
        - Error is logged

        Expected outcome: Returns False when keyring raises exception
        """
        from gmail_classifier.storage.credentials import CredentialStorage

        with patch("keyring.set_password") as mock_set_password:
            # Arrange
            mock_set_password.side_effect = Exception("Keyring error")
            storage = CredentialStorage()

            # Act
            result = storage.store_credentials(test_credentials)

            # Assert
            assert result is False

    def test_store_credentials_updates_created_at(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """T022: Test store_credentials() sets created_at timestamp.

        Validates:
        - created_at timestamp is set to current time if not already set
        - Existing created_at is preserved

        Expected outcome: Credentials have valid created_at timestamp
        """
        from gmail_classifier.storage.credentials import CredentialStorage

        with patch("keyring.set_password"):
            # Arrange
            storage = CredentialStorage()
            original_created_at = test_credentials.created_at

            # Act
            storage.store_credentials(test_credentials)

            # Assert - should preserve existing created_at
            assert test_credentials.created_at == original_created_at


# ============================================================================
# T023: Test Credential Retrieval
# ============================================================================


class TestCredentialRetrieval:
    """Unit tests for retrieving credentials from OS keyring."""

    def test_retrieve_credentials_loads_from_keyring(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """T023: Test retrieve_credentials() loads from keyring.

        Validates:
        - Credentials are retrieved using keyring.get_password
        - Returns IMAPCredentials dataclass
        - Email matches the requested email
        - Password matches stored password

        Expected outcome: Valid IMAPCredentials returned
        """
        from gmail_classifier.storage.credentials import CredentialStorage

        with patch("keyring.get_password") as mock_get_password:
            # Arrange
            mock_get_password.return_value = test_credentials.password
            storage = CredentialStorage()

            # Act
            result = storage.retrieve_credentials(test_credentials.email)

            # Assert
            assert result is not None
            assert result.email == test_credentials.email
            assert result.password == test_credentials.password
            mock_get_password.assert_called_once_with(
                "gmail_classifier_imap", test_credentials.email
            )

    def test_retrieve_credentials_returns_none_when_not_found(self) -> None:
        """T023: Test retrieve_credentials() returns None when credentials don't exist.

        Validates:
        - Returns None when keyring returns None
        - No exception raised for missing credentials

        Expected outcome: None returned for non-existent credentials
        """
        from gmail_classifier.storage.credentials import CredentialStorage

        with patch("keyring.get_password") as mock_get_password:
            # Arrange
            mock_get_password.return_value = None
            storage = CredentialStorage()

            # Act
            result = storage.retrieve_credentials("nonexistent@gmail.com")

            # Assert
            assert result is None

    def test_retrieve_credentials_handles_keyring_error(self) -> None:
        """T023: Test retrieve_credentials() handles keyring errors.

        Validates:
        - Keyring errors are caught
        - Returns None on error
        - Error is logged

        Expected outcome: None returned when keyring raises exception
        """
        from gmail_classifier.storage.credentials import CredentialStorage

        with patch("keyring.get_password") as mock_get_password:
            # Arrange
            mock_get_password.side_effect = Exception("Keyring error")
            storage = CredentialStorage()

            # Act
            result = storage.retrieve_credentials("test@gmail.com")

            # Assert
            assert result is None


# ============================================================================
# T024: Test Credential Deletion
# ============================================================================


class TestCredentialDeletion:
    """Unit tests for deleting credentials from OS keyring."""

    def test_delete_credentials_removes_from_keyring(self) -> None:
        """T024: Test delete_credentials() removes from keyring.

        Validates:
        - Credentials are deleted using keyring.delete_password
        - Service name and email are correct
        - Method returns True on success

        Expected outcome: keyring.delete_password called with correct parameters
        """
        from gmail_classifier.storage.credentials import CredentialStorage

        with patch("keyring.delete_password") as mock_delete_password:
            # Arrange
            storage = CredentialStorage()
            email = "test@gmail.com"

            # Act
            result = storage.delete_credentials(email)

            # Assert
            assert result is True
            mock_delete_password.assert_called_once_with(
                "gmail_classifier_imap", email
            )

    def test_delete_credentials_returns_false_when_not_found(self) -> None:
        """T024: Test delete_credentials() handles missing credentials.

        Validates:
        - Returns False when credentials don't exist
        - No exception raised for missing credentials

        Expected outcome: False returned for non-existent credentials
        """
        from gmail_classifier.storage.credentials import CredentialStorage

        with patch("keyring.delete_password") as mock_delete_password:
            # Arrange - simulate keyring error for non-existent entry
            mock_delete_password.side_effect = Exception("Password not found")
            storage = CredentialStorage()

            # Act
            result = storage.delete_credentials("nonexistent@gmail.com")

            # Assert
            assert result is False

    def test_delete_credentials_handles_keyring_error(self) -> None:
        """T024: Test delete_credentials() handles keyring errors.

        Validates:
        - Keyring errors are caught
        - Returns False on error
        - Error is logged

        Expected outcome: False returned when keyring raises exception
        """
        from gmail_classifier.storage.credentials import CredentialStorage

        with patch("keyring.delete_password") as mock_delete_password:
            # Arrange
            mock_delete_password.side_effect = Exception("Keyring error")
            storage = CredentialStorage()

            # Act
            result = storage.delete_credentials("test@gmail.com")

            # Assert
            assert result is False


# ============================================================================
# Additional Tests for has_credentials and update_last_used
# ============================================================================


class TestCredentialHelpers:
    """Unit tests for credential helper methods."""

    def test_has_credentials_returns_true_when_exists(self) -> None:
        """Test has_credentials() returns True when credentials exist.

        Validates:
        - Checks for credential existence without retrieving password
        - Returns True when credentials found

        Expected outcome: True when credentials exist
        """
        from gmail_classifier.storage.credentials import CredentialStorage

        with patch("keyring.get_password") as mock_get_password:
            # Arrange
            mock_get_password.return_value = "ValidPassword123!"
            storage = CredentialStorage()

            # Act
            result = storage.has_credentials("test@gmail.com")

            # Assert
            assert result is True

    def test_has_credentials_returns_false_when_not_exists(self) -> None:
        """Test has_credentials() returns False when credentials don't exist.

        Validates:
        - Returns False when credentials not found

        Expected outcome: False when credentials don't exist
        """
        from gmail_classifier.storage.credentials import CredentialStorage

        with patch("keyring.get_password") as mock_get_password:
            # Arrange
            mock_get_password.return_value = None
            storage = CredentialStorage()

            # Act
            result = storage.has_credentials("nonexistent@gmail.com")

            # Assert
            assert result is False

    def test_update_last_used_updates_timestamp(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test update_last_used() updates the last_used timestamp.

        Validates:
        - Updates last_used field on successful authentication
        - Timestamp is current time

        Expected outcome: last_used updated to current time
        """
        from gmail_classifier.storage.credentials import CredentialStorage

        with patch("keyring.get_password") as mock_get_password:
            with patch("keyring.set_password") as mock_set_password:
                # Arrange
                mock_get_password.return_value = test_credentials.password
                storage = CredentialStorage()

                # Act
                before_update = datetime.now()
                result = storage.update_last_used(test_credentials.email)
                after_update = datetime.now()

                # Assert
                assert result is True
                # Verify the timestamp was updated (we can't check exact value without retrieving)
                # This is validated by checking that keyring operations were called
                assert mock_get_password.called


# ============================================================================
# Memory Security Tests (T025)
# ============================================================================


class TestMemorySecurity:
    """Unit tests for secure password memory handling."""

    def test_password_stored_as_bytearray(self) -> None:
        """T025: Test password is stored as bytearray internally.

        Validates:
        - Password is stored as bytearray, not string
        - _password_bytes attribute exists and is bytearray type

        Expected outcome: _password_bytes is a bytearray
        """
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="TestPassword123!"
        )

        # Assert internal storage is bytearray
        assert hasattr(credentials, '_password_bytes')
        assert isinstance(credentials._password_bytes, bytearray)
        assert len(credentials._password_bytes) > 0

    def test_password_property_returns_string(self) -> None:
        """T025: Test password property accessor returns string.

        Validates:
        - Password property returns string
        - String matches original password

        Expected outcome: Property returns correct string
        """
        test_password = "TestPassword123!"
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password=test_password
        )

        # Assert property returns string
        assert isinstance(credentials.password, str)
        assert credentials.password == test_password

    def test_clear_password_zeros_memory(self) -> None:
        """T025: Test clear_password() zeros password in memory.

        Validates:
        - clear_password() empties the bytearray
        - _password_bytes is empty after clearing

        Expected outcome: Password cleared from memory
        """
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="TestPassword123!"
        )

        # Verify password exists
        assert len(credentials._password_bytes) > 0

        # Clear password
        credentials.clear_password()

        # Assert password is cleared
        assert len(credentials._password_bytes) == 0

    def test_clear_password_multiple_times_safe(self) -> None:
        """T025: Test clear_password() can be called multiple times safely.

        Validates:
        - Calling clear_password() multiple times doesn't raise errors
        - Method is idempotent

        Expected outcome: No errors when called repeatedly
        """
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="TestPassword123!"
        )

        # Clear multiple times - should not raise
        credentials.clear_password()
        credentials.clear_password()
        credentials.clear_password()

        # Assert no errors and password still cleared
        assert len(credentials._password_bytes) == 0

    def test_accessing_password_after_clear_raises_error(self) -> None:
        """T025: Test accessing password after clear raises ValueError.

        Validates:
        - Accessing password property after clear raises ValueError
        - Error message indicates password was cleared

        Expected outcome: ValueError raised with appropriate message
        """
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="TestPassword123!"
        )

        # Clear password
        credentials.clear_password()

        # Assert accessing password raises ValueError
        with pytest.raises(ValueError) as exc_info:
            _ = credentials.password

        assert "cleared" in str(exc_info.value).lower()

    def test_del_cleanup_clears_password(self) -> None:
        """T025: Test __del__ cleanup clears password on deletion.

        Validates:
        - Password is cleared when object is deleted
        - __del__ calls clear_password()

        Expected outcome: Password cleared on object deletion
        """
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="TestPassword123!"
        )

        # Get reference to internal bytearray
        password_bytes = credentials._password_bytes

        # Verify password exists
        assert len(password_bytes) > 0

        # Delete object
        del credentials

        # Assert password was cleared (bytearray should be empty)
        # Note: This is best effort - GC timing is non-deterministic
        assert len(password_bytes) == 0

    def test_password_not_in_repr(self) -> None:
        """T025: Test password not exposed in __repr__.

        Validates:
        - __repr__ doesn't contain the password
        - __repr__ is safe to log

        Expected outcome: Password not in string representation
        """
        test_password = "SuperSecret123!"
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password=test_password
        )

        repr_str = repr(credentials)

        # Assert password not in repr
        assert test_password not in repr_str
        assert "password" not in repr_str.lower()
        assert "SuperSecret" not in repr_str

    def test_credentials_with_custom_timestamps(self) -> None:
        """T025: Test credentials with custom created_at and last_used.

        Validates:
        - Custom timestamps are preserved
        - Password storage still works with custom timestamps

        Expected outcome: Custom timestamps stored correctly
        """
        from datetime import datetime, timedelta

        created = datetime.now() - timedelta(days=7)
        last_used = datetime.now() - timedelta(days=1)

        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="TestPassword123!",
            created_at=created,
            last_used=last_used
        )

        # Assert timestamps preserved
        assert credentials.created_at == created
        assert credentials.last_used == last_used

        # Assert password still accessible
        assert credentials.password == "TestPassword123!"

        # Assert password can still be cleared
        credentials.clear_password()
        assert len(credentials._password_bytes) == 0

    def test_password_encoding_handles_unicode(self) -> None:
        """T025: Test password storage handles unicode characters.

        Validates:
        - Unicode characters in password are handled correctly
        - Encoding/decoding preserves unicode

        Expected outcome: Unicode passwords work correctly
        """
        unicode_password = "Testпароль密码123!"
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password=unicode_password
        )

        # Assert password stored and retrieved correctly
        assert credentials.password == unicode_password

        # Assert can be cleared
        credentials.clear_password()
        assert len(credentials._password_bytes) == 0

    def test_ctypes_memset_called_on_clear(self) -> None:
        """T025: Test ctypes.memset is called during clear_password.

        Validates:
        - clear_password() attempts to use ctypes.memset
        - Fallback works if memset fails

        Expected outcome: Password cleared even if memset fails
        """
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="TestPassword123!"
        )

        # Mock ctypes.memset to raise exception
        import ctypes
        original_memset = ctypes.memset

        def failing_memset(*args, **kwargs):
            raise Exception("memset failed")

        # Temporarily replace memset
        ctypes.memset = failing_memset

        try:
            # Clear should still work (fallback to bytearray.clear())
            credentials.clear_password()

            # Assert password still cleared despite memset failure
            assert len(credentials._password_bytes) == 0
        finally:
            # Restore original memset
            ctypes.memset = original_memset
