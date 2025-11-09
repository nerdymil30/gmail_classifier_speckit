"""Unit tests for IMAP folder operations.

These tests verify folder listing, selection, and status operations.
Tests use mocked IMAPClient to avoid real IMAP server interactions.

Test Organization:
- T033: Folder listing (list_folders)
- T034: Folder selection (select_folder)

NOTE: These tests use mocked IMAPClient to avoid network operations.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from gmail_classifier.auth.imap import IMAPAuthenticator, IMAPCredentials, SessionState


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def test_credentials() -> IMAPCredentials:
    """Provide test IMAP credentials."""
    return IMAPCredentials(
        email="test@gmail.com",
        password="test_app_password_16ch",
    )


@pytest.fixture
def mock_imap_session():
    """Provide a mocked IMAP session with connection."""
    with patch("imapclient.IMAPClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.login.return_value = b"LOGIN completed"
        mock_client.noop.return_value = (b"OK", [b"NOOP completed"])
        mock_client_class.return_value = mock_client

        authenticator = IMAPAuthenticator()
        credentials = IMAPCredentials(
            email="test@gmail.com",
            password="test_app_password_16ch",
        )
        session_info = authenticator.authenticate(credentials)

        yield (authenticator, session_info, mock_client)


# ============================================================================
# T033: Test Folder Listing
# ============================================================================


class TestFolderListing:
    """Unit tests for listing IMAP folders."""

    def test_list_folders_returns_all_gmail_folders(self, mock_imap_session) -> None:
        """T033: Test list_folders() returns all Gmail folders.

        Validates:
        - Retrieves folders using IMAPClient.list_folders()
        - Returns list of EmailFolder entities
        - Parses Gmail-specific folder names correctly
        - Includes INBOX, Sent, Drafts, custom labels

        Expected outcome: List of folders with correct types
        """
        from gmail_classifier.email.fetcher import FolderManager

        authenticator, session_info, mock_client = mock_imap_session

        # Mock list_folders response (Gmail format)
        mock_client.list_folders.return_value = [
            ((b"\\HasNoChildren",), b"/", "INBOX"),
            ((b"\\HasNoChildren", b"\\Sent"), b"/", "[Gmail]/Sent Mail"),
            ((b"\\HasNoChildren", b"\\Drafts"), b"/", "[Gmail]/Drafts"),
            ((b"\\HasNoChildren",), b"/", "Work"),
            ((b"\\HasNoChildren",), b"/", "Projects/Q4"),
        ]

        # Create FolderManager
        folder_manager = FolderManager(authenticator)

        # Act
        folders = folder_manager.list_folders(session_info.session_id)

        # Assert
        assert len(folders) == 5
        assert any(f.folder_name == "INBOX" for f in folders)
        assert any(f.folder_name == "[Gmail]/Sent Mail" for f in folders)
        assert any(f.folder_name == "Work" for f in folders)

    def test_list_folders_caches_results(self, mock_imap_session) -> None:
        """T033: Test list_folders() caches folder list.

        Validates:
        - First call fetches from server
        - Second call returns cached results
        - IMAPClient.list_folders called only once

        Expected outcome: Cached results on subsequent calls
        """
        from gmail_classifier.email.fetcher import FolderManager

        authenticator, session_info, mock_client = mock_imap_session

        mock_client.list_folders.return_value = [
            ((b"\\HasNoChildren",), b"/", "INBOX"),
        ]

        folder_manager = FolderManager(authenticator)

        # First call
        folders1 = folder_manager.list_folders(session_info.session_id)

        # Second call
        folders2 = folder_manager.list_folders(session_info.session_id)

        # Assert
        assert folders1 == folders2
        # list_folders should be called only once (cached)
        assert mock_client.list_folders.call_count == 1

    def test_list_folders_handles_empty_mailbox(self, mock_imap_session) -> None:
        """T033: Test list_folders() handles empty mailbox.

        Validates:
        - Returns empty list when no folders exist
        - No exception raised

        Expected outcome: Empty list returned
        """
        from gmail_classifier.email.fetcher import FolderManager

        authenticator, session_info, mock_client = mock_imap_session

        mock_client.list_folders.return_value = []

        folder_manager = FolderManager(authenticator)
        folders = folder_manager.list_folders(session_info.session_id)

        assert folders == []

    def test_list_folders_force_refresh_bypasses_cache(self, mock_imap_session) -> None:
        """T033: Test list_folders() force_refresh bypasses cache.

        Validates:
        - force_refresh=True bypasses cache
        - IMAPClient.list_folders called on each force refresh
        - Cached results ignored when force_refresh=True

        Expected outcome: Server called on each force refresh
        """
        from gmail_classifier.email.fetcher import FolderManager

        authenticator, session_info, mock_client = mock_imap_session

        mock_client.list_folders.return_value = [
            ((b"\\HasNoChildren",), b"/", "INBOX"),
        ]

        folder_manager = FolderManager(authenticator)

        # First call (cached)
        folders1 = folder_manager.list_folders(session_info.session_id)

        # Second call with force_refresh=True (bypasses cache)
        folders2 = folder_manager.list_folders(session_info.session_id, force_refresh=True)

        # Third call with force_refresh=True (bypasses cache again)
        folders3 = folder_manager.list_folders(session_info.session_id, force_refresh=True)

        # Assert
        assert folders1 == folders2 == folders3
        # list_folders should be called three times (force refresh twice)
        assert mock_client.list_folders.call_count == 3

    def test_list_folders_cache_expires_after_ttl(self, mock_imap_session) -> None:
        """T033: Test list_folders() cache expires after TTL.

        Validates:
        - Cache expires after 10 minutes TTL
        - Fresh data fetched when cache is stale
        - is_stale() method correctly identifies stale cache

        Expected outcome: Cache refreshed after TTL expires
        """
        from datetime import datetime, timedelta
        from unittest.mock import patch

        from gmail_classifier.email.fetcher import FolderManager

        authenticator, session_info, mock_client = mock_imap_session

        mock_client.list_folders.return_value = [
            ((b"\\HasNoChildren",), b"/", "INBOX"),
        ]

        folder_manager = FolderManager(authenticator)

        # First call (cached)
        folders1 = folder_manager.list_folders(session_info.session_id)
        assert mock_client.list_folders.call_count == 1

        # Second call (should use cache)
        folders2 = folder_manager.list_folders(session_info.session_id)
        assert mock_client.list_folders.call_count == 1  # Still 1, used cache

        # Simulate cache expiration by manually setting created_at to 11 minutes ago
        cache_entry = folder_manager._folder_cache[session_info.session_id]
        cache_entry.created_at = datetime.now() - timedelta(minutes=11)

        # Third call (cache should be stale, refetch)
        folders3 = folder_manager.list_folders(session_info.session_id)
        assert mock_client.list_folders.call_count == 2  # Refetched due to stale cache

        # All results should be equal
        assert folders1 == folders2 == folders3


# ============================================================================
# T034: Test Folder Selection
# ============================================================================


class TestFolderSelection:
    """Unit tests for selecting IMAP folders."""

    def test_select_folder_changes_active_folder(self, mock_imap_session) -> None:
        """T034: Test select_folder() changes active folder and returns metadata.

        Validates:
        - Calls IMAPClient.select_folder()
        - Updates session state with selected folder
        - Returns folder metadata (message_count, unread_count)

        Expected outcome: Folder selected, metadata returned
        """
        from gmail_classifier.email.fetcher import FolderManager

        authenticator, session_info, mock_client = mock_imap_session

        # Mock select_folder response
        mock_client.select_folder.return_value = {
            b"EXISTS": 42,
            b"RECENT": 5,
            b"UNSEEN": 3,
        }

        folder_manager = FolderManager(authenticator)
        result = folder_manager.select_folder(session_info.session_id, "INBOX")

        # Assert
        assert result["message_count"] == 42
        assert result["unread_count"] == 3
        mock_client.select_folder.assert_called_once_with("INBOX", readonly=False)

        # Verify session state updated
        session = authenticator.get_session(session_info.session_id)
        assert session.selected_folder == "INBOX"

    def test_select_folder_handles_non_existent_folder(self, mock_imap_session) -> None:
        """T034: Test select_folder() handles non-existent folder.

        Validates:
        - Raises exception when folder doesn't exist
        - Error message is clear

        Expected outcome: Exception raised with clear message
        """
        from gmail_classifier.email.fetcher import FolderManager

        authenticator, session_info, mock_client = mock_imap_session

        # Mock select_folder to raise error
        from imapclient.exceptions import IMAPClientError

        mock_client.select_folder.side_effect = IMAPClientError("Mailbox doesn't exist")

        folder_manager = FolderManager(authenticator)

        with pytest.raises(Exception) as exc_info:
            folder_manager.select_folder(session_info.session_id, "NonExistent")

        assert "mailbox" in str(exc_info.value).lower() or "folder" in str(exc_info.value).lower()

    def test_select_folder_readonly_mode(self, mock_imap_session) -> None:
        """T034: Test select_folder() with readonly mode.

        Validates:
        - Can select folder in readonly mode
        - No modifications allowed to messages

        Expected outcome: Folder selected in readonly mode
        """
        from gmail_classifier.email.fetcher import FolderManager

        authenticator, session_info, mock_client = mock_imap_session

        mock_client.select_folder.return_value = {
            b"EXISTS": 10,
            b"RECENT": 0,
        }

        folder_manager = FolderManager(authenticator)
        result = folder_manager.select_folder(
            session_info.session_id, "INBOX", readonly=True
        )

        # Assert
        assert result is not None
        mock_client.select_folder.assert_called_with("INBOX", readonly=True)


# ============================================================================
# Test get_folder_status (without selecting)
# ============================================================================


class TestFolderStatus:
    """Unit tests for getting folder status without selecting."""

    def test_get_folder_status_without_selecting(self, mock_imap_session) -> None:
        """Test get_folder_status() gets info without selecting folder.

        Validates:
        - Uses STATUS command instead of SELECT
        - Returns message counts
        - Doesn't change selected folder

        Expected outcome: Status returned without folder selection
        """
        from gmail_classifier.email.fetcher import FolderManager

        authenticator, session_info, mock_client = mock_imap_session

        # Mock folder_status response
        mock_client.folder_status.return_value = {
            b"MESSAGES": 100,
            b"UNSEEN": 15,
        }

        folder_manager = FolderManager(authenticator)
        status = folder_manager.get_folder_status(session_info.session_id, "Work")

        # Assert
        assert status["message_count"] == 100
        assert status["unread_count"] == 15
        mock_client.folder_status.assert_called_once()

        # Verify selected folder not changed
        session = authenticator.get_session(session_info.session_id)
        assert session.selected_folder != "Work"  # Should still be None or previous folder
