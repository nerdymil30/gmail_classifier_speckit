---
status: pending
priority: p3
issue_id: "014"
tags: [code-review, architecture, medium, refactoring, configuration]
dependencies: []
---

# Extract Configuration to Domain-Specific Modules

## Problem Statement

The `Config` class in `lib/config.py` is a 108-line monolithic configuration module mixing concerns from multiple domains (Gmail, Claude, storage, logging, privacy). This makes it hard to find relevant settings and violates the Single Responsibility Principle. As the project grows, this file will become unwieldy.

## Findings

**Discovered by:** architecture-strategist agent during configuration analysis

**Location:** `src/gmail_classifier/lib/config.py` (lines 13-107)

**Current Structure:**
```python
class Config:
    # Gmail API settings (lines 18-23)
    GMAIL_SCOPES = [...]
    GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
    GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")

    # Claude API settings (lines 25-31)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    CLAUDE_MODEL = "claude-3-haiku-20240307"
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))

    # Storage settings (lines 33-40)
    HOME_DIR = Path.home() / ".gmail_classifier"
    LOG_DIR = HOME_DIR / "logs"
    SESSION_DB_PATH = HOME_DIR / "sessions.db"
    CREDENTIALS_PATH = HOME_DIR / "credentials.json"

    # Classification settings (lines 42-51)
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
    MAX_BATCH_SIZE = 50
    AUTO_SAVE_FREQUENCY = 50

    # Rate limiting settings (lines 53-56)
    GMAIL_QUOTA_UNITS_PER_SECOND = 250
    RATE_LIMIT_DELAY = 0.1

    # Logging settings (lines 58-66)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "..."

    # Privacy settings (lines 68-71)
    PII_SANITIZATION_ENABLED = True
    CONSENT_REQUIRED = True
```

**Issues:**
1. Mixed concerns in single file
2. Hard to locate domain-specific settings
3. No validation or type safety
4. Mutable class variables
5. Will grow unmanageably as features added

**Risk Level:** MEDIUM - Maintainability and scalability concern

## Proposed Solutions

### Option 1: Split into Domain Modules (RECOMMENDED)
**Pros:**
- Clear separation by domain
- Easy to locate settings
- Independent evolution
- Better imports (only import what you need)

**Cons:**
- Need to update imports
- More files

**Effort:** Medium (2-3 hours)
**Risk:** Low

**Implementation:**

**New structure:**
```
lib/config/
├── __init__.py          # Re-exports all configs
├── gmail_config.py      # Gmail API settings
├── claude_config.py     # Claude API settings
├── storage_config.py    # Paths and storage
├── app_config.py        # General app settings
└── privacy_config.py    # Privacy and logging
```

**`lib/config/gmail_config.py`:**
```python
"""Gmail API configuration."""

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class GmailConfig:
    """Configuration for Gmail API."""

    # OAuth Scopes
    scopes: list[str] = None

    # Credentials (from environment)
    client_id: str = ""
    client_secret: str = ""

    # Rate limiting
    quota_units_per_second: int = 250
    api_rate_limit: float = 10.0  # calls per second

    # Retry settings
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0

    def __post_init__(self):
        # Set default scopes
        if object.__getattribute__(self, 'scopes') is None:
            object.__setattr__(self, 'scopes', [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.modify",
                "https://www.googleapis.com/auth/gmail.labels",
            ])

    @classmethod
    def from_env(cls) -> "GmailConfig":
        """Create config from environment variables."""
        return cls(
            client_id=os.getenv("GMAIL_CLIENT_ID", ""),
            client_secret=os.getenv("GMAIL_CLIENT_SECRET", ""),
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
```

**`lib/config/claude_config.py`:**
```python
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
    batch_size: int = 10
    max_batch_size: int = 50

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

        if self.batch_size > self.max_batch_size:
            raise ValueError(
                f"Batch size ({self.batch_size}) exceeds maximum ({self.max_batch_size})"
            )
```

**`lib/config/storage_config.py`:**
```python
"""Storage and file path configuration."""

import os
from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class StorageConfig:
    """Configuration for file storage."""

    # Base directory
    home_dir: Path = Path.home() / ".gmail_classifier"

    # Subdirectories
    log_dir: Path = None
    cache_dir: Path = None

    # Database
    session_db_path: Path = None
    cache_db_path: Path = None

    # Credentials
    credentials_path: Path = None

    # Auto-save settings
    auto_save_frequency: int = 50

    def __post_init__(self):
        # Set derived paths
        if object.__getattribute__(self, 'log_dir') is None:
            object.__setattr__(self, 'log_dir', self.home_dir / "logs")

        if object.__getattribute__(self, 'cache_dir') is None:
            object.__setattr__(self, 'cache_dir', self.home_dir / "cache")

        if object.__getattribute__(self, 'session_db_path') is None:
            object.__setattr__(self, 'session_db_path', self.home_dir / "sessions.db")

        if object.__getattribute__(self, 'cache_db_path') is None:
            object.__setattr__(self, 'cache_db_path', self.cache_dir / "classifications.db")

        if object.__getattribute__(self, 'credentials_path') is None:
            object.__setattr__(self, 'credentials_path', self.home_dir / "credentials.json")

    @classmethod
    def from_env(cls) -> "StorageConfig":
        """Create config from environment variables."""
        home_dir_str = os.getenv("GMAIL_CLASSIFIER_HOME")
        home_dir = Path(home_dir_str) if home_dir_str else Path.home() / ".gmail_classifier"

        return cls(
            home_dir=home_dir,
            auto_save_frequency=int(os.getenv("AUTO_SAVE_FREQUENCY", "50"))
        )

    def ensure_directories(self) -> None:
        """Create necessary directories with secure permissions."""
        from gmail_classifier.lib.utils import ensure_secure_directory

        ensure_secure_directory(self.home_dir, mode=0o700)
        ensure_secure_directory(self.log_dir, mode=0o700)
        ensure_secure_directory(self.cache_dir, mode=0o700)

    def validate(self) -> None:
        """Validate configuration."""
        if self.auto_save_frequency <= 0:
            raise ValueError("Auto-save frequency must be positive")
```

**`lib/config/__init__.py`:**
```python
"""Configuration management for Gmail Classifier."""

from gmail_classifier.lib.config.gmail_config import GmailConfig
from gmail_classifier.lib.config.claude_config import ClaudeConfig
from gmail_classifier.lib.config.storage_config import StorageConfig
from gmail_classifier.lib.config.app_config import AppConfig
from gmail_classifier.lib.config.privacy_config import PrivacyConfig

# Load and validate all configs
gmail_config = GmailConfig.from_env()
claude_config = ClaudeConfig.from_env()
storage_config = StorageConfig.from_env()
app_config = AppConfig.from_env()
privacy_config = PrivacyConfig.from_env()

# Validate
gmail_config.validate()
claude_config.validate()
storage_config.validate()
app_config.validate()
privacy_config.validate()

# Ensure directories
storage_config.ensure_directories()

__all__ = [
    "gmail_config",
    "claude_config",
    "storage_config",
    "app_config",
    "privacy_config",
]
```

**Usage:**
```python
# Old
from gmail_classifier.lib.config import Config
scopes = Config.GMAIL_SCOPES

# New (explicit)
from gmail_classifier.lib.config import gmail_config
scopes = gmail_config.scopes

# Or (convenience)
from gmail_classifier.lib import config
scopes = config.gmail_config.scopes
```

### Option 2: Pydantic Settings (Modern Approach)
**Pros:**
- Automatic validation
- Type safety
- Environment variable parsing
- JSON schema generation
- Widely used in modern Python

**Cons:**
- External dependency (pydantic)
- Might be overkill

**Effort:** Medium (2-3 hours)
**Risk:** Low

**Not Recommended Yet** - Save for future if needs grow.

### Option 3: Keep Single Config, Add Validation
**Pros:**
- Minimal changes
- Backward compatible

**Cons:**
- Doesn't solve organization issue
- Still monolithic

**Effort:** Small (30 minutes)
**Risk:** Low

**Not Recommended** - Doesn't address root problem.

## Recommended Action

**Implement Option 1** - Split into domain-specific configuration modules with immutable dataclasses.

**Migration Plan:**
1. Create `lib/config/` directory
2. Create domain-specific config modules
3. Update `__init__.py` with re-exports
4. Update imports across codebase (use find/replace)
5. Remove old `config.py`
6. Run tests

## Technical Details

**Affected Files:**
- `src/gmail_classifier/lib/config.py` (DELETE, replace with directory)
- `src/gmail_classifier/lib/config/` (NEW DIRECTORY)
- All files importing from config (update imports)

**Related Components:**
- All services using configuration
- CLI initialization
- Test fixtures

**Database Changes:** No

**Breaking Changes:**
- Import paths change
- `Config.SETTING` becomes `config_module.setting`

**Backward Compatibility:**
```python
# In lib/config/__init__.py - provide compatibility layer
class Config:
    """Backward compatibility wrapper (deprecated)."""

    @property
    def GMAIL_SCOPES(self):
        return gmail_config.scopes

    # ... other properties for compatibility

# Usage
from gmail_classifier.lib.config import Config  # Still works (deprecated)
```

## Resources

- [Configuration Management Best Practices](https://12factor.net/config)
- [Python Dataclasses](https://docs.python.org/3/library/dataclasses.html)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- Related findings: ARCH-3 in detailed review

## Acceptance Criteria

- [ ] `lib/config/` directory created
- [ ] `gmail_config.py` with GmailConfig dataclass
- [ ] `claude_config.py` with ClaudeConfig dataclass
- [ ] `storage_config.py` with StorageConfig dataclass
- [ ] `app_config.py` with AppConfig dataclass
- [ ] `privacy_config.py` with PrivacyConfig dataclass
- [ ] All configs immutable (frozen=True)
- [ ] `from_env()` class methods for environment loading
- [ ] `validate()` methods for configuration validation
- [ ] `__init__.py` re-exports all configs
- [ ] Old `config.py` removed
- [ ] All imports updated across codebase
- [ ] Unit tests pass
- [ ] Configuration validation tests added

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (architecture-strategist agent)
**Actions:**
- Discovered monolithic configuration during architecture review
- Identified mixed concerns (Gmail, Claude, storage, etc.)
- Noted lack of validation
- Categorized as P3 medium priority (maintainability)

**Learnings:**
- Configuration should be split by domain
- Immutable dataclasses better than class variables
- Validation at startup prevents runtime errors
- Clear organization helps locate settings quickly
