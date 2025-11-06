"""Claude API configuration."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ClaudeConfig:
    """Configuration for Claude API."""

    # API credentials
    api_key: str | None = None

    # Model settings
    model: str = "claude-3-haiku-20240307"
    max_tokens: int = 500
    temperature: float = 0.0

    # Classification settings
    confidence_threshold: float = 0.5
    top_k_results: int = 3
    batch_size: int = 10

    # Rate limiting
    api_rate_limit: float = 2.0  # calls per second

    @classmethod
    def from_env(cls) -> "ClaudeConfig":
        """Create config from environment variables."""
        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            model=os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307"),
            confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.5")),
            batch_size=int(os.getenv("BATCH_SIZE", "10")),
            api_rate_limit=float(os.getenv("CLAUDE_API_RATE_LIMIT", "2.0")),
        )

    def validate(self) -> None:
        """Validate configuration."""
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError(
                f"Confidence threshold must be 0.0-1.0, got {self.confidence_threshold}"
            )

        if self.batch_size <= 0:
            raise ValueError("Batch size must be positive")

        if self.top_k_results <= 0:
            raise ValueError("Top K results must be positive")

        if self.api_rate_limit <= 0:
            raise ValueError("API rate limit must be positive")

        if self.max_tokens <= 0:
            raise ValueError("Max tokens must be positive")

        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError("Temperature must be between 0.0 and 1.0")
