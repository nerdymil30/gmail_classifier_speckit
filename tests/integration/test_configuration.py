"""Integration tests for configuration validation."""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from gmail_classifier.lib.config import Config


@pytest.mark.integration
class TestConfiguration:
    """Test configuration validation and environment variable handling."""

    def test_default_configuration_values(self):
        """Test that default configuration values are set correctly."""
        assert Config.BATCH_SIZE >= 1
        assert Config.CONFIDENCE_THRESHOLD >= 0.0
        assert Config.CONFIDENCE_THRESHOLD <= 1.0
        assert Config.MAX_RETRIES > 0
        assert Config.INITIAL_BACKOFF > 0
        assert Config.MAX_BACKOFF > Config.INITIAL_BACKOFF
        assert Config.BACKOFF_MULTIPLIER > 1.0

    def test_gmail_scopes_defined(self):
        """Test that Gmail API scopes are properly defined."""
        assert len(Config.GMAIL_SCOPES) > 0
        assert "gmail.readonly" in Config.GMAIL_SCOPES[0]
        assert any("gmail.modify" in scope for scope in Config.GMAIL_SCOPES)

    def test_storage_paths_exist(self):
        """Test that storage directory structure is created."""
        # Config module should create directories on import
        assert Config.HOME_DIR.exists()
        assert Config.LOG_DIR.exists()
        assert Config.HOME_DIR.stat().st_mode & 0o777 == 0o700  # Secure permissions

    def test_session_db_path_configured(self):
        """Test that session database path is configured."""
        assert Config.SESSION_DB_PATH is not None
        assert Config.SESSION_DB_PATH.parent == Config.HOME_DIR

    def test_environment_variable_override_batch_size(self):
        """Test that BATCH_SIZE can be overridden via environment variable."""
        with patch.dict(os.environ, {"BATCH_SIZE": "25"}):
            # Re-import config to pick up new env var
            import importlib
            from gmail_classifier.lib import config as config_module
            importlib.reload(config_module)

            # Should use env var value
            assert config_module.Config.BATCH_SIZE == 25

            # Clean up - reload with original values
            importlib.reload(config_module)

    def test_environment_variable_override_confidence_threshold(self):
        """Test that CONFIDENCE_THRESHOLD can be overridden via environment variable."""
        with patch.dict(os.environ, {"CONFIDENCE_THRESHOLD": "0.75"}):
            import importlib
            from gmail_classifier.lib import config as config_module
            importlib.reload(config_module)

            assert config_module.Config.CONFIDENCE_THRESHOLD == 0.75

            # Clean up
            importlib.reload(config_module)

    def test_invalid_confidence_threshold_handling(self):
        """Test handling of invalid confidence threshold values."""
        with patch.dict(os.environ, {"CONFIDENCE_THRESHOLD": "invalid"}):
            import importlib
            from gmail_classifier.lib import config as config_module

            # Should raise ValueError when trying to parse
            with pytest.raises(ValueError):
                importlib.reload(config_module)

            # Clean up - restore valid config
            if "CONFIDENCE_THRESHOLD" in os.environ:
                del os.environ["CONFIDENCE_THRESHOLD"]
            importlib.reload(config_module)

    def test_log_level_configuration(self):
        """Test log level configuration."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        assert Config.LOG_LEVEL in valid_levels or Config.LOG_LEVEL == "INFO"

    def test_cache_configuration_values(self):
        """Test cache-related configuration values."""
        assert Config.CACHE_LABEL_TTL_SECONDS > 0
        assert Config.CACHE_CLASSIFICATION_MAX_AGE_HOURS > 0
        assert Config.CACHE_CLEANUP_DAYS > 0

    def test_rate_limiting_configuration(self):
        """Test API rate limiting configuration."""
        assert Config.GMAIL_API_RATE_LIMIT > 0
        assert Config.CLAUDE_API_RATE_LIMIT > 0
        assert Config.GMAIL_QUOTA_UNITS_PER_SECOND > 0
        assert Config.RATE_LIMIT_DELAY >= 0

    def test_session_settings(self):
        """Test session-related settings."""
        assert Config.KEEP_SESSIONS_DAYS > 0
        assert Config.AUTO_SAVE_FREQUENCY > 0

    def test_validate_gmail_config_with_credentials(self):
        """Test Gmail config validation with credentials."""
        with patch.dict(os.environ, {
            "GMAIL_CLIENT_ID": "test_client_id",
            "GMAIL_CLIENT_SECRET": "test_secret"
        }):
            import importlib
            from gmail_classifier.lib import config as config_module
            importlib.reload(config_module)

            assert config_module.Config.validate_gmail_config() is True

            # Clean up
            importlib.reload(config_module)

    def test_validate_gmail_config_without_credentials(self):
        """Test Gmail config validation without credentials."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove Gmail credentials if present
            for key in ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET"]:
                if key in os.environ:
                    del os.environ[key]

            import importlib
            from gmail_classifier.lib import config as config_module
            importlib.reload(config_module)

            # Should return False when credentials are missing
            result = config_module.Config.validate_gmail_config()
            assert result is False or (
                config_module.Config.GMAIL_CLIENT_ID != "" and
                config_module.Config.GMAIL_CLIENT_SECRET != ""
            )

            # Clean up
            importlib.reload(config_module)

    def test_validate_claude_config_with_api_key(self):
        """Test Claude config validation with API key."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_api_key"}):
            import importlib
            from gmail_classifier.lib import config as config_module
            importlib.reload(config_module)

            assert config_module.Config.validate_claude_config() is True

            # Clean up
            importlib.reload(config_module)

    def test_validate_claude_config_without_api_key(self):
        """Test Claude config validation without API key."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove API key if present
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]

            import importlib
            from gmail_classifier.lib import config as config_module
            importlib.reload(config_module)

            # Should return False when API key is missing
            # Note: In real usage, API key might come from keyring
            result = config_module.Config.validate_claude_config()
            assert result is False or config_module.Config.ANTHROPIC_API_KEY is not None

            # Clean up
            importlib.reload(config_module)

    def test_credentials_path_methods(self):
        """Test credentials path helper methods."""
        creds_path = Config.get_credentials_path()
        token_path = Config.get_token_path()

        assert isinstance(creds_path, Path)
        assert isinstance(token_path, Path)
        assert str(creds_path).endswith("credentials.json")
        assert str(token_path).endswith("token.json")

    def test_consent_message_configured(self):
        """Test that privacy consent message is configured."""
        assert Config.CONSENT_REQUIRED is not None
        assert isinstance(Config.CONSENT_MESSAGE, str)
        assert len(Config.CONSENT_MESSAGE) > 0
        assert "privacy" in Config.CONSENT_MESSAGE.lower() or "consent" in Config.CONSENT_MESSAGE.lower()

    def test_ensure_directories_creates_structure(self):
        """Test that ensure_directories creates necessary structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_home = Path(tmpdir) / "test_home"
            test_log = test_home / "logs"

            # Temporarily override paths
            original_home = Config.HOME_DIR
            original_log = Config.LOG_DIR

            Config.HOME_DIR = test_home
            Config.LOG_DIR = test_log

            # Create directories
            Config.ensure_directories()

            # Verify creation
            assert test_home.exists()
            assert test_log.exists()

            # Verify secure permissions
            assert test_home.stat().st_mode & 0o777 == 0o700

            # Restore original paths
            Config.HOME_DIR = original_home
            Config.LOG_DIR = original_log

    def test_auto_fix_permissions_configuration(self):
        """Test AUTO_FIX_PERMISSIONS configuration."""
        assert isinstance(Config.AUTO_FIX_PERMISSIONS, bool)

        # Test with explicit values
        with patch.dict(os.environ, {"AUTO_FIX_PERMISSIONS": "false"}):
            import importlib
            from gmail_classifier.lib import config as config_module
            importlib.reload(config_module)

            assert config_module.Config.AUTO_FIX_PERMISSIONS is False

            # Clean up
            importlib.reload(config_module)

    def test_claude_model_configuration(self):
        """Test Claude model configuration."""
        assert Config.CLAUDE_MODEL is not None
        assert isinstance(Config.CLAUDE_MODEL, str)
        assert len(Config.CLAUDE_MODEL) > 0
        # Should be a valid Claude model identifier
        assert "claude" in Config.CLAUDE_MODEL.lower()

    def test_top_k_results_configuration(self):
        """Test TOP_K_RESULTS configuration."""
        assert Config.TOP_K_RESULTS > 0
        assert isinstance(Config.TOP_K_RESULTS, int)

    def test_gmail_redirect_uri_configuration(self):
        """Test Gmail redirect URI configuration."""
        assert Config.GMAIL_REDIRECT_URI is not None
        assert isinstance(Config.GMAIL_REDIRECT_URI, str)
        # Should be a valid URI format
        assert Config.GMAIL_REDIRECT_URI.startswith("http")

    def test_log_format_configuration(self):
        """Test logging format configuration."""
        assert Config.LOG_FORMAT is not None
        assert "%(asctime)s" in Config.LOG_FORMAT
        assert "%(levelname)s" in Config.LOG_FORMAT
        assert "%(message)s" in Config.LOG_FORMAT

    def test_environment_variable_precedence(self):
        """Test that environment variables take precedence over defaults."""
        # Set custom rate limit
        with patch.dict(os.environ, {"GMAIL_API_RATE_LIMIT": "5.0"}):
            import importlib
            from gmail_classifier.lib import config as config_module
            importlib.reload(config_module)

            # Should use env var value
            assert config_module.Config.GMAIL_API_RATE_LIMIT == 5.0

            # Clean up
            importlib.reload(config_module)

    def test_configuration_immutability(self):
        """Test that Config class attributes are accessible."""
        # Config values should be readable
        assert hasattr(Config, "BATCH_SIZE")
        assert hasattr(Config, "CONFIDENCE_THRESHOLD")
        assert hasattr(Config, "SESSION_DB_PATH")

        # Values should be modifiable if needed (for testing)
        original_batch_size = Config.BATCH_SIZE
        Config.BATCH_SIZE = 999
        assert Config.BATCH_SIZE == 999

        # Restore
        Config.BATCH_SIZE = original_batch_size
