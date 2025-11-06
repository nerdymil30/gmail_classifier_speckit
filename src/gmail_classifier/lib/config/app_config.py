"""Application-level configuration."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """Configuration for application settings."""

    # Session settings
    keep_sessions_days: int = 30

    # Rate limiting
    rate_limit_delay: float = 0.1  # seconds between requests

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_date_format: str = "%Y-%m-%d %H:%M:%S"

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create config from environment variables."""
        return cls(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    def validate(self) -> None:
        """Validate configuration."""
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(
                f"Log level must be one of {valid_log_levels}, got {self.log_level}"
            )

        if self.keep_sessions_days <= 0:
            raise ValueError("Keep sessions days must be positive")

        if self.rate_limit_delay < 0:
            raise ValueError("Rate limit delay must be non-negative")
