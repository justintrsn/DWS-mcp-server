"""Logger utility for PostgreSQL MCP Server.

Provides centralized logging configuration for debugging and monitoring.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Create logs directory if it doesn't exist
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""

    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(
    name: str = "mcp_server",
    level: str = "DEBUG",
    console_output: bool = True,
    file_output: bool = True
) -> logging.Logger:
    """Set up a logger with console and file handlers.

    Args:
        name: Logger name (module name recommended)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_output: Enable console output
        file_output: Enable file output

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper()))

    # Console Handler with colors
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # File Handler - rotates daily
    if file_output:
        today = datetime.now().strftime('%Y-%m-%d')
        file_handler = logging.FileHandler(
            LOG_DIR / f"mcp-server-{today}.log",
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


# Create default logger instance
logger = setup_logger()

# Convenience functions for module-specific loggers
def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Args:
        name: Module name (use __name__ in modules)

    Returns:
        Logger instance for the module
    """
    return setup_logger(name)


# Context manager for temporary log level changes
class LogLevel:
    """Context manager to temporarily change log level."""

    def __init__(self, logger: logging.Logger, level: str):
        self.logger = logger
        self.new_level = getattr(logging, level.upper())
        self.old_level = logger.level

    def __enter__(self):
        self.logger.setLevel(self.new_level)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.old_level)


# Convenience functions for common logging patterns
def log_function_call(func):
    """Decorator to log function calls with arguments."""
    def wrapper(*args, **kwargs):
        func_logger = get_logger(func.__module__)
        func_logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            func_logger.debug(f"{func.__name__} returned: {result}")
            return result
        except Exception as e:
            func_logger.error(f"{func.__name__} raised {e.__class__.__name__}: {e}")
            raise
    return wrapper


def log_database_query(query: str, params: Optional[tuple] = None, logger_instance: Optional[logging.Logger] = None):
    """Log database queries for debugging.

    Args:
        query: SQL query string
        params: Query parameters
        logger_instance: Logger to use (defaults to main logger)
    """
    if logger_instance is None:
        logger_instance = logger

    # Truncate very long queries
    display_query = query[:500] + "..." if len(query) > 500 else query
    display_query = ' '.join(display_query.split())  # Normalize whitespace

    if params:
        logger_instance.debug(f"SQL Query: {display_query} | Params: {params}")
    else:
        logger_instance.debug(f"SQL Query: {display_query}")


def log_error_with_context(error: Exception, context: dict, logger_instance: Optional[logging.Logger] = None):
    """Log an error with additional context information.

    Args:
        error: Exception that occurred
        context: Dictionary with context information
        logger_instance: Logger to use (defaults to main logger)
    """
    if logger_instance is None:
        logger_instance = logger

    logger_instance.error(
        f"{error.__class__.__name__}: {error} | Context: {context}",
        exc_info=True
    )


# Export convenience
__all__ = [
    'logger',
    'get_logger',
    'setup_logger',
    'LogLevel',
    'log_function_call',
    'log_database_query',
    'log_error_with_context'
]