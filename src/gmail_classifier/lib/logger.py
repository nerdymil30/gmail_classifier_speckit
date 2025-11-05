"""Structured logging with PII sanitization for Gmail Classifier."""

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

from gmail_classifier.lib.config import Config


class PIISanitizer:
    """Sanitize personally identifiable information from log messages."""

    # Regex patterns for PII detection
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    API_KEY_PATTERN = re.compile(r"(sk-ant-[a-zA-Z0-9-]+)")
    TOKEN_PATTERN = re.compile(r"(ya29\.[a-zA-Z0-9_-]+)")

    @classmethod
    def sanitize_email(cls, text: str) -> str:
        """Replace email addresses with sanitized version."""
        return cls.EMAIL_PATTERN.sub(lambda m: f"***@{m.group(0).split('@')[1]}", text)

    @classmethod
    def sanitize_api_key(cls, text: str) -> str:
        """Replace API keys with masked version."""
        return cls.API_KEY_PATTERN.sub("sk-ant-***", text)

    @classmethod
    def sanitize_token(cls, text: str) -> str:
        """Replace OAuth tokens with masked version."""
        return cls.TOKEN_PATTERN.sub("ya29.***", text)

    @classmethod
    def sanitize(cls, text: str) -> str:
        """Apply all sanitization rules to text."""
        if not isinstance(text, str):
            text = str(text)

        text = cls.sanitize_email(text)
        text = cls.sanitize_api_key(text)
        text = cls.sanitize_token(text)

        return text


class SanitizingFormatter(logging.Formatter):
    """Custom formatter that sanitizes PII from log records."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with PII sanitization."""
        # Sanitize the message
        if isinstance(record.msg, str):
            record.msg = PIISanitizer.sanitize(record.msg)

        # Sanitize args if present
        if record.args:
            sanitized_args = tuple(
                PIISanitizer.sanitize(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
            record.args = sanitized_args

        return super().format(record)


def setup_logger(
    name: str,
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """
    Set up a logger with PII sanitization.

    Args:
        name: Logger name (usually __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for file logging

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Set log level
    log_level = level or Config.LOG_LEVEL
    logger.setLevel(getattr(logging, log_level.upper()))

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Create formatter with PII sanitization
    formatter = SanitizingFormatter(
        fmt=Config.LOG_FORMAT,
        datefmt=Config.LOG_DATE_FORMAT,
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if log_file specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    Get or create a logger for the given module.

    Args:
        name: Logger name (usually __name__)
        log_file: Optional log file name (will be placed in LOG_DIR)

    Returns:
        Configured logger instance
    """
    log_path = None
    if log_file:
        log_path = Config.LOG_DIR / log_file

    return setup_logger(name, log_file=log_path)


class StructuredLogger:
    """
    Structured logger for classification operations.

    Provides context-aware logging with automatic PII sanitization.
    """

    def __init__(self, name: str, log_file: Optional[str] = None):
        """
        Initialize structured logger.

        Args:
            name: Logger name
            log_file: Optional log file name
        """
        self.logger = get_logger(name, log_file)
        self.context: Dict[str, Any] = {}

    def set_context(self, **kwargs: Any) -> None:
        """Set context fields for all subsequent log messages."""
        self.context.update(kwargs)

    def clear_context(self) -> None:
        """Clear all context fields."""
        self.context.clear()

    def _format_message(self, message: str, **kwargs: Any) -> str:
        """Format message with context and additional fields."""
        fields = {**self.context, **kwargs}
        if fields:
            field_str = " | ".join(f"{k}={v}" for k, v in fields.items())
            return f"{message} | {field_str}"
        return message

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with context."""
        self.logger.debug(self._format_message(message, **kwargs))

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with context."""
        self.logger.info(self._format_message(message, **kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with context."""
        self.logger.warning(self._format_message(message, **kwargs))

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message with context."""
        self.logger.error(self._format_message(message, **kwargs))

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message with context."""
        self.logger.critical(self._format_message(message, **kwargs))

    def log_classification(
        self,
        email_id: str,
        suggested_label: str,
        confidence: float,
        reasoning: Optional[str] = None,
    ) -> None:
        """Log email classification result."""
        self.info(
            "Email classified",
            email_id=email_id,
            suggested_label=suggested_label,
            confidence=f"{confidence:.2f}",
            reasoning=reasoning[:100] if reasoning else None,
        )

    def log_api_call(
        self,
        api: str,
        endpoint: str,
        status: str,
        duration_ms: Optional[float] = None,
    ) -> None:
        """Log API call with timing information."""
        self.info(
            f"{api} API call",
            endpoint=endpoint,
            status=status,
            duration_ms=f"{duration_ms:.2f}" if duration_ms else None,
        )

    def log_session_progress(
        self,
        session_id: str,
        processed: int,
        total: int,
        success_rate: Optional[float] = None,
    ) -> None:
        """Log processing session progress."""
        self.info(
            "Session progress",
            session_id=session_id,
            processed=processed,
            total=total,
            progress=f"{(processed/total*100):.1f}%" if total > 0 else "0%",
            success_rate=f"{success_rate:.2f}" if success_rate else None,
        )


# Module-level convenience function
def get_structured_logger(name: str, log_file: Optional[str] = None) -> StructuredLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)
        log_file: Optional log file name

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name, log_file)
