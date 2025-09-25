"""SQL Query Validation for PostgreSQL MCP Server.

This module provides validation to ensure only safe, read-only queries
are executed by the MCP tools.
"""

import re
from typing import Tuple
from src.models.error_types import InvalidQueryError


def validate_select_only(query: str) -> bool:
    """Validate that a query is SELECT-only (no DML/DDL operations).

    Args:
        query: SQL query string to validate

    Returns:
        True if query is safe to execute

    Raises:
        InvalidQueryError: If query contains unsafe operations
    """
    if not query or not query.strip():
        raise InvalidQueryError(query, "Empty query")

    # Normalize query: strip whitespace and convert to uppercase
    normalized = query.strip().upper()

    # Remove comments (both -- and /* */ style)
    normalized = _remove_comments(normalized)

    # Split into statements (semicolon-separated)
    statements = [stmt.strip() for stmt in normalized.split(';') if stmt.strip()]

    if not statements:
        raise InvalidQueryError(query, "No valid statements found")

    # Validate each statement
    for stmt in statements:
        _validate_single_statement(stmt, query)

    return True


def _remove_comments(query: str) -> str:
    """Remove SQL comments from query."""
    # Remove -- comments (to end of line)
    query = re.sub(r'--.*$', '', query, flags=re.MULTILINE)

    # Remove /* */ comments
    query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)

    return query


def _validate_single_statement(stmt: str, original_query: str) -> None:
    """Validate a single SQL statement.

    Args:
        stmt: Single normalized SQL statement
        original_query: Original query for error reporting

    Raises:
        InvalidQueryError: If statement is not safe
    """
    # List of dangerous keywords that indicate write operations
    dangerous_keywords = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'GRANT', 'REVOKE', 'COMMIT', 'ROLLBACK',
        'SET', 'RESET', 'COPY', 'IMPORT', 'CALL', 'EXECUTE'
    ]

    # List of allowed statement prefixes
    allowed_prefixes = ['SELECT', 'WITH', 'EXPLAIN', 'ANALYZE']

    # Check if statement starts with an allowed keyword
    starts_with_allowed = any(stmt.startswith(prefix) for prefix in allowed_prefixes)

    if not starts_with_allowed:
        raise InvalidQueryError(
            original_query,
            f"Statement must start with one of: {', '.join(allowed_prefixes)}"
        )

    # Check for dangerous keywords anywhere in the statement
    # Use word boundaries to avoid false positives (e.g. "SELECT description" shouldn't match "UPDATE")
    for keyword in dangerous_keywords:
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, stmt):
            raise InvalidQueryError(
                original_query,
                f"Query contains forbidden operation: {keyword}"
            )

    # Additional safety checks
    _check_for_functions(stmt, original_query)


def _check_for_functions(stmt: str, original_query: str) -> None:
    """Check for potentially dangerous function calls.

    Args:
        stmt: SQL statement to check
        original_query: Original query for error reporting

    Raises:
        InvalidQueryError: If dangerous functions are found
    """
    # List of dangerous functions that could modify data or system state
    dangerous_functions = [
        'DBLINK_EXEC', 'DBLINK_CONNECT', 'DBLINK_DISCONNECT',
        'PG_RELOAD_CONF', 'PG_ROTATE_LOGFILE', 'PG_CANCEL_BACKEND',
        'PG_TERMINATE_BACKEND', 'PG_FILE_WRITE', 'PG_FILE_UNLINK',
        'PG_FILE_RENAME', 'COPY_FILE', 'PG_READ_FILE',
        'LO_IMPORT', 'LO_EXPORT', 'LO_UNLINK'
    ]

    for func in dangerous_functions:
        pattern = r'\b' + func + r'\s*\('
        if re.search(pattern, stmt):
            raise InvalidQueryError(
                original_query,
                f"Query contains forbidden function: {func}"
            )


def add_limit_if_missing(query: str, default_limit: int = 100) -> str:
    """Add LIMIT clause to SELECT query if not present.

    Args:
        query: SQL query string
        default_limit: Default limit to apply

    Returns:
        Query with LIMIT clause added if necessary
    """
    # First validate the query is safe
    validate_select_only(query)

    normalized = query.strip().upper()

    # Check if LIMIT already exists
    if re.search(r'\bLIMIT\s+\d+', normalized):
        return query

    # Check if it's an EXPLAIN query (don't add LIMIT to EXPLAIN)
    if normalized.startswith('EXPLAIN'):
        return query

    # Add LIMIT to the end of the query
    return f"{query.rstrip(';')} LIMIT {default_limit}"


def extract_table_references(query: str) -> list:
    """Extract table names referenced in the query.

    Args:
        query: SQL query string

    Returns:
        List of table names found in the query
    """
    validate_select_only(query)

    # Simple extraction of table names after FROM and JOIN keywords
    # This is a basic implementation - could be enhanced with proper SQL parsing
    normalized = query.upper()

    tables = []

    # Find table names after FROM
    from_matches = re.findall(r'\bFROM\s+([^\s,\(]+)', normalized)
    tables.extend(from_matches)

    # Find table names after JOIN
    join_matches = re.findall(r'\bJOIN\s+([^\s,\(]+)', normalized)
    tables.extend(join_matches)

    # Remove schema qualifiers and clean up
    cleaned_tables = []
    for table in tables:
        # Remove schema prefix (schema.table -> table)
        if '.' in table:
            table = table.split('.')[-1]
        # Remove quotes if present
        table = table.strip('"\'`')
        if table and table.upper() not in ['SELECT', 'WHERE', 'GROUP', 'ORDER', 'HAVING']:
            cleaned_tables.append(table.lower())

    return list(set(cleaned_tables))  # Remove duplicates