"""Authentication module for Gmail and Claude."""

from gmail_classifier.auth.gmail_auth import (
    GmailAuthenticator,
    get_gmail_credentials,
)
from gmail_classifier.auth.claude_auth import (
    setup_claude_api_key,
    get_claude_api_key,
    validate_claude_api_key,
    delete_claude_api_key,
)
from gmail_classifier.auth.protocols import (
    IMAPAuthProtocol,
    IMAPClientProtocol,
)

__all__ = [
    # Gmail authentication
    "GmailAuthenticator",
    "get_gmail_credentials",
    # Claude authentication
    "setup_claude_api_key",
    "get_claude_api_key",
    "validate_claude_api_key",
    "delete_claude_api_key",
    # IMAP protocols
    "IMAPAuthProtocol",
    "IMAPClientProtocol",
]
