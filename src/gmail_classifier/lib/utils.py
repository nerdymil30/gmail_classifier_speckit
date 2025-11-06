"""Utility functions for Gmail Classifier."""

import os
import random
import stat
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from googleapiclient.errors import HttpError

from gmail_classifier.lib.config import gmail_config, privacy_config
from gmail_classifier.lib.logger import get_logger

logger = get_logger(__name__)

# Type variable for generic function return type
T = TypeVar("T")


def retry_with_exponential_backoff(
    max_retries: Optional[int] = None,
    initial_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    multiplier: Optional[float] = None,
    jitter: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: gmail_config.max_retries)
        initial_delay: Initial delay in seconds (default: gmail_config.initial_backoff)
        max_delay: Maximum delay in seconds (default: gmail_config.max_backoff)
        multiplier: Backoff multiplier (default: gmail_config.backoff_multiplier)
        jitter: Add random jitter to delays (default: True)

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_exponential_backoff(max_retries=3)
        def fetch_data():
            return api.get_data()
    """
    _max_retries = max_retries or gmail_config.max_retries
    _initial_delay = initial_delay or gmail_config.initial_backoff
    _max_delay = max_delay or gmail_config.max_backoff
    _multiplier = multiplier or gmail_config.backoff_multiplier

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = _initial_delay
            last_exception = None

            for attempt in range(_max_retries):
                try:
                    return func(*args, **kwargs)

                except HttpError as error:
                    last_exception = error
                    status_code = error.resp.status

                    # Only retry on rate limit (429) or server errors (5xx)
                    if status_code == 429 or 500 <= status_code < 600:
                        if attempt < _max_retries - 1:
                            # Calculate delay with optional jitter
                            actual_delay = delay
                            if jitter:
                                actual_delay = delay * (0.5 + random.random())

                            actual_delay = min(actual_delay, _max_delay)

                            logger.warning(
                                f"HTTP {status_code} error in {func.__name__}, "
                                f"retrying in {actual_delay:.2f}s "
                                f"(attempt {attempt + 1}/{_max_retries})"
                            )

                            time.sleep(actual_delay)
                            delay *= _multiplier
                        else:
                            logger.error(
                                f"Max retries ({_max_retries}) exceeded for {func.__name__}"
                            )
                            raise
                    else:
                        # Don't retry on client errors (4xx except 429)
                        logger.error(
                            f"HTTP {status_code} error in {func.__name__}, not retrying"
                        )
                        raise

                except Exception as error:
                    # Don't retry on non-HTTP errors
                    logger.error(f"Non-retryable error in {func.__name__}: {error}")
                    raise

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise Exception(f"Unexpected error in retry logic for {func.__name__}")

        return wrapper

    return decorator


def rate_limit(calls_per_second: Optional[float] = None) -> Callable:
    """
    Decorator to rate limit function calls.

    Args:
        calls_per_second: Maximum calls per second (default: based on Gmail quota)

    Returns:
        Decorated function with rate limiting

    Example:
        @rate_limit(calls_per_second=10)
        def api_call():
            return api.fetch()
    """
    delay = 1.0 / (calls_per_second or gmail_config.quota_units_per_second)
    last_call_time = [0.0]  # Use list to allow modification in nested function

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Calculate time since last call
            elapsed = time.time() - last_call_time[0]

            # Sleep if we need to throttle
            if elapsed < delay:
                time.sleep(delay - elapsed)

            # Update last call time
            last_call_time[0] = time.time()

            return func(*args, **kwargs)

        return wrapper

    return decorator


def sanitize_email_content(content: str, max_length: int = 500) -> str:
    """
    Sanitize email content for logging.

    Args:
        content: Email content to sanitize
        max_length: Maximum length of sanitized content

    Returns:
        Sanitized content string
    """
    if not content:
        return ""

    # Truncate to max length
    sanitized = content[:max_length]

    # Add ellipsis if truncated
    if len(content) > max_length:
        sanitized += "..."

    return sanitized


def format_confidence(confidence: float) -> str:
    """
    Format confidence score as percentage string.

    Args:
        confidence: Confidence score (0.0-1.0)

    Returns:
        Formatted percentage string (e.g., "87.5%")
    """
    return f"{confidence * 100:.1f}%"


def get_confidence_category(confidence: float) -> str:
    """
    Categorize confidence score.

    Args:
        confidence: Confidence score (0.0-1.0)

    Returns:
        Category: "high", "medium", "low", or "no_match"
    """
    if confidence >= 0.7:
        return "high"
    elif confidence >= 0.5:
        return "medium"
    elif confidence >= 0.3:
        return "low"
    else:
        return "no_match"


def batch_items(items: list[T], batch_size: int) -> list[list[T]]:
    """
    Split a list into batches of specified size.

    Args:
        items: List of items to batch
        batch_size: Size of each batch

    Returns:
        List of batches

    Example:
        >>> batch_items([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]
    """
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


def validate_email_address(email: str) -> bool:
    """
    Basic email address validation.

    Args:
        email: Email address to validate

    Returns:
        True if email appears valid, False otherwise
    """
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to maximum length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert value to integer.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Integer value or default
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Float value or default
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class Timer:
    """Simple context manager for timing operations."""

    def __init__(self, name: str = "Operation"):
        """
        Initialize timer.

        Args:
            name: Name of the operation being timed
        """
        self.name = name
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.elapsed: Optional[float] = None

    def __enter__(self) -> "Timer":
        """Start the timer."""
        self.start_time = time.time()
        return self

    def __exit__(self, *args: Any) -> None:
        """Stop the timer and log the duration."""
        self.end_time = time.time()
        if self.start_time is not None:
            self.elapsed = self.end_time - self.start_time
            logger.debug(f"{self.name} took {self.elapsed:.2f} seconds")

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self.elapsed is not None:
            return self.elapsed * 1000
        return 0.0


def ensure_secure_file(file_path: Path, mode: int = 0o600) -> None:
    """
    Ensure file has secure permissions, fix if needed.

    This function checks if a file has overly permissive permissions
    (readable/writable by group or others) and fixes them to be
    owner-only access.

    Args:
        file_path: Path to the file to secure
        mode: Target permission mode (default: 0o600 - owner read/write only)

    Example:
        >>> ensure_secure_file(Path("credentials.json"))
        # Ensures credentials.json has 600 permissions
    """
    if not file_path.exists():
        # Create with secure permissions
        file_path.touch(mode=mode)
        logger.debug(f"Created {file_path} with secure permissions {oct(mode)}")
        return

    current_mode = stat.S_IMODE(os.stat(file_path).st_mode)

    # Check if permissions are too permissive (group or others have any access)
    if current_mode & (stat.S_IRWXG | stat.S_IRWXO):
        logger.warning(
            f"Insecure permissions detected on {file_path}: {oct(current_mode)}. "
            f"Fixing to {oct(mode)}."
        )

        # Auto-fix if enabled
        if privacy_config.auto_fix_permissions:
            os.chmod(file_path, mode)
            logger.info(f"Fixed permissions on {file_path} to {oct(mode)}")
        else:
            logger.warning(
                f"AUTO_FIX_PERMISSIONS is disabled. "
                f"Please manually run: chmod {oct(mode)[-3:]} {file_path}"
            )


def ensure_secure_directory(dir_path: Path, mode: int = 0o700) -> None:
    """
    Ensure directory has secure permissions.

    Creates the directory if it doesn't exist and ensures it has
    owner-only permissions.

    Args:
        dir_path: Path to the directory to secure
        mode: Target permission mode (default: 0o700 - owner access only)

    Example:
        >>> ensure_secure_directory(Path.home() / ".gmail_classifier")
        # Ensures ~/.gmail_classifier has 700 permissions
    """
    # Create directory with secure permissions
    dir_path.mkdir(parents=True, exist_ok=True, mode=mode)

    # Verify and fix if needed (mkdir might be affected by umask)
    current_mode = stat.S_IMODE(os.stat(dir_path).st_mode)

    # Check if permissions are too permissive
    if current_mode & (stat.S_IRWXG | stat.S_IRWXO):
        logger.warning(
            f"Insecure permissions detected on directory {dir_path}: {oct(current_mode)}. "
            f"Fixing to {oct(mode)}."
        )

        # Auto-fix if enabled
        if privacy_config.auto_fix_permissions:
            os.chmod(dir_path, mode)
            logger.info(f"Fixed directory permissions on {dir_path} to {oct(mode)}")
        else:
            logger.warning(
                f"AUTO_FIX_PERMISSIONS is disabled. "
                f"Please manually run: chmod {oct(mode)[-3:]} {dir_path}"
            )
