"""Storage and file path configuration."""

import os
from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class StorageConfig:
    """Configuration for file storage."""

    # Base directory
    home_dir: Path

    # Subdirectories (derived from home_dir)
    log_dir: Path

    # Database paths
    session_db_path: Path

    # Config file
    config_file: Path

    # OAuth credentials paths (relative paths)
    credentials_path: Path
    token_path: Path

    # Auto-save settings
    auto_save_frequency: int = 50

    @classmethod
    def from_env(cls) -> "StorageConfig":
        """Create config from environment variables."""
        home_dir_str = os.getenv("GMAIL_CLASSIFIER_HOME")
        home_dir = Path(home_dir_str) if home_dir_str else Path.home() / ".gmail_classifier"

        return cls(
            home_dir=home_dir,
            log_dir=home_dir / "logs",
            session_db_path=home_dir / "sessions.db",
            config_file=home_dir / "config.yml",
            credentials_path=Path("credentials.json"),  # Relative path in current directory
            token_path=Path("token.json"),  # Relative path in current directory
            auto_save_frequency=int(os.getenv("AUTO_SAVE_FREQUENCY", "50")),
        )

    def ensure_directories(self) -> None:
        """Create necessary directories with secure permissions."""
        from gmail_classifier.lib.utils import ensure_secure_directory

        ensure_secure_directory(self.home_dir, mode=0o700)
        ensure_secure_directory(self.log_dir, mode=0o700)

    def validate(self) -> None:
        """Validate configuration."""
        if self.auto_save_frequency <= 0:
            raise ValueError("Auto-save frequency must be positive")

    def get_credentials_path(self) -> Path:
        """Get the path to Gmail credentials file."""
        return self.credentials_path

    def get_token_path(self) -> Path:
        """Get the path to OAuth token file."""
        return self.token_path
