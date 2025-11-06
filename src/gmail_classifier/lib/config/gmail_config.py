"""Gmail API configuration."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GmailConfig:
    """Configuration for Gmail API."""

    # OAuth Scopes
    scopes: list[str] = field(default_factory=lambda: [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
    ])

    # Credentials (from environment)
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8080/"

    # Rate limiting
    quota_units_per_second: int = 250
    api_rate_limit: float = 10.0  # calls per second

    # Retry settings
    max_retries: int = 5
    initial_backoff: float = 1.0  # seconds
    max_backoff: float = 60.0  # seconds
    backoff_multiplier: float = 2.0

    @classmethod
    def from_env(cls) -> "GmailConfig":
        """Create config from environment variables."""
        return cls(
            client_id=os.getenv("GMAIL_CLIENT_ID", ""),
            client_secret=os.getenv("GMAIL_CLIENT_SECRET", ""),
            redirect_uri=os.getenv("GMAIL_REDIRECT_URI", "http://localhost:8080/"),
            api_rate_limit=float(os.getenv("GMAIL_API_RATE_LIMIT", "10.0")),
        )

    def validate(self) -> None:
        """Validate configuration."""
        if not self.scopes:
            raise ValueError("Gmail scopes cannot be empty")

        if self.quota_units_per_second <= 0:
            raise ValueError("Quota units per second must be positive")

        if not 0 < self.api_rate_limit <= self.quota_units_per_second:
            raise ValueError(
                f"API rate limit ({self.api_rate_limit}) must be between 0 "
                f"and quota limit ({self.quota_units_per_second})"
            )

        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")

        if self.initial_backoff <= 0 or self.max_backoff <= 0:
            raise ValueError("Backoff delays must be positive")

        if self.backoff_multiplier <= 1.0:
            raise ValueError("Backoff multiplier must be greater than 1.0")
