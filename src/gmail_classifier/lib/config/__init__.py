"""Configuration management for Gmail Classifier."""

from dotenv import load_dotenv

from gmail_classifier.lib.config.gmail_config import GmailConfig
from gmail_classifier.lib.config.claude_config import ClaudeConfig
from gmail_classifier.lib.config.storage_config import StorageConfig
from gmail_classifier.lib.config.app_config import AppConfig
from gmail_classifier.lib.config.privacy_config import PrivacyConfig
from gmail_classifier.lib.config.cache_config import CacheConfig

# Load environment variables from .env file
load_dotenv()

# Load and validate all configs
gmail_config = GmailConfig.from_env()
claude_config = ClaudeConfig.from_env()
storage_config = StorageConfig.from_env()
app_config = AppConfig.from_env()
privacy_config = PrivacyConfig.from_env()
cache_config = CacheConfig.from_env()

# Validate
gmail_config.validate()
claude_config.validate()
storage_config.validate()
app_config.validate()
privacy_config.validate()
cache_config.validate()

# Ensure directories
storage_config.ensure_directories()

__all__ = [
    "gmail_config",
    "claude_config",
    "storage_config",
    "app_config",
    "privacy_config",
    "cache_config",
    "GmailConfig",
    "ClaudeConfig",
    "StorageConfig",
    "AppConfig",
    "PrivacyConfig",
    "CacheConfig",
]
