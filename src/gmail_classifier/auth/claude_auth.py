"""Claude API authentication and key management."""

import os
import logging
from typing import Optional

import anthropic
import keyring

logger = logging.getLogger(__name__)

# Keyring configuration
KEYRING_SERVICE = "gmail_classifier"
KEYRING_KEY = "anthropic_api_key"


def setup_claude_api_key(api_key: str) -> None:
    """Store Claude API key in system keyring.

    Args:
        api_key: Anthropic API key (starts with 'sk-ant-')

    Raises:
        ValueError: If API key format is invalid
    """
    if not api_key or not api_key.startswith("sk-ant-"):
        raise ValueError("Invalid Claude API key format")

    # Validate key works
    if not validate_claude_api_key(api_key):
        raise ValueError("Claude API key validation failed")

    # Store in keyring
    keyring.set_password(KEYRING_SERVICE, KEYRING_KEY, api_key)
    logger.info("Claude API key stored successfully")


def get_claude_api_key() -> Optional[str]:
    """Retrieve Claude API key from keyring or environment.

    Returns:
        API key if found, None otherwise

    Priority:
        1. Environment variable (ANTHROPIC_API_KEY)
        2. System keyring
    """
    # Try environment variable first
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        logger.debug("Using Claude API key from environment")
        return api_key

    # Try keyring
    api_key = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY)
    if api_key:
        logger.debug("Using Claude API key from keyring")
        return api_key

    logger.warning("No Claude API key found in environment or keyring")
    return None


def validate_claude_api_key(api_key: str) -> bool:
    """Validate Claude API key by making a test request.

    Args:
        api_key: API key to validate

    Returns:
        True if key is valid, False otherwise
    """
    try:
        client = anthropic.Anthropic(api_key=api_key)

        # Make minimal test request
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}],
        )

        logger.debug("Claude API key validation successful")
        return True

    except anthropic.AuthenticationError:
        logger.error("Claude API key authentication failed")
        return False
    except Exception as e:
        logger.error(f"Claude API key validation error: {e}")
        return False


def delete_claude_api_key() -> None:
    """Remove Claude API key from keyring."""
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_KEY)
        logger.info("Claude API key removed from keyring")
    except keyring.errors.PasswordDeleteError:
        logger.warning("No Claude API key found in keyring")
