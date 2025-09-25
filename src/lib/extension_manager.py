"""PostgreSQL Extension Manager

Handles detection and management of PostgreSQL extensions.
Provides graceful fallback when extensions are not available.
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ExtensionNotAvailable(Exception):
    """Exception raised when a required extension is not available."""

    def __init__(self, extension_name: str, message: str = None):
        self.extension_name = extension_name
        self.message = message or f"Extension '{extension_name}' is not installed"
        super().__init__(self.message)


def check_extension(db_service, extension_name: str) -> Dict[str, Any]:
    """
    Check if a PostgreSQL extension is installed and available.

    Args:
        db_service: Database service instance
        extension_name: Name of the extension to check

    Returns:
        Dictionary with extension status information
    """
    try:
        query = """
            SELECT
                extname,
                extversion,
                extnamespace::regnamespace AS schema
            FROM pg_extension
            WHERE extname = %s
        """
        result = db_service.execute_query(query, [extension_name])

        if result and len(result) > 0:
            ext = result[0]
            return {
                'installed': True,
                'name': ext[0],
                'version': ext[1],
                'schema': ext[2]
            }
        else:
            return {
                'installed': False,
                'name': extension_name,
                'version': None,
                'schema': None
            }
    except Exception as e:
        logger.error(f"Error checking extension {extension_name}: {e}")
        return {
            'installed': False,
            'name': extension_name,
            'version': None,
            'schema': None,
            'error': str(e)
        }


def get_extension_status(db_service) -> Dict[str, Dict[str, Any]]:
    """
    Get status of all relevant PostgreSQL extensions.

    Args:
        db_service: Database service instance

    Returns:
        Dictionary mapping extension names to their status
    """
    extensions_to_check = [
        'pg_stat_statements',
        'hypopg',
        'pg_trgm',
        'pgcrypto',
        'uuid-ossp'
    ]

    status = {}
    for ext_name in extensions_to_check:
        status[ext_name] = check_extension(db_service, ext_name)

    return status


def format_extension_not_available_message(extension_name: str) -> str:
    """
    Format a helpful message when an extension is not available.

    Args:
        extension_name: Name of the missing extension

    Returns:
        Formatted message with installation instructions
    """
    messages = {
        'pg_stat_statements': (
            "The pg_stat_statements extension is required for query statistics.\n"
            "To install:\n"
            "1. Add 'pg_stat_statements' to shared_preload_libraries in postgresql.conf\n"
            "2. Restart PostgreSQL\n"
            "3. Run: CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
        ),
        'hypopg': (
            "The hypopg extension is required for index recommendations.\n"
            "To install:\n"
            "1. Install the hypopg package for your PostgreSQL version\n"
            "2. Run: CREATE EXTENSION IF NOT EXISTS hypopg;"
        ),
        'pg_trgm': (
            "The pg_trgm extension is required for fuzzy text search.\n"
            "To install:\n"
            "Run: CREATE EXTENSION IF NOT EXISTS pg_trgm;"
        )
    }

    return messages.get(extension_name,
        f"The {extension_name} extension is not installed.\n"
        f"To install: CREATE EXTENSION IF NOT EXISTS {extension_name};"
    )


def require_extension(extension_name: str):
    """
    Decorator to require a specific PostgreSQL extension.

    Args:
        extension_name: Name of the required extension

    Usage:
        @require_extension('pg_stat_statements')
        def get_top_queries(db_service, ...):
            ...
    """
    def decorator(func):
        def wrapper(db_service, *args, **kwargs):
            ext_status = check_extension(db_service, extension_name)
            if not ext_status['installed']:
                raise ExtensionNotAvailable(
                    extension_name,
                    format_extension_not_available_message(extension_name)
                )
            return func(db_service, *args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


def check_extensions_enabled(db_service) -> bool:
    """
    Check if extensions are enabled in configuration.

    Args:
        db_service: Database service instance

    Returns:
        Boolean indicating if extensions are enabled
    """
    import os
    return os.getenv('ENABLE_EXTENSIONS', 'false').lower() == 'true'