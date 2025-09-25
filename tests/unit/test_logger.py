"""Unit tests for logger utility."""

import pytest
import logging
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO
import sys

from src.utils.logger import (
    setup_logger,
    get_logger,
    LogLevel,
    log_function_call,
    log_database_query,
    log_error_with_context
)


class TestLoggerSetup:
    """Tests for logger setup and configuration."""

    def test_setup_logger_creates_logger(self):
        """Test that setup_logger creates a logger with correct level."""
        logger = setup_logger(name="test_logger", level="DEBUG")
        assert logger.name == "test_logger"
        assert logger.level == logging.DEBUG

    def test_setup_logger_with_different_levels(self):
        """Test logger creation with different log levels."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in levels:
            logger = setup_logger(name=f"test_{level}", level=level)
            assert logger.level == getattr(logging, level)

    def test_get_logger_returns_same_instance(self):
        """Test that get_logger returns the same logger instance."""
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")
        assert logger1 is logger2

    def test_logger_console_output(self):
        """Test that logger outputs to console correctly."""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            logger = setup_logger(
                name="test_console",
                level="INFO",
                console_output=True,
                file_output=False
            )
            logger.info("Test message")
            output = mock_stdout.getvalue()
            assert "Test message" in output
            assert "INFO" in output

    def test_logger_file_output(self, tmp_path):
        """Test that logger writes to file correctly."""
        with patch('src.utils.logger.LOG_DIR', tmp_path):
            logger = setup_logger(
                name="test_file",
                level="DEBUG",
                console_output=False,
                file_output=True
            )
            logger.debug("Debug message")
            logger.info("Info message")

            # Check that log file was created
            log_files = list(tmp_path.glob("*.log"))
            assert len(log_files) == 1

            # Check file contents
            with open(log_files[0], 'r') as f:
                content = f.read()
                assert "Debug message" in content
                assert "Info message" in content


class TestLogLevel:
    """Tests for LogLevel context manager."""

    def test_log_level_context_manager(self):
        """Test that LogLevel temporarily changes log level."""
        logger = setup_logger(name="test_context", level="INFO")

        # Initially should be INFO
        assert logger.level == logging.INFO

        # Change to DEBUG temporarily
        with LogLevel(logger, "DEBUG") as ctx_logger:
            assert ctx_logger.level == logging.DEBUG
            assert logger.level == logging.DEBUG

        # Should revert to INFO
        assert logger.level == logging.INFO

    def test_log_level_context_with_exception(self):
        """Test that LogLevel reverts level even on exception."""
        logger = setup_logger(name="test_exception", level="WARNING")

        try:
            with LogLevel(logger, "ERROR"):
                assert logger.level == logging.ERROR
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should still revert to WARNING
        assert logger.level == logging.WARNING


class TestLogFunctions:
    """Tests for logging utility functions."""

    def test_log_function_call_decorator(self):
        """Test that log_function_call decorator logs function calls."""
        mock_logger = MagicMock()

        with patch('src.utils.logger.get_logger', return_value=mock_logger):
            @log_function_call
            def test_func(a, b, c=3):
                return a + b + c

            result = test_func(1, 2, c=4)

            assert result == 7
            assert mock_logger.debug.call_count == 2

            # Check that function call was logged
            call_args = mock_logger.debug.call_args_list[0][0][0]
            assert "test_func" in call_args
            assert "args=(1, 2)" in call_args
            assert "kwargs={'c': 4}" in call_args

    def test_log_function_call_with_exception(self):
        """Test that log_function_call logs exceptions."""
        mock_logger = MagicMock()

        with patch('src.utils.logger.get_logger', return_value=mock_logger):
            @log_function_call
            def failing_func():
                raise ValueError("Test error")

            with pytest.raises(ValueError):
                failing_func()

            # Check that error was logged
            mock_logger.error.assert_called_once()
            error_msg = mock_logger.error.call_args[0][0]
            assert "ValueError" in error_msg
            assert "Test error" in error_msg

    def test_log_database_query(self):
        """Test database query logging."""
        mock_logger = MagicMock()

        query = "SELECT * FROM users WHERE id = %s"
        params = (123,)

        log_database_query(query, params, mock_logger)

        mock_logger.debug.assert_called_once()
        call_msg = mock_logger.debug.call_args[0][0]
        assert "SELECT * FROM users" in call_msg
        assert "Params: (123,)" in call_msg

    def test_log_database_query_truncates_long_queries(self):
        """Test that very long queries are truncated."""
        mock_logger = MagicMock()

        long_query = "SELECT " + "column, " * 100 + "FROM table"
        log_database_query(long_query, None, mock_logger)

        call_msg = mock_logger.debug.call_args[0][0]
        assert len(call_msg) < len(long_query)
        assert "..." in call_msg

    def test_log_error_with_context(self):
        """Test error logging with context."""
        mock_logger = MagicMock()

        try:
            raise ValueError("Test error")
        except ValueError as e:
            context = {"user_id": 123, "action": "test_action"}
            log_error_with_context(e, context, mock_logger)

        mock_logger.error.assert_called_once()
        call_msg = mock_logger.error.call_args[0][0]
        assert "ValueError" in call_msg
        assert "Test error" in call_msg
        assert "user_id" in call_msg
        assert "123" in call_msg


class TestColoredFormatter:
    """Tests for ColoredFormatter."""

    def test_colored_formatter_adds_colors(self):
        """Test that ColoredFormatter adds ANSI color codes."""
        from src.utils.logger import ColoredFormatter

        formatter = ColoredFormatter('%(levelname)s | %(message)s')

        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )

        formatted = formatter.format(record)

        # Check for color codes
        assert '\033[' in formatted  # ANSI escape code
        assert '\033[0m' in formatted  # Reset code

    def test_colored_formatter_different_levels(self):
        """Test that different log levels get different colors."""
        from src.utils.logger import ColoredFormatter

        formatter = ColoredFormatter('%(levelname)s')

        levels = [
            (logging.DEBUG, '\033[36m'),    # Cyan
            (logging.INFO, '\033[32m'),     # Green
            (logging.WARNING, '\033[33m'),  # Yellow
            (logging.ERROR, '\033[31m'),    # Red
            (logging.CRITICAL, '\033[35m'), # Magenta
        ]

        for level, expected_color in levels:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="",
                lineno=0,
                msg="",
                args=(),
                exc_info=None
            )

            formatted = formatter.format(record)
            assert expected_color in formatted