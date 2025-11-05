"""Configuration management for Gmail Classifier."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration settings."""

    # Gmail API Configuration
    GMAIL_SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
    ]
    GMAIL_CLIENT_ID: str = os.getenv("GMAIL_CLIENT_ID", "")
    GMAIL_CLIENT_SECRET: str = os.getenv("GMAIL_CLIENT_SECRET", "")
    GMAIL_REDIRECT_URI: str = os.getenv("GMAIL_REDIRECT_URI", "http://localhost:8080/")

    # Credentials paths
    CREDENTIALS_PATH: str = "credentials.json"
    TOKEN_PATH: str = "token.json"

    # Anthropic Claude API Configuration
    CLAUDE_MODEL: str = "claude-3-haiku-20240307"
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")

    # Classification settings
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
    TOP_K_RESULTS: int = 3
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "10"))

    # Rate limiting and retry settings
    MAX_RETRIES: int = 5
    INITIAL_BACKOFF: float = 1.0  # seconds
    MAX_BACKOFF: float = 60.0  # seconds
    BACKOFF_MULTIPLIER: float = 2.0

    # Gmail API quota settings
    GMAIL_QUOTA_UNITS_PER_SECOND: int = 250
    RATE_LIMIT_DELAY: float = 0.1  # seconds between requests

    # Privacy and consent
    CONSENT_REQUIRED: bool = True
    CONSENT_MESSAGE: str = """
    Gmail Classifier Privacy Notice:

    This application will send your email content (subject, body, sender, and metadata)
    to Anthropic's Claude API for classification and summarization purposes.

    - Email content is processed in the cloud by Anthropic
    - According to Anthropic's policy, email content is not stored permanently
    - Only email IDs and metadata are stored locally
    - You can revoke this consent at any time

    Do you consent to this data processing? (yes/no): """

    # Storage paths
    HOME_DIR: Path = Path.home() / ".gmail_classifier"
    SESSION_DB_PATH: Path = HOME_DIR / "sessions.db"
    LOG_DIR: Path = HOME_DIR / "logs"
    CONFIG_FILE: Path = HOME_DIR / "config.yml"

    # Logging configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

    # Session settings
    KEEP_SESSIONS_DAYS: int = 30
    AUTO_SAVE_FREQUENCY: int = 50  # Save session every N emails

    @classmethod
    def ensure_directories(cls) -> None:
        """Create necessary directories if they don't exist."""
        cls.HOME_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate_gmail_config(cls) -> bool:
        """Validate that Gmail API configuration is present."""
        return bool(cls.GMAIL_CLIENT_ID and cls.GMAIL_CLIENT_SECRET)

    @classmethod
    def validate_claude_config(cls) -> bool:
        """Validate that Claude API configuration is present."""
        # API key can be in env var or keyring
        return cls.ANTHROPIC_API_KEY is not None

    @classmethod
    def get_credentials_path(cls) -> Path:
        """Get the path to Gmail credentials file."""
        return Path(cls.CREDENTIALS_PATH)

    @classmethod
    def get_token_path(cls) -> Path:
        """Get the path to OAuth token file."""
        return Path(cls.TOKEN_PATH)


# Create directories on module import
Config.ensure_directories()
