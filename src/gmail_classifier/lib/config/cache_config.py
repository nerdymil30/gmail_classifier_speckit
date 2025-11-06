"""Cache configuration."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CacheConfig:
    """Configuration for caching."""

    # Label cache settings (in-memory)
    label_ttl_seconds: int = 3600  # 1 hour

    # Classification cache settings (SQLite persistent)
    classification_max_age_hours: int = 48  # 2 days
    classification_cleanup_days: int = 30  # Keep 30 days

    @classmethod
    def from_env(cls) -> "CacheConfig":
        """Create config from environment variables."""
        return cls(
            label_ttl_seconds=int(os.getenv("CACHE_LABEL_TTL_SECONDS", "3600")),
            classification_max_age_hours=int(os.getenv("CACHE_CLASSIFICATION_MAX_AGE_HOURS", "48")),
            classification_cleanup_days=int(os.getenv("CACHE_CLEANUP_DAYS", "30")),
        )

    def validate(self) -> None:
        """Validate configuration."""
        if self.label_ttl_seconds <= 0:
            raise ValueError("Label TTL must be positive")

        if self.classification_max_age_hours <= 0:
            raise ValueError("Classification max age must be positive")

        if self.classification_cleanup_days <= 0:
            raise ValueError("Classification cleanup days must be positive")
