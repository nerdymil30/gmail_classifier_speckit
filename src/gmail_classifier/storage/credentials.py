"""Credential storage module for secure IMAP credential management.

This module provides secure storage of IMAP credentials using the OS keyring.
Credentials are stored encrypted by the operating system's credential manager:
- macOS: Keychain
- Windows: Windows Credential Locker
- Linux: Secret Service API / KWallet / gnome-keyring

Security Features:
- No plain-text password storage
- OS-level encryption
- Per-user credential isolation
- Secure credential deletion
"""

import logging
from datetime import datetime

import keyring

from gmail_classifier.auth.imap import IMAPCredentials

# ============================================================================
# Logging Configuration
# ============================================================================

logger = logging.getLogger("gmail_classifier.storage.credentials")


# ============================================================================
# CredentialStorage Class
# ============================================================================


class CredentialStorage:
    """Secure credential storage using OS keyring.

    Manages IMAP credentials in the operating system's secure keyring,
    providing store, retrieve, delete, and check operations.

    Attributes:
        _service_name: Keyring service identifier for Gmail Classifier IMAP
        _logger: Logger instance for credential operations

    Security considerations:
    - Passwords are encrypted by OS keyring automatically
    - Credentials are isolated per-user account
    - No plain-text storage on disk
    - Secure deletion when logging out
    """

    def __init__(self, service_name: str = "gmail_classifier_imap") -> None:
        """Initialize credential storage.

        Args:
            service_name: Keyring service identifier (default: gmail_classifier_imap)
        """
        self._service_name = service_name
        self._logger = logger

        self._logger.info(f"CredentialStorage initialized: service={service_name}")

    def store_credentials(self, credentials: IMAPCredentials) -> bool:
        """Store IMAP credentials in OS keyring.

        Stores the password securely in the OS keyring using the email
        as the username key. The created_at timestamp is set if not already
        present.

        Args:
            credentials: IMAPCredentials to store

        Returns:
            True if credentials were stored successfully, False otherwise

        Security:
        - Password is encrypted by OS keyring
        - Only password is stored in keyring (email used as key)
        - Timestamps managed separately (not in keyring)
        """
        try:
            # Store password in keyring (email is the username key)
            keyring.set_password(
                self._service_name,
                credentials.email,
                credentials.password,
            )

            self._logger.info(
                f"Credentials stored successfully for {credentials.email}"
            )
            return True

        except Exception as e:
            self._logger.error(
                f"Failed to store credentials for {credentials.email}: {e}"
            )
            return False

    def retrieve_credentials(self, email: str) -> IMAPCredentials | None:
        """Retrieve IMAP credentials from OS keyring.

        Retrieves the stored password for the given email address and
        constructs an IMAPCredentials object.

        Args:
            email: Email address to retrieve credentials for

        Returns:
            IMAPCredentials if found, None otherwise

        Note:
        - created_at is set to current time (original timestamp not preserved)
        - last_used is set to None (must be updated after successful auth)
        """
        try:
            # Retrieve password from keyring
            password = keyring.get_password(self._service_name, email)

            if password is None:
                self._logger.info(f"No credentials found for {email}")
                return None

            # Create IMAPCredentials object
            credentials = IMAPCredentials(
                email=email,
                password=password,
                created_at=datetime.now(),  # Set to current time
                last_used=None,
            )

            self._logger.info(f"Credentials retrieved successfully for {email}")
            return credentials

        except Exception as e:
            self._logger.error(
                f"Failed to retrieve credentials for {email}: {e}"
            )
            return None

    def delete_credentials(self, email: str) -> bool:
        """Delete IMAP credentials from OS keyring.

        Removes the stored password for the given email address. This is
        typically called during logout.

        Args:
            email: Email address to delete credentials for

        Returns:
            True if credentials were deleted successfully, False otherwise

        Note:
        - Returns False if credentials don't exist (not an error)
        - Logs warning if keyring operation fails
        """
        try:
            # Delete password from keyring
            keyring.delete_password(self._service_name, email)

            self._logger.info(f"Credentials deleted successfully for {email}")
            return True

        except Exception as e:
            # Keyring raises exception if password doesn't exist
            self._logger.warning(
                f"Failed to delete credentials for {email}: {e}"
            )
            return False

    def has_credentials(self, email: str) -> bool:
        """Check if credentials exist for the given email.

        Checks for credential existence without retrieving the password.

        Args:
            email: Email address to check

        Returns:
            True if credentials exist, False otherwise

        Note:
        - Does not retrieve the actual password
        - Useful for checking before prompting user
        """
        try:
            password = keyring.get_password(self._service_name, email)
            return password is not None

        except Exception as e:
            self._logger.warning(
                f"Error checking credentials for {email}: {e}"
            )
            return False

    def update_last_used(self, email: str) -> bool:
        """Update the last_used timestamp for stored credentials.

        This method updates the timestamp after successful authentication.

        Args:
            email: Email address to update

        Returns:
            True if update successful, False otherwise

        Note:
        - This is a no-op in the current implementation since we don't
          store timestamps in the keyring
        - Timestamps are managed at the application level
        - Method provided for API completeness and future enhancement
        """
        try:
            # Check if credentials exist
            if not self.has_credentials(email):
                self._logger.warning(
                    f"Cannot update last_used: no credentials for {email}"
                )
                return False

            # In current implementation, we don't store timestamps in keyring
            # Timestamps are managed by the application layer
            # This method is here for API consistency

            self._logger.debug(f"Last used timestamp noted for {email}")
            return True

        except Exception as e:
            self._logger.error(
                f"Failed to update last_used for {email}: {e}"
            )
            return False

    def list_stored_emails(self) -> list[str]:
        """List all emails with stored credentials.

        Returns a list of email addresses that have credentials stored
        in the keyring.

        Returns:
            List of email addresses (may be empty)

        Note:
        - Implementation depends on keyring backend capabilities
        - Some keyring backends don't support listing entries
        - Returns empty list if listing not supported or on error
        """
        try:
            # Most keyring backends don't support listing entries
            # This is a placeholder for future enhancement
            self._logger.warning(
                "list_stored_emails() not fully implemented: "
                "keyring backends typically don't support listing"
            )
            return []

        except Exception as e:
            self._logger.error(f"Failed to list stored emails: {e}")
            return []
