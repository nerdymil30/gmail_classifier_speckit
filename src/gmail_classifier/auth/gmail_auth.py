"""Gmail OAuth2 authentication flow."""

import os
from pathlib import Path
from typing import Optional

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from gmail_classifier.lib.config import Config
from gmail_classifier.lib.logger import get_logger

logger = get_logger(__name__)


class GmailAuthenticator:
    """Handle Gmail OAuth2 authentication with secure credential storage."""

    KEYRING_SERVICE = "gmail_classifier"
    KEYRING_USERNAME = "gmail_refresh_token"

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        scopes: Optional[list[str]] = None,
    ):
        """
        Initialize Gmail authenticator.

        Args:
            credentials_path: Path to credentials.json from Google Cloud Console
            scopes: Gmail API scopes to request
        """
        self.credentials_path = credentials_path or Config.get_credentials_path()
        self.scopes = scopes or Config.GMAIL_SCOPES
        self.creds: Optional[Credentials] = None

    def authenticate(self, force_reauth: bool = False) -> Credentials:
        """
        Authenticate with Gmail API using OAuth2.

        Args:
            force_reauth: Force re-authentication even if token exists

        Returns:
            Valid credentials object

        Raises:
            FileNotFoundError: If credentials.json not found
            Exception: If authentication fails
        """
        # Check if credentials file exists
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Credentials file not found: {self.credentials_path}\n"
                "Please download credentials.json from Google Cloud Console:\n"
                "1. Go to https://console.cloud.google.com/\n"
                "2. Navigate to APIs & Services > Credentials\n"
                "3. Create OAuth 2.0 Client ID (Desktop app)\n"
                "4. Download JSON and save as credentials.json"
            )

        # Try to load existing credentials from keyring
        if not force_reauth:
            self.creds = self._load_credentials_from_keyring()

        # Refresh credentials if expired
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                logger.info("Refreshing expired Gmail credentials")
                self.creds.refresh(Request())
                self._save_credentials_to_keyring(self.creds)
                logger.info("Gmail credentials refreshed successfully")
            except Exception as e:
                logger.warning(f"Failed to refresh credentials: {e}")
                self.creds = None

        # Perform new OAuth2 flow if no valid credentials
        if not self.creds or not self.creds.valid or force_reauth:
            logger.info("Starting Gmail OAuth2 authentication flow")
            self.creds = self._perform_oauth_flow()
            self._save_credentials_to_keyring(self.creds)
            logger.info("Gmail authentication completed successfully")

        return self.creds

    def _perform_oauth_flow(self) -> Credentials:
        """
        Perform OAuth2 authentication flow.

        Returns:
            Valid credentials object
        """
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_path),
            scopes=self.scopes,
        )

        # Run local server to handle OAuth callback
        creds = flow.run_local_server(
            port=8080,
            prompt="consent",
            success_message="Authentication successful! You can close this window.",
        )

        return creds

    def _load_credentials_from_keyring(self) -> Optional[Credentials]:
        """
        Load credentials from system keyring.

        Returns:
            Credentials object if found, None otherwise
        """
        try:
            refresh_token = keyring.get_password(self.KEYRING_SERVICE, self.KEYRING_USERNAME)

            if not refresh_token:
                logger.debug("No refresh token found in keyring")
                return None

            # Reconstruct credentials from refresh token
            # Note: This requires client_id and client_secret from credentials.json
            import json

            with open(self.credentials_path) as f:
                creds_data = json.load(f)
                client_config = creds_data.get("installed") or creds_data.get("web")

            creds = Credentials(
                token=None,  # Will be refreshed
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_config["client_id"],
                client_secret=client_config["client_secret"],
                scopes=self.scopes,
            )

            logger.debug("Loaded credentials from keyring")
            return creds

        except Exception as e:
            logger.warning(f"Failed to load credentials from keyring: {e}")
            return None

    def _save_credentials_to_keyring(self, creds: Credentials) -> None:
        """
        Save credentials to system keyring.

        Args:
            creds: Credentials object to save
        """
        try:
            if creds.refresh_token:
                keyring.set_password(
                    self.KEYRING_SERVICE,
                    self.KEYRING_USERNAME,
                    creds.refresh_token,
                )
                logger.debug("Saved refresh token to keyring")
            else:
                logger.warning("No refresh token available to save")

        except Exception as e:
            logger.error(f"Failed to save credentials to keyring: {e}")

    def revoke_credentials(self) -> None:
        """Revoke and delete stored credentials."""
        try:
            # Delete from keyring
            keyring.delete_password(self.KEYRING_SERVICE, self.KEYRING_USERNAME)
            logger.info("Revoked Gmail credentials from keyring")

        except Exception as e:
            logger.warning(f"Failed to revoke credentials: {e}")

    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated.

        Returns:
            True if valid credentials exist
        """
        try:
            creds = self._load_credentials_from_keyring()
            return creds is not None and creds.valid
        except Exception:
            return False


def get_gmail_credentials(force_reauth: bool = False) -> Credentials:
    """
    Convenience function to get Gmail credentials.

    Args:
        force_reauth: Force re-authentication

    Returns:
        Valid Gmail API credentials
    """
    authenticator = GmailAuthenticator()
    return authenticator.authenticate(force_reauth=force_reauth)


def setup_claude_api_key(api_key: str) -> None:
    """
    Store Claude API key in system keyring.

    Args:
        api_key: Anthropic API key
    """
    keyring.set_password("gmail_classifier", "anthropic_api_key", api_key)
    logger.info("Claude API key stored securely in keyring")


def get_claude_api_key() -> Optional[str]:
    """
    Retrieve Claude API key from keyring or environment.

    Returns:
        API key if found, None otherwise
    """
    # Try keyring first
    api_key = keyring.get_password("gmail_classifier", "anthropic_api_key")

    # Fallback to environment variable
    if not api_key:
        api_key = os.getenv("ANTHROPIC_API_KEY")

    return api_key


def validate_claude_api_key(api_key: str) -> bool:
    """
    Validate Claude API key by making a test request.

    Args:
        api_key: API key to validate

    Returns:
        True if key is valid
    """
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        # Make a minimal test request
        client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}],
        )

        return True

    except Exception as e:
        logger.error(f"Claude API key validation failed: {e}")
        return False
