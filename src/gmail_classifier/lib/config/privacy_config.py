"""Privacy and security configuration."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PrivacyConfig:
    """Configuration for privacy and security settings."""

    # Consent settings
    consent_required: bool = True
    consent_message: str = """
    Gmail Classifier Privacy Notice:

    This application will send your email content (subject, body, sender, and metadata)
    to Anthropic's Claude API for classification and summarization purposes.

    - Email content is processed in the cloud by Anthropic
    - According to Anthropic's policy, email content is not stored permanently
    - Only email IDs and metadata are stored locally
    - You can revoke this consent at any time

    Do you consent to this data processing? (yes/no): """

    # Security settings
    auto_fix_permissions: bool = True

    @classmethod
    def from_env(cls) -> "PrivacyConfig":
        """Create config from environment variables."""
        return cls(
            auto_fix_permissions=os.getenv("AUTO_FIX_PERMISSIONS", "true").lower() == "true",
        )

    def validate(self) -> None:
        """Validate configuration."""
        # No validation needed for privacy config currently
        pass
