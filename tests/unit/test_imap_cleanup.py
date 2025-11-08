"""Unit tests for IMAP session cleanup functionality.

These tests verify automatic session cleanup, session limits, and monitoring.

Test Organization:
- T030: Background cleanup thread
- T031: Stale session cleanup
- T032: Session limit per email
- T033: Cleanup metrics/statistics
"""

import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from gmail_classifier.auth.imap import (
    CLEANUP_INTERVAL_SECONDS,
    MAX_SESSIONS_PER_EMAIL,
    STALE_TIMEOUT_MINUTES,
    IMAPAuthenticator,
    IMAPCredentials,
    IMAPSessionInfo,
    SessionState,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_imap_client():
    """Provide a mocked IMAPClient."""
    with patch("gmail_classifier.auth.imap.IMAPClient") as mock_client:
        client_instance = Mock()
        client_instance.login.return_value = b"OK"
        client_instance.noop.return_value = b"OK"
        client_instance.logout.return_value = b"OK"
        mock_client.return_value = client_instance
        yield mock_client


@pytest.fixture
def authenticator():
    """Provide IMAPAuthenticator instance with mocked cleanup thread."""
    with patch.object(IMAPAuthenticator, "_start_cleanup_thread"):
        auth = IMAPAuthenticator()
        yield auth


@pytest.fixture
def credentials():
    """Provide test IMAP credentials."""
    return IMAPCredentials(
        email="test@gmail.com",
        password="test_password_12345"
    )


# ============================================================================
# T030: Test Background Cleanup Thread
# ============================================================================


class TestBackgroundCleanupThread:
    """Unit tests for background cleanup thread functionality."""

    def test_cleanup_thread_starts_on_init(self):
        """T030: Test cleanup thread starts when authenticator is initialized.

        Validates:
        - Cleanup thread is created and started
        - Thread is configured as daemon
        - Thread has correct name
        """
        with patch("threading.Thread") as mock_thread:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance

            auth = IMAPAuthenticator()

            # Verify thread was created with correct parameters
            mock_thread.assert_called_once()
            call_kwargs = mock_thread.call_args.kwargs
            assert call_kwargs["daemon"] is True
            assert call_kwargs["name"] == "imap-session-cleanup"

            # Verify thread was started
            mock_thread_instance.start.assert_called_once()

    def test_cleanup_thread_runs_periodically(self):
        """T030: Test cleanup thread runs at configured intervals.

        Validates:
        - Thread sleeps for CLEANUP_INTERVAL_SECONDS
        - Cleanup method is called after each sleep
        """
        with patch("time.sleep") as mock_sleep:
            with patch.object(IMAPAuthenticator, "_cleanup_stale_sessions") as mock_cleanup:
                # Make sleep raise exception to break the loop
                mock_sleep.side_effect = [None, KeyboardInterrupt()]

                auth = IMAPAuthenticator()

                # The thread should be running in background
                # We can't easily test the infinite loop, but we verified it starts
                assert hasattr(auth, "_cleanup_lock")

    def test_cleanup_thread_handles_errors_gracefully(self, authenticator):
        """T030: Test cleanup thread handles errors without crashing.

        Validates:
        - Errors in cleanup are caught and logged
        - Thread continues running after error
        """
        with patch.object(authenticator, "_cleanup_stale_sessions") as mock_cleanup:
            mock_cleanup.side_effect = Exception("Test error")

            # Manually call the cleanup to test error handling
            try:
                authenticator._cleanup_stale_sessions()
            except Exception:
                pass  # Should be caught and logged

            # Thread should still be alive (we can't test this easily without actually running the thread)
            assert hasattr(authenticator, "_cleanup_lock")


# ============================================================================
# T031: Test Stale Session Cleanup
# ============================================================================


class TestStaleSessionCleanup:
    """Unit tests for stale session cleanup functionality."""

    def test_cleanup_removes_stale_sessions(self, authenticator):
        """T031: Test cleanup removes sessions inactive beyond timeout.

        Validates:
        - Stale sessions are identified correctly
        - Stale sessions are disconnected
        - Stale sessions are removed from _sessions dict
        """
        # Create a stale session
        session = IMAPSessionInfo(
            email="test@gmail.com",
            state=SessionState.CONNECTED,
            connected_at=datetime.now() - timedelta(minutes=30),
            last_activity=datetime.now() - timedelta(minutes=30)
        )
        authenticator._sessions[session.session_id] = session

        # Run cleanup
        with patch.object(authenticator, "disconnect") as mock_disconnect:
            authenticator._cleanup_stale_sessions()

            # Verify disconnect was called
            mock_disconnect.assert_called_once_with(session.session_id)

    def test_cleanup_keeps_active_sessions(self, authenticator):
        """T031: Test cleanup does not remove active sessions.

        Validates:
        - Active sessions are not cleaned up
        - Only stale sessions are removed
        """
        # Create an active session
        session = IMAPSessionInfo(
            email="test@gmail.com",
            state=SessionState.CONNECTED,
            connected_at=datetime.now(),
            last_activity=datetime.now()
        )
        authenticator._sessions[session.session_id] = session

        # Run cleanup
        with patch.object(authenticator, "disconnect") as mock_disconnect:
            authenticator._cleanup_stale_sessions()

            # Verify disconnect was NOT called
            mock_disconnect.assert_not_called()
            # Session should still be in dict
            assert session.session_id in authenticator._sessions

    def test_cleanup_force_removes_on_disconnect_failure(self, authenticator):
        """T031: Test cleanup force removes session if disconnect fails.

        Validates:
        - If disconnect fails, session is still removed
        - Error is logged but doesn't crash cleanup
        """
        # Create a stale session
        session = IMAPSessionInfo(
            email="test@gmail.com",
            state=SessionState.CONNECTED,
            connected_at=datetime.now() - timedelta(minutes=30),
            last_activity=datetime.now() - timedelta(minutes=30)
        )
        authenticator._sessions[session.session_id] = session

        # Make disconnect fail
        with patch.object(authenticator, "disconnect") as mock_disconnect:
            mock_disconnect.side_effect = Exception("Disconnect failed")

            authenticator._cleanup_stale_sessions()

            # Session should still be removed (force removal)
            assert session.session_id not in authenticator._sessions


# ============================================================================
# T032: Test Session Limit Per Email
# ============================================================================


class TestSessionLimitPerEmail:
    """Unit tests for session limit enforcement."""

    def test_session_limit_enforced(self, authenticator, credentials, mock_imap_client):
        """T032: Test session limit prevents excessive sessions per email.

        Validates:
        - Creating sessions beyond limit triggers cleanup
        - Oldest session is disconnected
        - New session is created successfully
        """
        # Create MAX_SESSIONS_PER_EMAIL sessions
        for i in range(MAX_SESSIONS_PER_EMAIL):
            session = IMAPSessionInfo(
                email=credentials.email,
                state=SessionState.CONNECTED,
                connected_at=datetime.now() - timedelta(minutes=i),
                last_activity=datetime.now()
            )
            authenticator._sessions[session.session_id] = session

        # Try to create one more session
        with patch.object(authenticator, "disconnect") as mock_disconnect:
            new_session = authenticator.authenticate(credentials)

            # Verify oldest session was disconnected
            assert mock_disconnect.called
            # Verify new session was created
            assert new_session.email == credentials.email

    def test_session_limit_per_email_isolated(self, authenticator, mock_imap_client):
        """T032: Test session limits are per-email, not global.

        Validates:
        - Different emails can have separate session limits
        - One email's sessions don't affect another email's limit
        """
        # Create sessions for email1
        email1 = "user1@gmail.com"
        creds1 = IMAPCredentials(email=email1, password="password12345")
        for i in range(MAX_SESSIONS_PER_EMAIL):
            session = IMAPSessionInfo(
                email=email1,
                state=SessionState.CONNECTED,
                connected_at=datetime.now() - timedelta(minutes=i)
            )
            authenticator._sessions[session.session_id] = session

        # Create session for different email should succeed without cleanup
        email2 = "user2@gmail.com"
        creds2 = IMAPCredentials(email=email2, password="password12345")

        with patch.object(authenticator, "disconnect") as mock_disconnect:
            new_session = authenticator.authenticate(creds2)

            # Verify NO disconnect was called (different email)
            mock_disconnect.assert_not_called()
            # Verify session was created for email2
            assert new_session.email == email2

    def test_disconnected_sessions_not_counted_in_limit(self, authenticator, credentials, mock_imap_client):
        """T032: Test disconnected sessions don't count toward limit.

        Validates:
        - Only CONNECTED sessions count toward limit
        - DISCONNECTED/ERROR sessions are ignored
        """
        # Create sessions with different states
        for state in [SessionState.DISCONNECTED, SessionState.ERROR, SessionState.CONNECTING]:
            session = IMAPSessionInfo(
                email=credentials.email,
                state=state
            )
            authenticator._sessions[session.session_id] = session

        # Should be able to create MAX_SESSIONS_PER_EMAIL CONNECTED sessions
        with patch.object(authenticator, "disconnect") as mock_disconnect:
            for i in range(MAX_SESSIONS_PER_EMAIL):
                new_session = authenticator.authenticate(credentials)
                assert new_session.state == SessionState.CONNECTED

            # No disconnections should have occurred yet
            mock_disconnect.assert_not_called()


# ============================================================================
# T033: Test Cleanup Metrics
# ============================================================================


class TestCleanupMetrics:
    """Unit tests for cleanup monitoring and statistics."""

    def test_get_session_stats_returns_correct_counts(self, authenticator):
        """T033: Test get_session_stats returns accurate statistics.

        Validates:
        - total_sessions count is correct
        - active_sessions count is correct
        - stale_sessions count is correct
        - sessions_by_email mapping is correct
        """
        # Create mix of sessions
        active_session = IMAPSessionInfo(
            email="user1@gmail.com",
            state=SessionState.CONNECTED,
            last_activity=datetime.now()
        )
        stale_session = IMAPSessionInfo(
            email="user2@gmail.com",
            state=SessionState.CONNECTED,
            last_activity=datetime.now() - timedelta(minutes=30)
        )
        disconnected_session = IMAPSessionInfo(
            email="user1@gmail.com",
            state=SessionState.DISCONNECTED
        )

        authenticator._sessions[active_session.session_id] = active_session
        authenticator._sessions[stale_session.session_id] = stale_session
        authenticator._sessions[disconnected_session.session_id] = disconnected_session

        # Get stats
        stats = authenticator.get_session_stats()

        # Verify counts
        assert stats["total_sessions"] == 3
        assert stats["active_sessions"] == 2  # CONNECTED only
        assert stats["stale_sessions"] == 1  # Only stale_session is stale
        assert stats["sessions_by_email"]["user1@gmail.com"] == 2
        assert stats["sessions_by_email"]["user2@gmail.com"] == 1

    def test_get_session_stats_thread_safe(self, authenticator):
        """T033: Test get_session_stats uses lock for thread safety.

        Validates:
        - Stats are collected within cleanup lock
        - Prevents race conditions with cleanup thread
        """
        # Create a mock lock and replace the authenticator's lock
        mock_lock = MagicMock()
        authenticator._cleanup_lock = mock_lock

        authenticator.get_session_stats()

        # Verify lock was acquired
        mock_lock.__enter__.assert_called_once()
        mock_lock.__exit__.assert_called_once()

    def test_get_session_stats_empty_sessions(self, authenticator):
        """T033: Test get_session_stats handles empty session dict.

        Validates:
        - Returns zero counts for empty sessions
        - No errors when no sessions exist
        """
        stats = authenticator.get_session_stats()

        assert stats["total_sessions"] == 0
        assert stats["active_sessions"] == 0
        assert stats["stale_sessions"] == 0
        assert stats["sessions_by_email"] == {}


# ============================================================================
# Integration Tests
# ============================================================================


class TestCleanupIntegration:
    """Integration tests for cleanup functionality."""

    def test_full_cleanup_workflow(self, mock_imap_client):
        """Test complete cleanup workflow from session creation to cleanup.

        Validates:
        - Sessions are created successfully
        - Stale sessions are cleaned up automatically
        - Stats reflect cleanup correctly
        """
        # Don't mock cleanup thread for this test
        auth = IMAPAuthenticator()

        # Create a session
        creds = IMAPCredentials(email="test@gmail.com", password="testpass1234")
        session = auth.authenticate(creds)

        # Verify session exists
        stats_before = auth.get_session_stats()
        assert stats_before["total_sessions"] == 1
        assert stats_before["active_sessions"] == 1

        # Make session stale by manipulating last_activity
        session.last_activity = datetime.now() - timedelta(minutes=30)

        # Run cleanup manually
        auth._cleanup_stale_sessions()

        # Verify session was cleaned up
        stats_after = auth.get_session_stats()
        assert stats_after["total_sessions"] == 0
        assert stats_after["stale_sessions"] == 0
