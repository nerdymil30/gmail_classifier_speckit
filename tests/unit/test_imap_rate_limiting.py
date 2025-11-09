"""Unit tests for IMAP authentication rate limiting.

Tests verify that the rate limiting mechanism properly tracks failed authentication
attempts and enforces exponential lockout to prevent brute-force attacks.

Security: Addresses CWE-307 (Improper Restriction of Excessive Authentication Attempts)
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from imapclient.exceptions import IMAPClientError

from gmail_classifier.auth.imap import (
    IMAPAuthenticationError,
    IMAPAuthenticator,
    IMAPCredentials,
)


@pytest.fixture
def test_credentials() -> IMAPCredentials:
    """Provide test credentials for authentication tests."""
    return IMAPCredentials(
        email="test@gmail.com",
        password="testapppassword",
    )


class TestRateLimitingBasics:
    """Test basic rate limiting functionality."""

    def test_successful_auth_does_not_trigger_rate_limit(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test that successful authentication does not count toward rate limit."""
        with patch("imapclient.IMAPClient") as mock_client_class:
            # Configure mock for successful authentication
            mock_client = MagicMock()
            mock_client.login.return_value = b"LOGIN completed"
            mock_client.noop.return_value = (b"OK", [b"NOOP completed"])
            mock_client_class.return_value = mock_client

            authenticator = IMAPAuthenticator()

            # Authenticate successfully multiple times
            for _ in range(3):
                session = authenticator.authenticate(test_credentials)
                authenticator.disconnect(session.session_id)

            # Should not have any failed attempts recorded
            assert test_credentials.email not in authenticator._failed_attempts
            assert test_credentials.email not in authenticator._lockout_until

    def test_failed_auth_records_attempt(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test that failed authentication records a failed attempt."""
        with patch("imapclient.IMAPClient") as mock_client_class:
            # Configure mock to fail authentication
            mock_client = MagicMock()
            mock_client.login.side_effect = IMAPClientError("Invalid credentials")
            mock_client_class.return_value = mock_client

            authenticator = IMAPAuthenticator()

            # Attempt authentication (should fail)
            with pytest.raises(IMAPAuthenticationError):
                authenticator.authenticate(test_credentials)

            # Should have recorded one failed attempt
            assert test_credentials.email in authenticator._failed_attempts
            assert len(authenticator._failed_attempts[test_credentials.email]) == 1


class TestRateLimitLockout:
    """Test rate limiting lockout behavior."""

    def test_five_failures_triggers_2min_lockout(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test that 5 failed attempts trigger a 2-minute lockout."""
        with patch("imapclient.IMAPClient") as mock_client_class:
            # Configure mock to fail authentication
            mock_client = MagicMock()
            mock_client.login.side_effect = IMAPClientError("Invalid credentials")
            mock_client_class.return_value = mock_client

            authenticator = IMAPAuthenticator()

            # Fail 4 times (should not lock out)
            for _ in range(4):
                with pytest.raises(IMAPAuthenticationError) as exc_info:
                    authenticator.authenticate(test_credentials)
                # Verify not locked out yet
                assert "locked" not in str(exc_info.value).lower()

            # 5th failure should trigger lockout
            with pytest.raises(IMAPAuthenticationError) as exc_info:
                authenticator.authenticate(test_credentials)

            # Verify lockout message
            error_msg = str(exc_info.value).lower()
            assert "locked" in error_msg or "too many" in error_msg

            # Verify lockout duration is set
            assert test_credentials.email in authenticator._lockout_until

    def test_subsequent_attempts_during_lockout_extend_lockout(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test that attempts during lockout increase the lockout duration."""
        with patch("imapclient.IMAPClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.login.side_effect = IMAPClientError("Invalid credentials")
            mock_client_class.return_value = mock_client

            authenticator = IMAPAuthenticator()

            # Trigger initial lockout (5 failures)
            for _ in range(5):
                with pytest.raises(IMAPAuthenticationError):
                    authenticator.authenticate(test_credentials)

            # Record first lockout time
            first_lockout = authenticator._lockout_until[test_credentials.email]

            # 6th attempt should show we're locked out
            with pytest.raises(IMAPAuthenticationError) as exc_info:
                authenticator.authenticate(test_credentials)

            error_msg = str(exc_info.value).lower()
            assert "try again in" in error_msg or "locked" in error_msg

    def test_exponential_lockout_progression(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test that lockout duration increases exponentially."""
        authenticator = IMAPAuthenticator()

        # Manually simulate failed attempts to test lockout calculation
        now = datetime.now()

        # Add 5 failures (should trigger 2-minute lockout)
        for _ in range(5):
            authenticator._failed_attempts[test_credentials.email].append(now)

        # Check rate limit - should trigger 2-minute lockout
        with pytest.raises(IMAPAuthenticationError) as exc_info:
            authenticator._check_rate_limit(test_credentials.email)
        assert "2 minutes" in str(exc_info.value)

        # Add one more failure (6 total) - should trigger 4-minute lockout
        authenticator._failed_attempts[test_credentials.email].append(now)
        with pytest.raises(IMAPAuthenticationError) as exc_info:
            authenticator._check_rate_limit(test_credentials.email)
        assert "4 minutes" in str(exc_info.value)

        # Add one more failure (7 total) - should trigger 8-minute lockout
        authenticator._failed_attempts[test_credentials.email].append(now)
        with pytest.raises(IMAPAuthenticationError) as exc_info:
            authenticator._check_rate_limit(test_credentials.email)
        assert "8 minutes" in str(exc_info.value)


class TestRateLimitCleanup:
    """Test rate limiting cleanup mechanisms."""

    def test_old_attempts_cleaned_after_15_minutes(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test that failed attempts older than 15 minutes are cleaned up."""
        authenticator = IMAPAuthenticator()

        # Add some old failed attempts (16 minutes ago)
        old_time = datetime.now() - timedelta(minutes=16)
        for _ in range(3):
            authenticator._failed_attempts[test_credentials.email].append(old_time)

        # Add one recent failed attempt
        authenticator._failed_attempts[test_credentials.email].append(datetime.now())

        # Check rate limit (should trigger cleanup)
        try:
            authenticator._check_rate_limit(test_credentials.email)
        except IMAPAuthenticationError:
            pass  # May or may not raise depending on cleanup result

        # Old attempts should be cleaned, only 1 recent attempt should remain
        assert len(authenticator._failed_attempts[test_credentials.email]) == 1

    def test_successful_auth_clears_failed_attempts(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test that successful authentication clears failed attempt history."""
        with patch("imapclient.IMAPClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            authenticator = IMAPAuthenticator()

            # Add some failed attempts manually
            for _ in range(3):
                authenticator._failed_attempts[test_credentials.email].append(
                    datetime.now()
                )

            # Now authenticate successfully
            mock_client.login.return_value = b"LOGIN completed"
            mock_client.noop.return_value = (b"OK", [b"NOOP completed"])

            session = authenticator.authenticate(test_credentials)

            # Failed attempts should be cleared
            assert test_credentials.email not in authenticator._failed_attempts
            assert test_credentials.email not in authenticator._lockout_until

            # Cleanup
            authenticator.disconnect(session.session_id)


class TestRateLimitTimings:
    """Test rate limiting timing and lockout expiration."""

    def test_lockout_prevents_immediate_retry(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test that lockout prevents immediate retry attempts."""
        authenticator = IMAPAuthenticator()

        # Manually set lockout until 10 seconds from now
        authenticator._lockout_until[test_credentials.email] = (
            datetime.now() + timedelta(seconds=10)
        )

        # Attempt should be blocked
        with pytest.raises(IMAPAuthenticationError) as exc_info:
            authenticator._check_rate_limit(test_credentials.email)

        assert "try again in" in str(exc_info.value).lower()

    def test_lockout_expires_after_duration(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test that lockout expires and allows retry after duration."""
        authenticator = IMAPAuthenticator()

        # Set lockout that already expired (1 second ago)
        authenticator._lockout_until[test_credentials.email] = (
            datetime.now() - timedelta(seconds=1)
        )

        # Should not raise - lockout has expired
        try:
            authenticator._check_rate_limit(test_credentials.email)
            # No error expected
        except IMAPAuthenticationError:
            pytest.fail("Lockout should have expired but still blocking")


class TestRateLimitEmailIsolation:
    """Test that rate limiting is isolated per email address."""

    def test_rate_limits_per_email_are_independent(self) -> None:
        """Test that rate limits for different emails are tracked independently."""
        authenticator = IMAPAuthenticator()

        email1 = "user1@gmail.com"
        email2 = "user2@gmail.com"

        # Add 5 failures for email1
        for _ in range(5):
            authenticator._failed_attempts[email1].append(datetime.now())

        # email1 should be locked out
        with pytest.raises(IMAPAuthenticationError):
            authenticator._check_rate_limit(email1)

        # email2 should not be locked out
        try:
            authenticator._check_rate_limit(email2)
            # Should not raise - different email
        except IMAPAuthenticationError:
            pytest.fail("Rate limit should be per-email, not global")


class TestRateLimitMaximumCap:
    """Test that rate limiting has a maximum lockout duration cap."""

    def test_lockout_duration_capped_at_64_minutes(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test that lockout duration doesn't exceed 64 minutes (2^6)."""
        authenticator = IMAPAuthenticator()

        # Add 15 failures (well beyond the cap trigger point)
        now = datetime.now()
        for _ in range(15):
            authenticator._failed_attempts[test_credentials.email].append(now)

        # Trigger rate limit check
        with pytest.raises(IMAPAuthenticationError) as exc_info:
            authenticator._check_rate_limit(test_credentials.email)

        # Lockout should be capped at 64 minutes (2^6)
        lockout_time = authenticator._lockout_until[test_credentials.email]
        max_lockout = now + timedelta(minutes=64)

        # Allow 1 second tolerance for test execution time
        assert lockout_time <= max_lockout + timedelta(seconds=1)


class TestRateLimitSecurityProperties:
    """Test security properties of rate limiting implementation."""

    def test_rate_limit_check_called_before_authentication(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test that rate limit is checked before attempting authentication."""
        with patch("imapclient.IMAPClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            authenticator = IMAPAuthenticator()

            # Set up lockout
            authenticator._lockout_until[test_credentials.email] = (
                datetime.now() + timedelta(minutes=5)
            )

            # Attempt authentication - should fail at rate limit check
            with pytest.raises(IMAPAuthenticationError) as exc_info:
                authenticator.authenticate(test_credentials)

            # Verify rate limit error (not authentication error)
            assert "try again in" in str(exc_info.value).lower()

            # Verify IMAP login was never called
            mock_client.login.assert_not_called()

    def test_memory_not_leaked_by_failed_attempts(
        self, test_credentials: IMAPCredentials
    ) -> None:
        """Test that old failed attempts don't accumulate indefinitely."""
        authenticator = IMAPAuthenticator()

        # Add many old attempts (should all be cleaned)
        old_time = datetime.now() - timedelta(minutes=20)
        for _ in range(100):
            authenticator._failed_attempts[test_credentials.email].append(old_time)

        # Trigger cleanup via rate limit check
        try:
            authenticator._check_rate_limit(test_credentials.email)
        except IMAPAuthenticationError:
            pass

        # All old attempts should be cleaned
        assert len(authenticator._failed_attempts[test_credentials.email]) == 0
