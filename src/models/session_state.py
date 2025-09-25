"""Session state management for MCP tool prerequisite tracking.

This module provides thread-safe session state management to track which
tables have been inspected and ensure proper sequencing of MCP tool calls.
"""

import threading
from typing import Set, Optional
from lib.logging_config import get_logger

logger = get_logger(__name__)


class SessionState:
    """Thread-safe session state for tracking MCP tool prerequisites.

    Tracks which tables have been inspected to enforce proper tool sequencing:
    discover_tables -> inspect_table_schema -> safe_read_query
    """

    def __init__(self, session_id: Optional[str] = None):
        """Initialize session state.

        Args:
            session_id: Optional session identifier for logging
        """
        self.session_id = session_id or "default"
        self.inspected_tables: Set[str] = set()
        self.tables_discovered = False
        self._lock = threading.RLock()  # Re-entrant lock for thread safety

        logger.info(f"Created session state for session: {self.session_id}")

    def mark_tables_discovered(self) -> None:
        """Mark that tables have been discovered via discover_tables."""
        with self._lock:
            self.tables_discovered = True
            logger.debug(f"Session {self.session_id}: Tables discovered")

    def add_inspected_table(self, table_name: str) -> None:
        """Add a table to the inspected tables set.

        Args:
            table_name: Name of the table that was inspected
        """
        with self._lock:
            self.inspected_tables.add(table_name.lower())  # Normalize to lowercase
            logger.debug(f"Session {self.session_id}: Added inspected table '{table_name}'. "
                        f"Total inspected: {len(self.inspected_tables)}")

    def is_table_inspected(self, table_name: str) -> bool:
        """Check if a table has been inspected.

        Args:
            table_name: Name of the table to check

        Returns:
            True if the table has been inspected
        """
        with self._lock:
            return table_name.lower() in self.inspected_tables

    def get_uninspected_tables(self, table_names: Set[str]) -> Set[str]:
        """Get list of tables that haven't been inspected.

        Args:
            table_names: Set of table names to check

        Returns:
            Set of table names that haven't been inspected
        """
        with self._lock:
            uninspected = {t for t in table_names
                          if t.lower() not in self.inspected_tables}

            if uninspected:
                logger.warning(f"Session {self.session_id}: Found {len(uninspected)} uninspected tables: "
                              f"{', '.join(uninspected)}")

            return uninspected

    def validate_query_prerequisites(self, table_names: Set[str]) -> Optional[dict]:
        """Validate that all required tables have been inspected.

        Args:
            table_names: Set of table names that will be queried

        Returns:
            None if validation passes, or dict with error details if validation fails
        """
        with self._lock:
            uninspected = self.get_uninspected_tables(table_names)

            if uninspected:
                uninspected_list = sorted(uninspected)
                error_response = {
                    "error": "Cannot execute query - table structure unknown",
                    "uninspected_tables": uninspected_list,
                    "action_required": f"First call inspect_table_schema for: {', '.join(uninspected_list)}",
                    "why": "Query execution requires understanding table structure to prevent errors",
                    "next_step": f"inspect_table_schema('{uninspected_list[0]}')"
                }

                logger.warning(f"Session {self.session_id}: Query validation failed. "
                              f"Missing inspections for: {', '.join(uninspected_list)}")

                return error_response

            logger.info(f"Session {self.session_id}: Query validation passed for {len(table_names)} tables")
            return None

    def reset(self) -> None:
        """Reset session state for a new session."""
        with self._lock:
            old_count = len(self.inspected_tables)
            self.inspected_tables.clear()
            self.tables_discovered = False

            logger.info(f"Session {self.session_id}: Reset state. "
                       f"Cleared {old_count} inspected tables")

    def get_status(self) -> dict:
        """Get current session status for debugging.

        Returns:
            Dict with session status information
        """
        with self._lock:
            return {
                "session_id": self.session_id,
                "tables_discovered": self.tables_discovered,
                "inspected_tables_count": len(self.inspected_tables),
                "inspected_tables": sorted(self.inspected_tables)
            }


# Global session state instance (thread-safe)
_session_state = SessionState()


def get_session_state() -> SessionState:
    """Get the global session state instance.

    Returns:
        The global SessionState instance
    """
    return _session_state


def reset_session_state() -> None:
    """Reset the global session state."""
    global _session_state
    _session_state.reset()
    logger.info("Global session state reset")